"""Tests for User Preferences and Long-Term Memory (PostgreSQL + LangGraph)."""

import pytest

from src.agents.system_prompt import build_system_prompt
from src.agents.tools.preferences import get_user_preferences, save_user_preference
from src.database import (
    db_delete_preference,
    db_get_preference,
    db_get_preferences,
    db_save_preference,
    init_db,
)


@pytest.fixture(autouse=True)
def setup_prefs_db():
    init_db()
    # Clean up test keys
    for key in ["preferred_temp", "wake_time", "fav_music"]:
        db_delete_preference(key)
    yield
    for key in ["preferred_temp", "wake_time", "fav_music"]:
        db_delete_preference(key)


def test_db_save_and_get_preference():
    saved = db_save_preference("preferred_temp", 24, category="climate", description="Nhiệt độ phòng ngủ")
    assert saved["key"] == "preferred_temp"
    assert saved["value"] == 24
    assert saved["category"] == "climate"

    val = db_get_preference("preferred_temp")
    assert val == 24

    all_prefs = db_get_preferences(category="climate")
    assert any(p["key"] == "preferred_temp" for p in all_prefs)

    deleted = db_delete_preference("preferred_temp")
    assert deleted is True
    assert db_get_preference("preferred_temp") is None


def test_preference_tools():
    import json

    # Test tool invocation
    save_raw = save_user_preference.invoke(
        {"key": "wake_time", "value": "06:30", "category": "schedule", "description": "Giờ thức dậy"}
    )
    save_res = json.loads(save_raw)
    assert save_res["status"] == "success"

    get_raw = get_user_preferences.invoke({"category": "schedule"})
    get_res = json.loads(get_raw)
    assert get_res["status"] == "success"
    assert get_res["count"] >= 1
    items = [x for x in get_res["data"] if x["key"] == "wake_time"]
    assert len(items) == 1
    assert items[0]["value"] == "06:30"



def test_system_prompt_injects_preferences():
    db_save_preference("fav_music", "Acoustic Pop", category="routine", description="Nhạc yêu thích")
    prompt = build_system_prompt()
    assert "# USER HABITS & PREFERENCES (LONG-TERM MEMORY)" in prompt
    assert "fav_music: Acoustic Pop" in prompt


@pytest.mark.asyncio
async def test_preference_api_routes(client):
    # Create
    post_res = await client.post(
        "/api/v1/preferences",
        json={"key": "preferred_temp", "value": 26, "category": "climate", "description": "Nhiệt độ mát"},
    )
    assert post_res.status_code == 200
    data = post_res.json()
    assert data["key"] == "preferred_temp"
    assert data["value"] == 26

    # List
    get_res = await client.get("/api/v1/preferences?category=climate")
    assert get_res.status_code == 200
    prefs = get_res.json()
    assert any(p["key"] == "preferred_temp" for p in prefs)

    # Delete
    del_res = await client.delete("/api/v1/preferences/preferred_temp")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"
