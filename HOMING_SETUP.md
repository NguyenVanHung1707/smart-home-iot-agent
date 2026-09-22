# Homing Hub MVP: cài đặt, vận hành và kiểm thử

Hướng dẫn này chạy toàn bộ Homing Hub local: dashboard React, FastAPI, frontend/backend VAD, Zipformer STT tiếng Việt, LangGraph Agent, Qwen qua llama.cpp, MQTT, device simulator và Piper TTS.

## 1. Kiến trúc MVP

```text
Microphone trình duyệt
→ frontend VAD (tự dừng sau 2 giây im lặng)
→ WAV mono PCM16 16 kHz
→ backend VAD (chặn silence, cắt khoảng lặng)
→ Zipformer STT
→ AI Agent
→ MQTT command/state/ack
→ Piper TTS
→ trình duyệt phát phản hồi
```

| Thành phần | Công nghệ | Vai trò |
| --- | --- | --- |
| Dashboard (`frontend/`) | React + Vite | Thu âm, hiển thị transcript, trạng thái và kết quả |
| Simulator UI (`frontend-simulator/`) | HTML5 Canvas + React | Mô phỏng 2D Virtual Home Lab trực quan |
| Frontend VAD | RMS energy | Tự dừng recorder sau 2 giây không còn speech |
| Backend | FastAPI | Điều phối STT, Agent, MQTT và TTS |
| Backend VAD | Energy VAD | Xác nhận speech và lọc silence trước Zipformer |
| STT | sherpa-onnx Zipformer | Chuyển giọng nói tiếng Việt thành text |
| Agent | LangGraph + Qwen | Phân tích ý định, tạo và thực thi kế hoạch |
| MQTT | Eclipse Mosquitto | Gửi command, nhận state và acknowledgment |
| TTS | Piper | Tạo WAV phản hồi tiếng Việt |
| Simulator | Python MQTT client | Mô phỏng thiết bị local |

MQTT chỉ vận chuyển lệnh/trạng thái thiết bị. Audio, transcript và TTS không đi qua MQTT.

## 2. Yêu cầu

- Docker Engine hoặc Docker Desktop.
- Docker Compose v2.
- `curl`, `tar`, `sha256sum` để tải voice models.
- Trình duyệt hỗ trợ microphone.

```bash
docker --version
docker compose version
```

Chạy mọi lệnh sau từ thư mục gốc repository.

## 3. Cấu hình `.env`

```bash
cp .env.example .env
```

Không commit `.env`.

Cấu hình full MVP:

```env
# Qwen local qua llama.cpp
LLM_ENABLED=true
MODEL_NAME=qwen2.5-3b-instruct-q4_k_m.gguf
LLAMA_MODEL_FILE=qwen2.5-3b-instruct-q4_k_m.gguf
LLAMA_BASE_URL=http://llama:8080/v1
LLM_TIMEOUT_SECONDS=12

# MQTT trong Compose network
MQTT_ENABLED=true
MQTT_BROKER=mqtt
MQTT_PORT=1883
MQTT_TOPIC_PREFIX=homing
MQTT_QOS=1
MQTT_RETAIN_STATE=true
MQTT_CLIENT_ID=homing-hub

# Zipformer + VAD + Piper
VOICE_ENABLED=true
ZIPFORMER_MODEL_DIR=/models/zipformer/sherpa-onnx-zipformer-vi-int8-2025-04-20
ZIPFORMER_NUM_THREADS=2
PIPER_ENDPOINT=http://piper:5000
PIPER_VOICE=vi_VN-vais1000-medium
TTS_TIMEOUT_SECONDS=30
VOICE_MAX_AUDIO_SECONDS=20
VOICE_MAX_AUDIO_BYTES=1000000
VOICE_MAX_TTS_CHARS=1000

CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

Muốn chạy dashboard/API/MQTT không có model:

```env
LLM_ENABLED=false
VOICE_ENABLED=false
```

## 4. Chuẩn bị models

### Voice models

```bash
bash scripts/download_voice_models.sh
```

Script tải và kiểm tra checksum:

```text
models/
├── zipformer/sherpa-onnx-zipformer-vi-int8-2025-04-20/
│   ├── encoder-epoch-12-avg-8.int8.onnx
│   ├── decoder-epoch-12-avg-8.onnx
│   ├── joiner-epoch-12-avg-8.int8.onnx
│   └── tokens.txt
└── piper/
    ├── vi_VN-vais1000-medium.onnx
    └── vi_VN-vais1000-medium.onnx.json
