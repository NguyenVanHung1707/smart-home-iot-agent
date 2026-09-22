import pytest

from src.services.auth import create_access_token, create_refresh_token
from src.services.devices import registry
from src.services.users import users


@pytest.mark.asyncio
async def test_login_success_and_me(unauthenticated_client):
    login = await unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin-password"},
    )

    assert login.status_code == 200
    data = login.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["user"]["role"] == "ADMIN"
    assert "password" not in data["user"]

    me = await unauthenticated_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )

    assert me.status_code == 200
    assert me.json()["email"] == "admin@example.com"


@pytest.mark.asyncio
async def test_login_rejects_bad_password_without_enumerating_user(unauthenticated_client):
    wrong_password = await unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "wrong-password"},
    )
    missing_user = await unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "wrong-password"},
    )

    assert wrong_password.status_code == 401
    assert missing_user.status_code == 401
    assert wrong_password.json()["detail"] == "invalid_credentials"
    assert missing_user.json()["detail"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_protected_api_requires_access_token(unauthenticated_client):
    response = await unauthenticated_client.get("/api/v1/devices")

    assert response.status_code == 401
    assert response.json()["detail"] == "missing_token"


@pytest.mark.asyncio
async def test_member_cannot_call_admin_routes(member_client):
    create_device = await member_client.post(
        "/api/v1/devices",
        json={
            "id": "desk-light",
            "name": "Desk Light",
            "room": "Office",
            "kind": "light",
            "state": {"power": False},
        },
    )
    fault = await member_client.post("/api/v1/simulator/devices/living-light/fault", json={"mode": "offline"})

    assert create_device.status_code == 403
    assert fault.status_code == 403


@pytest.mark.asyncio
async def test_member_unlock_with_pin_only_creates_own_approval(member_client, admin_client):
    registry.update("entry-lock", {"state": {"locked": True}})

    response = await member_client.post(
        "/api/v1/devices/entry-lock/command?pin=1234",
        json={"action": "unlock"},
    )

    assert response.status_code == 200
    approval = response.json()
    assert approval["status"] == "pending"
    assert approval["requested_by"]
    assert registry.get("entry-lock").state["locked"] is True

    member_approvals = await member_client.get("/api/v1/approvals")
    assert [item["id"] for item in member_approvals.json()] == [approval["id"]]

    approve_as_member = await member_client.post(f"/api/v1/approvals/{approval['id']}/approve")
    assert approve_as_member.status_code == 403

    approve_as_admin = await admin_client.post(f"/api/v1/approvals/{approval['id']}/approve")
    assert approve_as_admin.status_code == 200
    assert approve_as_admin.json()["state"]["locked"] is False


@pytest.mark.asyncio
async def test_admin_unlock_with_pin_directly_unlocks_device(admin_client):
    registry.update("entry-lock", {"state": {"locked": True}})

    response = await admin_client.post(
        "/api/v1/devices/entry-lock/command?pin=1234",
        json={"action": "unlock"},
    )

    assert response.status_code == 200
    device = response.json()
    assert device["id"] == "entry-lock"
    assert device["state"]["locked"] is False
    assert registry.get("entry-lock").state["locked"] is False


@pytest.mark.asyncio
async def test_admin_can_create_member_user(admin_client):
    response = await admin_client.post(
        "/api/v1/auth/users",
        json={
            "email": "new-member@example.com",
            "password": "member-password",
            "display_name": "New Member",
            "role": "MEMBER",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "MEMBER"
    assert users.get_by_email("new-member@example.com") is not None


@pytest.mark.asyncio
async def test_refresh_token_cannot_access_protected_api(unauthenticated_client):
    user = users.get_by_email("member@example.com")
    refresh_token = create_refresh_token(user)

    response = await unauthenticated_client.get(
        "/api/v1/devices",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_token_type"


@pytest.mark.asyncio
async def test_logout_invalidates_existing_token(unauthenticated_client):
    user = users.get_by_email("member@example.com")
    access_token = create_access_token(user)

    logout = await unauthenticated_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    after_logout = await unauthenticated_client.get(
        "/api/v1/devices",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert logout.status_code == 200
    assert after_logout.status_code == 401


@pytest.mark.asyncio
async def test_locked_account_cannot_login_or_keep_using_old_token(unauthenticated_client):
    user = users.get_by_email("member@example.com")
    access_token = create_access_token(user)
    users.update(user["id"], {"locked": True})

    login = await unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"email": "member@example.com", "password": "member-password"},
    )
    protected = await unauthenticated_client.get(
        "/api/v1/devices",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert login.status_code == 401
    assert login.json()["detail"] == "account_locked"
    assert protected.status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limit_returns_429(unauthenticated_client):
    for _ in range(5):
        response = await unauthenticated_client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401

    limited = await unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "wrong-password"},
    )

    assert limited.status_code == 429
