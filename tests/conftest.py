from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.middleware.rate_limit import clear_rate_limits
from src.services.approvals import approvals
from src.services.auth import clear_login_rate_limits, create_access_token
from src.services.mqtt import get_mqtt_hub
from src.services.users import users


@pytest.fixture(autouse=True)
def auth_test_store(tmp_path, monkeypatch):
    """Isolate auth state and device registries from local files for every test."""
    import shutil

    from src.config import get_settings
    from src.services.devices import _REGISTRIES, get_registry, registry

    users.configure(tmp_path / "users.json")
    users.create("admin@example.com", "admin-password", "Test Admin", "ADMIN")
    users.create("member@example.com", "member-password", "Test Member", "MEMBER")
    approvals.clear()
    clear_login_rate_limits()
    clear_rate_limits()
    get_mqtt_hub().stop()

    tmp_sim = tmp_path / "app_devices.json"
    tmp_real = tmp_path / "app_devices_real.json"

    sim_source = Path("data/devices.json") if Path("data/devices.json").exists() else Path("runtime/devices.json")
    if sim_source.exists():
        shutil.copy(sim_source, tmp_sim)
    else:
        import json

        from src.services.devices import _DEFAULT_SIMULATOR_DEVICES

        tmp_sim.write_text(json.dumps(_DEFAULT_SIMULATOR_DEVICES, ensure_ascii=False), encoding="utf-8")

    real_source = Path("data/devices_real.json")
    if real_source.exists():
        shutil.copy(real_source, tmp_real)
    else:
        import json

        from src.services.devices import _DEFAULT_REAL_DEVICES

        tmp_real.write_text(json.dumps(_DEFAULT_REAL_DEVICES, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(get_settings(), "device_storage_path", str(tmp_sim))
    monkeypatch.setattr(get_settings(), "simulator_device_storage_path", str(tmp_sim))
    monkeypatch.setattr(get_settings(), "real_device_storage_path", str(tmp_real))

    _REGISTRIES.clear()
    registry.storage_path = tmp_sim
    registry.load()
    _REGISTRIES[f"simulator:{tmp_sim}"] = registry
    get_registry("real")

    monkeypatch.setattr(get_mqtt_hub().settings, "mqtt_enabled", False)
    yield
    clear_login_rate_limits()
    clear_rate_limits()
    get_mqtt_hub().stop()
    _REGISTRIES.clear()
    registry.storage_path = (
        Path("runtime/devices.json") if Path("runtime/devices.json").exists() else Path("data/devices.json")
    )
    registry.load()


@pytest.fixture
def admin_auth_headers():
    user = users.get_by_email("admin@example.com")
    return {"Authorization": f"Bearer {create_access_token(user)}"}


@pytest.fixture
def member_auth_headers():
    user = users.get_by_email("member@example.com")
    return {"Authorization": f"Bearer {create_access_token(user)}"}


@pytest_asyncio.fixture
async def unauthenticated_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def client(admin_auth_headers):
    """Authenticated admin HTTP client for legacy API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=admin_auth_headers) as ac:
        yield ac


@pytest_asyncio.fixture
async def admin_client(admin_auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=admin_auth_headers) as ac:
        yield ac


@pytest_asyncio.fixture
async def member_client(member_auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=member_auth_headers) as ac:
        yield ac


@pytest.fixture
def mock_llm():
    """Mock LLM to avoid calling OpenAI during tests.

    Usage in test:
        def test_something(mock_llm):
            # LLM calls will return mock response instead of hitting OpenAI
            ...
    """
    mock = AsyncMock()
    mock.ainvoke.return_value = AsyncMock(content="Mocked LLM response")
    return mock
