# Homing Smart Home Hub — AI Agent IoT System

Hệ thống nhà thông minh thế hệ mới kết hợp giữa **Trí tuệ nhân tạo (AI Agent)**, **Internet of Things (IoT)** và mạng điều khiển phần cứng không dây **ESP-NOW / MQTT**.

---

## 1. Giới thiệu tổng quan dự án

Homing Smart Home Hub là nền tảng quản trị và tự động hóa nhà thông minh toàn diện, cho phép người dùng giám sát môi trường, điều khiển các thiết bị điện trong gia đình, đảm bảo an ninh cửa ra vào và tương tác điều khiển bằng ngôn ngữ tự nhiên thông qua Giọng nói (Voice AI) hoặc Chatbot.

Hệ thống được thiết kế với kiến trúc **Serverless & Hybrid Cloud**:
- **Tầng Cloud / Server**: Backend FastAPI điều phối AI Agent, lưu trữ dữ liệu PostgreSQL và giao diện Web Dashboard React thời gian thực.
- **Tầng Giao tiếp IoT**: Kết nối hai chiều qua MQTT (hỗ trợ cả Local Mosquitto và Cloud HiveMQ WSS bảo mật SSL/TLS).
- **Tầng Thiết bị Biên (Hardware)**: 3 bo mạch vi điều khiển ESP32 giao tiếp với nhau bằng sóng vô tuyến tốc độ cao **ESP-NOW** (< 2ms, không phụ thuộc WiFi/Internet cục bộ).

---

## 2. Kiến trúc hệ thống tổng thể

