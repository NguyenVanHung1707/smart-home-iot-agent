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

router = APIRouter()
logger = logging.getLogger(__name__)


async def _invoke_agent(query: str, session_id: str | None = None, mode: str | None = None) -> dict:
    """Use the ReAct agent, then fall back without exposing LLM failures."""
    conversation_id = session_id or str(uuid4())
    history = [
        HumanMessage(content=content) if role == "user" else AIMessage(content=content)
        for role, content in conversations.snapshot(conversation_id, mode=mode).messages
    ]
    state = {
        "messages": [*history, HumanMessage(content=query)],
        "query": query,
        "session_id": conversation_id,
        "data_mode": mode or "simulator",
    }
    try:
        result = await agent.ainvoke(state)
        if result.get("fallback_required"):
            result = await fallback_node(state)
    except Exception:
        logger.warning("LLM agent unavailable; using deterministic fallback", exc_info=True)
        result = await fallback_node(state)
    result["session_id"] = conversation_id
    conversations.add_turn(conversation_id, query, result.get("response", ""))
    return result


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    x_data_mode: str | None = Header(None, alias="X-Data-Mode"),
    mode: str | None = Query(None),
) -> ChatResponse:
    active_mode = (mode or x_data_mode or "simulator").strip().lower()
    set_active_data_mode(active_mode)
    result = await _invoke_agent(request.message, request.session_id, mode=active_mode)
    return ChatResponse(
        response=result.get("response", ""),
        analysis=result.get("analysis", ""),
        session_id=result["session_id"],
    )


@router.get("/status")
async def agent_status(
    x_data_mode: str | None = Header(None, alias="X-Data-Mode"),
    mode: str | None = Query(None),
):
    active_mode = (mode or x_data_mode or "simulator").strip().lower()
    return {"status": "ready", "agent": "Homing LangGraph controller", "mode": active_mode}


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
    active_mode = (mode or x_data_mode or "simulator").strip().lower()
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
    return {
        "transcript": request.transcript,
        "response": result.get("response", ""),
        "analysis": result.get("analysis", ""),
        "plan": result.get("metadata", {}).get("commands", []),
        "session_id": result["session_id"],
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
    return StreamingResponse(
        io.BytesIO(result.audio),
        media_type="audio/wav",
        headers={
            "X-TTS-Engine": "piper",
            "X-TTS-Voice": result.voice,
            "X-TTS-Latency-Ms": str(result.latency_ms),
        },
    )


@router.get("/voice/status")
async def voice_status():
    return await get_speech_runtime().status()
