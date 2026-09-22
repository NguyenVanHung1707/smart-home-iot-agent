# Báo Cáo Triển Khai Kết Nối 2 ESP32 Với Homing Hub AI Agent Qua MQTT Protocol

**Ngày hoàn thành:** 11/08/2026  
**Dự án:** Homing Hub Smart Home (P-140)  
**Nhánh Git:** `feature/esp32-agent-integration`

---

## 1. Tóm Tắt Mục Tiêu và Kết Quả Triển Khai

Báo cáo này trình bày chi tiết việc chuyển đổi 2 bo mạch điều khiển phần cứng ESP32 ([`esp32_home_appliances.ino`](../src/firmware/esp32_home_appliances/esp32_home_appliances.ino) và [`esp32_main_entrance.ino`](../src/firmware/esp32_main_entrance/esp32_main_entrance.ino)) sang giao thức **Native MQTT Protocol Client**, kết nối trực tiếp với **Mosquitto MQTT Broker** và **Homing Hub AI Agent**.

### Kết quả đạt được:
- ✅ **Đã loại bỏ phụ thuộc Blynk Cloud:** Cả 2 ESP32 hiện tại chạy 100% **Local Off-grid** không cần kết nối Internet ra bên ngoài.
- ✅ **Chuẩn hóa MQTT Data Contract:** Hỗ trợ đầy đủ các kênh `command`, `state`, `ack` và `telemetry` theo kiến trúc dự án.
- ✅ **Mở rộng Hub Device Registry:** Bổ sung đầy đủ thông tin thiết bị (`kitchen-light`, `bedroom-fan`, `kitchen-fan`, `living-fan`, `kitchen-gas`, `window-servo`, `entry-lock`) vào backend Homing Hub ([`devices.py`](../src/services/devices.py)) và LangChain Agent Tools ([`smart_home_tools.py`](../src/agents/tools/smart_home_tools.py)).
- ✅ **Kiểm thử hệ thống thành công:** Toàn bộ 46/46 unit tests của backend và 3/3 VAD tests của frontend pass 100%.

---

## 2. Kiến Trúc Kết Nối Mạng Local (Local Network Topology)

```text
                                       ┌────────────────────────────────────────────────────────┐
                                       │                   Wi-Fi Router Local                   │
                                       └───────────────────────────┬────────────────────────────┘
                                                                   │
                         ┌─────────────────────────────────────────┼─────────────────────────────────────────┐
                         │ (IP: 192.168.1.100)                     │ (IP Wi-Fi DHCP)                         │ (IP Wi-Fi DHCP)
                         ▼                                         ▼                                         ▼
┌──────────────────────────────────────────────────┐  ┌───────────────────────────────┐  ┌───────────────────────────────┐
│              Máy Chủ Homing Hub Host             │  │       ESP32 Bo Mạch #1        │  │       ESP32 Bo Mạch #2        │
│ ┌──────────────────────────────────────────────┐ │  │   (Home Appliances System)    │  │   (Main Entrance Security)    │
│ │ Docker: Mosquitto MQTT Broker (Port 1883)    │ │  │                               │  │                               │
│ └──────────────────────┬───────────────────────┘ │  │ • DHT11, MQ2, PIR, OLED, LDR  │  │ • RFID RC522, Keypad 4x4, LCD │
│ ┌──────────────────────┴───────────────────────┐ │  │ • 3 Đèn LED, 3 Quạt DC        │  │ • Servo Cửa Chính (GPIO 4)    │
│ │ Docker: FastAPI Backend & AI Agent           │ │  │ • Servo Cửa Sổ Thông Gió      │  │ • Buzzer Báo Động (GPIO 15)   │
│ └──────────────────────────────────────────────┘ │  └───────────────────────────────┘  └───────────────────────────────┘
└──────────────────────────────────────────────────┘
```

---

## 3. Chi Tiết Giao Thức MQTT và Message Payload Format

### A. Giao thức Lệnh (Command) từ Agent -> ESP32
Khi người dùng ra lệnh bằng giọng nói hoặc giao diện web (ví dụ: *"Bật đèn phòng bếp"* hoặc *"Mở cửa chính"*), Agent đẩy JSON payload tới topic `homing/devices/{device_id}/command`:

```json
{
  "command_id": "cmd-8f3a1b2c",
  "action": "on",
  "device_id": "kitchen-light"
}
```

### B. Giao thức Phản hồi Xác nhận (Acknowledgment - ACK) từ ESP32 -> Hub
Ngay sau khi ESP32 thực thi bật/tắt GPIO tương ứng, ESP32 gửi tin nhắn ACK về topic `homing/devices/{device_id}/ack`:

```json
{
  "command_id": "cmd-8f3a1b2c",
  "status": "executed",
  "device_id": "kitchen-light"
}
```

### C. Giao thức Trạng thái (State Update) từ ESP32 -> Hub
ESP32 đồng thời cập nhật trạng thái mới nhất lên topic `homing/devices/{device_id}/state` với cờ `retain=true`:

```json
{
  "power": true
}
```

### D. Báo cáo Cảm biến Định kỳ (Telemetry)
- **Cảm biến Nhiệt độ & Độ ẩm (DHT11):**  
  `homing/devices/living-temperature/state` ➡️ `{"temperature": 28.2, "humidity": 62.0}`
