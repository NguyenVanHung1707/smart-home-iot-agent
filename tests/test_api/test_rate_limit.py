import asyncio

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.config import Settings
from src.middleware.rate_limit import (
    DEFAULT_MAX_REQUESTS_PER_MINUTE,
    HEAVY_AI_ENDPOINTS,
    RateLimitMiddleware,
    clear_rate_limits,
)
from src.services.users import UserStore


@pytest.mark.asyncio
async def test_health_bypasses_rate_limit(unauthenticated_client):
    """Health endpoint should never be rate limited."""
    clear_rate_limits()
    for _ in range(610):
        response = await unauthenticated_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


@pytest.mark.skip(reason="Per-IP rate limit temporarily disabled")
@pytest.mark.asyncio
async def test_global_ip_rate_limit_returns_429(unauthenticated_client):
    """Exceeding 600 req/min from the same IP returns 429 rate_limit_exceeded with Retry-After header."""
    clear_rate_limits()
    headers = {"X-Forwarded-For": "203.0.113.10"}

    # 600 allowed requests
    for i in range(600):
        response = await unauthenticated_client.get("/api/v1/auth/me", headers=headers)
        # 401 is expected because no auth token is passed, but NOT 429
        assert response.status_code == 401

    # 601st request should be rate limited
    limited_response = await unauthenticated_client.get("/api/v1/auth/me", headers=headers)
    assert limited_response.status_code == 429
    assert limited_response.json() == {"detail": "rate_limit_exceeded"}
    assert limited_response.headers.get("Retry-After") == "5"

    # Different IP should still be allowed
    other_ip_response = await unauthenticated_client.get(
        "/api/v1/auth/me",
        headers={"X-Forwarded-For": "203.0.113.11"},
    )
    assert other_ip_response.status_code == 401


@pytest.mark.asyncio
async def test_ai_queue_sequential_execution():
    """When 1 request is executing, subsequent requests wait and execute sequentially."""
    test_app = FastAPI()
    test_app.add_middleware(
        RateLimitMiddleware,
        max_ai_concurrent=1,
        max_ai_queue=5,
        queue_timeout_seconds=5.0,
        max_requests_per_minute=100,
    )

    execution_order: list[str] = []
    active_concurrent = 0
    max_observed_concurrent = 0

    @test_app.post("/api/v1/chat")
    async def fake_chat(data: dict):
        nonlocal active_concurrent, max_observed_concurrent
        active_concurrent += 1
        max_observed_concurrent = max(max_observed_concurrent, active_concurrent)
        req_id = data.get("id")
        execution_order.append(f"start_{req_id}")
        await asyncio.sleep(0.05)
        execution_order.append(f"end_{req_id}")
        active_concurrent -= 1
        return {"id": req_id}

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        tasks = [
            asyncio.create_task(ac.post("/api/v1/chat", json={"id": 1})),
            asyncio.create_task(ac.post("/api/v1/chat", json={"id": 2})),
            asyncio.create_task(ac.post("/api/v1/chat", json={"id": 3})),
        ]
        responses = await asyncio.gather(*tasks)

        for res in responses:
            assert res.status_code == 200

        assert max_observed_concurrent == 1
        assert execution_order == [
            "start_1",
            "end_1",
            "start_2",
            "end_2",
            "start_3",
            "end_3",
        ]


@pytest.mark.asyncio
async def test_ai_queue_capacity_returns_429_queue_full():
    """When waiting queue capacity is reached, incoming requests receive 429 queue_full."""
    test_app = FastAPI()
    test_app.add_middleware(
        RateLimitMiddleware,
        max_ai_concurrent=1,
        max_ai_queue=2,
        queue_timeout_seconds=5.0,
        max_requests_per_minute=100,
    )

    blocker = asyncio.Event()

    @test_app.post("/api/v1/chat")
    async def fake_chat():
        await blocker.wait()
        return {"status": "ok"}

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Request 1: active and blocked
        t1 = asyncio.create_task(ac.post("/api/v1/chat"))
        await asyncio.sleep(0.02)

        # Requests 2 and 3: wait in queue (capacity is 2)
        t2 = asyncio.create_task(ac.post("/api/v1/chat"))
        t3 = asyncio.create_task(ac.post("/api/v1/chat"))
        await asyncio.sleep(0.02)

        # Request 4: queue is full -> 429 queue_full with Retry-After: 5
        overflow_res = await ac.post("/api/v1/chat")
        assert overflow_res.status_code == 429
        assert overflow_res.json() == {"detail": "queue_full"}
        assert overflow_res.headers.get("Retry-After") == "5"

        # Release active request and drain queue
        blocker.set()
        res1, res2, res3 = await asyncio.gather(t1, t2, t3)
        assert res1.status_code == 200
        assert res2.status_code == 200
        assert res3.status_code == 200

        # After queue clears, new requests succeed
        after_res = await ac.post("/api/v1/chat")
        assert after_res.status_code == 200


