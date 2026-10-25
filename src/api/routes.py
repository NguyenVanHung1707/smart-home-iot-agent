import io
import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage

import src.services.devices as devices_mod
from src.agents.graph import agent, fallback_node
from src.api.deps import AuthUser, current_user, get_current_registry, require_admin
from src.config import get_settings
from src.models.schemas import (
    Approval,
    ChatRequest,
    ChatResponse,
    ConversationHistoryResponse,
    ConversationRecord,
    CreateConversationLogRequest,
    CreateDeviceRequest,
    Device,
    DeviceCommand,
    DiscoveredDevice,
    PairDeviceRequest,
    RAGQuery,
    RenameRoomRequest,
    SimulatorFault,
    UpdateDeviceRequest,
    VoiceRequest,
    VoiceSynthesisRequest,
    VoiceTranscriptionResponse,
)
from src.services.approvals import approvals
from src.services.conversation import conversations
from src.services.device_control import control_device
from src.services.devices import registry, set_active_data_mode
from src.services.mqtt import get_mqtt_hub
from src.services.rag import search_device_guides
from src.services.speech import (
    InvalidAudioError,
    NoSpeechDetectedError,
    SpeechError,
    SpeechTimeoutError,
    SpeechUnavailableError,
    get_speech_runtime,
)
from src.services.xiaozhi import xiaozhi_service

router = APIRouter()
logger = logging.getLogger(__name__)


async def _invoke_agent(query: str, session_id: str | None = None, mode: str | None = None) -> dict:
    """Use Xiaozhi AI for real hardware or the Local Model ReAct agent for simulator."""
    conversation_id = session_id or str(uuid4())
    active_mode = (mode or "simulator").strip().lower()

    if active_mode in {"real", "live", "hardware"}:
        result = await xiaozhi_service.process(query, session_id=conversation_id)
        result["session_id"] = conversation_id
        try:
            from src.database import db_log_conversation
            db_log_conversation(
                source="web",
                user_query=query,
                ai_response=result.get("response", ""),
                session_id=conversation_id,
                intent=result.get("analysis", "real_control"),
                device_action=result.get("action"),
                metadata={"ai_engine": "xiaozhi_ai", "mode": active_mode},
            )
        except Exception as log_err:
            logger.warning("Failed to persist conversation history: %s", log_err)
        return result

    history = [
        HumanMessage(content=content) if role == "user" else AIMessage(content=content)
        for role, content in conversations.snapshot(conversation_id, mode=active_mode).messages
    ]
    state = {
        "messages": [*history, HumanMessage(content=query)],
        "query": query,
        "session_id": conversation_id,
        "data_mode": "simulator",
    }
    try:
        result = await agent.ainvoke(state)
        if result.get("fallback_required"):
            result = await fallback_node(state)
    except Exception:
        logger.warning("Local LLM agent unavailable; using deterministic fallback", exc_info=True)
        result = await fallback_node(state)
    result["session_id"] = conversation_id
    if "metadata" not in result:
        result["metadata"] = {}
    result["metadata"]["ai_engine"] = "local_model"
    result["metadata"]["mode"] = "simulator"
    conversations.add_turn(conversation_id, query, result.get("response", ""))
    try:
        from src.database import db_log_conversation
        cmds = result.get("metadata", {}).get("commands", [])
        act_str = ", ".join([f"{c.get('device_id')}:{c.get('action')}" for c in cmds if isinstance(c, dict)]) if cmds else None
        db_log_conversation(
            source="web",
            user_query=query,
            ai_response=result.get("response", ""),
            session_id=conversation_id,
            intent=result.get("analysis", "local_model"),
            device_action=act_str,
            metadata={"ai_engine": "local_model", "mode": "simulator"},
        )
    except Exception as log_err:
        logger.warning("Failed to persist conversation history: %s", log_err)
    return result


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    x_data_mode: str | None = Header(None, alias="X-Data-Mode"),
    mode: str | None = Query(None),
) -> ChatResponse:
    from src.services.guardrails import guardrails

    # 1. Input Guardrail: Block prompt injection, secrets theft, physical threats, toxicity
    input_guard = guardrails.inspect_input(request.message)
    if not input_guard.passed:
        reply = input_guard.suggested_response or "Yêu cầu bị từ chối bởi rào chắn an toàn của ngôi nhà."
        session_id = request.session_id or "default"
        conversations.add_turn(session_id, request.message, reply)
        return ChatResponse(
            response=reply,
            analysis="guardrail_blocked",
            session_id=session_id,
        )

    active_mode = (mode or x_data_mode or "simulator").strip().lower()
    set_active_data_mode(active_mode)
    result = await _invoke_agent(request.message, request.session_id, mode=active_mode)
    # 2. Output Guardrail: Redact any accidental credentials or tokens
    sanitized_response = guardrails.sanitize_output(result.get("response", ""))
    return ChatResponse(
        response=sanitized_response,
        analysis=result.get("analysis", ""),
        session_id=result["session_id"],
        track=result.get("track") or result.get("metadata", {}).get("track"),
        url=result.get("url") or result.get("metadata", {}).get("url"),
        audio_stream_url=result.get("audio_stream_url") or result.get("metadata", {}).get("audio_stream_url"),
        thumbnail=result.get("thumbnail") or result.get("metadata", {}).get("thumbnail"),
        duration=result.get("duration") or result.get("metadata", {}).get("duration"),
        metadata=result.get("metadata"),
    )