- **Cảm biến Khí Gas (MQ2):**  
  `homing/devices/kitchen-gas/state` ➡️ `{"gas_level": 415, "alert": false}`

---

## 4. Các Thay Đổi Chi Tiết Trong Mã Nguồn

### 1. ESP32 #1 ([`src/firmware/esp32_home_appliances.ino`](../src/firmware/esp32_home_appliances/esp32_home_appliances.ino))
- Thêm thư viện `<PubSubClient.h>` và `<ArduinoJson.h>`.
- Khởi tạo `mqttClient.setServer(mqtt_server, 1883)` và `mqttClient.setCallback(mqttCallback)`.
- Hàm `mqttCallback()` tự động phân tích và điều khiển 3 Đèn LED (D15, D2, D4), 3 Quạt DC (D16, D17, D5) và Servo Cửa Sổ (D13).
- Hàm `sendTelemetry()` tự động gửi định kỳ dữ liệu DHT11 và MQ2 Gas lên Hub mỗi 3 giây.

### 2. ESP32 #2 ([`src/firmware/esp32_main_entrance.ino`](../src/firmware/esp32_main_entrance/esp32_main_entrance.ino))
- Thêm kết nối MQTT Client xử lý điều khiển khóa cửa từ xa (`entry-lock`).
- Khi nhận lệnh mở cửa từ Agent, hàm `unlockDoor("AGENT_REMOTE")` xoay Servo cửa 90°, hú còi bíp, giữ mở 5 giây rồi tự đóng lại.
- Tự động đẩy nhật ký quẹt thẻ RFID hoặc báo động nhập sai mật khẩu Keypad quá 3 lần lên topic `homing/security/access_log`.

### 3. Backend Hub Registry ([`src/services/devices.py`](../src/services/devices.py))
- Thêm khai báo 6 thiết bị mới vào danh sách `DeviceRegistry`:
  - `kitchen-light` (Đèn bếp)
  - `bedroom-fan`, `kitchen-fan`, `living-fan` (Các quạt phòng)
  - `kitchen-gas` (Cảm biến khí gas MQ2)
  - `window-servo` (Cửa sổ thông gió)

### 4. Agent Tools ([`src/agents/tools/smart_home_tools.py`](../src/agents/tools/smart_home_tools.py))
- Cập nhật `DeviceId` Literal type giúp Qwen LLM và LangGraph Agent nhận diện đúng tên thiết bị khi chuyển đổi ngôn ngữ tự nhiên thành công cụ điều khiển.

---

## 5. Kết Quả Kiểm Thử và Xác Nhận

### Kiểm thử Tự động (Automated Unit Tests)
```bash
pytest tests/test_services/test_speech.py tests/test_api/test_routes.py tests/test_services/test_mqtt.py tests/test_services/test_device_control.py -q
```
**Kết quả:** `46 passed in 4.65s` (100% tests PASSED).

Kiểm thử hồi quy toàn bộ hệ thống:
```bash
pytest tests/ -v -m "not live_model and not hardware"
```
**Kết quả:** `463 passed, 1 skipped` (100% core tests PASSED).

```bash
npm --prefix frontend run test:vad
```
**Kết quả:** `3 passed` (100% tests PASSED).

### Kiểm thử Dịch vụ Health Check
```json
// GET http://localhost:8000/health
{"status":"ok","env":"development"}

// GET http://localhost:8000/api/v1/voice/status
{"enabled":true,"ready":true,"stt":{"ready":true,"model":"sherpa-onnx-zipformer-vi-int8-2025-04-20","vad":true},"tts":{"ready":true,"voice":"vi_VN-vais1000-medium"}}

// GET http://localhost:8080/health
{"status":"ok"}
```

---

## 6. Hướng Dẫn Sử Dụng và Nạp Firmware Cho Người Dùng

1. **Chuẩn bị phần mềm Arduino IDE:**
   - Cài đặt 2 thư viện: **`PubSubClient`** (bởi Nick O'Leary) và **`ArduinoJson`** (bởi Benoit Blanchon v6.x).
2. **Cấu hình IP máy tính:**
   - Tìm dòng `const char* mqtt_server = "192.168.1.100";` trong cả 2 file `.ino`.
   - Đổi `192.168.1.100` thành IP máy tính của bạn (kiểm tra bằng lệnh `ipconfig` trên Windows).
3. **Nạp Firmware:**
   - Chọn Board: **ESP32 Dev Module**.
   - Nạp `esp32_home_appliances.ino` vào ESP32 #1.
   - Nạp `esp32_main_entrance.ino` vào ESP32 #2.
4. **Trải nghiệm với AI Agent:**
   - Mở React Dashboard (`frontend/`): `http://localhost/` (hoặc Virtual Home Simulator `frontend-simulator/` tại `http://localhost:8001/`).
   - Ra lệnh bằng giọng nói: *"Bật quạt phòng bếp và mở cửa chính"*.
   - AI Agent sẽ tự động gửi lệnh qua MQTT, ESP32 điều khiển thiết bị thực tế và phản hồi lại ngay lập tức!
