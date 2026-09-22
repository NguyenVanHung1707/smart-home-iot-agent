# Hướng Dẫn Biên Dịch & Nạp Code 2 ESP32 Bằng Arduino CLI (Cloud WSS MQTT)

Tài liệu hướng dẫn từng bước cài đặt thư viện, biên dịch, nạp firmware và kiểm thử 2 bo mạch ESP32 ([`esp32_home_appliances.ino`](../src/firmware/esp32_home_appliances/esp32_home_appliances.ino) và [`esp32_main_entrance.ino`](../src/firmware/esp32_main_entrance/esp32_main_entrance.ino)) kết nối trực tiếp với **Cloud MQTT Broker** `wss://mqtt.blask.id.vn:443/mqtt` sử dụng công cụ dòng lệnh **Arduino CLI**.

---

## 1. Kiểm Tra Công Cụ và Thư Viện Đã Cài Đặt

### A. Kiểm tra Arduino CLI & ESP32 Core
Mở Terminal / PowerShell tại thư mục gốc của dự án và chạy:

```bash
arduino-cli version
arduino-cli core list
```

*Xác nhận đã có `esp32:esp32` core (phiên bản 3.x).*

### B. Thư viện bắt buộc
Các thư viện cần thiết cho dự án:
- `ArduinoWebsockets` (Giao tiếp WebSocket Secure WSS với Cloud Broker)
- `PubSubClient` (Giao thức MQTT tiêu chuẩn)
- `ArduinoJson` (Đóng/mở gói dữ liệu JSON)
- `U8g2` (Màn hình OLED SH1106)
- `LiquidCrystal_I2C` (Màn hình LCD 16x2)
- `MFRC522` (Đầu đọc thẻ RFID RC522)
- `Keypad` (Bàn phím ma trận 4x4)
- `ESP32Servo` (Động cơ Servo cửa sổ & cửa chính)
- `DHT sensor library` & `Adafruit Unified Sensor` (Cảm biến DHT11)

Lệnh cài đặt tự động trên máy tính:
```bash
arduino-cli lib install PubSubClient ArduinoJson U8g2 LiquidCrystal_I2C MFRC522 Keypad ESP32Servo "DHT sensor library" "Adafruit Unified Sensor"
```

---

## 2. Kiểm Tra Cổng COM Đang Kết Nối

Cắm ESP32 vào cổng USB máy tính và kiểm tra danh sách cổng giao tiếp:

```bash
arduino-cli board list
```

**Ví dụ kết quả:**
```text
Port Protocol Type              Board Name FQBN Core
COM3 serial   Serial Port (USB) Unknown
```
➡️ Ghi nhớ tên cổng `COM` (ví dụ: `COM3`, `COM4`...) tương ứng với từng con ESP32.

---

## 3. Cấu Hình Wi-Fi và Cloud WSS Broker

Trước khi nạp code, bạn mở 2 file firmware để chỉnh sửa thông tin mạng Wi-Fi tại nhà:

1. **File 1:** [`src/firmware/esp32_home_appliances/esp32_home_appliances.ino`](../src/firmware/esp32_home_appliances/esp32_home_appliances.ino)
2. **File 2:** [`src/firmware/esp32_main_entrance/esp32_main_entrance.ino`](../src/firmware/esp32_main_entrance/esp32_main_entrance.ino)

```cpp
// Thông tin Wi-Fi nhà bạn
char ssid[] = "TP-Link_ED49";
char pass[] = "76664748";

// Địa chỉ Cloud WebSocket Secure (WSS) Broker ngoài Internet
const char* wss_host = "mqtt.blask.id.vn";
const int wss_port = 443;
const char* wss_path = "/mqtt";
```

---

## 4. Lệnh Biên Dịch (Compile) và Nạp Code (Upload)

### ESP32 #1: Thiết Bị Trong Nhà và Môi Trường (`esp32_home_appliances.ino`)

1. **Biên dịch:**
   ```bash
   arduino-cli compile --fqbn esp32:esp32:esp32 src/firmware/esp32_home_appliances/esp32_home_appliances.ino
   ```
2. **Nạp xuống mạch (Thay `COM3` bằng cổng thực tế):**
   ```bash
   arduino-cli upload -p COM3 --fqbn esp32:esp32:esp32 src/firmware/esp32_home_appliances/esp32_home_appliances.ino
   ```

---

### ESP32 #2: Cổng Chính và Khóa Cửa An Ninh (`esp32_main_entrance.ino`)

1. **Biên dịch:**
   ```bash
   arduino-cli compile --fqbn esp32:esp32:esp32 src/firmware/esp32_main_entrance/esp32_main_entrance.ino
   ```
2. **Nạp xuống mạch (Thay `COM4` bằng cổng thực tế):**
   ```bash
   arduino-cli upload -p COM4 --fqbn esp32:esp32:esp32 src/firmware/esp32_main_entrance/esp32_main_entrance.ino
   ```

---

## 5. Đọc Log Serial Trực Tiếp Từ CLI

Để kiểm tra trạng thái kết nối Wi-Fi và Cloud WSS MQTT của ESP32 sau khi nạp:

```bash
arduino-cli monitor -p COM3 -c baudrate=115200
```

Nhấn `Ctrl + C` để thoát màn hình monitor.

**Xác nhận log thành công:**
```text
WiFi Connected! IP Address: 192.168.1.50
[WSS-MQTT Client] Đang thử kết nối Cloud Mosquitto Broker: wss://mqtt.blask.id.vn:443/mqtt
[WSS-MQTT Client] KẾT NỐI CLOUD WSS THÀNH CÔNG!
[WSS-MQTT Client] Subscribed: homing/devices/+/command, homing/broadcast/scan
```

---

## 6. Mẹo Xử Lý Lỗi Thường Gặp (Troubleshooting)

- **Lỗi `Failed to connect to ESP32: Timed out waiting for packet header` khi nạp:**  
  Giữ nút **BOOT** trên bo mạch ESP32 khi lệnh `upload` bắt đầu hiển thị `Connecting......` cho đến khi quá trình ghi flash bắt đầu.
- **Lỗi `COM port busy`:**  
  Đảm bảo không mở ứng dụng nào khác (như Serial Monitor của phần mềm khác) đang chiếm cổng COM đó.
