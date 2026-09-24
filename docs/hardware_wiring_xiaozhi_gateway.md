# HƯỚNG DẪN ĐẤU NỐI PHẦN CỨNG: ESP32 + MAX98357A + INMP441 + LOA 3W + OLED 1.3" I2C
*(Dự án Homing AI Gateway - Tương thích kiến trúc Xiaozhi-ESP32)*

---

## 1. Danh sách linh kiện phần cứng

1. **Board mạch vi điều khiển ESP32**:
   - Tùy chọn A: **ESP32 Classic** (WROOM-32, ESP32 DevKit V1 30 chân hoặc 38 chân).
   - Tùy chọn B: **ESP32-S3** (ESP32-S3 DevKitC-1 N16R8 hoặc tương đương).
2. **Màn hình OLED 1.3 inch I2C (4 chân)**:
   - Độ phân giải 128x64 pixel, driver SH1106 (hoặc SSD1306). Giao tiếp I2C chỉ cần 2 dây (SDA, SCL).
3. **Mạch khuếch đại âm thanh số I2S MAX98357A**:
   - Tích hợp sẵn DAC giải mã I2S và tầng công suất Mono Class-D (tối đa 3.2W ở 4Ω với nguồn 5V).
4. **Cảm biến âm thanh Micro I2S INMP441**:
   - Micro điện dung kỹ thuật số chuẩn MEMS, giao tiếp trực tiếp I2S, độ nhạy cao, chống nhiễu vượt trội so với micro analog mic thường.
5. **Loa mini công suất 3W**:
   - Trở kháng 4Ω hoặc 8Ω, đường kính 28mm – 40mm.
6. **Dây nối cắm breadboard hoặc dây hàn**.
7. *(Khuyến nghị)*: 1 tụ điện hóa **100µF - 470µF 10V** để lọc nguồn cho MAX98357A.

---

## 2. Sơ đồ đấu nối chi tiết (Wiring Diagram)

### 2.1. Bảng nối chân cho ESP32 Classic (ESP-WROOM-32 / NodeMCU 30 & 38 chân)

```
       +-------------------------------------------------------------+
       |                     ESP32 CLASSIC (WROOM)                  |
       |                                                             |
       |  [5V / VIN] --------+-----------------> VIN (MAX98357A)     |
       |  [3.3V] ------------+-----------------> VDD (INMP441 & OLED)|
       |  [GND] -------------+--+--------------> GND (Chung tất cả)  |
       |                        |                                    |
       |  [GPIO 21] ------------|--------------> SDA (OLED 1.3" I2C) |
       |  [GPIO 22] ------------|--------------> SCL (OLED 1.3" I2C) |
       |                                                             |
       |  [GPIO 26] ---------------------------> BCLK (MAX98357A)    |
       |  [GPIO 25] ---------------------------> LRC  (MAX98357A)    |
       |  [GPIO 27] ---------------------------> DIN  (MAX98357A)    |
       |                                                             |
       |  [GPIO 14] ---------------------------> SCK  (INMP441)      |
       |  [GPIO 15] ---------------------------> WS   (INMP441)      |
       |  [GPIO 32] ---------------------------> SD   (INMP441)      |
       |                        +--------------> L/R  (INMP441)      |
       +------------------------|------------------------------------+
                                v
                           (Nối GND)
```

| Tên Module | Chân trên Module | Chân nối trên ESP32 | Chức năng chi tiết |
| :--- | :--- | :--- | :--- |
| **OLED 1.3" I2C** (SH1106) | **VCC** | **3.3V** (hoặc 5V) | Cấp nguồn cho màn hình OLED |
| | **GND** | **GND** | Nối Mass chung hệ thống |
| | **SCL** | **GPIO 22** | Chân xung Clock I2C phần cứng ESP32 |
| | **SDA** | **GPIO 21** | Chân dữ liệu Data I2C phần cứng ESP32 |
| **MAX98357A** (Khuếch đại I2S) | **VIN** | **VIN (hoặc 5V)** | Cấp nguồn 5V cho công suất loa. **Không dùng 3.3V** |
| | **GND** | **GND** | Nối Mass chung hệ thống |
| | **BCLK** | **GPIO 26** | Bit Clock phát âm thanh (I2S0 BCLK) |
| | **LRC** | **GPIO 25** | Left/Right Clock (I2S0 WS) |
| | **DIN** | **GPIO 27** | Dữ liệu PCM ra loa (chuyển sang 27 để nhường 21 & 22 cho OLED) |
| | **GAIN** | *Để trống* | Mặc định Gain = 9dB (âm thanh rõ, không vỡ tiếng) |
| | **SD** | *Để trống* | Shutdown pin (để trống: chạy kênh (L+R)/2) |
| **Loa mini 3W** | Cực Dương `+` (Đỏ) | Cọc **+ (OUT+)** | Nối vào cọc vặn ốc hoặc pad hàn `+` trên MAX98357A |
| | Cực Âm `-` (Đen) | Cọc **- (OUT-)** | Nối vào cọc vặn ốc hoặc pad hàn `-` trên MAX98357A |
| **INMP441** (Micro I2S) | **VDD** | **3.3V** | Cấp nguồn 3.3V từ chân 3V3 của ESP32 |
| | **GND** | **GND** | Nối Mass chung hệ thống |
| | **SD** | **GPIO 32** | Serial Data Out từ Mic vào chân đọc I2S1 DIN của ESP32 |
| | **WS** | **GPIO 15** | Word Select thu âm (I2S1 WS) |
| | **SCK** | **GPIO 14** | Serial Clock thu âm (I2S1 BCLK) |
| | **L/R** | **GND** | **BẮT BUỘC NỐI GND** để chọn kênh Left Mono |

