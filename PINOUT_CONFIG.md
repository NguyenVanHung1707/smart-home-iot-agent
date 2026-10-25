# BẢNG CẤU HÌNH CHÂN (PINOUT) & SƠ ĐỒ ĐẤU NỐI PHẦN CỨNG ESP32

Tài liệu này cung cấp sơ đồ chân chi tiết cho toàn bộ **3 bo mạch ESP32** trong hệ thống Homing Smart Home Hub.

---

## 1. Tổng quan hệ thống phần cứng

Hệ thống sử dụng **3 vi điều khiển ESP32** (chuẩn ESP32 DevKit WROOM-32 30 hoặc 38 chân):

| Bo Mạch | Tên File Firmware | Vai Trò Chính | Chuẩn Giao Tiếp |
| :--- | :--- | :--- | :--- |
| **ESP32 #1** | `esp32_home_appliances_espnow.ino` | Thiết bị gia dụng & Môi trường | ESP-NOW (Slave) |
| **ESP32 #2** | `esp32_main_entrance_espnow.ino` | Cửa chính & An ninh thông minh | ESP-NOW (Slave) |
| **ESP32 #3** | `esp32_xiaozhi_gateway.ino` | Xiaozhi AI Voice Gateway Master | WiFi + MQTT + I2S + ESP-NOW (Master) |

> **MAC Address thực tế ESP32 #3**: `94:54:C5:A9:91:E8`  
> **IP LAN thực tế**: `192.168.1.101` (ESP32 Gateway kết nối WiFi `TP-Link_ED49`)

---

## 2. ESP32 Bo Mạch #1: Thiết Bị Trong Nhà & Môi Trường

> **Thư mục firmware**: `src/firmware/esp32_home_appliances_espnow/esp32_home_appliances_espnow.ino`

### 2.1. Bảng nối chân chi tiết

| Module / Linh kiện | Chân Module | Chân ESP32 (GPIO) | Mức điện áp | Ghi chú / Chức năng |
| :--- | :--- | :--- | :--- | :--- |
| **Cảm biến DHT11** | VCC | 3.3V | 3.3V | Cấp nguồn cảm biến |
| | GND | GND | 0V | Nối đất Mass chung |
| | DATA | **GPIO 14** | Logic 3.3V | Đọc nhiệt độ & độ ẩm phòng khách |
| **Cảm biến Khí Gas MQ-2** | VCC | **VIN (5V)** | 5V | Cảm biến MQ-2 cần 5V sấy sensor |
| | GND | GND | 0V | Nối Mass |
| | A0 (Analog) | **GPIO 34** | ADC (0-3.3V) | Đọc nồng độ khói/gas analog |
| **Cảm biến Chuyển động PIR** | VCC | **VIN (5V)** | 5V | Cấp nguồn PIR HC-SR501 |
| | GND | GND | 0V | Nối Mass |
| | OUT | **GPIO 35** | Logic 3.3V | Mức HIGH (1) khi phát hiện người |
| **Cảm biến Ánh sáng LDR** | A0 / D0 | **GPIO 33** | ADC (0-3.3V) | Đo cường độ sáng phòng |
| **Còi Báo Động Buzzer** | (+) | **GPIO 12** | PWM / Digital | Hú còi cảnh báo khi rò rỉ khí gas |
| | (-) | GND | 0V | Nối Mass |
| **Servo Cửa Sổ (SG90)** | Dây Đỏ (VCC) | **VIN (5V)** | 5V | Nguồn 5V cho động cơ servo |
| | Dây Nâu (GND) | GND | 0V | Nối Mass chung |
| | Dây Cam (PWM) | **GPIO 13** | PWM | 0°: Đóng cửa sổ, 90°: Mở thoát gas |
| **Đèn LED Phòng Ngủ** | Anode (+) | **GPIO 15** | Digital OUT | Bật/tắt đèn qua điện trở 220Ω |
| **Đèn LED Phòng Bếp** | Anode (+) | **GPIO 2** | Digital OUT | LED Onboard / Đèn bếp |
| **Đèn LED Phòng Khách** | Anode (+) | **GPIO 4** | Digital OUT | Đèn chiếu sáng phòng khách |
| **Quạt Mini Phòng Ngủ** | Điều khiển Relay/Transistor | **GPIO 16** | Digital OUT | Bật/tắt quạt phòng ngủ |
| **Quạt Mini Phòng Bếp** | Điều khiển Relay/Transistor | **GPIO 17** | Digital OUT | Bật/tắt quạt thông gió bếp |
| **Quạt Mini Phòng Khách** | Điều khiển Relay/Transistor | **GPIO 5** | Digital OUT | Bật/tắt quạt phòng khách |
| **Nút Bấm Cơ Thủ Công** | 1 đầu nút | **GPIO 18** | INPUT_PULLUP | Bật/tắt đèn ngủ tại chỗ bằng nút |
| | 1 đầu nút | GND | 0V | Nhấn nút nối xuống GND |
| **Màn hình OLED 1.3" I2C** | VCC | 3.3V | 3.3V | Nguồn màn hình SH1106 |
| | GND | GND | 0V | Nối Mass |
| | SCL | **GPIO 22** | I2C Clock | Xung clock I2C mặc định ESP32 |
| | SDA | **GPIO 21** | I2C Data | Dữ liệu data I2C mặc định ESP32 |