```text
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                           NGƯỜI DÙNG & GIAO DIỆN                        │
 │  • Web Dashboard (React 18 + Vite + Three.js 2D/3D + Lucide Icons)      │
 │  • Loa thông minh AI Xiaozhi (Micro INMP441 & Loa MAX98357A)            │
 └───────────────────────────────────┬─────────────────────────────────────┘
                                     │ HTTPS / WSS / REST
                                     ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                       HOMING BACKEND & CLOUD RUNTIME                    │
 │  • FastAPI Core: Quản trị thiết bị, phòng ốc, preset ngữ cảnh, JWT auth │
 │  • AI Agent Engine: LangGraph + LLM Tool Calling (Qwen / OpenAI API)    │
 │  • Database: PostgreSQL (Lưu trữ tài khoản, lịch sử lệnh, phê duyệt)    │
 │  • MQTT Broker: Eclipse Mosquitto (Local LAN) & HiveMQ Cloud (WSS)      │
 └───────────────────────────────────┬─────────────────────────────────────┘
                                     │ MQTT (Port 1883 / 8883 / 8884)
                                     ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                       HẠ TẦNG PHẦN CỨNG 3 ESP32                         │
 │                                                                         │
 │   [ESP32 #3 - Gateway Master]                                           │
 │   ├── Nhận lệnh từ Cloud MQTT & Micro giọng nói                         │
 │   └── Phát sóng không dây ESP-NOW (2.4GHz nội bộ)                       │
 │            │                                  │                         │
 │            ▼ (ESP-NOW < 2ms)                  ▼ (ESP-NOW < 2ms)         │
 │   [ESP32 #1 - Thiết bị gia dụng]     [ESP32 #2 - Cửa an ninh chính]     │
 │   ├── 3 Đèn, 3 Quạt DC, Rèm Servo    ├── Khóa chốt Servo 90°            │
 │   ├── DHT11, MQ2 Khí gas, PIR, LDR   ├── Quẹt thẻ từ RFID RC522         │
 │   └── Màn hình OLED & Nút bấm cơ     ├── Bàn phím số Keypad 4x4 & LCD   │
 └─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Các tính năng cốt lõi

### 3.1. Điều khiển thiết bị & Quản lý phòng trực quan
- Giám sát trạng thái thiết bị thời gian thực theo từng phòng (Phòng khách, Phòng ngủ, Phòng bếp, Cửa chính).
- Điều khiển tức thì đèn, quạt, rèm cửa, khóa cửa với độ trễ phản hồi cực thấp.
- Cơ chế gom nhóm và điều khiển ngữ cảnh một chạm (Preset): "Đi ngủ", "Tiếp khách", "Ra khỏi nhà".

### 3.2. Giám sát an toàn môi trường & Báo động tự động
- **Cảm biến khí Gas / Khói MQ-2**: Tự động hú còi báo động và kích hoạt mở cửa sổ thông gió khi nồng độ gas vượt ngưỡng nguy hiểm.
- **Cảm biến nhiệt độ & độ ẩm DHT11**: Cập nhật biểu đồ nhiệt độ phòng khách liên tục.
- **Cảm biến chuyển động PIR**: Tự động bật đèn khi có người di chuyển.

### 3.3. Hệ thống kiểm soát an ninh đa tầng
- Mở khóa cửa chính bằng **Thẻ từ RFID** hoặc **Mật mã phím số Keypad 4x4**.
- Chốt bảo mật an toàn: Khóa cửa có thể mở từ xa qua Web hoặc Voice với cơ chế bảo vệ mã PIN hoặc phê duyệt của Chủ nhà.
- Tự động đóng chốt an toàn sau 5 giây mở cửa.

### 3.4. Trí tuệ nhân tạo (AI Agent Voice & Chat)
- Hỗ trợ ra lệnh bằng ngôn ngữ tự nhiên tiếng Việt:
  - *"Bật đèn phòng khách và mở quạt phòng ngủ"*
  - *"Kiểm tra nhiệt độ nhà mình hiện tại bao nhiêu độ?"*
  - *"Mở khóa cửa chính"* (Agent kích hoạt bước kiểm tra an ninh).
- Điều hướng và gọi công cụ (Tool-calling) chính xác, tự động phân tích ý định người dùng.

---

## 4. Công nghệ sử dụng

| Tầng | Công nghệ / Thư viện |
| :--- | :--- |
| **Backend** | Python 3.11, FastAPI, Pydantic v2, Uvicorn, LangGraph, SQLAlchemy, Psycopg2 |
| **Frontend** | React 18, TypeScript, Vite, Vanilla CSS, Lucide Icons, MQTT.js, Three.js |
| **Cơ sở dữ liệu** | PostgreSQL 16 Alpine |
| **Giao thức IoT** | MQTT (Mosquitto 2.0 / HiveMQ Cloud TLS/WSS), ESP-NOW (Espressif) |
| **Trợ lý giọng nói** | Xiaozhi ESP32 Voice Server (Self-hosted WebSocket Opus, Edge-TTS Tiếng Việt, Function Calling) |
| **Phần cứng** | 3 bo mạch vi điều khiển ESP32, cảm biến DHT11, MQ2, PIR, RFID-RC522, Keypad 4x4, Servo SG90, OLED SH1106, LCD 16x2 I2C, Micro I2S INMP441, Khuếch đại I2S MAX98357A |
| **Triển khai** | Docker, Docker Compose, Cloudflare Tunnel |

---

## 5. Cấu trúc mã nguồn

```text
smart-home-iot-agent/
├── data/                       # Dữ liệu cấu hình JSON (thiết bị, phòng, tài khoản)
├── frontend/                   # Mã nguồn ứng dụng Web Dashboard React + Vite
│   ├── src/                    # Components giao diện, hooks, API client
│   └── nginx.conf              # Cấu hình Web Server Nginx cho Frontend
├── infra/                      # Cấu hình Mosquitto MQTT & Xiaozhi AI Voice Server
│   ├── mosquitto.conf          # Cấu hình Mosquitto Broker
│   └── xiaozhi/                # Máy chủ Xiaozhi Server (config & plugins điều khiển IoT)
├── runtime/                    # Lưu trữ trạng thái hoạt động của thiết bị
├── scripts/                    # Các tiện ích cấu hình bảo mật MQTT & sao lưu DB
├── src/                        # Mã nguồn Backend FastAPI
│   ├── agents/                 # Logic xử lý AI Agent, Prompt và Tools
│   ├── api/                    # Các API endpoint REST (auth, devices, rooms, approvals)
│   ├── firmware/               # Mã nguồn Arduino C++ cho 3 bo mạch ESP32
│   │   ├── esp32_home_appliances_espnow/
│   │   ├── esp32_main_entrance_espnow/
│   │   └── esp32_xiaozhi_gateway/
│   ├── services/               # Dịch vụ MQTT, Device Registry, Users, Speech
│   └── main.py                 # Điểm khởi chạy ứng dụng FastAPI
├── docker-compose.yml          # File khởi chạy toàn bộ dịch vụ với Docker
├── Dockerfile                  # Docker image cho Backend
├── Makefile                    # Lệnh thao tác nhanh (build, format, lint)
├── requirements.txt            # Danh sách thư viện Python
├── PINOUT_CONFIG.md            # Tài liệu cấu hình chân đấu nối chi tiết ESP32
└── SETUP_GUIDE.md              # Hướng dẫn chi tiết triển khai cho người mới từ A-Z
```
