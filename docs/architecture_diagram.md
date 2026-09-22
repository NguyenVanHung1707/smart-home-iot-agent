# Architecture Diagram

## System Overview

```mermaid
graph TB
    User([User]) --> UI[Frontend Dashboard<br/>React + Vite]
    User --> UISim[Frontend Simulator<br/>2D Canvas & Fault Injection]
    UI -->|REST API & Audio| API[FastAPI Backend]
    API --> STT[sherpa-onnx Zipformer STT<br/>sherpa-onnx-zipformer-vi-int8-2025-04-20]
    API --> TTS[Piper TTS Service<br/>vi_VN-vais1000-medium]
    API --> Agent[LangGraph Agent]
    Agent --> LLM[Qwen2.5-3B / Qwen2.5-1.5B / Qwen3.5-2B<br/>llama.cpp Q4_K_M]
    LLM -->|exact single fenced homeassistant JSON| Agent
    Agent --> Rollout{Rollout mode}
    Rollout -->|legacy_active / typed_shadow| Legacy[Legacy compatibility adapter]
    Rollout -->|gated typed_active| Typed[Typed interpreter]
    Legacy --> Validator[Shared validator + policy + idempotency + verification]
    Typed --> Validator
    Validator --> Hub[Device control authority]
    Hub -->|MQTT QoS 1| Broker[Mosquitto Broker]
    Broker <--> Hardware[ESP32 Firmware]
    Broker <--> Sim[Device Simulator: 8 virtual devices]
```

## Agent Flow

```mermaid
graph LR
    START((Start)) --> Input[Parse Input]
    Input --> Route{Deterministic command?}
    Route -->|Yes| Control[Validated Hub control]
    Route -->|No| Model[One Qwen2.5 / Qwen3.5 call]
    Model --> Parse{Exact fenced control block?}
    Parse -->|Yes| Control
    Parse -->|No/plain answer| Generate[Return model answer]
    Control --> Confirm[Respond from Hub result]
    Generate --> END((End))
    Confirm --> END
```

## Component Details

| Component | Technology | Purpose |
|---|---|---|
| Frontend | React 18, Vite, TypeScript (`frontend/`) | User dashboard, Web Audio recorder, state view |
| Frontend Simulator | 2D Canvas Interactive (`frontend-simulator/`) | Virtual home floor plan and MQTT fault injection |
| Backend | FastAPI, Uvicorn, Pydantic v2 | API server, voice streaming, device registry |
| Speech-to-Text | `sherpa-onnx` Zipformer (`sherpa-onnx-zipformer-vi-int8-2025-04-20`) | On-device Vietnamese speech recognition |
| Text-to-Speech | Piper TTS (`vi_VN-vais1000-medium`) | Local Vietnamese voice synthesis |
| Agent | LangGraph | State graph orchestration and routing |
| LLM | `Qwen2.5-3B-Instruct` / `Qwen2.5-1.5B` / `Qwen3.5-2B` (Q4_K_M via `llama.cpp`) | Local reasoning; single fenced control block |
| Control authority | Registry validation + Hub (`src/services/devices.py`) | Device capability checks and execution |
| Transport & IoT | Mosquitto MQTT Broker (QoS 1) | Topics: `command`, `state`, `ack`, `fault` |
| Hardware & Simulation | ESP32 SoC (`src/firmware/`) & 8 virtual devices (`src/simulator.py`) | Physical actuators/sensors and virtual home devices |
| Rollout | `legacy_active` / `typed_shadow` / gated `typed_active` | Only active mode publishes; typed remains disabled without enabled, capability, and artifact gates |
| Testing | Pytest (`pytest tests/ -v -m "not live_model and not hardware"`) | Automated test suite: 463 passed, 1 skipped |
| Database | SQLite | State and automation persistence |
