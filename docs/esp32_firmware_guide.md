# Hướng Dẫn & Phân Tích Hệ Thống Firmware 2 ESP32 (Cloud WSS MQTT Client)

Tài liệu này tổng hợp cấu trúc mã nguồn, sơ đồ chân (Pinout), nguyên lý hoạt động và giao thức **Cloud MQTT over WebSocket Secure (WSS)** kết nối trực tiếp từ xa qua Internet với Cloud Broker `wss://mqtt.blask.id.vn:443/mqtt` cho hệ thống **Smart Home 2 ESP32**.

---

## Tổng Quan Kiến Trúc 2 ESP32 và Cloud MQTT Broker

Hệ thống được chia thành 2 bo mạch điều khiển độc lập, kết nối trực tiếp lên Cloud Broker ngoài Internet qua cổng WSS 443 (được bảo vệ bởi SSL/TLS và Cloudflare CDN):

```text
                  ┌──────────────────────────────────────────────┐
                  │    Cloud MQTT Broker (Internet WSS 443)      │
                  │        wss://mqtt.blask.id.vn:443/mqtt       │
                  └──────────────────────┬───────────────────────┘
                                         │
                    ┌────────────────────┴─────────────────────┐
                    ▼                                          ▼
    ┌───────────────────────────────┐          ┌───────────────────────────────┐
    │       ESP32 Bo Mạch #1        │          │       ESP32 Bo Mạch #2        │
    │ (Home Appliances & Environment)│         │        (Main Entrance)        │
    │src/firmware/esp32_home_appliances.ino│   │src/firmware/esp32_main_entrance.ino│
    └───────────────┬───────────────┘          └───────────────┬───────────────┘
                    │                                          │
  ┌─────────────────┴─────────────────┐      ┌─────────────────┴─────────────────┐
  │ • DHT11 (Nhiệt độ & Độ ẩm)        │      │ • RFID RC522 (Quẹt thẻ an ninh)   │
  │ • MQ2 (Khí Gas & Khói)           │      │ • Keypad 4x4 (Mật khẩu mã số)     │
  │ • PIR HC-SR501 (Chuyển động)     │      │ • LCD I2C 16x2 (Màn hình trạng thái)│
  │ • OLED SH1106 I2C (Màn hình 0.96")│      │ • Servo SG90 (Đóng/Mở cửa chính)  │
  │ • 3 Đèn LED (Phòng ngủ/bếp/khách) │      │ • Buzzer Chíp (Báo đúng/sai)      │
  │ • 3 Quạt DC (Phòng ngủ/bếp/khách) │      └───────────────────────────────────┘
  │ • Servo SG90 (Cửa sổ thông gió)  │
  │ • Còi Báo Động Gas + 7 Nút Cơ   │
  └───────────────────────────────────┘
```

---

## 1. ESP32 Bo Mạch #1: Thiết Bị Trong Nhà (`esp32_home_appliances.ino`)

Mã nguồn lưu tại: [`src/firmware/esp32_home_appliances/esp32_home_appliances.ino`](../src/firmware/esp32_home_appliances/esp32_home_appliances.ino)

### A. Bảng Chân Phần Cứng (Pinout Mapping)
| Linh kiện / Thiết bị | Chân ESP32 (GPIO) | Chức năng |
| :--- | :--- | :--- |
| **DHT11** | GPIO 14 | Đo Nhiệt độ & Độ ẩm phòng |
| **MQ2** | GPIO 34 (Analog) | Đo nồng độ Khí Gas / Khói |
| **PIR HC-SR501** | GPIO 35 | Cảm biến chuyển động tự động |
| **OLED SH1106** | SDA / SCL (I2C) | Hiển thị thông số môi trường |
| **Buzzer** | GPIO 12 | Phát âm thanh cảnh báo sự cố Gas |
| **Servo Cửa Sổ** | GPIO 13 | Đóng (0°) / Mở (90°) cửa sổ thông gió |
| **Đèn LED Phòng Ngủ** | GPIO 15 | Bật / Tắt Đèn Phòng Ngủ (`bedroom-light`) |
| **Đèn LED Phòng Bếp** | GPIO 2 | Bật / Tắt Đèn Phòng Bếp (`kitchen-light`) |
| **Đèn LED Phòng Khách**| GPIO 4 | Bật / Tắt Đèn Phòng Khách (`living-light`) |
| **Quạt DC Phòng Ngủ** | GPIO 16 | Bật / Tắt Quạt Phòng Ngủ (`bedroom-fan`) |
| **Quạt DC Phòng Bếp** | GPIO 17 | Bật / Tắt Quạt Phòng Bếp (`kitchen-fan`) |
| **Quạt DC Phòng Khách**| GPIO 5 | Bật / Tắt Quạt Phòng Khách (`living-fan`) |
| **7 Nút bấm cơ** | GPIO 18, 19, 27, 32, 23, 25, 26 | Nút bấm thủ công trực tiếp tại chỗ |

### B. Giao Thức MQTT Contract
- **Subscribe Command:** `homing/devices/+/command`
- **Publish Telemetry:** Định kỳ 3 giây gửi dữ liệu môi trường:
  - `homing/devices/living-temperature/state` ➡️ `{"temperature": 27.5, "humidity": 65}`
  - `homing/devices/kitchen-gas/state` ➡️ `{"gas_level": 420, "alert": false}`