```

### Qwen GGUF

Đặt model tại:

```text
models/qwen2.5-3b-instruct-q4_k_m.gguf
```

Nếu tên khác, cập nhật cả hai biến:

```env
LLAMA_MODEL_FILE=ten-model.gguf
MODEL_NAME=ten-model.gguf
```

## 5. Khởi động Docker

`scripts/docker.sh` là entrypoint chính.

| Chế độ | Lệnh | Thành phần |
| --- | --- | --- |
| Base | `bash scripts/docker.sh up` | Dashboard, API, MQTT, simulator |
| Voice | `bash scripts/docker.sh up voice` | Base + Zipformer + Piper |
| LLM | `bash scripts/docker.sh up llm` | Base + llama.cpp/Qwen |
| Full MVP | `bash scripts/docker.sh up full` | Tất cả thành phần |

```bash
bash scripts/docker.sh up full
bash scripts/docker.sh ps
```

Quản lý stack:

```bash
bash scripts/docker.sh logs
bash scripts/docker.sh logs backend frontend
bash scripts/docker.sh logs backend piper llama mqtt device-simulator
bash scripts/docker.sh config
bash scripts/docker.sh down full
```

`down` giữ MQTT volume. Chỉ xóa volume khi chủ động muốn xóa dữ liệu local:

```bash
docker compose down -v
```

## 6. Địa chỉ dịch vụ

| Dịch vụ | Địa chỉ |
| --- | --- |
| Dashboard | [http://localhost/](http://localhost/) |
| Swagger API | [http://localhost:8000/docs](http://localhost:8000/docs) |
| Health | [http://localhost:8000/health](http://localhost:8000/health) |
| Voice status | [http://localhost:8000/api/v1/voice/status](http://localhost:8000/api/v1/voice/status) |
| MQTT TCP | `localhost:1883` |
| MQTT WebSocket | `ws://localhost:9001` |
| llama.cpp health | [http://localhost:8080/health](http://localhost:8080/health) |

Mosquitto chỉ bind `127.0.0.1` trên host. Piper chỉ chạy trong Compose network. Dashboard proxy API qua `/api/`.

## 7. UX voice: tự gửi sau 2 giây

1. Mở `http://localhost/`, vào tab **Trợ lý**.
2. Bấm microphone một lần và cấp quyền.
3. Nói câu lệnh, ví dụ: “Bật đèn phòng khách và đặt điều hòa 26 độ”.
4. Ngừng nói.
5. Sau 2 giây không còn speech, recorder tự dừng và gửi WAV.
6. Zipformer trả transcript; frontend tự gửi transcript cho Agent.
7. Agent thực thi command qua MQTT.
8. Piper tạo audio phản hồi nếu TTS sẵn sàng.

Không cần bấm nút gửi hoặc microphone lần hai. Nút microphone vẫn cho phép dừng thủ công; recorder có hard limit `VOICE_MAX_AUDIO_SECONDS`, mặc định 20 giây.

Frontend VAD mặc định:

```text
RMS speech threshold: 0.018
Minimum speech:       120 ms
Silence timeout:      2.000 ms (2 giây)
```

Hai lớp VAD có mục đích khác nhau:

- Frontend VAD tối ưu UX, xác định thời điểm dừng recorder.
- Backend VAD là biên kiểm tra chính, reject audio toàn silence và cắt silence đầu/cuối trước Zipformer.

Microphone cần secure context: `localhost` hoặc HTTPS. Truy cập qua IP LAN không HTTPS có thể bị browser chặn.

## 8. Voice API

### Status

```bash
curl -s http://localhost:8000/api/v1/voice/status
```

Response sẵn sàng:

```json
{
  "enabled": true,
  "ready": true,
  "stt": {
    "ready": true,
    "model": "sherpa-onnx-zipformer-vi-int8-2025-04-20",
    "vad": true
  },
  "tts": {
    "ready": true,
    "voice": "vi_VN-vais1000-medium"
  },
  "limits": {"max_audio_seconds": 20}
}
```

### Transcribe

```bash
curl -s -F "file=@command.wav;type=audio/wav" \
  http://localhost:8000/api/v1/voice/transcribe
```

Audio phải là WAV uncompressed, mono, signed PCM16, 16 kHz và nằm trong size/duration limits.

```json
{
  "transcript": "bật đèn phòng khách",
  "language": "vi",
  "audio_duration_ms": 1800,
  "stt_latency_ms": 250,
  "model": "sherpa-onnx-zipformer-vi-int8-2025-04-20",
  "vad_applied": true
}
```

### Gửi transcript cho Agent

```bash
curl -s -H "Content-Type: application/json" \
  -d '{"transcript":"bật đèn phòng khách"}' \
  http://localhost:8000/api/v1/voice/process
```

Voice và text dùng cùng Agent/device-control path.

### Piper TTS

```bash
curl -s -H "Content-Type: application/json" \
  -d '{"text":"Đã bật đèn phòng khách."}' \
  http://localhost:8000/api/v1/voice/synthesize \
  --output reply.wav
```

Headers gồm `X-TTS-Engine`, `X-TTS-Voice`, `X-TTS-Latency-Ms`.

## 9. MQTT contract

| Mục đích | Topic |
| --- | --- |
| Command | `homing/devices/{device_id}/command` |
| State | `homing/devices/{device_id}/state` |
| Ack | `homing/devices/{device_id}/ack` |

```text
Agent plan
→ device validation/approval
→ MQTT command có command_id
→ device/simulator xử lý
→ state hoặc ack
→ Hub cập nhật state
→ frontend hiển thị kết quả
```

QoS mặc định là 1. Nếu không nhận ack đúng hạn, Hub trả timeout thay vì giả thành công.

Theo dõi event nếu máy có Mosquitto CLI:

```bash
mosquitto_sub -h localhost -p 1883 -t 'homing/#' -v
```

## 10. Quy trình demo MVP

```bash
bash scripts/download_voice_models.sh
bash scripts/docker.sh up full
bash scripts/docker.sh ps
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/api/v1/voice/status
curl -fsS http://localhost:8080/health
```

Demo:

1. Mở dashboard và MQTT event stream.
2. Bấm microphone, nói “Bật đèn phòng khách”.
3. Im lặng 2 giây.
4. Xác nhận UI tự nhận dạng và tự gửi transcript.
5. Xác nhận MQTT có command và ack.
6. Xác nhận device state đổi.
7. Xác nhận Piper đọc phản hồi.
8. Tắt TTS để kiểm tra text fallback.
9. Mô phỏng device offline/timeout để xác nhận UI không giả thành công.

## 11. Kiểm thử

Kiểm thử tự động core services:

```bash
pytest \
  tests/test_services/test_speech.py \
  tests/test_api/test_routes.py \
  tests/test_services/test_mqtt.py \
  tests/test_services/test_device_control.py \
  -q
```

Kiểm thử hồi quy toàn bộ hệ thống (offline, không cần live GPU/hardware):

```bash
pytest tests/ -v -m "not live_model and not hardware"
```
Kết quả: `463 passed, 1 skipped`.

Lint phần voice:

```bash
ruff check src/services/speech.py tests/test_services/test_speech.py
```

Frontend:

```bash
cd frontend
npm install
npm run build
npm run test:vad
cd ..
```

VAD tests xác nhận silence trước speech không trigger, 2 giây silence sau speech trigger đúng một lần, và speech mới reset timeout.

## 12. Tối ưu tài nguyên

Cho Raspberry Pi hoặc CPU ít core:

```env
ZIPFORMER_NUM_THREADS=2
```

Runtime serialize STT/TTS để tránh peak cùng lúc. Khi tài nguyên hạn chế:

1. Chạy `voice` trước.
2. Kiểm tra Zipformer/Piper ổn định.
3. Sau đó mới bật Qwen bằng `full`.
4. Theo dõi RAM, swap và nhiệt độ.

Để giảm latency cảm nhận: dùng câu lệnh ngắn, microphone gần người dùng, giữ silence timeout 2 giây và không gửi audio qua MQTT.

Frontend VAD dùng RMS. Noise liên tục trên threshold có thể khiến recorder chờ đến max duration. Ưu tiên giảm noise/chọn đúng microphone trước khi điều chỉnh threshold. Với môi trường production nhiều noise, có thể nâng cấp riêng sang streaming Silero VAD.

## 13. Troubleshooting

### Dashboard/API không lên

```bash
bash scripts/docker.sh ps
bash scripts/docker.sh logs frontend backend
lsof -i :5173 -i :8000
```

### Zipformer chưa sẵn sàng

```bash
bash scripts/download_voice_models.sh
bash scripts/docker.sh logs backend
```

Kiểm tra đủ bốn file model. Trong container, `ZIPFORMER_MODEL_DIR` phải là `/models/...`, không phải path host tương đối.

### Piper chưa sẵn sàng

```bash
bash scripts/docker.sh logs piper backend
```

Kiểm tra hai file Piper `.onnx` và `.onnx.json`. Backend gọi `http://piper:5000` trong Compose network.

### Voice không tự gửi sau 2 giây

1. Kiểm tra browser đã cấp microphone.
2. Dùng `localhost` hoặc HTTPS.
3. Xác nhận UI ở trạng thái recording.
4. Nói đủ lớn để vượt threshold.
5. Kiểm tra noise nền có giảm dưới threshold sau khi nói.
6. Bấm microphone lần hai để thử dừng thủ công.
7. Xem browser console và `bash scripts/docker.sh logs backend frontend`.

### `no_speech_detected`

Backend VAD không thấy speech. Nói gần microphone hơn, kiểm tra input gain/WAV và không gửi file toàn silence.

### Agent/LLM không sẵn sàng

```bash
ls -lh models/*.gguf
bash scripts/docker.sh logs llama backend
curl -fsS http://localhost:8080/health
```

Đảm bảo `LLAMA_MODEL_FILE` khớp tên file.

### MQTT không có command/ack

```bash
bash scripts/docker.sh logs mqtt device-simulator backend
mosquitto_sub -h localhost -p 1883 -t 'homing/#' -v
```

Kiểm tra topic prefix, simulator, device ID và broker auth/TLS.

### Port bị chiếm

```bash
lsof -i :5173 -i :8000 -i :8080 -i :1883 -i :9001
```

## 14. Checklist MVP

- [ ] `.env` bật đúng Zipformer, backend VAD và Piper.
- [ ] Zipformer/Piper models đủ file và checksum pass.
- [ ] Qwen GGUF nằm đúng trong `models/`.
- [ ] `bash scripts/docker.sh up full` chạy thành công.
- [ ] Backend, frontend, MQTT, simulator, Piper và llama running/healthy.
- [ ] Voice status báo Zipformer, VAD và Piper sẵn sàng.
- [ ] Browser có quyền microphone.
- [ ] Im lặng 2 giây tự dừng và tự gửi.
- [ ] Transcript tự chuyển cho Agent.
- [ ] Agent command đi qua MQTT và nhận ack.
- [ ] Dashboard cập nhật state.
- [ ] Piper hoặc text fallback hoạt động.
- [ ] Backend/frontend tests pass.
- [ ] MQTT không expose ra LAN ngoài ý muốn.

Khi checklist đạt, hệ thống sẵn sàng demo MVP local end-to-end.
