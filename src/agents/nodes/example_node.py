import asyncio

from src.agents.state import AgentState
from src.services.device_control import control_device
from src.services.llm_planner import plan_home_request
from src.services.rag import search_device_guides


async def analyze_node(state: AgentState, *, use_llm: bool = True) -> dict:
    """Planner/tool router. A local SLM can replace this deterministic first pass."""
    query = state.get("query", "")
    normalized = query.lower()
    llm_plan = await plan_home_request(query) if use_llm else None
    if llm_plan:
        commands = llm_plan["commands"]
        if not commands:
            return {"analysis": "llama_chat", "metadata": {"assistant_reply": llm_plan["reply"]}}
        results = await asyncio.gather(
            *(asyncio.to_thread(control_device, item["device_id"], item["action"], item["value"]) for item in commands)
        )
        if any(error for _, error in results):
            return {"error": "One or more device commands failed"}
        devices = [device.model_dump() for device, _ in results if device]
        return {
            "analysis": f"tool: llama_plan({len(devices)} commands)",
            "metadata": {"devices": devices, "commands": commands, "assistant_reply": llm_plan["reply"]},
        }

    from src.services.natural_language_control import _normalize, _room_topology_reply

    if topology_reply := _room_topology_reply(_normalize(query)):
        return {
            "analysis": "home_topology_query",
            "metadata": {"assistant_reply": topology_reply},
        }
    aliases = {
        "den": ("living-light", "bedroom-light"),
        "đèn": ("living-light", "bedroom-light"),
        "quat": ("living-fan",),
        "quạt": ("living-fan",),
        "dieu hoa": ("living-aircon",),
        "điều hòa": ("living-aircon",),
    }
    room_aliases = {
        "phòng ngủ": "bedroom-light",
        "phong ngu": "bedroom-light",
        "phòng khách": "living-light",
        "phong khach": "living-light",
    }
    light_requested = any(keyword in normalized for keyword in ("den", "đèn"))
    target = (
        next((device_id for room, device_id in room_aliases.items() if room in normalized), None)
        if light_requested
        else None
    )
    if target is None:
        target = next((ids[0] for keyword, ids in aliases.items() if keyword in normalized), None)
    action = (
        "on"
        if any(word in normalized for word in ("bat", "bật", "mo ", "mở ", " on"))
        else "off"
        if any(word in normalized for word in ("tat", "tắt", " off"))
        else None
    )
    if action and target:
        device, error = control_device(target, action)
        if error:
            return {"error": f"Device command failed: {error}"}
        return {
            "analysis": f"tool: device_control({target}, {action})",
            "metadata": {"device": device.model_dump() if device else {}},
        }
    guides = search_device_guides(query)
    return {"analysis": "tool: rag_search" if guides else "general_assistant", "metadata": {"guides": guides}}


async def respond_node(state: AgentState) -> dict:
    error = state.get("error")
    if error:
        return {"response": f"Lỗi: {error}"}
    metadata = state.get("metadata", {})
    if reply := metadata.get("assistant_reply"):
        return {"response": reply}
    if devices := metadata.get("devices"):
        return {"response": f"Đã thực hiện: {', '.join(device['name'] for device in devices)}."}
    if device := metadata.get("device"):
        power = "bật" if device["state"].get("power") else "tắt"
        return {"response": f"Đã {power} {device['name']}."}
    if guides := metadata.get("guides"):
        return {"response": f"Theo hướng dẫn {guides[0]['source']}: {guides[0]['content'][:350]}"}
    return {"response": "Tôi có thể điều khiển thiết bị, tra hướng dẫn hoặc lập kế hoạch cho ngôi nhà."}
