# CẨM NANG HƯỚNG DẪN NẠP CODE & TRIỂN KHAI HOMING SERVERLESS IOT
### Kiến trúc 3 ESP32: Xiaozhi Master Gateway + ESP-NOW Slaves + Web WSS MQTT (Zero-PC)

Tài liệu này hướng dẫn chi tiết từng bước để bạn tự nạp code vào 3 bo mạch ESP32 và triển khai hệ thống nhà thông minh chạy **hoàn toàn độc lập 24/7 mà không cần máy tính, không cần bật Docker ở nhà**.

---

## 1. Sơ đồ phân công 3 bo mạch ESP32

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                             HỆ THỐNG HOMING IOT                             │
├──────────────────────────┬─────────────────────────┬────────────────────────┤
│     ESP32 #1 (SLAVE)     │     ESP32 #2 (SLAVE)    │    ESP32 #3 (GATEWAY)  │
│  Thiết bị trong nhà      │   Cửa an ninh chính     │   Xiaozhi AI Loa & Cầu nối
├──────────────────────────┼─────────────────────────┼────────────────────────┤
│ • Giao thức: ESP-NOW     │ • Giao thức: ESP-NOW    │ • Giao thức: WiFi, WSS │
│ • 3 Đèn (Relay)          │ • Khóa chốt Servo       │   MQTT & ESP-NOW       │
│ • 3 Quạt (PWM/Transistor)│ • Keypad mật mã 4x4     │ • Mic I2S (INMP441)    │
│ • Cửa sổ/Rèm Servo       │ • Đầu đọc thẻ từ RFID   │ • Loa I2S (MAX98357A)  │
│ • DHT11, MQ2 Gas, PIR    │ • Màn hình LCD 16x2     │ • Cầu nối Internet với │
│ • Màn hình OLED SH1106   │ • Còi báo động Buzzer   │   HiveMQ & Xiaozhi     │
└──────────────────────────┴─────────────────────────┴────────────────────────┘
```

---

## 2. Chuẩn bị phần mềm & Thư viện Arduino IDE

### 2.1. Cài đặt ESP32 Board Package (nếu chưa có)
1. Mở **Arduino IDE** > Vào **File** > **Preferences**.
2. Tại mục *Additional Boards Manager URLs*, dán đường link:
   ```text
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. Vào **Tools** > **Board** > **Boards Manager...**, tìm kiếm `esp32` của **Espressif Systems** và bấm **Install** (khuyên dùng bản `2.0.14` hoặc `3.0.x`).

