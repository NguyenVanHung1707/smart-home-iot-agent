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
- Ra lệnh ngôn ngữ tự nhiên tiếng Việt:
  - *"Bật đèn phòng khách và mở quạt phòng ngủ"*
  - *"Kiểm tra nhiệt độ nhà mình hiện tại bao nhiêu độ?"*
  - *"Phát bài Lạc Trôi của Sơn Tùng M-TP"*
  - *"Thời tiết ngày mai ở Hà Nội thế nào?"*
  - *"Thêm sữa vào danh sách mua sắm"*
- **Tool Categories**: Điều khiển thiết bị, cảm biến, lịch hẹn, phát nhạc, thời tiết, chất lượng không khí, phân tích năng lượng, ghi chú, danh sách mua sắm, kiểm tra an ninh, tối ưu giấc ngủ, tính toán & đổi đơn vị, tìm kiếm mạng xã hội.
- **MCP Server** hỗ trợ tool-calling theo chuẩn Model Context Protocol (dùng với Claude, Gemini API).
- **Guardrails** kiểm duyệt an toàn mọi phản hồi LLM trước khi gửi đến người dùng.

### 3.5. Loa thông minh AI Xiaozhi (Phát nhạc + Voice AI)
- **Phát nhạc**: Nói *"phát bài Lạc Trôi"* → Máy chủ tìm kiếm YouTube, convert sang WAV, stream qua HTTP → ESP32 phát ra Loa MAX98357A I2S.
- **Đồng bộ Web + ESP32**: Nút **🔥 Phát cả ESP32 & WEB** trên Web Dashboard phát nhạc đồng thời trên loa phần cứng và trình duyệt.
- **Cấu hình AI Settings**: Tùy chỉnh Persona, System Prompt, Giọng đọc (Edge-TTS), Mô hình AI và Wake Words trực tiếp trên giao diện Web.

---

## 4. Công nghệ sử dụng

| Tầng | Công nghệ / Thư viện |
| :--- | :--- |
| **Backend** | Python 3.11, FastAPI, Pydantic v2, Uvicorn, LangGraph, SQLAlchemy, Psycopg2 |
| **AI Engine** | LangGraph (Tool Calling), OpenAI-compatible API, Ollama (Qwen 2.5 7B GPU local) |
| **MCP & Safety** | MCP Server (Model Context Protocol), Guardrails service |
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
├── scripts/                        # Scripts hỗ trợ: benchmark HIL, serial monitor
│   ├── benchmark_ai.py             # Benchmark AI Agent end-to-end
│   ├── benchmark_mcp.py            # Benchmark MCP tool-calling
│   ├── run_full_hil_benchmark.py   # Chạy full Hardware-in-the-Loop test
│   └── check_serial.py             # Monitor Serial ESP32 qua COM port
├── src/                            # Mã nguồn Backend FastAPI
│   ├── agents/
│   │   ├── graph.py                # LangGraph AI Agent workflow
│   │   ├── harness.py              # Agent execution harness
│   │   ├── system_prompt.py        # System prompt builder
│   │   └── tools/                  # 30+ AI tools
│   │       ├── smart_device.py     # Điều khiển thiết bị thông minh
│   │       ├── media_player.py     # Phát nhạc YouTube → WAV → ESP32 I2S
│   │       ├── weather_forecast.py # Thời tiết thực tế
│   │       ├── air_quality_advisor.py  # Tư vấn chất lượng không khí
│   │       ├── energy_analytics.py    # Phân tích tiêu thụ điện
│   │       ├── home_notes.py          # Ghi chú trong nhà
│   │       ├── home_safety_audit.py   # Kiểm tra an toàn nhà
│   │       ├── shopping_list.py       # Quản lý danh sách mua sắm
│   │       ├── sleep_optimizer.py     # Tối ưu giấc ngủ
│   │       ├── smart_calc_converter.py # Tính toán & đổi đơn vị
│   │       ├── social_search.py       # Tìm kiếm mạng xã hội
│   │       └── ...                    # Và nhiều tools khác
│   ├── api/                        # REST API endpoints (auth, devices, rooms…)
│   ├── firmware/                   # Arduino C++ cho 3 bo mạch ESP32
│   │   ├── esp32_home_appliances_espnow/
│   │   ├── esp32_main_entrance_espnow/
│   │   └── esp32_xiaozhi_gateway/  # Gateway AI Voice (MQTT + I2S + ESP-NOW)
│   ├── services/
│   │   ├── ai_config.py            # Quản lý Persona, Giọng, Mô hình AI
│   │   ├── guardrails.py           # Kiểm duyệt an toàn LLM response
│   │   ├── mcp_server.py           # MCP Server (Model Context Protocol)
│   │   ├── mqtt.py                 # MQTT Bridge Backend ↔ ESP32
│   │   ├── speech.py               # TTS / STT service
│   │   ├── xiaozhi.py              # Xiaozhi Hub API client
│   │   └── natural_language_control.py  # Xử lý lệnh ngôn ngữ tự nhiên
│   └── main.py                     # Điểm khởi chạy FastAPI + WebSocket
├── tests/                          # Unit & integration tests
│   ├── test_guardrails.py
│   └── test_mcp_tools.py
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