---

## 3. ESP32 Bo Mạch #2: Cổng Chính & Khóa Cửa An Ninh

> **Thư mục firmware**: `src/firmware/esp32_main_entrance_espnow/esp32_main_entrance_espnow.ino`

### 3.1. Bảng nối chân chi tiết

| Module / Linh kiện | Chân Module | Chân ESP32 (GPIO) | Mức điện áp | Ghi chú / Chức năng |
| :--- | :--- | :--- | :--- | :--- |
| **Khóa Chốt Servo SG90** | Dây Đỏ (VCC) | **VIN (5V)** | 5V | Nguồn servo chốt cửa |
| | Dây Nâu (GND) | GND | 0V | Nối Mass |
| | Dây Cam (PWM) | **GPIO 4** | PWM | 0°: Khóa chốt, 90°: Mở khóa chốt |
| **Còi Bíp Báo Hiệu** | (+) | **GPIO 15** | Digital OUT | Kêu bíp khi bấm phím / quẹt thẻ |
| | (-) | GND | 0V | Nối Mass |
| **Đầu đọc thẻ RFID-RC522** | 3.3V (VCC) | **3.3V** | **Tuyệt đối 3.3V** | **CẮM 5V SẼ CHÁY MODULE RFID** |
| | GND | GND | 0V | Nối Mass |
| | RST | **GPIO 2** | Logic 3.3V | Chân Reset |
| | SDA (SS) | **GPIO 5** | SPI CS | Chip Select SPI |
| | SCK | **GPIO 18** | SPI SCK | Xung nhịp SPI |
| | MISO | **GPIO 19** | SPI MISO | Dữ liệu từ RFID về ESP32 |
| | MOSI | **GPIO 23** | SPI MOSI | Dữ liệu từ ESP32 sang RFID |
| **Màn hình LCD 16x2 I2C** | VCC | **VIN (5V)** | 5V | Màn LCD 16x2 cần 5V để sáng rõ |
| | GND | GND | 0V | Nối Mass |
| | SDA | **GPIO 21** | I2C Data | Giao tiếp I2C hiển thị thông báo |
| | SCL | **GPIO 22** | I2C Clock | Xung clock I2C |
| **Bàn phím ma trận 4x4** | Hàng 1 (Row 1) | **GPIO 13** | Digital I/O | Quét hàng bàn phím |
| | Hàng 2 (Row 2) | **GPIO 12** | Digital I/O | Quét hàng bàn phím |
| | Hàng 3 (Row 3) | **GPIO 14** | Digital I/O | Quét hàng bàn phím |
| | Hàng 4 (Row 4) | **GPIO 27** | Digital I/O | Quét hàng bàn phím |
| | Cột 1 (Col 1) | **GPIO 26** | Digital I/O | Quét cột bàn phím |
| | Cột 2 (Col 2) | **GPIO 25** | Digital I/O | Quét cột bàn phím |
| | Cột 3 (Col 3) | **GPIO 33** | Digital I/O | Quét cột bàn phím |
| | Cột 4 (Col 4) | **GPIO 32** | Digital I/O | Quét cột bàn phím |

