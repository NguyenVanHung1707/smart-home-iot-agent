# HƯỚNG DẪN CÀI ĐẶT & TRIỂN KHAI DỰ ÁN TỪ A-Z (CHO NGƯỜI MỚI BẮT ĐẦU)

Tài liệu này được biên soạn từng bước cụ thể, chi tiết và dễ hiểu nhất để bất kỳ ai dù chưa từng làm việc với Docker hay ESP32 cũng có thể tự cài đặt và vận hành hoàn chỉnh hệ thống **Homing Smart Home Hub**.

---

## MỤC LỤC
1. [Chuẩn bị công cụ & phần mềm](#1-chuẩn-bị-công-cụ--phần-mềm)
2. [Cài đặt và chạy hệ thống Server & Web Dashboard](#2-cài-đặt-và-chạy-hệ-thống-server--web-dashboard)
3. [Hướng dẫn cài đặt Arduino IDE / Arduino CLI & nạp code cho ESP32](#3-hướng-dẫn-cài-đặt-arduino-ide--nạp-code-cho-esp32)
4. [Kiểm tra vận hành toàn bộ hệ thống](#4-kiểm-tra-vận-hành-toàn-bộ-hệ-thống)
5. [Khắc phục các lỗi thường gặp (Troubleshooting)](#5-khắc-phục-các-lỗi-thường-gặp-troubleshooting)

---

## 1. Chuẩn bị công cụ & phần mềm

Trước khi bắt đầu, hãy tải và cài đặt sẵn các phần mềm miễn phí sau trên máy tính của bạn:

1. **Git**: Tải tại [https://git-scm.com/](https://git-scm.com/) (chọn Next mặc định khi cài đặt).
2. **Docker Desktop**: Tải tại [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/) (cần bật tính năng WSL2 trên Windows khi được hỏi).
3. **Arduino IDE 2.x**: Tải tại [https://www.arduino.cc/en/software](https://www.arduino.cc/en/software) (dùng để nạp code cho ESP32).
4. **Driver kết nối máy tính với ESP32**:
   - Nếu bo mạch dùng chip nạp **CP2102**: Tải driver [Silicon Labs CP210x](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers).
   - Nếu bo mạch dùng chip nạp **CH340 / CH341**: Tải driver [WCH CH341SER](http://www.wch-ic.com/downloads/CH341SER_EXE.html).

---

## 2. Cài đặt và chạy hệ thống Server & Web Dashboard

### Bước 2.1: Mở thư mục dự án
Mở cửa sổ dòng lệnh (Terminal trên macOS/Linux hoặc **PowerShell** trên Windows), chuyển đến thư mục dự án:
```powershell
cd e:\hung\VinAI\Prj\smart-home-iot-agent
```

### Bước 2.2: Thiết lập file môi trường (.env)
Dự án đã có sẵn file mẫu `.env.example` hoặc `.env`. Mở file `.env` và kiểm tra các cấu hình cơ bản:
```ini
# Cấu hình AI API (Sử dụng OpenAI API hoặc tương thích)
OPENAI_API_KEY=sk-xxxxxx...
MODEL_NAME=gpt-4o-mini

# MQTT Broker nội bộ
MQTT_ENABLED=true
MQTT_BROKER=mqtt
MQTT_PORT=1883

# Mật khẩu tài khoản chủ nhà khởi tạo
BOOTSTRAP_ADMIN_PASSWORD=admin123456
```

### Bước 2.3: Khởi động hệ thống với Docker Compose
Chỉ cần chạy duy nhất một câu lệnh sau:
```bash
docker compose up -d --build
```
> **Giải thích**: Docker sẽ tự động tải các dịch vụ (PostgreSQL, Eclipse Mosquitto MQTT, FastAPI Backend, React Frontend Nginx) và biên dịch mã nguồn.

Sau khoảng 1-2 phút, bạn kiểm tra trạng thái hoạt động:
```bash
docker compose ps
```
Nếu thấy các dịch vụ `backend`, `frontend`, `mqtt`, `postgres` đều ở trạng thái `Up` (hoặc `healthy`) là hệ thống đã sẵn sàng!

- **Giao diện Web Dashboard**: Mở trình duyệt truy cập: [http://localhost](http://localhost)
- **API Backend Docs**: Mở trình duyệt truy cập: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 3. Hướng dẫn cài đặt Arduino IDE & nạp code cho ESP32

Hệ thống có 3 file mã nguồn ESP32 nằm tại thư mục `src/firmware/`:
1. `src/firmware/esp32_home_appliances_espnow/esp32_home_appliances_espnow.ino` (Bo mạch #1: Thiết bị trong nhà)
2. `src/firmware/esp32_main_entrance_espnow/esp32_main_entrance_espnow.ino` (Bo mạch #2: Cửa chính & An ninh)
3. `src/firmware/esp32_xiaozhi_gateway/esp32_xiaozhi_gateway.ino` (Bo mạch #3: Gateway Master)

### Bước 3.1: Thêm gói bo mạch ESP32 vào Arduino IDE
1. Mở **Arduino IDE** > Chọn menu **File** > **Preferences** (Cài đặt).
2. Tại dòng **Additional boards manager URLs**, dán đường dẫn sau:
   ```text
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. Nhấn **OK**.
4. Vào menu **Tools** > **Board** > **Boards Manager...**
5. Gõ từ khóa `esp32` của **Espressif Systems** và bấm **Install**.

### Bước 3.2: Cài đặt các thư viện Arduino cần thiết
Vào menu **Tools** > **Manage Libraries...** (hoặc bấm tổ hợp phím `Ctrl + Shift + I`), lần lượt tìm kiếm và bấm **Install** các thư viện sau:
- **`PubSubClient`** (bởi Nick O'Leary) — Thư viện MQTT client.
- **`ArduinoJson`** (bởi Benoit Blanchon) — Chọn phiên bản **6.x** (khuyên dùng bản 6.21.x).
- **`ESP32Servo`** (bởi Kevin Harrington) — Điều khiển động cơ servo chốt cửa và cửa sổ.
- **`DHT sensor library`** (bởi Adafruit) — Đọc cảm biến nhiệt độ DHT11.
- **`Adafruit Unified Sensor`** (bởi Adafruit) — Thư viện hỗ trợ cảm biến.
- **`U8g2`** (bởi oliver) — Điều khiển màn hình OLED 1.3" I2C SH1106.
- **`LiquidCrystal_I2C`** (bởi Frank de Brabander) — Điều khiển màn hình LCD 16x2.
- **`MFRC522`** (bởi GithubCommunity) — Đọc thẻ từ RFID RC522.
- **`Keypad`** (bởi Mark Stanley) — Bàn phím số ma trận 4x4.

---

### Bước 3.3: Lấy địa chỉ MAC của ESP32 #3 (Gateway Master)
Sóng ESP-NOW cần biết chính xác địa chỉ phần cứng (MAC Address) của bo mạch Gateway Master để gửi nhận tin:
1. Cắm bo mạch ESP32 #3 vào máy tính qua cáp Micro-USB hoặc Type-C.
2. Mở Arduino IDE, tạo file mới và nạp đoạn code ngắn sau để đọc địa chỉ MAC:
   ```cpp
   #include <WiFi.h>
   void setup() {
     Serial.begin(115200);
     WiFi.mode(WIFI_STA);
     Serial.print("ESP32 MAC Address: ");
     Serial.println(WiFi.macAddress());
   }
   void loop() {}
   ```
3. Mở **Serial Monitor** (tốc độ 115200 baud), bạn sẽ thấy địa chỉ MAC hiển thị dạng:
   `94:54:C5:A9:91:E8`
4. Ghi lại địa chỉ MAC này để cấu hình vào code của Bo mạch #1 và Bo mạch #2.

---

### Bước 3.4: Nạp code cho từng bo mạch

#### 1. Nạp Bo Mạch #1 (Thiết bị gia dụng & Môi trường)
1. Mở file: `src/firmware/esp32_home_appliances_espnow/esp32_home_appliances_espnow.ino`.
2. Kiểm tra dòng 22 xem địa chỉ MAC đã khớp với địa chỉ MAC của Bo mạch #3 vừa lấy ở bước trên chưa:
   ```cpp
   uint8_t masterGatewayMac[] = {0x94, 0x54, 0xC5, 0xA9, 0x91, 0xE8};
   ```
3. Cắm bo mạch #1 vào máy tính.
4. Tại Arduino IDE:
   - **Tools** > **Board** > chọn **ESP32 Dev Module** (hoặc DOIT ESP32 DEVKIT V1).
   - **Tools** > **Port** > chọn đúng cổng COM xuất hiện (ví dụ `COM3`, `COM4`).
5. Bấm nút **Upload** (mũi tên hướng sang phải). Khi màn hình hiện `Connecting......`, bạn có thể nhấn giữ nút **BOOT** trên bo mạch khoảng 2 giây để nạp.

#### 2. Nạp Bo Mạch #2 (Cửa chính & An ninh)
1. Mở file: `src/firmware/esp32_main_entrance_espnow/esp32_main_entrance_espnow.ino`.
2. Kiểm tra địa chỉ MAC dòng 23 và điền đúng địa chỉ MAC của Bo mạch #3.
3. Cắm bo mạch #2 vào máy tính, chọn đúng cổng COM và bấm **Upload**.

#### 3. Nạp Bo Mạch #3 (Xiaozhi Master Voice AI Gateway)
1. Mở file: [`src/firmware/esp32_xiaozhi_gateway/esp32_xiaozhi_gateway.ino`](file:///e:/hung/VinAI/Prj/smart-home-iot-agent/src/firmware/esp32_xiaozhi_gateway/esp32_xiaozhi_gateway.ino).
2. Kiểm tra các thông số cấu hình ở đầu file:
   - **Loại bo mạch (Dòng 38-39)**: Chọn `#define BOARD_ESP32_CLASSIC` (cho ESP32 WROOM-32) hoặc `#define BOARD_ESP32_S3` (cho ESP32-S3).
   - **Driver màn hình OLED (Dòng 76-77)**: Mặc định `#define OLED_DRIVER_SH1106` (OLED 1.3 inch). Nếu dùng OLED 0.96 inch SSD1306 thì mở comment `#define OLED_DRIVER_SSD1306`.
   - **WiFi 2.4GHz (Dòng 99-100)**: Điền đúng WiFi gia đình:
     ```cpp
     const char *wifi_ssid = "Ten_WiFi_Nha_Ban";
     const char *wifi_pass = "Mat_Khau_WiFi";
     ```
   - **Máy chủ AI Hub (Dòng 112)**: Đã trỏ sẵn theo domain tự host:
     ```cpp
     const char *xiaozhi_ota_url = "http://lophocso.io.vn/xiaozhi/ota/";
     ```
3. Cài đặt thông số biên dịch trong Arduino IDE (menu **Tools**):
   - **Board**: Chọn **ESP32 Dev Module**
   - **Partition Scheme**: Chọn **`Huge APP (3MB No OTA/1MB SPIFFS)`** *(Bắt buộc chọn mục này để tránh lỗi tràn dung lượng bộ nhớ Flash)*
   - **Upload Speed**: `921600` (hoặc `115200` nếu dây cáp kém)
   - **Port**: Chọn đúng cổng COM của bo mạch
4. Bấm nút **Upload**. Khi Serial hiện `Connecting........_____.....`, hãy **nhấn giữ nút BOOT** trên bo ESP32 khoảng 2 giây rồi thả ra.
5. Sau khi nạp thành công:
   - Loa MAX98357A sẽ phát 2 tiếng chuông chào mừng.
   - Màn hình OLED hiển thị: `HOMING AI GATEWAY`, `Hub: lophocso.io.vn` và `Voice AI: SAN SANG`.

---

### Bước 3.5: Lựa chọn nâng cao — Biên dịch & Nạp code bằng Arduino CLI (Command Line)

Dành cho các bạn muốn biên dịch và nạp code trực tiếp từ cửa sổ dòng lệnh (Terminal / PowerShell) mà không cần mở giao diện đồ họa Arduino IDE:

#### 1. Kiểm tra hoặc Cài đặt Arduino CLI
Kiểm tra xem máy tính của bạn đã có `arduino-cli` chưa:
```powershell
arduino-cli version
```
*(Nếu chưa cài, trên Windows mở PowerShell chạy lệnh: `winget install Arduino.ArduinoCLI`)*.

#### 2. Cài đặt Core ESP32 & Thư viện tự động
```powershell
# Cấu hình nguồn package ESP32
arduino-cli config init
arduino-cli config add board_manager.additional_urls https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
arduino-cli core update-index
arduino-cli core install esp32:esp32

# Cài đặt tự động toàn bộ thư viện cần thiết cho dự án
arduino-cli lib install "PubSubClient" "ArduinoJson@6.21.4" "U8g2" "ESP32Servo" "DHT sensor library" "Adafruit Unified Sensor" "LiquidCrystal_I2C" "MFRC522" "Keypad"
```

#### 3. Tìm cổng COM của bo mạch
Cắm ESP32 vào máy tính và chạy:
```powershell
arduino-cli board list
```
*(Ghi nhớ cổng COM hiển thị, ví dụ `COM3`, `COM5`...)*.

#### 4. Biên dịch và Nạp code cho Bo mạch #3 (Voice AI Gateway)
> [!IMPORTANT]
> Bo mạch AI Gateway có thư viện xử lý âm thanh I2S và màn hình OLED nên bắt buộc truyền tham số `--build-property "build.partitions=huge_app"` để cấp đủ 3MB bộ nhớ Flash.

* **Biên dịch & Nạp ngay trong 1 câu lệnh (thay `COM3` bằng cổng COM thực tế của bạn)**:
  ```powershell
  arduino-cli compile --fqbn esp32:esp32:esp32 --build-property "build.partitions=huge_app" -p COM3 -u src/firmware/esp32_xiaozhi_gateway
  ```
  *(Nếu bạn sử dụng bo mạch **ESP32-S3**, đổi FQBN thành: `--fqbn esp32:esp32:esp32s3`)*.

* **Chỉ biên dịch kiểm tra lỗi cú pháp (không nạp vào mạch)**:
  ```powershell
  arduino-cli compile --fqbn esp32:esp32:esp32 --build-property "build.partitions=huge_app" src/firmware/esp32_xiaozhi_gateway
  ```

#### 5. Biên dịch và Nạp code cho Bo mạch #1 & Bo mạch #2
* **Bo mạch #1 (Thiết bị gia dụng)**:
  ```powershell
  arduino-cli compile --fqbn esp32:esp32:esp32 -p COM3 -u src/firmware/esp32_home_appliances_espnow
  ```
* **Bo mạch #2 (Cửa chính & An ninh)**:
  ```powershell
  arduino-cli compile --fqbn esp32:esp32:esp32 -p COM3 -u src/firmware/esp32_main_entrance_espnow
  ```

#### 6. Theo dõi Log Serial Monitor trực tiếp từ dòng lệnh
```powershell
arduino-cli monitor -p COM3 -c baudrate=115200
```
*(Bấm `Ctrl + C` để thoát Serial Monitor)*.



---

## 4. Kiểm tra vận hành toàn bộ hệ thống

1. **Đăng nhập Web Dashboard**:
   - Truy cập: **[http://localhost](http://localhost)**
   - Sử dụng tài khoản Chủ nhà:
     - **Email**: `admin@homing.dev` (hoặc `chunha1@homing.dev`, `chunha2@homing.dev`)
     - **Mật khẩu**: `admin123456`
2. **Kiểm tra trạng thái thiết bị**:
   - Trên màn hình **Phòng & Thiết bị**, bạn sẽ thấy các thiết bị: Đèn phòng khách, Đèn phòng ngủ, Quạt, Khóa cửa, Cảm biến nhiệt độ, Khí gas.
   - Thử bấm nút Bật/Tắt Đèn phòng khách trên giao diện web -> Quan sát đèn LED trên ESP32 #1 sáng/tắt ngay lập tức!
3. **Thử nghiệm mở khóa an ninh**:
   - Quẹt thẻ RFID vào đầu đọc bo mạch #2 -> Khóa servo quay 90° mở chốt, màn hình LCD hiển thị *"Access Granted"*.
   - Hoặc gõ mật khẩu `1234#` trên bàn phím Keypad 4x4 để mở khóa.
4. **Thử nghiệm điều khiển bằng Giọng nói (Voice AI)**:
   - **Cách 1 - Nói trực tiếp qua Micro phần cứng trên ESP32 #3 (INMP441 + OLED 1.3" + Loa MAX98357A)**:
     - Nói vào Micro INMP441 (ví dụ nói rõ: *"alo"*, *"xin chào"*, *"bật đèn"*, *"mở cửa"*).
     - ESP32 sẽ phát chuông thức tỉnh êm ái (Wake Chime), tự động ghi âm 1.5 giây và gửi đến máy chủ FunASR SenseVoice.
     - **Màn hình OLED 1.3"**: Hiển thị chữ bạn vừa nói (ví dụ: `> Ban: alo`, `> Ban: bat den`) và sau đó hiển thị câu trả lời của AI (`> AI: Toi nghe day`, `> AI: Da bat den cho ban`).
     - **Loa MAX98357A**: Tự động phát trực tiếp giọng nói tiếng Việt câu trả lời ra loa (ví dụ: *"Tôi nghe đây, xin chào bạn!"*, *"Đã bật đèn cho bạn."*).
     - Đồng thời, nếu là câu lệnh thiết bị, ESP32 sẽ bắn lệnh tức thì sang các node thiết bị qua mạng ESP-NOW!
   - **Cách 2 - Điều khiển qua Web Dashboard**:
     - Bấm vào biểu tượng Micro ở góc dưới màn hình web [http://localhost](http://localhost).
     - Nói câu lệnh: *"Bật đèn phòng khách và mở quạt phòng bếp"* -> Agent sẽ tự động phân tích và kích hoạt thiết bị.

---

## 5. Khắc phục các lỗi thường gặp (Troubleshooting)

### Lỗi 1: Cổng COM không nhận khi cắm ESP32 vào máy tính
- **Nguyên nhân**: Thiếu driver chip nạp UART (CP2102 hoặc CH340).
- **Cách xử lý**: Cài driver ở [Mục 1](#1-chuẩn-bị-công-cụ--phần-mềm). Đổi sang dây cáp USB có chức năng truyền dữ liệu (nhiều dây cáp sạc điện thoại giá rẻ chỉ có 2 lõi nguồn, không truyền được dữ liệu).

### Lỗi 2: Arduino IDE báo lỗi khi nạp: `A fatal error occurred: Failed to connect to ESP32`
- **Cách xử lý**: Khi Arduino IDE bắt đầu in dòng chữ `Connecting........_____.....`, hãy **nhấn và giữ nút BOOT (hoặc FLASH)** trên mạch ESP32 khoảng 2-3 giây rồi thả tay ra để đưa mạch vào chế độ nạp firmware.

### Lỗi 3: ESP32 bị reset liên tục khi cắm Servo SG90 hoặc cảm biến MQ-2
- **Nguyên nhân**: Sụt áp nguồn (Brownout detector reset) do động cơ Servo và cảm biến sấy khí gas ăn dòng lớn.
- **Cách xử lý**: Cấp nguồn 5V ngoài (Adapter 5V/2A) cho chân VIN của Servo và MQ-2, đồng thời **nối chung chân GND của nguồn ngoài với chân GND của ESP32**.

### Lỗi 4: Port 80 bị chiếm dụng (Không mở được giao diện Web)
- **Cách xử lý**: Nếu trên máy tính của bạn đã có sẵn IIS hoặc ứng dụng khác chiếm cổng 80, hãy mở file `docker-compose.yml`, sửa dòng `ports: ["80:80"]` thành `ports: ["3000:80"]`. Khi đó truy cập web qua địa chỉ `http://localhost:3000`.

---

## 6. Vận hành Loa AI Xiaozhi Tự Chủ (Self-hosted Xiaozhi Server)

Hệ thống đã tích hợp sẵn container `xiaozhi-server` mã nguồn mở (tối ưu hóa từ XinNan Tech) để chạy hoàn toàn cục bộ:

### 1. Kiến trúc luồng giọng nói cục bộ
- **HTTP OTA & Vision Endpoint**: `http://lophocso.io.vn/xiaozhi/ota/` (hoặc nội bộ cổng `8093`)
- **WebSocket Voice Server**: `ws://lophocso.io.vn/xiaozhi/v1/` (hoặc nội bộ cổng `8090`)
- **Text-to-Speech (TTS)**: Sử dụng **Edge-TTS** giọng Tiếng Việt tự nhiên (`vi-VN-HoaiMyNeural` hoặc `vi-VN-NamMinhNeural`).
- **Smart Home Plugin**: File `infra/xiaozhi/plugins/smart_home.py` tự động nhận diện ý định và kích hoạt điều khiển 13 thiết bị thực tế qua API Backend / MQTT.

### 2. Cấu hình bo mạch ESP32 #3 kết nối Server cục bộ
Trong file [`src/firmware/esp32_xiaozhi_gateway/esp32_xiaozhi_gateway.ino`](file:///e:/hung/VinAI/Prj/smart-home-iot-agent/src/firmware/esp32_xiaozhi_gateway/esp32_xiaozhi_gateway.ino):
1. Đặt địa chỉ OTA Domain chính thức:
   ```cpp
   const char *xiaozhi_ota_url = "http://lophocso.io.vn/xiaozhi/ota/";
   ```
   *(ESP32 kết nối trực tiếp qua Domain hoặc IP mạng LAN `http://<IP_LAN>:8093/xiaozhi/ota/`)*
2. Nạp code vào ESP32 #3. Khi khởi động, màn hình OLED sẽ hiển thị trạng thái kết nối tới server cục bộ.
3. Nói vào Micro INMP441: *"Bật đèn phòng khách"* -> Server phân tích và loa MAX98357A sẽ phản hồi bằng giọng Tiếng Việt, đồng thời đèn phòng khách trên ESP32 #1 sẽ sáng ngay lập tức!

### 3. Tùy chỉnh Nhân vật, System Prompt & Giọng nói trên Web Dashboard
Bạn có thể truy cập trang **"Cấu hình AI Voice"** trên thanh menu bên trái của Web Dashboard (`https://lophocso.io.vn/`):
- **Chọn mẫu tính cách (Persona)**: Quản gia Jarvis, Cô Tấm dịu dàng, Trợ lý HomeMind, Vệ binh Sentinel.
- **Tùy chỉnh System Prompt**: Thay đổi phong cách xưng hô (em - anh/chị), quy tắc kiểm tra an ninh hoặc cách trả lời ngắn gọn.
- **Giọng đọc & Tốc độ**: Chọn giọng Hoài My (Nữ), Nam Minh (Nam), chỉnh tốc độ đọc (0.8x - 1.4x) và nhấn **"Nghe thử giọng"**.
- **Mô hình & Từ khóa đánh thức (Wake words)**: Thêm/bớt từ khóa gọi loa (xiaozhi, jarvis, homing...). Nhấn **"Lưu & Đồng bộ"** để tự động cập nhật ngay lập tức xuống cả Master ESP32 Gateway và Web Hub.


