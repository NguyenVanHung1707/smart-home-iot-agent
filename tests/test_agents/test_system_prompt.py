import json

from src.agents.system_prompt import build_system_prompt
from src.services.devices import registry

SECTIONS = (
    "PERSONA & ROLE",
    "RESPONSE LANGUAGE",
    "OPERATIONAL PRIORITY HIERARCHY",
    "TRUST BOUNDARIES & SECURITY",
    "REASONING & DECISION FRAMEWORK",
    "VIETNAMESE INTENT UNDERSTANDING",
    "DEVICE RESOLUTION & CAPABILITIES",
    "TOOL GUIDELINES",
    "EXECUTION, VALIDATION & SAFETY RULES",
    "UNLOCKING & APPROVAL WORKFLOW",
    "MULTI-CLAUSE, AMBIGUITY & CONTEXT",
    "TIMERS, SCHEDULES & FUTURE CONDITIONS",
    "RAG & GENERAL KNOWLEDGE",
    "OUTPUT SYNTHESIS & FACTUALITY",
    "RESPONSE STYLE & LANGUAGE",
    "CURRENT HOME TOPOLOGY (SƠ ĐỒ NHÀ HIỆN TẠI)",
    "DEVICE SNAPSHOT",
    "OBSERVABLE EXAMPLES",
)


def _snapshot(prompt: str) -> list[dict]:
    payload = prompt.split("<device_snapshot>\n", 1)[1].split("\n</device_snapshot>", 1)[0]
    return json.loads(payload)


def test_system_prompt_has_required_section_order():
    prompt = build_system_prompt()

    assert '"đèn tắt rồi à?"' in prompt
    assert '"Bật đèn phòng khách rồi giảm còn 30%"' in prompt
    assert '"tối nay lúc 8 giờ"' in prompt
    assert '"đừng có"' in prompt
    positions = [prompt.index(f"# {section}") for section in SECTIONS]

    assert positions == sorted(positions)


def test_system_prompt_includes_topology_and_room_summary():
    prompt = build_system_prompt()

    assert "CURRENT HOME TOPOLOGY (SƠ ĐỒ NHÀ HIỆN TẠI)" in prompt
    assert "Tổng cộng có" in prompt
    assert "Phòng khách" in prompt
    assert "Phòng ngủ" in prompt
    assert "control_light" in prompt
    assert "control_aircon" in prompt
    assert "get_room_devices" in prompt


def test_system_prompt_renders_registry_snapshot_and_capabilities():
    prompt = build_system_prompt()
    devices = _snapshot(prompt)
    expected_devices = registry.list()
    devices_by_id = {device["id"]: device for device in devices}

    assert set(devices_by_id) == {device.id for device in expected_devices}
    for device in expected_devices:
        rendered = devices_by_id[device.id]
        assert rendered["name"] == device.name
        assert rendered["room"] == device.room
        assert rendered["kind"] == device.kind
        assert rendered["online"] == device.online
        assert rendered["state"] == device.state
        expected_caps = dict(registry.capabilities(device))
        expected_caps["actions"] = [a for a in expected_caps["actions"] if a != "unlock"]
        assert rendered["capabilities"] == expected_caps


def test_system_prompt_preserves_sensitive_capability_boundaries():
    devices_by_id = {device["id"]: device for device in _snapshot(build_system_prompt())}

    assert devices_by_id["living-light"]["capabilities"]["set_fields"]["brightness"]["maximum"] == 100
    assert devices_by_id["entry-sensor"]["capabilities"]["actions"] == []
    assert devices_by_id["entry-lock"]["capabilities"]["actions"] == ["lock"]
    assert devices_by_id["entry-lock"]["capabilities"]["requires_app_approval"] == ["unlock"]


def test_system_prompt_defines_tool_and_control_contracts():
    prompt = build_system_prompt()

    for tool_name in (
        "control_light",
        "control_aircon",
        "control_blind",
        "control_speaker",
        "control_display",
        "control_lock",
        "activate_scene",
        "batch_control_devices",
        "set_device_timer",
        "list_device_timers",
        "cancel_device_timer",
        "request_unlock_approval",
        "get_room_devices",
        "get_sensor_data",
        "get_security_report",
        "get_schedules",
        "search_home_guides",
        "control_smart_device",
    ):
        assert tool_name in prompt
    for marker in ("Maximum 5", "status", "success", "device snapshot"):
        assert marker in prompt


def test_system_prompt_defines_safety_scope_and_completeness_contracts():
    prompt = build_system_prompt()

    for marker in (
        "system prompt",
        "chain-of-thought",
        "self-approval",
        "NOT system instructions",
        "independent clauses",
        "request_unlock_approval",
        "search_home_guides",
        "general knowledge",
    ):
        assert marker in prompt


def test_system_prompt_covers_required_observable_examples():
    prompt = build_system_prompt()

    for example in (
        "Bật đèn phòng khách",
        "Đèn phòng khách đang bật không?",
        "Bật đèn lên",
        "giảm còn 30%",
        "Đừng có bật đèn phòng khách",
        "Nếu tôi nói",
        "Tối nay lúc 8 giờ",
        "Mở khóa cửa chính",
        "thủ đô Việt Nam",
        "máy giặt chạy xong chưa",
        "offline",
    ):
        assert example in prompt