@pytest.mark.asyncio
async def test_ai_queue_timeout_returns_429_queue_timeout():
    """Requests waiting longer than queue_timeout_seconds receive 429 queue_timeout."""
    test_app = FastAPI()
    test_app.add_middleware(
        RateLimitMiddleware,
        max_ai_concurrent=1,
        max_ai_queue=5,
        queue_timeout_seconds=0.1,
        max_requests_per_minute=100,
    )

    blocker = asyncio.Event()

    @test_app.post("/api/v1/chat")
    async def fake_chat():
        await blocker.wait()
        return {"status": "ok"}

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Request 1: active and blocked
        t1 = asyncio.create_task(ac.post("/api/v1/chat"))
        await asyncio.sleep(0.02)

        # Request 2: waits in queue with 0.1s timeout
        t2 = asyncio.create_task(ac.post("/api/v1/chat"))
        res2 = await t2

        assert res2.status_code == 429
        assert res2.json() == {"detail": "queue_timeout"}
        assert res2.headers.get("Retry-After") == "5"

        # Release blocker for Request 1
        blocker.set()
        res1 = await t1
        assert res1.status_code == 200

        # Subsequent requests succeed
        res3 = await ac.post("/api/v1/chat")
        assert res3.status_code == 200


def test_ai_queue_reset_clears_state():
    """Reset cleans up both IP rate limits and the queue state."""
    app = FastAPI()
    middleware = RateLimitMiddleware(app, max_ai_concurrent=1, max_ai_queue=2)
    middleware._active_ai_count = 1
    middleware._ai_queue.append(asyncio.Event())
    middleware._ip_requests["127.0.0.1"].append(12345.0)

    assert middleware.active_ai_count == 1
    assert middleware.waiting_ai_count == 1
    assert len(middleware._ip_requests) == 1

    middleware.reset()

    assert middleware.active_ai_count == 0
    assert middleware.waiting_ai_count == 0
    assert len(middleware._ip_requests) == 0


def test_settings_ai_queue_defaults():
    """Settings provides appropriate Jetson Nano defaults for AI request queue."""
    settings = Settings(_env_file=None)
    assert settings.ai_max_concurrent == 1
    assert settings.ai_queue_capacity == 10
    assert settings.ai_queue_timeout_seconds == 15.0
    assert settings.rate_limit_per_minute == 600
    assert DEFAULT_MAX_REQUESTS_PER_MINUTE == 600


def test_heavy_ai_endpoints_list():
    """Verify all required endpoints are categorized as heavy AI endpoints."""
    expected_endpoints = {
        "/api/v1/chat",
        "/api/v1/voice/process",
        "/api/v1/voice/transcribe",
        "/api/v1/voice/synthesize",
    }
    assert expected_endpoints.issubset(HEAVY_AI_ENDPOINTS)


def test_bootstrap_admin_generates_random_password_when_not_provided(tmp_path):
    """When bootstrap_admin_password is empty, a 16-character secure random password is generated and returned."""
    store = UserStore(tmp_path / "users.json")
    settings = Settings(
        _env_file=None,
        bootstrap_admin_email="admin@homing.dev",
        bootstrap_admin_password="",
    )

    generated_password = store.bootstrap_admin(settings)
    assert generated_password is not None
    assert len(generated_password) == 16

    # Verify admin was created
    admin = store.get_by_email("admin@homing.dev")
    assert admin is not None
    assert admin["role"] == "ADMIN"

    # Verify no default member was created
    member = store.get_by_email("member@homing.dev")
    assert member is None


def test_bootstrap_admin_uses_configured_password(tmp_path):
    """When bootstrap_admin_password is provided in settings, it is used without returning it."""
    store = UserStore(tmp_path / "users.json")
    settings = Settings(
        _env_file=None,
        bootstrap_admin_email="custom-admin@homing.dev",
        bootstrap_admin_password="CustomSecretPassword123!",
    )

    returned_password = store.bootstrap_admin(settings)
    assert returned_password is None

    # Verify admin was created with configured password
    record, error = store.verify_login("custom-admin@homing.dev", "CustomSecretPassword123!")
    assert error is None
    assert record is not None
