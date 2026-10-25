# Homing Smart Home Hub — AI Agent IoT System

Hệ thống nhà thông minh thế hệ mới kết hợp giữa **Trí tuệ nhân tạo (AI Agent)**, **Internet of Things (IoT)** và mạng điều khiển phần cứng không dây **ESP-NOW / MQTT**.

---

## 1. Giới thiệu tổng quan dự án

Homing Smart Home Hub là nền tảng quản trị và tự động hóa nhà thông minh toàn diện, cho phép người dùng giám sát môi trường, điều khiển các thiết bị điện trong gia đình, đảm bảo an ninh cửa ra vào và tương tác điều khiển bằng ngôn ngữ tự nhiên thông qua Giọng nói (Voice AI) hoặc Chatbot.

Hệ thống được thiết kế với kiến trúc **Serverless & Hybrid Cloud**:
- **Tầng Cloud / Server**: Backend FastAPI điều phối AI Agent (LangGraph + Tool Calling), lưu trữ dữ liệu PostgreSQL và giao diện Web Dashboard React thời gian thực.
- **Tầng Giao tiếp IoT**: Kết nối hai chiều qua MQTT (hỗ trợ cả Local Mosquitto và Cloud HiveMQ WSS bảo mật SSL/TLS).
- **Tầng Thiết bị Biên (Hardware)**: 3 bo mạch vi điều khiển ESP32 giao tiếp với nhau bằng sóng vô tuyến tốc độ cao **ESP-NOW** (< 2ms, không phụ thuộc WiFi/Internet cục bộ).
- **Tầng AI Giọng Nói Phần Cứng**: Loa thông minh Xiaozhi tự host — ESP32 #3 + Micro INMP441 + Loa MAX98357A I2S, phát nhạc và trả lời tiếng Việt hoàn toàn cục bộ.

---

## 2. Kiến trúc hệ thống tổng thể