---

### 2.2. Bảng nối chân cho ESP32-S3 (Chuẩn cấu hình `bread-compact-wifi`)

Nếu bạn sử dụng bo mạch **ESP32-S3**, các chân GPIO được phân bổ theo chuẩn board `bread-compact-wifi` của dự án gốc Xiaozhi-ESP32:

| Tên Module | Chân trên Module | Chân nối trên ESP32-S3 |
| :--- | :--- | :--- |
| **MAX98357A** (Loa) | **VIN** / **GND** | **5V** / **GND** |
| | **BCLK** | **GPIO 15** |
| | **LRC** | **GPIO 16** |
| | **DIN** | **GPIO 7** |
| **INMP441** (Mic) | **VDD** / **GND** | **3.3V** / **GND** |
| | **L/R** | **GND** (Bắt buộc) |
| | **SCK** | **GPIO 5** |
| | **WS** | **GPIO 4** |
| | **SD** | **GPIO 6** |

---

## 3. Các lưu ý kỹ thuật bắt buộc để mạch hoạt động ổn định

### ⚠️ Lưu ý 1: Về nguồn cấp 5V và lỗi Brownout Reset
- Mạch khuếch đại MAX98357A khi đánh loa 3W ở âm lượng cao có thể rút dòng tức thời lên tới **500mA - 800mA**.
- Nếu bạn cắm nguồn qua cổng USB máy tính lỏng hoặc dây cáp USB kém chất lượng, điện áp 5V sẽ bị sụt giảm xuống dưới 4.5V làm chip ESP32 kích hoạt cơ chế bảo vệ **Brownout detector was triggered** và khởi động lại liên tục.
- **Giải pháp**:
  - Dùng củ sạc điện thoại 5V/2A cắm trực tiếp vào ESP32.
  - Hàn một tụ hóa **100µF - 470µF (10V - 16V)** mắc song song giữa chân `VIN` và `GND` ngay tại mạch MAX98357A để bù dòng tức thời khi loa phát âm thanh lớn.

### ⚠️ Lưu ý 2: Chân L/R của Micro INMP441
- Chân `L/R` (Left/Right) quyết định vị trí dữ liệu âm thanh nằm ở chu kỳ xung Clock mức Thấp hay mức Cao.
- Với firmware Xiaozhi và ESP32 I2S Mono driver, kênh âm thanh mặc định là **Left Channel**. Do đó, chân **L/R PHẢI NỐI VÀO GND**.
- Nếu chân này bị lỏng hoặc thả nổi (floating), micro sẽ không thể đồng bộ frame clock, kết quả là âm thanh thu vào chỉ là nhiễu trắng (white noise) hoặc toàn số 0.

### ⚠️ Lưu ý 3: Tuyệt đối không nối cọc loa OUT- vào GND
- Ngõ ra loa của MAX98357A là dạng cầu vi sai **BTL (Bridge-Tied Load)**.
- Hai dây loa được nối riêng vào `OUT+` và `OUT-`. Tuyệt đối không để cực âm của loa chạm vào GND mạch hoặc mass vỏ kim loại, nếu không chip MAX98357A sẽ bị đoản mạch và hỏng ngay lập tức.

---

## 4. Kiểm tra hoạt động (Test Procedure)

1. **Test Loa & MAX98357A**:
   - Khi nạp firmware `esp32_xiaozhi_gateway.ino`, hàm `setup()` sẽ tự động chạy hàm phát âm thanh khởi động `playBootChime()`.
   - Loa sẽ phát ra một đoạn hợp âm 3 nốt (Do - Mi - Sol) du dương. Nếu bạn nghe thấy tiếng nhạc khởi động rõ ràng, tức là mạch MAX98357A, I2S Tx và Loa 3W đã hoạt động 100%.
2. **Test Micro INMP441**:
   - Khi nói vào micro, task `audio_reader_task` sẽ liên tục đọc mẫu dữ liệu I2S và tính giá trị RMS (năng lượng âm thanh).
   - Khi phát hiện tiếng nói lớn hơn ngưỡng VAD, Serial Monitor sẽ hiển thị:
     `[I2S MIC] Phat hien giong noi! RMS: 1850 | Bat dau ghi am...`
3. **Test Lệnh Web / Cloud MQTT**:
   - Khi gửi tin nhắn MQTT đến topic `homing/speaker/say`, gateway sẽ phát tín hiệu âm thanh thông báo ra loa.