---

## 4. ESP32 Bo Mạch #3: Xiaozhi AI Voice Gateway Master

> **Thư mục firmware**: `src/firmware/esp32_xiaozhi_gateway/esp32_xiaozhi_gateway.ino`

Đóng vai trò **loa thông minh AI tự host**, cầu nối WiFi / MQTT với Cloud và điều phối sóng vô tuyến ESP-NOW tới Bo mạch #1 và #2. Hỗ trợ:
- **Ghi âm & ASR**: Micro INMP441 → FunASR SenseVoice nhận diện tiếng Việt
- **Phát TTS & Nhạc**: Edge-TTS Tiếng Việt + Phát nhạc WAV stream qua HTTP trực tiếp ra Loa MAX98357A I2S
- **Điều khiển MQTT**: Nhận lệnh từ Topic `homing/speaker/play`, `homing/speaker/say`, `homing/devices/+/command`
- **Hiển thị OLED**: Biểu cảm robot (happy, neutral, speaking, thinking) + văn bản ASR/TTS

### 4.1. Bảng nối chân chi tiết

| Module / Linh kiện | Chân Module | Chân ESP32 Classic (WROOM) | Chân ESP32-S3 | Mức điện áp | Ghi chú / Chức năng |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **LED Onboard** | Tích hợp trên bo | **GPIO 2** | **GPIO 48** | Logic 3.3V | Đèn LED phản hồi trạng thái kết nối & truyền audio |
| **Mạch công suất MAX98357A** | VIN / VCC | **VIN (5V)** | **5V** | 5V | Cấp nguồn 5V cho loa công suất 3W |
| | GND | GND | GND | 0V | Nối Mass |
| | BCLK | **GPIO 26** | **GPIO 15** | I2S0 BCLK | Bit Clock truyền âm thanh |
| | LRC | **GPIO 25** | **GPIO 16** | I2S0 LRC | Left/Right Word Select Clock |
| | DIN | **GPIO 27** | **GPIO 7** | I2S0 DATA | Dữ liệu âm thanh phát ra loa |
| | GAIN | GND / Để trống | GND / Để trống | - | Mặc định Gain 9dB hoặc 12dB |
| | SD_MODE | Để trống | Để trống | - | Tự động bật kênh |
| **Micro số I2S INMP441** | VDD | **3.3V** | **3.3V** | 3.3V | **Chỉ dùng 3.3V, không dùng 5V** |
| | GND | GND | GND | 0V | Nối Mass chung |
| | SCK | **GPIO 14** | **GPIO 5** | I2S1 SCK | Serial Clock thu âm thanh |
| | WS | **GPIO 15** | **GPIO 4** | I2S1 WS | Word Select thu âm thanh |
| | SD | **GPIO 32** | **GPIO 6** | I2S1 SD | Serial Data Input vào ESP32 |
| | L/R | GND | GND | 0V | Nối GND để chọn kênh Left |
| **Màn hình OLED 1.3" I2C** | VCC | 3.3V | 3.3V | 3.3V | Nguồn màn hình hiển thị biểu cảm AI |
| | GND | GND | GND | 0V | Nối Mass |
| | SDA | **GPIO 21** | **GPIO 17** | I2C SDA | Dữ liệu màn hình |
| | SCL | **GPIO 22** | **GPIO 18** | I2C SCL | Xung clock màn hình |