@router.get("/status")
async def agent_status(
    x_data_mode: str | None = Header(None, alias="X-Data-Mode"),
    mode: str | None = Query(None),
):
    active_mode = (mode or x_data_mode or "simulator").strip().lower()
    if active_mode in {"real", "live", "hardware"}:
        return {
            "status": "ready",
            "agent": "Trợ lý AI Xiaozhi Gateway",
            "ai_engine": "xiaozhi_ai",
            "mode": "real",
        }
    return {
        "status": "ready",
        "agent": "Homing Local Model (Qwen/Llama)",
        "ai_engine": "local_model",
        "mode": "simulator",
    }


@router.get("/devices", response_model=list[Device])
async def list_devices(reg: Any = Depends(get_current_registry)) -> list[Device]:
    return reg.list()


@router.get("/rooms", response_model=list[str])
async def list_rooms(reg: Any = Depends(get_current_registry)) -> list[str]:
    return reg.rooms()


@router.post("/devices", response_model=Device, status_code=201, dependencies=[Depends(require_admin)])
async def create_device(request: CreateDeviceRequest, reg: Any = Depends(get_current_registry)) -> Device:
    try:
        device = Device(**request.model_dump())
        created = reg.add(device)
    except ValueError as error:
        if str(error) == "device_id_exists":
            raise HTTPException(status_code=409, detail="Device ID already exists") from error
        raise HTTPException(status_code=422, detail=str(error)) from error

    return created


