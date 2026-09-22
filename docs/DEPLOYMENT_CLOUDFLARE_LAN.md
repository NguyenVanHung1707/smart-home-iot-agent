# Hướng Dẫn Triển Khai Homing Hub Tại Domain lophocso.io.vn
## (Sử dụng Cloudflare Tunnel & Docker, Kết Nối ESP32 Qua WiFi LAN)

Tài liệu này hướng dẫn chi tiết cách triển khai toàn bộ hệ thống Smart Home AI Agent (Homing Hub) phục vụ:
1. **Truy cập Web Dashboard & AI Voice Agent** từ bất kỳ đâu qua domain **`https://lophocso.io.vn`** (bảo mật SSL/HTTPS tự động từ Cloudflare Edge, không cần mở cổng modem).
2. **Đóng gói và vận hành bằng Docker Compose**.
3. **Giao tiếp phần cứng 2 bo mạch ESP32** nội bộ qua **mạng WiFi LAN** (giao thức TCP MQTT cổng 1883, phản hồi tức thời < 10ms, không tốn tài nguyên Internet).

---

## 1. Sơ Đồ Kiến Trúc Hệ Thống

```text
  [ Người Dùng (Điện thoại / Laptop) ]
                  │
                  ▼  (HTTPS / SSL Cổng 443)
       https://lophocso.io.vn
                  │
                  ▼
   ┌───────────────────────────────┐
   │    Cloudflare Edge Network    │
   │  (Tự động cấp SSL & DDoS WAF) │
   └──────────────┬────────────────┘
                  │  (Mã hóa 2 chiều qua Cloudflare Tunnel)
                  ▼
 ┌─────────────────────────────────────────────────────────────────┐
 │ MÁY CHỦ DOCKER TẠI NHÀ (IP LAN: ví dụ 192.168.1.16)             │
 │                                                                 │
 │   Container: cloudflared                                        │
 │        │ (HTTP)                                                 │
 │        ▼                                                        │
 │   Container: frontend (Nginx Port 80)                           │
 │        ├── /      ──> React Web Dashboard (SPA)                 │
 │        ├── /api/  ──> Container: backend (FastAPI Port 8000)    │
 │        └── /mqtt  ──> Container: mqtt (WebSocket Port 9001)     │
 │                                                                 │
 │   Container: mqtt (Mosquitto Port 1883 TCP bind 0.0.0.0)        │
 └───────────────────────┬─────────────────────────────────────────┘
                         │ (Mạng WiFi nội bộ gia đình - TCP 1883)
          ┌──────────────┴──────────────┐
          ▼                             ▼
 ┌──────────────────┐          ┌──────────────────┐
 │ ESP32 Bo Mạch #1 │          │ ESP32 Bo Mạch #2 │
 │ (Đèn, Quạt, Cửa) │          │ (Cổng Khóa RFID) │
 └──────────────────┘          └──────────────────┘
```

---

## 2. Chuẩn Bị Máy Chủ Docker Tại Nhà

### Bước 2.1: Xác định địa chỉ IP LAN của máy chủ Docker

Để 2 ESP32 có thể gửi nhận dữ liệu với Mosquitto Broker, bạn cần biết địa chỉ IP nội bộ của máy chủ trong mạng WiFi gia đình:

- **Trên Windows**: Mở PowerShell hoặc Command Prompt:
  ```powershell
  ipconfig
  ```
  Tìm dòng `IPv4 Address` thuộc card mạng WiFi hoặc Ethernet (thường có dạng `192.168.1.X` hoặc `192.168.0.X`).
- **Trên Linux / Raspberry Pi**:
  ```bash
  hostname -I
  ```
*(Ví dụ IP LAN ghi nhận được là: `192.168.1.16`)*.

> [!TIP]
> Bạn nên vào trang quản trị modem WiFi (ví dụ `192.168.1.1`) và gán IP cố định (DHCP Static Lease / Address Reservation) cho máy tính này để IP không bị thay đổi khi khởi động lại modem.

### Bước 2.2: Mở tường lửa (Firewall) cho cổng MQTT 1883 (nếu cần)

Đảm bảo tường lửa trên máy chủ cho phép các thiết bị trong mạng LAN kết nối vào cổng 1883:
- **Trên Windows**: Chạy PowerShell quyền Administrator:
  ```powershell
  New-NetFirewallRule -DisplayName "Mosquitto MQTT LAN" -Direction Inbound -Protocol TCP -LocalPort 1883 -Action Allow
  ```
- **Trên Linux (UFW)**:
  ```bash
  sudo ufw allow 1883/tcp
  ```

---

## 3. Thiết Lập Cloudflare Tunnel Cho Domain `lophocso.io.vn`

Cloudflare Tunnel giúp đưa ứng dụng web local ra ngoài Internet với HTTPS an toàn mà **không cần mở cổng (port forward) trên router**.