- **Publish State & Ack:** Khi điều khiển thiết bị:
  - `homing/devices/{living-light|bedroom-light|kitchen-light|living-fan|bedroom-fan|kitchen-fan|window-servo}/state`
  - `homing/devices/{device_id}/ack` ➡️ `{"command_id": "...", "status": "executed"}`

---

## 2. ESP32 Bo Mạch #2: Cổng Chính và Khóa Cửa Smart (`esp32_main_entrance.ino`)

Mã nguồn lưu tại: [`src/firmware/esp32_main_entrance/esp32_main_entrance.ino`](../src/firmware/esp32_main_entrance/esp32_main_entrance.ino)

### A. Bảng Chân Phần Cứng (Pinout Mapping)
| Linh kiện / Module | Chân ESP32 (GPIO) | Chức năng / Chuẩn giao tiếp |
| :--- | :--- | :--- |
| **Servo Cửa Chính** | GPIO 4 | Mở khóa (90°) / Đóng khóa (0°) (`entry-lock`) |
| **Buzzer Báo Hiệu** | GPIO 15 | Bíp xác nhận / Cảnh báo nhập sai |
| **RFID RC522 SS (SDA)** | GPIO 5 | Chọn chip RFID (SPI CS) |
| **RFID RC522 RST** | GPIO 2 | Reset Module RFID |
| **RFID RC522 SCK** | GPIO 18 | Xung Clock SPI |
| **RFID RC522 MISO** | GPIO 19 | Dữ liệu SPI Master In |
| **RFID RC522 MOSI** | GPIO 23 | Dữ liệu SPI Master Out |
| **LCD I2C (16x2)** | GPIO 21 (SDA), GPIO 22 (SCL) | Hiển thị lời chào & Trạng thái |
| **Keypad 4x4 Hàng (Rows)** | GPIO 13, 12, 14, 27 | Quét hàng bàn phím |
| **Keypad 4x4 Cột (Cols)** | GPIO 26, 25, 33, 32 | Quét cột bàn phím |

### B. Giao Thức MQTT Contract
- **Subscribe Command:** `homing/devices/entry-lock/command`
  - Lệnh mở cửa từ xa từ Agent: `{"command_id": "...", "action": "unlock"}`
- **Publish State:** `homing/devices/entry-lock/state` ➡️ `{"locked": false}` / `{"locked": true}`
- **Publish Ack:** `homing/devices/entry-lock/ack` ➡️ `{"command_id": "...", "status": "executed"}`
- **Security Access Log:** `homing/security/access_log` ➡️ `{"method": "KEYPAD_PASSWORD", "success": true}`

---

## 3. Bảng Tổng Hợp MQTT Topics và Homing Hub Registry

| Device ID | ESP32 Phụ Trách | Loại Thiết Bị | Topic Command | Topic State |
| :--- | :--- | :--- | :--- | :--- |
| `living-light` | ESP32 #1 | Light | `homing/devices/living-light/command` | `homing/devices/living-light/state` |
| `bedroom-light` | ESP32 #1 | Light | `homing/devices/bedroom-light/command` | `homing/devices/bedroom-light/state` |
| `kitchen-light` | ESP32 #1 | Light | `homing/devices/kitchen-light/command` | `homing/devices/kitchen-light/state` |
| `living-fan` | ESP32 #1 | Aircon/Fan | `homing/devices/living-fan/command` | `homing/devices/living-fan/state` |
| `bedroom-fan` | ESP32 #1 | Aircon/Fan | `homing/devices/bedroom-fan/command` | `homing/devices/bedroom-fan/state` |
| `kitchen-fan` | ESP32 #1 | Aircon/Fan | `homing/devices/kitchen-fan/command` | `homing/devices/kitchen-fan/state` |
| `window-servo` | ESP32 #1 | Blind/Window| `homing/devices/window-servo/command` | `homing/devices/window-servo/state` |
| `living-temperature` | ESP32 #1 | Sensor | N/A | `homing/devices/living-temperature/state` |
| `kitchen-gas` | ESP32 #1 | Sensor | N/A | `homing/devices/kitchen-gas/state` |
| `entry-lock` | ESP32 #2 | Lock | `homing/devices/entry-lock/command` | `homing/devices/entry-lock/state` |

---

## 4. Hướng Dẫn Nạp Code Bằng Arduino IDE

1. **Cài đặt thư viện bắt buộc trong Arduino IDE Library Manager:**
   - `ArduinoWebsockets` (bởi Gil Maimon)
   - `PubSubClient` (bởi Nick O'Leary)
   - `ArduinoJson` (bởi Benoit Blanchon)
   - `U8g2`
   - `MFRC522`
   - `Keypad`
   - `ESP32Servo`
   - `Adafruit DHT Unified`
2. **Cấu hình địa chỉ Cloud WSS:**
   - Mở từng file `.ino`, kiểm tra biến:
     ```cpp
     const char* wss_host = "mqtt.blask.id.vn";
     const int wss_port = 443;
     const char* wss_path = "/mqtt";
     ```
3. **Biên dịch & Nạp code:**
   - Chọn Board: **ESP32 Dev Module**
   - Chọn đúng cổng COM Port của từng con ESP32 và bấm **Upload**.