### 4.2. Cấu hình firmware quan trọng (đầu file .ino)

| Tham số | Giá trị mặc định | Ý nghĩa |
| :--- | :--- | :--- |
| `BOARD_ESP32_CLASSIC` / `BOARD_ESP32_S3` | `BOARD_ESP32_CLASSIC` | Chọn đúng loại chip (WROOM-32 hoặc S3) |
| `OLED_DRIVER_SH1106` / `OLED_DRIVER_SSD1306` | `SH1106` | OLED 1.3" = SH1106, OLED 0.96" = SSD1306 |
| `wifi_ssid` / `wifi_pass` | *(cấu hình trong code)* | WiFi 2.4GHz (không dùng được WiFi 5GHz) |
| `xiaozhi_ota_url` | `http://lophocso.io.vn/xiaozhi/ota/` | Địa chỉ Hub AI Xiaozhi |
| `mqtt_server` | `192.168.1.105` | IP LAN máy chủ MQTT Mosquitto |
| `AUDIO_SAMPLE_RATE` | `16000` Hz | Tần số lấy mẫu âm thanh WAV |
| `VAD_THRESHOLD` | `1500` RMS | Ngưỡng phát hiện giọng nói (VAD) |

### 4.3. Các MQTT Topic ESP32 #3 xử lý

| Topic | Hướng | Chức năng |
| :--- | :--- | :--- |
| `homing/devices/+/command` | Subscribe | Nhận lệnh bật/tắt thiết bị → relay ESP-NOW sang #1, #2 |
| `homing/speaker/say` | Subscribe | Nhận văn bản → phát TTS Edge-TTS tiếng Việt ra Loa I2S |
| `homing/speaker/play` | Subscribe | Nhận URL WAV → tải stream → phát ra Loa MAX98357A I2S |
| `homing/broadcast/scan` | Subscribe | Quét danh sách thiết bị ESP-NOW đang online |
| `homing/gateway/state` | Publish | Báo cáo trạng thái Gateway (online, IP, MAC) |
| `homing/devices/+/state` | Publish | Báo cáo trạng thái từng thiết bị nhận từ ESP-NOW |

---

## 5. Lưu ý quan trọng khi đấu nối phần cứng

1. **Mass (GND) chung**: Tất cả các nguồn cấp (5V, 3.3V, Adapter ngoài) phải được **nối chung chân GND** lại với nhau. Nếu không chung GND, cảm biến và giao tiếp I2C/SPI sẽ bị nhiễu hoặc sai dữ liệu.

2. **Điện áp module RFID-RC522 và Micro INMP441**: Chỉ được cấp nguồn **3.3V**. Cấp 5V sẽ gây hỏng chip ngay lập tức.

3. **Nguồn cấp cho Động cơ Servo (SG90) và Cảm biến MQ-2**: Cần nguồn **5V / tối thiểu 2A**. Không lấy nguồn 3.3V từ chân ESP32 để kéo Servo vì sẽ làm sụt áp gây reset ESP32 liên tục (Brownout Detector reset).

4. **Partition Scheme cho Bo mạch #3**: Bắt buộc chọn **`Huge APP (3MB No OTA/1MB SPIFFS)`** trong Arduino IDE khi biên dịch Bo mạch #3 (Gateway AI) — firmware có thêm thư viện I2S âm thanh và JSON kích thước lớn.

5. **WiFi 2.4GHz**: ESP32 WROOM-32 **chỉ hỗ trợ WiFi 2.4GHz**. Đảm bảo router gia đình phát băng tần 2.4GHz và tên WiFi không chứa ký tự đặc biệt.

6. **Giao tiếp I2S Loa và Micro không xung đột**: Bo mạch #3 dùng **hai cổng I2S độc lập**:
   - **I2S Port 0** (GPIO 25, 26, 27): Loa MAX98357A (phát âm thanh)
   - **I2S Port 1** (GPIO 14, 15, 32): Micro INMP441 (thu âm thanh)