### Bước 3.1: Tạo Tunnel trên Cloudflare Zero Trust
1. Truy cập [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/).
2. Chọn menu **Networks** -> **Tunnels** -> Bấm **Add a tunnel**.
3. Chọn loại **Cloudflared** -> Bấm **Next**.
4. Đặt tên tunnel (ví dụ: `homing-hub`) -> Bấm **Save tunnel**.
5. Trong trang cài đặt, Cloudflare sẽ hiển thị đoạn lệnh chứa Token dạng:
   ```text
   eyJhIjoiYmNmN2...
   ```
   **Copy chuỗi token này**.

### Bước 3.2: Cấu hình Public Hostname cho Domain
1. Chuyển sang tab **Public Hostname** của Tunnel vừa tạo -> Bấm **Add a public hostname**.
2. Điền thông tin:
   - **Subdomain**: (để trống hoặc điền `www` nếu muốn)
   - **Domain**: chọn `lophocso.io.vn`
   - **Path**: (để trống)
   - **Type**: `HTTP`
   - **URL**: `frontend:80` (hoặc `localhost:80` nếu chạy ngoài container)
3. Bấm **Save hostname**.

---

## 4. Cấu Hình Biến Môi Trường (.env)

Mở file `.env` trong thư mục gốc dự án và điền Token Cloudflare cùng cấu hình CORS:

```env
# ---- Cloudflare Tunnel ----
CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoi...chuoi_token_copy_o_buoc_3...

# ---- App Config ----
APP_ENV=development
APP_PORT=8000
APP_HOST=0.0.0.0
CORS_ORIGINS=https://lophocso.io.vn,http://lophocso.io.vn,http://localhost:3000,http://localhost:5173,http://localhost

# ---- MQTT Broker ----
MQTT_ENABLED=true
MQTT_BROKER=mqtt
MQTT_PORT=1883
MQTT_TOPIC_PREFIX=homing
```

---

## 5. Khởi Động Toàn Bộ Hệ Thống Bằng Docker

Bạn có thể sử dụng file script hỗ trợ `scripts/docker.sh` hoặc lệnh `docker compose`:

### Cách 1: Khởi động với script (Khuyến nghị)
```bash
# Chế độ Base + Cloudflare Tunnel
bash scripts/docker.sh up tunnel

# Hoặc Full MVP (Voice tiếng Việt Zipformer/Piper + Qwen LLM + Cloudflare Tunnel)
bash scripts/docker.sh up full-tunnel
```

### Cách 2: Khởi động bằng Docker Compose trực tiếp
```bash
docker compose --profile tunnel up -d --build
```

### Kiểm tra trạng thái các container:
```bash
docker compose ps
```
Các service sau sẽ ở trạng thái `running` (hoặc `healthy`):
- `frontend`: Cổng 80 (Nginx phục vụ giao diện & reverse proxy API).
- `backend`: Cổng 8000 (FastAPI AI Agent, Voice pipeline).
- `mqtt`: Cổng `0.0.0.0:1883` (TCP LAN) và `9001` (WebSocket).
- `cloudflared`: Kết nối tunnel bảo mật tới `lophocso.io.vn`.

Xem log của tunnel:
```bash
docker compose logs -f cloudflared
```
Khi thấy dòng log: `Registered tunnel connection ... Connection ... is ready`, hệ thống đã sẵn sàng đón traffic từ Internet qua domain `lophocso.io.vn`.

---

## 6. Cấu Hình & Nạp Firmware Cho 2 ESP32 (Mạng WiFi LAN)

Hai file mã nguồn firmware:
- Bo mạch #1 (Thiết bị trong nhà): [`src/firmware/esp32_home_appliances/esp32_home_appliances.ino`](file:///e:/hung/VinAI/Prj/smart-home-iot-agent/src/firmware/esp32_home_appliances/esp32_home_appliances.ino)
- Bo mạch #2 (Cổng an ninh & khóa cửa): [`src/firmware/esp32_main_entrance/esp32_main_entrance.ino`](file:///e:/hung/VinAI/Prj/smart-home-iot-agent/src/firmware/esp32_main_entrance/esp32_main_entrance.ino)

### Bước 6.1: Cập nhật thông tin WiFi và IP máy chủ
Mở từng file `.ino` bằng **Arduino IDE** và kiểm tra 4 dòng cấu hình ở đầu file:

```cpp
// --- THÔNG TIN MẠNG WIFI & MQTT BROKER TRONG MẠNG LAN ---
char ssid[] = "TÊN_WIFI_NHA_BAN";       // Ví dụ: TP-Link_ED49
char pass[] = "MAT_KHAU_WIFI_NHA_BAN";   // Mật khẩu WiFi
const char* mqtt_server = "192.168.1.16"; // Thay bằng IP LAN máy Docker (ở Bước 2.1)
const int mqtt_port = 1883;               // Cổng TCP MQTT mặc định
```