### 2.2. Cài đặt các thư viện cần thiết qua Library Manager
Vào **Tools** > **Manage Libraries...** và cài đặt các thư viện sau:
* `PubSubClient` (bởi Nick O'Leary)
* `ArduinoJson` (bởi Benoit Blanchon - Chọn phiên bản 6.x)
* `ESP32Servo` (bởi Kevin Harrington)
* `DHT sensor library` (bởi Adafruit)
* `Adafruit Unified Sensor` (bởi Adafruit)
* `U8g2` (bởi oliver - cho màn hình OLED)
* `LiquidCrystal_I2C` (bởi Frank de Brabander - cho màn hình LCD)
* `MFRC522` (bởi GithubCommunity - cho thẻ từ)
* `Keypad` (bởi Mark Stanley - cho bàn phím số)

---

## 3. BƯỚC 1: Đăng ký Cụm Cloud MQTT Miễn phí (HiveMQ Cloud)

1. Truy cập trang chủ: **[https://www.hivemq.com/mqtt-cloud-broker/](https://www.hivemq.com/mqtt-cloud-broker/)**
2. Bấm **Sign Up Free** (gói miễn phí vĩnh viễn cho 100 thiết bị kết nối).
3. Đăng nhập và tạo một **Cluster Serverless** mới.
4. Sau khi tạo xong, bạn vào phần **Overview** để lấy thông tin:
   - **Cluster URL (Host)**: ví dụ `xxxxxx.s1.eu.hivemq.cloud`
   - **Port TLS**: `8883` (dùng cho ESP32)
   - **Port WebSockets (WSS)**: `8884` (dùng cho Web Dashboard)
5. Vào tab **Access Management** > Bấm **Add Credentials**:
   - Đặt `Username` (ví dụ: `homing_user`)
   - Đặt `Password` (ví dụ: `MatKhauHoming123`)
   - Quyền: Cho phép Publish & Subscribe vào mọi topic (`#`).
6. *Ghi lại 4 thông tin này để điền vào code ESP32 #3 và Web.*

---

## 4. BƯỚC 2: Lấy Địa chỉ MAC của 3 con ESP32

Để các con ESP32 bắn sóng ESP-NOW chính xác cho nhau, bạn cần biết địa chỉ MAC của từng con.

1. Tạo một sketch mới trên Arduino IDE và dán đoạn code sau:
```cpp
#include <WiFi.h>

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  delay(500);
  Serial.println("\n-----------------------------");
  Serial.print("ĐỊA CHỈ MAC CỦA CON NÀY: ");
  Serial.println(WiFi.macAddress());
  Serial.println("-----------------------------");
}

void loop() {}
```
2. Cắm lần lượt từng con ESP32 vào máy tính, nạp đoạn code trên, mở **Serial Monitor (baud 115200)** và ghi lại địa chỉ MAC:
   * **MAC ESP32 #1 (Thiết bị)**: `........................` (Ví dụ: `24:6F:28:AB:12:01`)
   * **MAC ESP32 #2 (Cổng chính)**: `........................` (Ví dụ: `24:6F:28:CD:34:02`)
   * **MAC ESP32 #3 (Xiaozhi Gateway)**: `........................` (Ví dụ: `24:6F:28:EF:56:03`)

---

## 5. BƯỚC 3: Nạp Code ESP32 #1 (Thiết bị trong nhà)

1. Mở file:
   `src/firmware/esp32_home_appliances_espnow/esp32_home_appliances_espnow.ino`
2. Tìm dòng số 20, thay địa chỉ MAC của **ESP32 #3 (Gateway)** vào biến `masterGatewayMac`:
   ```cpp
   // Điền địa chỉ MAC của con ESP32 #3 (Xiaozhi Gateway)
   uint8_t masterGatewayMac[] = {0x24, 0x6F, 0x28, 0xEF, 0x56, 0x03};
   ```
3. Cắm ESP32 #1 vào cổng USB máy tính.
4. Trong Arduino IDE:
   - **Board**: Chọn `ESP32 Dev Module` (hoặc tên board ESP32 tương ứng bạn mua).
   - **Port**: Chọn cổng COM của ESP32 #1.
   - Bấm nút **Upload (Nạp code)**.
5. Khi nạp xong, mở Serial Monitor: Màn hình OLED sẽ sáng lên thông báo `HOMING ESP-NOW #1: Ready (ESP-NOW)`.

---

## 6. BƯỚC 4: Nạp Code ESP32 #2 (Cổng an ninh chính)

1. Mở file:
   `src/firmware/esp32_main_entrance_espnow/esp32_main_entrance_espnow.ino`
2. Tìm dòng số 20, thay địa chỉ MAC của **ESP32 #3 (Gateway)** vào biến `masterGatewayMac`:
   ```cpp
   // Điền địa chỉ MAC của con ESP32 #3 (Xiaozhi Gateway)
   uint8_t masterGatewayMac[] = {0x24, 0x6F, 0x28, 0xEF, 0x56, 0x03};
   ```
3. Cắm ESP32 #2 vào cổng USB máy tính.
4. Chọn đúng cổng COM và bấm nút **Upload**.
5. Khi nạp xong, màn hình LCD 16x2 sẽ hiển thị `Nhap PIN hoac quet the RFID...`.

---

## 7. BƯỚC 5: Nạp Code ESP32 #3 (Xiaozhi Master Gateway)

1. Mở file:
   `src/firmware/esp32_xiaozhi_gateway/esp32_xiaozhi_gateway.ino`
2. Cập nhật các thông tin sau:
   - **Tên WiFi & Mật khẩu nhà bạn**:
     ```cpp
     const char* wifi_ssid = "TP-Link_NHA_BAN";
     const char* wifi_pass = "mat_khau_wifi";
     ```
   - **Thông tin HiveMQ Cloud** (đã lấy ở Bước 1):
     ```cpp
     const char* mqtt_server = "xxxxxx.s1.eu.hivemq.cloud";
     const int mqtt_port = 8883;
     const char* mqtt_user = "homing_user";
     const char* mqtt_pass = "MatKhauHoming123";
     ```
   - **Địa chỉ MAC của ESP32 #1 và ESP32 #2** (đã lấy ở Bước 2):
     ```cpp
     uint8_t mac_esp1_appliances[] = {0x24, 0x6F, 0x28, 0xAB, 0x12, 0x01}; // MAC của ESP #1
     uint8_t mac_esp2_entrance[]   = {0x24, 0x6F, 0x28, 0xCD, 0x34, 0x02}; // MAC của ESP #2
     ```
3. Cắm ESP32 #3 vào cổng USB máy tính, chọn cổng COM và bấm **Upload**.
4. Mở Serial Monitor:
   - ESP32 #3 sẽ kết nối WiFi, sau đó in dòng chữ:
     `[MQTT] Dang ket noi HiveMQ Cloud... KET NOI THANH CONG!`
   - Đồng thời đăng ký Peer ESP-NOW thành công với 2 con ESP kia.

---

## 8. BƯỚC 6: Sử dụng Web Dashboard điều khiển qua WSS & Xiaozhi AI

### Cách 1: Chạy thử trên máy tính
1. Mở terminal tại thư mục dự án:
   ```bash
   cd frontend
   npm run dev
   ```
2. Mở trình duyệt vào `http://localhost:5173`.
3. Vào trang **Cài đặt MQTT** (biểu tượng MQTT bên menu trái):
   - Nhập URL WSS HiveMQ: `wss://xxxxxx.s1.eu.hivemq.cloud:8884/mqtt`
   - Nhập Username & Password đã tạo ở Bước 1.
   - Bấm **Lưu & Kết nối lại WSS** -> Đèn báo sẽ chuyển sang **Xanh lục (Đã kết nối WSS)**.
4. Bấm nút **Gửi lệnh Test Đèn** hoặc vào trang **Thiết bị** bật/tắt đèn: Đèn trên ESP32 #1 sẽ bật/tắt ngay lập tức!
5. Bấm vào nút tím **Xiaozhi AI** (hoặc nút tròn góc dưới bên phải):
   - Màn hình Trợ lý ảo Xiaozhi hiện ra.
   - Bấm Micro nói *"Bật đèn phòng khách"* hoặc *"Mở khóa cửa"*: Xiaozhi sẽ trả lời bằng giọng nói và điều khiển phần cứng ngay!

### Cách 2: Deploy lên Internet miễn phí (Để mở bằng điện thoại khi ra ngoài đường)
1. Trong thư mục `frontend/`, chạy lệnh build:
   ```bash
   npm run build
   ```
2. Thư mục `frontend/dist/` sẽ chứa toàn bộ trang Web tĩnh đã được đóng gói hoàn chỉnh.
3. Kéo thả thư mục `dist/` lên **[Vercel](https://vercel.com)** hoặc **[Cloudflare Pages](https://pages.cloudflare.com)** (hoàn toàn miễn phí vĩnh viễn).
4. Bạn sẽ có đường link dạng `https://nha-thong-minh.vercel.app`:
   - Mở trên điện thoại bằng 4G.
   - Bấm "Thêm vào màn hình chính" (PWA) để dùng như một App ứng dụng.
   - Điều khiển từ xa không phụ thuộc bất kỳ máy tính nào ở nhà.

---

## 9. Khắc phục sự cố thường gặp (Troubleshooting)

1. **ESP-NOW không nhận tín hiệu**:
   - Đảm bảo kênh WiFi (`WIFI_CHANNEL`) trên cả 3 con ESP trùng nhau (mặc định là kênh WiFi của Router nhà bạn, thường là kênh 1 hoặc 6).
   - Kiểm tra xem bạn đã điền đúng địa chỉ MAC chưa (lưu ý thứ tự các byte `0xXX`).
2. **HiveMQ Cloud báo lỗi kết nối rc=-2**:
   - Kiểm tra lại WiFi gia đình có kết nối Internet không.
   - Kiểm tra Hostname `xxxx.s1.eu.hivemq.cloud` và Username/Password trong Access Management của HiveMQ.
3. **Micro trên Web không nhận giọng nói**:
   - Đảm bảo trình duyệt đã được cấp quyền Micro (bấm biểu tượng ổ khóa cạnh thanh địa chỉ URL).
   - Sử dụng trình duyệt Chrome hoặc Edge để có trải nghiệm nhận dạng giọng nói tiếng Việt mượt mà nhất.