```text
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                         NGƯỜI DÙNG & GIAO DIỆN                          │
 │  • Web Dashboard (React 18 + Vite + TypeScript + Vanilla CSS)            │
 │    - FloatingMediaPlayer: Phát nhạc đồng thời ESP32 & Web               │
 │    - AI Settings: Chọn persona, giọng, mô hình, wake words              │
 │    - AI Conversations: Lịch sử hội thoại toàn bộ phiên                  │
 │  • Loa thông minh AI Xiaozhi (Micro INMP441 & Loa I2S MAX98357A)         │
 └─────────────────────────────────┬───────────────────────────────────────┘
                                   │ HTTPS / WSS / REST / MQTT
                                   ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                      HOMING BACKEND & CLOUD RUNTIME                      │
 │  • FastAPI Core: Quản trị thiết bị, phòng ốc, preset ngữ cảnh, JWT auth │
 │  • AI Agent Engine: LangGraph + LLM Tool Calling (Qwen / OpenAI API)    │
 │    - 30+ Tools: điều khiển thiết bị, cảm biến, lịch, nhạc, thời tiết…  │
 │  • MCP Server: Tool-calling chuẩn Model Context Protocol                │
 │  • Guardrails: Lớp kiểm duyệt an toàn cho LLM response                 │
 │  • AI Config Service: Quản lý Persona, Giọng nói, Mô hình AI            │
 │  • Database: PostgreSQL 16 (Lưu trữ tài khoản, lịch sử, phê duyệt)     │
 │  • MQTT Broker: Eclipse Mosquitto (Local LAN) & HiveMQ Cloud (WSS)      │
 │  • Xiaozhi Voice Hub: WebSocket + FunASR + Edge-TTS + Smart Home Plugin │
 └─────────────────────────────────┬───────────────────────────────────────┘
                                   │ MQTT (Port 1883 / 8883 / 8884)
                                   │ ESP-NOW Radio (2.4GHz, < 2ms)
                                   ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                      HẠ TẦNG PHẦN CỨNG 3 ESP32                          │
 │  [ESP32 #3 - Gateway Master / Xiaozhi AI Voice]                          │
 │  ├── WiFi → MQTT Mosquitto + WebSocket Xiaozhi Hub                       │
 │  ├── I2S Mic INMP441: Thu âm → ASR (FunASR SenseVoice)                  │
 │  ├── I2S Loa MAX98357A: Phát TTS + Nhạc trực tiếp từ URL WAV            │
 │  ├── OLED 1.3" SH1106: Hiển thị biểu cảm + văn bản AI                  │
 │  └── ESP-NOW Radio: Phát sóng lệnh tới #1 và #2                         │
 │           │                                  │                           │
 │           ▼ (ESP-NOW < 2ms)                  ▼ (ESP-NOW < 2ms)          │
 │  [ESP32 #1 - Thiết bị gia dụng]   [ESP32 #2 - Cửa an ninh chính]        │
 │  ├── 3 Đèn LED, 3 Quạt DC          ├── Khóa chốt Servo 90°              │
 │  ├── Servo Rèm cửa sổ              ├── Quẹt thẻ từ RFID RC522           │
 │  ├── DHT11, MQ2, PIR, LDR          ├── Bàn phím số Keypad 4x4           │
 │  └── OLED 1.3" + Nút bấm           └── Màn hình LCD 16x2 I2C            │
 └─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Các tính năng cốt lõi

### 3.1. Điều khiển thiết bị & Quản lý phòng trực quan
- Giám sát trạng thái thiết bị thời gian thực theo từng phòng (Phòng khách, Phòng ngủ, Phòng bếp, Cửa chính).
- Điều khiển tức thì đèn, quạt, rèm cửa, khóa cửa với độ trễ phản hồi cực thấp qua MQTT + ESP-NOW.
- Cơ chế gom nhóm và điều khiển ngữ cảnh một chạm (Preset): *"Đi ngủ"*, *"Tiếp khách"*, *"Ra khỏi nhà"*.

### 3.2. Giám sát an toàn môi trường & Báo động tự động
- **Cảm biến khí Gas / Khói MQ-2**: Tự động hú còi báo động và kích hoạt mở cửa sổ thông gió khi nồng độ gas vượt ngưỡng nguy hiểm.
- **Cảm biến nhiệt độ & độ ẩm DHT11**: Cập nhật biểu đồ nhiệt độ liên tục trên Web Dashboard.
- **Cảm biến chuyển động PIR**: Tự động bật đèn khi phát hiện người di chuyển.

### 3.3. Hệ thống kiểm soát an ninh đa tầng
- Mở khóa cửa chính bằng **Thẻ từ RFID** hoặc **Mật mã phím số Keypad 4x4**.
- Chốt bảo mật: Khóa mở từ xa qua Web hoặc Voice với cơ chế bảo vệ mã PIN và phê duyệt Chủ nhà.
- Tự động đóng chốt an toàn sau 5 giây mở cửa.

### 3.4. Trí tuệ nhân tạo (AI Agent 30+ Tools)
- Ra lệnh ngôn ngữ tự nhiên tiếng Việt mượt mà:
  - *"Bật đèn phòng khách và mở quạt phòng ngủ"*
  - *"Kiểm tra nhiệt độ và nồng độ khí gas nhà mình hiện tại bao nhiêu?"*
  - *"Phát bài Lạc Trôi của Sơn Tùng M-TP"*
  - *"Dự báo thời tiết 3 ngày tới ở Hà Nội thế nào?"*
  - *"Tính tiền điện tháng này hết bao nhiêu nếu dùng 280 kWh?"*
  - *"Thêm sữa tươi và cà phê vào danh sách mua sắm"*
- **11 Phân hệ công cụ (Tool Categories)**:
  1. **Điều khiển thiết bị**: `control_light`, `control_aircon`, `control_blind`, `control_speaker`, `control_display`, `control_lock`, `control_smart_device`, `batch_control_devices`
  2. **Ngữ cảnh & Lịch hẹn**: `activate_scene`, `get_schedules`, `set_device_timer`, `list_device_timers`, `cancel_device_timer`
  3. **Âm nhạc & Đa phương tiện**: `play_youtube_music` (Tìm kiếm YouTube, trích xuất audio stream, phát qua FloatingMediaPlayer Web và ESP32 I2S MAX98357A)
  4. **Thông tin & Cảm biến**: `get_room_devices`, `get_sensor_data`, `get_security_report`
  5. **Tra cứu mở rộng**: `search_internet` (Tavily AI Search), `search_social_media` (Twitter / X Trends), `search_home_guides`
  6. **Thời tiết & Môi trường**: `get_weather_forecast` (Dự báo Open-Meteo), `evaluate_air_quality` (Đánh giá chỉ số AQI)
  7. **Năng lượng & Tiện ích**: `get_energy_analytics` (Phân tích kWh tiêu thụ), `smart_unit_and_cost_calculator` (Tính tiền điện EVN 6 bậc có VAT, tư vấn công suất BTU máy lạnh theo diện tích m2, quy đổi nhiệt độ C/F)
  8. **An toàn & An ninh**: `audit_home_safety` (Chẩn đoán rò rỉ gas, an ninh cửa, rơ-le), `request_unlock_approval` (Phê duyệt mở khóa bảo mật)
  9. **Chăm sóc gia đình & Giấc ngủ**: `manage_shopping_list` (Danh sách mua sắm nhu yếu phẩm), `optimize_sleep_environment` (Chế độ ngủ ngon)
  10. **Ghi chú gia đình**: `add_family_note`, `get_family_notes`, `delete_family_note`
  11. **Sở thích người dùng**: `save_user_preference`, `get_user_preferences`

### 3.5. Hệ thống Rào chắn An toàn 3 Lớp (3-Layer Guardrails System)
Hệ thống tích hợp lớp phòng thủ an ninh toàn diện tại `src/services/guardrails.py`:
- **Layer 1: Input Security Guardrail**:
  - Chống Prompt Injection & Jailbreak (ngăn chặn các kỹ thuật DAN, Developer Mode, Roleplay bằng cả tiếng Anh và tiếng Việt).
  - Ngăn chặn trích xuất bí mật hệ thống (Secret Exfiltration: mật khẩu wifi, API key, file `.env`, chuỗi kết nối database).
  - Phát hiện và ngăn chặn đe dọa vật lý (chập điện, cháy nổ gas, nhốt người).
  - Lọc bỏ ngôn từ thô tục, xúc phạm và độc hại (Profanity/Toxicity Filter).
- **Layer 2: Device Safety Guardrail**:
  - Chống bật/tắt dồn dập rơ-le (Anti-Flapping Relay Shield): Khóa rơ-le 10 giây nếu phát hiện bật/tắt quá 3 lần liên tục trong 5 giây, bảo vệ tiếp điểm phần cứng.
  - Chính sách khóa cửa nghiêm ngặt (Strict Door Security): Từ chối hoàn toàn lệnh mở khóa qua giọng nói/AI thông thường; bắt buộc mở bằng mã PIN hoặc thẻ từ RFID.
  - Giới hạn tham số hợp lệ (Parameter Bounds): Nhiệt độ điều hòa giới hạn từ 16°C – 30°C.
- **Layer 3: Output Privacy Guardrail (DLP)**:
  - Tự động nhận diện và che giấu (redaction) dữ liệu nhạy cảm trước khi phản hồi người dùng: `[REDACTED_JWT_TOKEN]`, `[REDACTED_API_KEY]`, `[REDACTED_DATABASE_URL]`.

### 3.6. Chuẩn Giao Tiếp MCP Server (Model Context Protocol)
- Tương thích chính thức chuẩn JSON-RPC 2.0 MCP (version `2024-11-05`), cho phép các AI client bên ngoài (Claude Desktop, Cursor, Gemini CLI) kết nối trực tiếp qua endpoint `/api/mcp` để điều khiển nhà thông minh.
- Hỗ trợ đầy đủ 13 công cụ: điều khiển thiết bị, đọc trạng thái/cảm biến, phát nhạc, tra cứu thời tiết, tìm kiếm Internet, phân tích an toàn, tính tiền điện EVN.

### 3.7. Loa thông minh AI Xiaozhi (Phát nhạc + Voice AI)
- **Phát nhạc**: Nói *"phát bài Lạc Trôi"* → Máy chủ tìm kiếm YouTube, trích xuất luồng audio stream WAV, stream qua HTTP → ESP32 phát trực tiếp ra Loa MAX98357A I2S.
- **Đồng bộ Web + ESP32**: Nút **🔥 Phát cả ESP32 & WEB** trên FloatingMediaPlayer phát nhạc đồng thời trên loa phần cứng và trình duyệt với độ trễ thấp.
- **Cấu hình AI Settings**: Tùy chỉnh Persona (Quản gia Jarvis, Cô Tấm, HomeMind, Sentinel), System Prompt, Giọng đọc (Edge-TTS Hoài My / Nam Minh), Mô hình AI (DeepSeek, GPT-4o-mini, Ollama Qwen) và Wake Words trực tiếp trên giao diện Web.

---

## 4. Công nghệ sử dụng

| Tầng | Công nghệ / Thư viện |
| :--- | :--- |
| **Backend** | Python 3.11, FastAPI, Pydantic v2, Uvicorn, LangGraph, SQLAlchemy, Psycopg2 |
| **AI Engine** | LangGraph (Tool Calling), OpenAI-compatible API, Ollama (Qwen 2.5 7B GPU local) |
| **MCP & Safety** | MCP Server (JSON-RPC 2.0), 3-Layer Guardrails System |
| **Frontend** | React 18, TypeScript, Vite, Vanilla CSS, MQTT.js (WebSocket), Lucide Icons |
| **Cơ sở dữ liệu** | PostgreSQL 16 Alpine |
| **Giao thức IoT** | MQTT (Mosquitto 2.0 / HiveMQ Cloud TLS/WSS), ESP-NOW (Espressif) |
| **Voice AI** | Xiaozhi ESP32 Server (Self-hosted) — FunASR SenseVoice ASR, Edge-TTS Tiếng Việt, Tool Calling |
| **Phần cứng** | 3 × ESP32 WROOM-32, DHT11, MQ2, PIR, RFID-RC522, Keypad 4×4, Servo SG90, OLED SH1106 1.3", LCD 16×2, INMP441 I2S Mic, MAX98357A I2S Amp |
| **Triển khai** | Docker Compose, Cloudflare Tunnel (HTTPS domain tự host), Nginx |

---

## 5. Cấu trúc mã nguồn

```text
smart-home-iot-agent/
├── data/                           # Dữ liệu JSON (thiết bị, phòng, tài khoản)
├── frontend/                       # Web Dashboard React + Vite + TypeScript
│   ├── src/
│   │   ├── components/
│   │   │   ├── layout/             # App.tsx, Sidebar, TopGreeting, PageShell
│   │   │   ├── rooms/              # HomeDashboard, RoomsPage, DeviceCard
│   │   │   ├── shared/
│   │   │   │   └── FloatingMediaPlayer.tsx  # Phát nhạc đồng thời ESP32 & Web
│   │   │   ├── history/
│   │   │   │   └── AIConversationsPage.tsx  # Lịch sử hội thoại AI
│   │   │   ├── settings/
│   │   │   │   └── AISettingsPage.tsx       # Cấu hình Persona, Giọng, Mô hình
│   │   │   ├── voice/              # VoiceOverlay, VoiceComposer, VoiceTranscript
│   │   │   └── mqtt/               # MqttPage (debug MQTT real-time)
│   │   ├── styles/
│   │   │   ├── home-dashboard.css  # Bao gồm FloatingMediaPlayer glassmorphic UI
│   │   │   ├── ai-conversations.css
│   │   │   └── ai-settings.css
│   │   └── api/cloudMqtt.ts        # MQTT client (Mosquitto local + HiveMQ Cloud WSS)
│   └── nginx.conf                  # Nginx + proxy /xiaozhi/audio/ → Xiaozhi Server
├── infra/
│   ├── mosquitto.conf              # Cấu hình MQTT Broker
│   └── xiaozhi/                    # Xiaozhi AI Voice Server tùy chỉnh
│       ├── data/                   # TTS cache WAV, cấu hình .config.yaml
│       ├── plugins/
│       │   └── smart_home.py       # Plugin điều khiển 14 thiết bị qua API & MQTT
│       ├── fun_local.py            # ASR FunASR SenseVoice cục bộ
│       └── http_server.py          # HTTP endpoint bổ sung (OTA, audio stream)
├── runtime/                        # Trạng thái hoạt động thiết bị thực tế
├── scripts/                        # Scripts hỗ trợ: benchmark, kiểm tra phần cứng, backup
│   ├── backup_db.py                # Sao lưu và phục hồi cơ sở dữ liệu PostgreSQL
│   ├── benchmark_ai.py             # Benchmark AI Agent end-to-end
│   ├── benchmark_mcp.py            # Benchmark MCP tool-calling
│   ├── check_serial.py             # Monitor Serial ESP32 qua COM port
│   ├── reboot_esp32.py             # Điều khiển reset cứng ESP32 qua DTR/RTS
│   ├── run_full_hil_benchmark.py   # Bộ kiểm thử phần cứng HIL (Hardware-in-the-Loop)
│   └── setup_mqtt_auth.py          # Thiết lập xác thực và phân quyền ACL Mosquitto
├── src/                            # Mã nguồn Backend FastAPI
│   ├── agents/
│   │   ├── graph.py                # LangGraph AI Agent workflow
│   │   ├── harness.py              # Agent execution harness
│   │   ├── system_prompt.py        # System prompt builder
│   │   └── tools/                  # 30+ AI tools (điều khiển, cảm biến, thời tiết, nhạc...)
│   │       ├── air_quality_advisor.py  # Tư vấn chất lượng không khí
│   │       ├── energy_analytics.py     # Phân tích tiêu thụ điện
│   │       ├── home_notes.py           # Ghi chú gia đình
│   │       ├── home_safety_audit.py    # Kiểm tra an toàn nhà
│   │       ├── media_player.py         # Phát nhạc YouTube → WAV → ESP32 I2S
│   │       ├── shopping_list.py        # Quản lý danh sách mua sắm
│   │       ├── sleep_optimizer.py      # Tối ưu giấc ngủ
│   │       ├── smart_calc_converter.py # Tính tiền điện EVN & đổi đơn vị
│   │       ├── smart_device.py         # Điều khiển thiết bị thông minh
│   │       ├── social_search.py        # Tìm kiếm mạng xã hội Twitter/X
│   │       ├── weather_forecast.py     # Thời tiết thực tế
│   │       └── ...                     # Và nhiều tools khác
│   ├── api/                        # REST API endpoints (auth, devices, rooms, mcp…)
│   ├── firmware/                   # Arduino C++ cho 3 bo mạch ESP32
│   │   ├── esp32_home_appliances_espnow/
│   │   ├── esp32_main_entrance_espnow/
│   │   └── esp32_xiaozhi_gateway/  # Gateway AI Voice (MQTT + I2S + ESP-NOW)
│   ├── services/
│   │   ├── ai_config.py            # Quản lý Persona, Giọng, Mô hình AI
│   │   ├── guardrails.py           # Kiểm duyệt an toàn LLM response (3-Layer)
│   │   ├── mcp_server.py           # MCP Server JSON-RPC 2.0 (Model Context Protocol)
│   │   ├── mqtt.py                 # MQTT Bridge Backend ↔ ESP32
│   │   ├── speech.py               # TTS (Edge-TTS/gTTS) / STT service
│   │   ├── xiaozhi.py              # Xiaozhi Hub API client
│   │   └── natural_language_control.py  # Xử lý lệnh ngôn ngữ tự nhiên
│   └── main.py                     # Điểm khởi chạy FastAPI + WebSocket
├── tests/                          # Unit & integration tests
│   ├── test_guardrails.py          # Kiểm thử 3 tầng rào chắn an toàn bảo mật
│   └── test_mcp_tools.py           # Kiểm thử giao thức MCP JSON-RPC 2.0 & tools
├── docker-compose.yml              # Khởi chạy đầy đủ (backend, frontend, mqtt, postgres, ollama, xiaozhi)
├── Dockerfile                      # Docker image Backend
├── Makefile                        # Lệnh thao tác nhanh
├── requirements.txt                # Thư viện Python
├── PINOUT_CONFIG.md                # Sơ đồ chân đấu nối chi tiết 3 ESP32
└── SETUP_GUIDE.md                  # Hướng dẫn triển khai từ A-Z
```

---

## 6. Hướng dẫn cài đặt nhanh

```bash
# 1. Clone dự án
git clone https://github.com/NguyenVanHung1707/smart-home-iot-agent.git
cd smart-home-iot-agent

# 2. Cấu hình biến môi trường
cp .env.example .env
# Chỉnh sửa .env: OPENAI_API_KEY, CLOUDFLARE_TUNNEL_TOKEN, ...

# 3. Khởi chạy toàn bộ dịch vụ
docker compose up -d --build

# 4. Truy cập giao diện
# Web Dashboard:  http://localhost
# API Docs:       http://localhost:8000/docs
# MQTT Monitor:   Vào trang "Cài đặt MQTT" trên Dashboard
```

Xem hướng dẫn chi tiết tại **[SETUP_GUIDE.md](./SETUP_GUIDE.md)** và sơ đồ phần cứng tại **[PINOUT_CONFIG.md](./PINOUT_CONFIG.md)**.

---

## 7. Thông tin liên hệ & Triển khai thực tế

- **Demo domain**: [https://lophocso.io.vn](https://lophocso.io.vn) *(Cloudflare Tunnel)*
- **MAC địa chỉ Gateway ESP32 #3**: `94:54:C5:A9:91:E8`
- **IP LAN**: `192.168.1.101` (ESP32 Gateway), `192.168.1.105` (Host Server)