### Bước 6.2: Cài đặt thư viện trên Arduino IDE
Đảm bảo đã cài đặt các thư viện sau qua Library Manager:
- `PubSubClient` (Nick O'Leary)
- `ArduinoJson` (Benoît Blanchon, v6.x)
- `DHT sensor library` & `Adafruit Unified Sensor`
- `ESP32Servo` (Kevin Harrington)
- `U8g2` (Oliver) - Cho màn hình OLED SH1106
- `LiquidCrystal_I2C` - Cho màn hình LCD 1602
- `MFRC522` - Cho module RFID RC522
- `Keypad` - Cho bàn phím ma trận 4x4

### Bước 6.3: Nạp Code và Kiểm tra Serial Monitor
1. Cắm cáp USB nối ESP32 với máy tính.
2. Chọn đúng cổng COM và Board `ESP32 Dev Module`.
3. Bấm **Upload**.
4. Mở **Serial Monitor** (tốc độ baud `115200`), bạn sẽ thấy luồng kết nối:
   ```text
   Connecting to WiFi: TP-Link_ED49.....
   WiFi Connected! IP Address: 192.168.1.45
   [LAN-MQTT Client] Đang thử kết nối Mosquitto Broker LAN: 192.168.1.16:1883
   [LAN-MQTT Client] KẾT NỐI BROKER LAN THÀNH CÔNG (ĐÃ ĐĂNG KÝ LWT)!
   [LAN-MQTT Client] Subscribed: homing/devices/+/command, homing/broadcast/scan
   ESP32 #1 (Home Appliances System - LAN TCP MQTT) SẴN SÀNG!
   ```

---

## 7. Kiểm Thử Vận Hành End-to-End

### 1. Truy cập Web Dashboard qua Domain
- Mở trình duyệt (trên máy tính hoặc điện thoại bất kỳ có 4G/WiFi):
  `https://lophocso.io.vn`
- Xác nhận trình duyệt hiển thị biểu tượng ổ khóa bảo mật **HTTPS** (do Cloudflare cấp).

### 2. Cấp quyền Microphone & Ra lệnh Giọng nói
- Vào tab **Trợ lý**.
- Bấm vào nút Microphone -> Chọn **Allow** (Cho phép) khi trình duyệt hỏi quyền truy cập Micro (tính năng này chỉ hoạt động được khi có HTTPS).
- Nói: *“Bật đèn phòng khách”* hoặc *“Mở cửa sổ”*.
- Im lặng 2 giây để bộ VAD tự động kết thúc thu âm và gửi đến Zipformer STT.
- Quan sát:
  1. Dashboard nhận transcript và gọi Agent.
  2. Agent gửi lệnh qua MQTT Topic `homing/devices/living-light/command`.
  3. Đèn trên ESP32 bật sáng ngay lập tức (độ trễ < 10ms qua WiFi LAN).
  4. ESP32 gửi lại trạng thái `state` và `ack`.

### 3. Tự Động Quét & Nhận Diện Thiết Bị (Auto-Discovery)
- Trên Dashboard, bấm nút **Quét thiết bị** (Discovery Scan).
- Backend gửi broadcast `homing/broadcast/scan`.
- Cả 2 ESP32 trong mạng WiFi LAN sẽ tự động phản hồi danh sách thiết bị về topic `homing/discovery`.
- Trên màn hình xuất hiện các thiết bị: Đèn, Quạt, Cửa sổ, Khóa cửa... Bấm **Kết nối (Pair)** để đưa vào điều khiển.

---

## 8. Xử Lý Sự Cố Thường Gặp (Troubleshooting)

| Hiện tượng | Nguyên nhân | Cách khắc phục |
| :--- | :--- | :--- |
| Trình duyệt báo `Error 502 Bad Gateway` khi vào domain | Container `frontend` chưa chạy hoặc chưa lắng nghe cổng 80 | Chạy `docker compose ps` kiểm tra container `frontend` và xem log qua `docker compose logs frontend`. |
| Cloudflared log báo `Failed to connect to service` | URL trong Public Hostname điền sai | Trong Cloudflare Zero Trust, chỉnh URL thành `http://frontend:80`. |
| ESP32 báo `[LAN-MQTT Error] Thất bại, rc=-2` | ESP32 không tìm thấy máy chủ hoặc bị Firewall chặn | 1. Kiểm tra lại IP máy Docker có đúng không.<br>2. Tắt thử Windows Firewall hoặc mở rule cổng 1883.<br>3. Đảm bảo ESP32 và máy Docker bắt cùng một sóng WiFi router. |
| Bấm Micro không có phản hồi hoặc bị chặn | Truy cập qua HTTP thay vì HTTPS | Luôn truy cập bằng `https://lophocso.io.vn`. Trình duyệt chặn Micro trên kết nối không bảo mật. |
| Mất kết nối Internet từ ngoài nhưng muốn điều khiển trong nhà | Đứt cáp quang hoặc mất mạng quốc tế | Tại nhà, mở trình duyệt vào thẳng IP LAN: `http://192.168.1.16/`. Toàn bộ thiết bị ESP32 và Hub LAN vẫn hoạt động 100% bình thường. |