@router.get("/devices/{device_id}", response_model=Device)
async def get_device(device_id: str, reg: Any = Depends(get_current_registry)) -> Device:
    device = reg.get(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.put("/devices/{device_id}", response_model=Device, dependencies=[Depends(require_admin)])
async def update_device(
    device_id: str, request: UpdateDeviceRequest, reg: Any = Depends(get_current_registry)
) -> Device:
    if reg.get(device_id) is None:
        raise HTTPException(status_code=404, detail="Device not found")
    updated = reg.update(device_id, request.model_dump(exclude_none=True))
    if updated is None:
        raise HTTPException(status_code=404, detail="Device not found")

    return updated


@router.delete("/devices/{device_id}", dependencies=[Depends(require_admin)])
async def delete_device(device_id: str, reg: Any = Depends(get_current_registry)) -> dict[str, Any]:
    existing = reg.get(device_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Device not found")
    if not reg.delete(device_id):
        raise HTTPException(status_code=500, detail="Failed to delete device")

    return {"status": "deleted", "device_id": device_id}


@router.post("/rooms/rename", dependencies=[Depends(require_admin)])
async def rename_room(request: RenameRoomRequest, reg: Any = Depends(get_current_registry)) -> dict[str, Any]:
    updated = reg.rename_room(request.old_name, request.new_name)
    return {
        "status": "ok",
        "old_name": request.old_name,
        "new_name": request.new_name,
        "updated_devices_count": len(updated),
        "devices": [device.model_dump() for device in updated],
    }


@router.delete("/rooms/{room_name}", dependencies=[Depends(require_admin)])
async def delete_room(room_name: str, reg: Any = Depends(get_current_registry)) -> dict[str, Any]:
    norm_target = room_name.strip().casefold()
    if norm_target not in [r.strip().casefold() for r in reg.rooms()]:
        raise HTTPException(status_code=404, detail="Room not found")
    deleted_device_ids = reg.delete_room(room_name)
    return {
        "status": "deleted",
        "room": room_name,
        "deleted_devices_count": len(deleted_device_ids),
        "deleted_devices": deleted_device_ids,
    }


@router.get("/discovery/devices", response_model=list[DiscoveredDevice], dependencies=[Depends(require_admin)])
async def list_discovered_devices(reg: Any = Depends(get_current_registry)) -> list[DiscoveredDevice]:
    return [DiscoveredDevice.model_validate(item) for item in reg.list_discovered()]


@router.post("/discovery/devices/{device_id}/pair", response_model=Device, dependencies=[Depends(require_admin)])
async def pair_discovered_device(
    device_id: str, request: PairDeviceRequest | None = None, reg: Any = Depends(get_current_registry)
) -> Device:
    paired = reg.pair_discovered(
        device_id,
        name=request.name if request else None,
        room=request.room if request else None,
    )
    if paired is None:
        raise HTTPException(status_code=404, detail="Discovered device not found")
    return paired


@router.delete("/discovery/devices/{device_id}", dependencies=[Depends(require_admin)])
async def dismiss_discovered_device(device_id: str, reg: Any = Depends(get_current_registry)) -> dict[str, Any]:
    dismissed = reg.dismiss_discovered(device_id)
    if not dismissed:
        raise HTTPException(status_code=404, detail="Discovered device not found")
    return {"status": "dismissed", "device_id": device_id}


@router.post("/discovery/scan", dependencies=[Depends(require_admin)])
async def trigger_discovery_scan(
    mode: str | None = Query(None),
    x_data_mode: str | None = Header(None, alias="X-Data-Mode"),
    reg: Any = Depends(get_current_registry),
) -> dict[str, Any]:
    active_mode = (mode or x_data_mode or "simulator").strip().lower()
    if active_mode in {"real", "live", "hardware"}:
        devices_mod.get_registry("real").clear_discovered()
    elif active_mode == "simulator":
        devices_mod.get_registry("simulator").clear_discovered()
    elif active_mode == "all":
        devices_mod.get_registry("real").clear_discovered()
        devices_mod.get_registry("simulator").clear_discovered()
    if reg is not None and hasattr(reg, "clear_discovered"):
        reg.clear_discovered()

    hub = get_mqtt_hub()
    try:
        initiated = hub.trigger_discovery_scan(mode=active_mode)
    except TypeError:
        initiated = hub.trigger_discovery_scan()

    if active_mode in {"real", "live", "hardware"}:
        message = "Đã phát sóng lệnh quét thiết bị tới tất cả các bo mạch ESP32"
    elif active_mode == "all":
        message = "Đã phát sóng lệnh quét thiết bị tới tất cả các bo mạch ESP32 và Simulator"
    else:
        message = "Đã phát sóng lệnh quét thiết bị tới Thiết bị ảo (Simulator)"

    return {
        "status": "scan_initiated" if initiated else "mqtt_unavailable",
        "message": message,
    }


@router.post("/devices/{device_id}/command", response_model=Device | Approval)
async def command_device(
    device_id: str,
    command: DeviceCommand,
    pin: str | None = None,
    x_data_mode: str | None = Header(None, alias="X-Data-Mode"),
    mode: str | None = Query(None),
    user: AuthUser = Depends(current_user),
    reg: Any = Depends(get_current_registry),
) -> Device | Approval:
    active_mode = (mode or x_data_mode or "real").strip().lower()
    existing = reg.get(device_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Device not found")
    if not reg.supports(existing, command.action) and not reg.requires_approval(existing, command.action):
        raise HTTPException(status_code=422, detail=f"Action {command.action} is not supported by {existing.kind}")
    if existing.kind == "lock" and command.action == "unlock":
        if user.role == "ADMIN" and pin == "1234":
            device, error = control_device(
                device_id,
                command.action,
                command.value,
                approved_sensitive=True,
                registry=reg,
                mode=active_mode,
            )
            if error in {"timeout", "ack_timeout", "state_timeout"}:
                raise HTTPException(status_code=504, detail="Device acknowledgement timed out")
            if error:
                raise HTTPException(status_code=503, detail=f"Device command failed: {error}")
            if not device:
                raise HTTPException(status_code=404, detail="Device not found")
            return device
        _, validation_error = reg.validate_command(
            device_id,
            command.action,
            command.value,
            approved_sensitive=True,
        )
        if validation_error:
            status_code = 409 if validation_error == "device_offline" else 422
            raise HTTPException(status_code=status_code, detail=validation_error)
        return approvals.create(device_id, command, requested_by=user.id, mode=active_mode)
    _, validation_error = reg.validate_command(device_id, command.action, command.value)
    if validation_error:
        status_code = 409 if validation_error == "device_offline" else 422
        raise HTTPException(status_code=status_code, detail=validation_error)
    device, error = control_device(device_id, command.action, command.value, registry=reg, mode=active_mode)
    if error in {"timeout", "ack_timeout", "state_timeout"}:
        raise HTTPException(status_code=504, detail="Device acknowledgement timed out")
    if error:
        raise HTTPException(status_code=503, detail=f"Device command failed: {error}")
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.get("/approvals", response_model=list[Approval])
async def list_approvals(
    user: AuthUser = Depends(current_user),
    x_data_mode: str | None = Header(None, alias="X-Data-Mode"),
    mode: str | None = Query(None),
) -> list[Approval]:
    active_mode = (mode or x_data_mode or "simulator").strip().lower()
    norm_mode = "real" if active_mode in {"real", "live", "hardware"} else "simulator"
    items = approvals.list(mode=norm_mode)
    if user.role == "ADMIN":
        return items
    return [item for item in items if item.requested_by == user.id]


@router.post("/approvals/{approval_id}/approve", response_model=Device, dependencies=[Depends(require_admin)])
async def approve(approval_id: str) -> Device:
    capability = approvals.approve(approval_id)
    if capability is None:
        raise HTTPException(status_code=404, detail="Pending approval not found")
    device, error = control_device(
        capability.device_id,
        capability.action,
        capability.value,
        approval=capability,
        command_id=capability.approval_id,
        mode=getattr(capability, "mode", "simulator"),
    )
    if error or not device:
        raise HTTPException(
            status_code=504 if error in {"timeout", "ack_timeout", "state_timeout"} else 503,
            detail=f"Approval command failed: {error or 'not_found'}",
        )
    return device


@router.post("/approvals/{approval_id}/reject", response_model=Approval, dependencies=[Depends(require_admin)])
async def reject(approval_id: str) -> Approval:
    item = approvals.decide(approval_id, approved=False)
    if not item:
        raise HTTPException(status_code=404, detail="Pending approval not found")
    return item


@router.post("/simulator/devices/{device_id}/fault", dependencies=[Depends(require_admin)])
async def set_fault(device_id: str, fault: SimulatorFault):
    if not any(item.id == device_id for item in registry.list()):
        raise HTTPException(status_code=404, detail="Device not found")
    if not get_mqtt_hub().fault(device_id, fault.mode):
        raise HTTPException(status_code=503, detail="Simulator unavailable")
    return {"device_id": device_id, "mode": fault.mode}


@router.get("/simulator/events", dependencies=[Depends(require_admin)])
async def simulator_events(
    x_data_mode: str | None = Header(None, alias="X-Data-Mode"),
    mode: str | None = Query(None),
):
    active_mode = (mode or x_data_mode or "simulator").strip().lower()
    norm_mode = "real" if active_mode in {"real", "live", "hardware"} else "simulator"
    all_events = get_mqtt_hub().events

    def matches_mode(e: dict[str, Any], target_mode: str) -> bool:
        event_mode = e.get("mode")
        if event_mode:
            return event_mode == target_mode
        is_simulator = e.get("source") == "simulator" or "simulator" in str(e.get("topic", ""))
        if target_mode == "simulator":
            return is_simulator
        return not is_simulator

    return [e for e in all_events if matches_mode(e, norm_mode)]


@router.post("/rag/search")
async def rag_search(request: RAGQuery):
    return {"results": search_device_guides(request.query)}


@router.post("/voice/process")
@router.post("/voice")
async def process_voice(
    request: VoiceRequest,
    x_data_mode: str | None = Header(None, alias="X-Data-Mode"),
    mode: str | None = Query(None),
):
    """Run a confirmed transcript through the same path as text commands."""
    active_mode = (mode or x_data_mode or "simulator").strip().lower()
    set_active_data_mode(active_mode)
    result = await _invoke_agent(request.transcript, request.session_id, mode=active_mode)
    settings = get_settings()
    ai_engine = "xiaozhi_ai" if active_mode in {"real", "live", "hardware"} else "local_model"
    return {
        "transcript": request.transcript,
        "response": result.get("response", ""),
        "analysis": result.get("analysis", ""),
        "plan": result.get("metadata", {}).get("commands", []),
        "session_id": result["session_id"],
        "ai_engine": ai_engine,
        "mode": active_mode,
        "track": result.get("track") or result.get("metadata", {}).get("track"),
        "url": result.get("url") or result.get("metadata", {}).get("url"),
        "audio_stream_url": result.get("audio_stream_url") or result.get("metadata", {}).get("audio_stream_url"),
        "thumbnail": result.get("thumbnail") or result.get("metadata", {}).get("thumbnail"),
        "duration": result.get("duration") or result.get("metadata", {}).get("duration"),
        "metadata": result.get("metadata", {}),
        "tts": {"engine": "piper", "voice": settings.piper_voice, "enabled": settings.voice_enabled},
    }


def _speech_http_error(exc: SpeechError) -> HTTPException:
    if isinstance(exc, SpeechTimeoutError):
        return HTTPException(status_code=504, detail=str(exc))
    if isinstance(exc, SpeechUnavailableError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


@router.post("/voice/transcribe", response_model=VoiceTranscriptionResponse)
async def transcribe_voice(file: UploadFile = File(...)) -> VoiceTranscriptionResponse:
    if file.content_type not in {"audio/wav", "audio/x-wav", "audio/wave", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="unsupported_audio_type")
    settings = get_settings()
    audio = await file.read(settings.voice_max_audio_bytes + 1)
    await file.close()
    try:
        result = await get_speech_runtime().transcribe(audio)
    except (InvalidAudioError, NoSpeechDetectedError, SpeechUnavailableError, SpeechTimeoutError) as exc:
        raise _speech_http_error(exc) from exc
    return VoiceTranscriptionResponse(
        transcript=result.text,
        language=result.language,
        audio_duration_ms=result.duration_ms,
        stt_latency_ms=result.latency_ms,
        model=result.model,
        vad_applied=result.vad_applied,
    )


@router.post("/voice/synthesize")
async def synthesize_voice(request: VoiceSynthesisRequest) -> StreamingResponse:
    try:
        result = await get_speech_runtime().synthesize(request.text)
    except SpeechError as exc:
        raise _speech_http_error(exc) from exc
    media_type = "audio/wav" if result.audio.startswith(b"RIFF") else "audio/mpeg"
    return StreamingResponse(
        io.BytesIO(result.audio),
        media_type=media_type,
        headers={
            "X-TTS-Engine": result.voice,
            "X-TTS-Voice": result.voice,
            "X-TTS-Latency-Ms": str(result.latency_ms),
        },
    )


@router.get("/voice/status")
async def voice_status():
    return await get_speech_runtime().status()


# --- Floorplan 2D & 3D Architectural State Routes ---


@router.get("/floorplan")
async def get_floorplan(
    x_data_mode: str | None = Header(None, alias="X-Data-Mode"),
    mode: str | None = Query(None),
):
    from src.services.floorplan import get_floorplan_state

    active_mode = (mode or x_data_mode or "simulator").strip().lower()
    return get_floorplan_state(active_mode)


@router.post("/floorplan/walls")
async def save_floorplan_walls_route(
    payload: dict[str, Any] | list[dict[str, Any]],
    x_data_mode: str | None = Header(None, alias="X-Data-Mode"),
    mode: str | None = Query(None),
):
    from src.services.floorplan import save_floorplan_walls

    active_mode = (mode or x_data_mode or "simulator").strip().lower()
    walls = payload.get("walls", []) if isinstance(payload, dict) else payload
    return save_floorplan_walls(walls, mode=active_mode)


@router.put("/floorplan/devices/{device_id}")
async def update_floorplan_device_route(
    device_id: str,
    payload: dict[str, Any],
    x_data_mode: str | None = Header(None, alias="X-Data-Mode"),
    mode: str | None = Query(None),
):
    from src.services.floorplan import update_floorplan_device

    active_mode = (mode or x_data_mode or "simulator").strip().lower()
    updated = update_floorplan_device(device_id, payload, mode=active_mode)
    if updated is None:
        raise HTTPException(status_code=404, detail="device_not_found")
    return updated


@router.post("/floorplan/reset")
async def reset_floorplan_route(
    x_data_mode: str | None = Header(None, alias="X-Data-Mode"),
    mode: str | None = Query(None),
):
    from src.services.floorplan import reset_floorplan_state

    active_mode = (mode or x_data_mode or "simulator").strip().lower()
    return reset_floorplan_state(active_mode)


# --- Home Assistant Integration Routes ---


@router.post("/integrations/homeassistant/sync")
async def sync_homeassistant_discovery():
    """Publish Home Assistant MQTT Discovery configuration for all registered devices."""
    from src.services.devices import registry
    from src.services.homeassistant_discovery import publish_all_devices_discovery

    devices = registry.list_all()
    count = publish_all_devices_discovery(devices)
    return {
        "status": "success",
        "message": f"Đã đồng bộ khám phá Home Assistant cho {len(devices)} thiết bị ({count} thực thể).",
        "device_count": len(devices),
        "entities_published": count,
    }


# --- User Preferences & Long-Term Memory Routes ---


@router.get("/preferences")
async def list_preferences_route(category: str | None = Query(None)):
    """List all long-term memory preferences for the user."""
    from src.database import db_get_preferences

    return db_get_preferences(category=category)


@router.post("/preferences")
async def save_preference_route(payload: dict[str, Any]):
    """Create or update a user habit preference in long-term memory."""
    key = payload.get("key")
    if not key:
        raise HTTPException(status_code=400, detail="missing_key")
    from src.database import db_save_preference

    return db_save_preference(
        key=str(key),
        value=payload.get("value"),
        category=payload.get("category", "general"),
        description=payload.get("description"),
    )


@router.delete("/preferences/{key}")
async def delete_preference_route(key: str):
    """Delete a user preference from long-term memory."""
    from src.database import db_delete_preference

    deleted = db_delete_preference(key)
    if not deleted:
        raise HTTPException(status_code=404, detail="preference_not_found")
    return {"status": "success", "deleted_key": key}


# --- AI Personality, System Prompt & Voice Settings Routes ---


@router.get("/ai/config")
async def get_ai_configuration():
    """Retrieve active AI personality, system prompt, voice, and model settings."""
    from src.services.ai_config import ai_config_service

    return ai_config_service.get_config()


@router.post("/ai/config")
async def update_ai_configuration(payload: dict[str, Any]):
    """Update and persist AI personality, system prompt, voice, and model settings."""
    from src.services.ai_config import ai_config_service

    updated = ai_config_service.save(payload)
    return {
        "status": "success",
        "message": "Cấu hình AI đã được lưu và đồng bộ thành công tới Master ESP32 & Web Hub!",
        "config": updated,
    }


@router.post("/ai/reset")
async def reset_ai_configuration():
    """Reset AI configuration back to factory default values."""
    from src.services.ai_config import ai_config_service

    reset = ai_config_service.reset_to_default()
    return {
        "status": "success",
        "message": "Đã khôi phục cấu hình AI về mặc định ban đầu.",
        "config": reset,
    }


# --- AI Conversation History Routes ---


@router.get("/conversations/history", response_model=ConversationHistoryResponse)
async def get_conversations_history(
    source: str | None = Query(None, description="Filter by source: 'web', 'esp_ai', or 'all'"),
    search: str | None = Query(None, description="Search query in user query or AI response"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> ConversationHistoryResponse:
    """Retrieve history of conversations from both Web and ESP AI."""
    from src.database import db_get_conversations

    items, total = db_get_conversations(source=source, search=search, limit=limit, offset=offset)
    return ConversationHistoryResponse(total=total, items=items)


@router.post("/conversations/history", response_model=ConversationRecord, status_code=201)
async def create_conversation_log(payload: CreateConversationLogRequest) -> ConversationRecord:
    """Record a conversation turn from an external source (such as ESP32 Xiaozhi server)."""
    from src.database import db_log_conversation

    record = db_log_conversation(
        source=payload.source,
        user_query=payload.user_query,
        ai_response=payload.ai_response,
        session_id=payload.session_id or "default",
        intent=payload.intent,
        device_action=payload.device_action,
        audio_url=payload.audio_url,
        metadata=payload.metadata,
    )
    return ConversationRecord(**record)


@router.delete("/conversations/history")
async def clear_conversations_history(
    source: str | None = Query(None, description="Filter by source: 'web', 'esp_ai', or 'all'"),
):
    """Clear conversation history, optionally filtered by source."""
    from src.database import db_clear_conversations

    deleted = db_clear_conversations(source=source)
    return {"status": "cleared", "deleted_count": deleted}


@router.delete("/conversations/history/{conversation_id}")
async def delete_single_conversation(conversation_id: str):
    """Delete a single conversation entry by ID."""
    from src.database import db_delete_conversation

    deleted = db_delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    return {"status": "deleted", "id": conversation_id}


# --- Model Context Protocol (MCP) JSON-RPC 2.0 Route ---


@router.post("/mcp")
async def mcp_endpoint(
    payload: dict[str, Any],
    mode: str | None = Query(None),
    x_data_mode: str | None = Header(None, alias="X-Data-Mode"),
):
    """MCP endpoint implementing JSON-RPC 2.0 tools/list, tools/call for Xiaozhi AI & AI agents."""
    from src.services.mcp_server import mcp_server

    active_mode = (mode or x_data_mode or devices_mod.get_active_data_mode()).strip().lower()
    return mcp_server.handle_request(payload, mode=active_mode)


# --- Voice Announce Endpoint (Xiaozhi active notification) ---


@router.post("/voice/announce")
async def voice_announce(
    payload: dict[str, Any],
    mode: str | None = Query(None),
    x_data_mode: str | None = Header(None, alias="X-Data-Mode"),
):
    """Announce an alert or notification via MQTT to the Xiaozhi Gateway speaker."""
    from src.services.mqtt import get_mqtt_hub

    message = payload.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=422, detail="message_required")

    hub = get_mqtt_hub()
    if hub and hasattr(hub, "client") and hub.client is not None:
        try:
            settings = get_settings()
            prefix = settings.mqtt_topic_prefix.strip("/")
            hub.client.publish(f"{prefix}/speaker/say", message, qos=0)
            return {"status": "announced", "message": message}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return {"status": "simulated", "message": message}



