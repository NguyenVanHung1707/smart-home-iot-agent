# Hướng Dẫn Cài Đặt, Tải Model AI & Chạy Docker (Homing Hub)

Tài liệu này hướng dẫn chi tiết từ A đến Z cách cấu hình môi trường, khởi chạy hệ thống bằng **Docker Compose**, kích hoạt tăng tốc phần cứng **GPU NVIDIA**, tải các mô hình ngôn ngữ lớn (**Qwen 2.5 7B / 3B**) và vận hành hệ thống nhà thông minh 2 luồng độc lập (**Mô phỏng 3D** & **Phần cứng thật Xiaozhi**).

---

## 1. Yêu Cầu Hệ Thống & Chuẩn Bị Môi Trường

### 1.1. Cấu hình phần cứng khuyến nghị
| Thành phần | Mức tối thiểu | Khuyến nghị tối ưu |
| :--- | :--- | :--- |
| **Hệ điều hành** | Windows 10/11 64-bit, Ubuntu 22.04+, macOS | Windows 11 (WSL2) hoặc Ubuntu 22.04 LTS |
| **RAM hệ thống** | 8 GB | **16 GB RAM** trở lên |
| **Card đồ họa (GPU)**| CPU only (tốc độ chậm) | **NVIDIA RTX 3050 (4GB VRAM)** trở lên (CUDA 12+) |
| **Ổ cứng trống** | 10 GB | **25 GB SSD** (chứa Docker images và model weights) |

### 1.2. Cài đặt các công cụ cần thiết
1. **Docker Desktop (cho Windows / macOS)** hoặc **Docker Engine (cho Linux)**:
   - Trên Windows: Cài [Docker Desktop](https://www.docker.com/products/docker-desktop/), bật chế độ **WSL 2 based engine**.
   - Cài đặt Driver NVIDIA mới nhất từ trang chủ [NVIDIA Driver](https://www.nvidia.com/download/index.aspx).
   - Kiểm tra GPU bằng terminal:
     ```powershell
     nvidia-smi
     ```
   - Kiểm tra Docker nhận GPU:
     ```bash
     docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
     ```
2. **Git**: Đảm bảo máy đã cài [Git](https://git-scm.com/).

---

## 2. Kiến Trúc 2 Luồng Độc Lập

Hệ thống được thiết kế phân tách hoàn toàn giữa 2 môi trường:

```
                          ┌───────────────────────────┐
                          │   Frontend Web Dashboard  │
                          │   (http://localhost:80)   │
                          └─────────────┬─────────────┘
                                        │ Header: X-Data-Mode
                                        ▼
                          ┌───────────────────────────┐
                          │   Backend Hub (Port 8000) │
                          └──────┬─────────────┬──────┘
                                 │             │
                [mode: simulator]│             │[mode: real]
                                 ▼             ▼
  ┌────────────────────────────────────┐ ┌────────────────────────────────────┐
  │         LUỒNG MÔ PHỎNG ẢO          │ │         LUỒNG PHẦN CỨNG THẬT       │
  ├────────────────────────────────────┤ ├────────────────────────────────────┤
  │ • AI Engine: Ollama Local (GPU)    │ │ • AI Engine: Xiaozhi AI Gateway    │
  │ • Model: Qwen 2.5 7B / 3B          │ │ • Giao tiếp: MQTT Cloud & Loa thật │
  │ • Sơ đồ: Dữ liệu 3D P-140          │ │ • Thiết bị: ESP32 phần cứng thật   │
  │ • Thiết bị: Virtual MQTT Simulator │ │ • Trạng thái: Lưu trữ biệt lập     │
  └────────────────────────────────────┘ └────────────────────────────────────┘
```

---

## 3. Các Bước Cài Đặt & Khởi Chạy

### Bước 1: Clone mã nguồn dự án

Mở Terminal (PowerShell hoặc Bash) và clone repository:

```bash
git clone https://github.com/NguyenVanHung1707/smart-home-iot-agent.git
cd smart-home-iot-agent
```

---

### Bước 2: Thiết lập file môi trường `.env`

Tạo file `.env` tại thư mục gốc của dự án (nếu chưa có):

```bash
cp .env.example .env
```

Mở file `.env` và kiểm tra/chỉnh sửa các thông số sau:

```env
# ============================================
# Cấu hình AI Local Model (Ollama GPU)
# ============================================
LLM_ENABLED=true
MODEL_NAME=qwen2.5:7b
LLAMA_BASE_URL=http://ollama:11434/v1
LLM_TIMEOUT_SECONDS=120

# ============================================
# Cấu hình Xác thực & Bảo mật (JWT Auth)
# ============================================
JWT_SECRET=homing-super-secret-jwt-token-key-2026
BOOTSTRAP_ADMIN_PASSWORD=admin123456

# ============================================
# MQTT Broker & Database
# ============================================
MQTT_ENABLED=true
MQTT_BROKER=mqtt
MQTT_PORT=1883
DATABASE_URL=postgresql://homing_user:homing_password@postgres:5432/homing_db

# ============================================
# Xiaozhi AI Cloud (Dành cho luồng phần cứng thật)
# ============================================
XIAOZHI_SERVER_URL=wss://api.tenclass.net/v1
XIAOZHI_DEVICE_MAC=
XIAOZHI_TOKEN=
```

---

### Bước 3: Khởi động hệ thống bằng Docker Compose

Khởi chạy toàn bộ hệ thống gồm Backend, Frontend, MQTT, PostgreSQL, Device Simulator và Ollama GPU:

```bash
docker compose up -d
```

> **Ghi chú về GPU Passthrough:** Service `ollama` trong `docker-compose.yml` đã được cấu hình tự động nhận GPU:
> ```yaml
> deploy:
>   resources:
>     reservations:
>       devices:
>         - driver: nvidia
>           count: all
>           capabilities: [gpu]
> ```

Kiểm tra trạng thái các container đang chạy:

```bash
docker compose ps
```

Xác nhận container `homing-ollama` đã nhận diện đúng card đồ họa NVIDIA:

```bash
docker exec homing-ollama nvidia-smi
```

Nếu xuất hiện thông tin card đồ họa (ví dụ: `NVIDIA GeForce RTX 3050 Laptop GPU`) là GPU đã được kích hoạt thành công!

---

### Bước 4: Tải mô hình AI (Model Pulling)

Do các mô hình AI có dung lượng từ vài GB, bạn dùng lệnh `ollama pull` để tải mô hình mong muốn trực tiếp vào container:

#### 1. Mô hình khuyên dùng: **Qwen 2.5 7B Instruct** (4.7 GB)
*Khả năng hiểu tiếng Việt xuất sắc nhất, sinh JSON điều khiển nhà thông minh chuẩn xác, chạy hybrid ~2.3GB VRAM trên RTX 3050 + RAM hệ thống:*
```bash
docker exec -it homing-ollama ollama pull qwen2.5:7b
```

#### 2. Mô hình siêu nhẹ & siêu tốc: **Qwen 2.5 3B Instruct** (1.9 GB)
*Nạp 100% vào VRAM 4GB, tốc độ phản hồi tức thì (~50 tokens/giây, không tốn RAM hệ thống):*
```bash
docker exec -it homing-ollama ollama pull qwen2.5:3b
```

#### 3. Mô hình suy luận tư duy chuỗi (Tùy chọn): **DeepSeek-R1 7B** (4.7 GB)
*Dành cho suy luận logic phức tạp (Chain-of-Thought):*
```bash
docker exec -it homing-ollama ollama pull deepseek-r1:7b
```

#### Kiểm tra danh sách mô hình đã tải:
```bash
docker exec homing-ollama ollama list
```
*Kết quả mẫu:*
```
NAME          ID              SIZE      MODIFIED
qwen2.5:7b    845dbda0ea48    4.7 GB    25 minutes ago
qwen2.5:3b    5ee4f07cdb9b    1.9 GB    5 minutes ago
```

---

## 4. Kiểm Tra & Trải Nghiệm Hệ Thống

### 4.1. Đăng nhập Web Dashboard
1. Mở trình duyệt truy cập: [http://localhost](http://localhost)
2. Đăng nhập tài khoản quản trị:
   - **Email:** `admin@homing.dev`
   - **Mật khẩu:** `admin123456` *(hoặc mật khẩu bạn đặt trong `.env`)*

### 4.2. Thử nghiệm Chế độ Mô phỏng (Simulator Mode)
1. Trên thanh công cụ, đảm bảo công tắc chọn chế độ đang ở: **Mô phỏng (Simulator)**.
2. Mở cửa sổ **Trợ lý AI / Voice Overlay** (biểu tượng Micro hoặc Chat).
3. Tiêu đề hiển thị: `Trợ lý AI Local Model (Mô phỏng)`.
4. Gửi các câu lệnh mẫu:
   - *"Xin chào, bạn có thể giúp gì cho tôi?"*
   - *"Bật đèn phòng khách giúp tôi"*
   - *"Tắt quạt phòng ngủ và mở rèm cửa"*
5. Quan sát mô hình 3D cập nhật trạng thái thiết bị trực quan ngay lập tức.

### 4.3. Thử nghiệm Chế độ Phần cứng thật (Real Hardware Mode)
1. Gạt công tắc chuyển sang: **Phần cứng thật (Real Hardware)**.
2. Tiêu đề hiển thị: `Trợ lý AI Xiaozhi (Phần cứng thật)`.
3. Gửi câu lệnh điều khiển:
   - Lệnh được định tuyến trực tiếp qua **Xiaozhi AI Gateway**, gửi qua topic MQTT phần cứng (`homing/devices/+/command`) và phát thông báo qua loa.

---

## 5. Hướng Dẫn Chuyển Đổi Mô Hình

Nếu bạn muốn chuyển đổi giữa các mô hình (ví dụ từ `qwen2.5:7b` sang `qwen2.5:3b` để đạt tốc độ tối đa):

1. Sửa biến `MODEL_NAME` trong file `.env`:
   ```env
   MODEL_NAME=qwen2.5:3b
   ```
2. Khởi động lại container Backend để nhận cấu hình mới:
   ```bash
   docker compose up -d backend
   ```
3. Kiểm tra ngay trên giao diện web hoặc test qua lệnh:
   ```bash
   docker exec smart-home-iot-agent-backend-1 python -c "from src.services.llm import get_llm; print(get_llm().invoke('Xin chào!').content)"
   ```

---

## 6. Xử Lý Sự Cố Thường Gặp (Troubleshooting)

### 1. Docker báo lỗi không nhận Driver GPU NVIDIA
- **Hiện tượng:** `could not select device driver "" with capabilities: [[gpu]]`.
- **Khắc phục:**
  - Đảm bảo bạn đang dùng **Docker Desktop** với chế độ **WSL 2**.
  - Kiểm tra xem NVIDIA Container Toolkit đã sẵn sàng bằng lệnh:
    ```bash
    docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
    ```
  - Nếu dùng Linux native, cần cài đặt `nvidia-container-toolkit`:
    ```bash
    sudo apt-get install -y nvidia-container-toolkit
    sudo systemctl restart docker
    ```

### 2. Cuộc gọi AI lần đầu bị Timeout (Cold Start)
- **Hiện tượng:** Lần gửi lệnh đầu tiên sau khi khởi động máy mất nhiều thời gian hoặc báo `APITimeoutError`.
- **Nguyên nhân:** Lần đầu tiên chạy, Ollama phải nạp 4.7 GB model từ ổ cứng SSD vào RAM và VRAM (Cold Start).
- **Khắc phục:**
  - Hệ thống đã tăng `LLM_TIMEOUT_SECONDS=120` để phòng tránh vấn đề này.
  - Bạn có thể làm ấm (warm-up) trước mô hình bằng lệnh:
    ```bash
    docker exec homing-ollama ollama run qwen2.5:7b "Hi"
    ```
  - Các lần gọi tiếp theo mô hình đã lưu sẵn trong bộ nhớ đệm, tốc độ phản hồi chỉ từ 1 – 2 giây.

### 3. Cổng bị chiếm dụng (Port Conflict)
- Nếu cổng `80`, `8000`, `1883`, hoặc `11434` bị chiếm dụng bởi ứng dụng khác:
  ```powershell
  # Kiểm tra tiến trình chiếm cổng (trên Windows PowerShell):
  Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess
  ```
  Hoặc dừng nhanh bằng:
  ```powershell
  npx kill-port 8000
  ```

### 4. Kiểm tra mức tiêu thụ VRAM thực tế của GPU
Trong khi AI đang sinh câu trả lời, bạn có thể mở một cửa sổ terminal riêng để theo dõi mức sử dụng VRAM:
```powershell
nvidia-smi -l 1
```
*(Tham số `-l 1` sẽ làm mới thông số GPU mỗi 1 giây một lần).*

---

## 7. Các Lệnh Tiện Ích Thường Dùng

| Thao tác | Lệnh thực hiện |
| :--- | :--- |
| **Khởi động toàn bộ hệ thống** | `docker compose up -d` |
| **Dừng toàn bộ hệ thống** | `docker compose down` |
| **Xem log thời gian thực của Ollama** | `docker logs -f homing-ollama` |
| **Xem log của Backend Hub** | `docker logs -f smart-home-iot-agent-backend-1` |
| **Kiểm tra danh sách model Ollama** | `docker exec homing-ollama ollama list` |
| **Xóa một model cũ giải phóng ổ cứng** | `docker exec homing-ollama ollama rm <tên_model>` |
| **Chạy kiểm thử tự động toàn hệ thống** | `pytest tests -q` |
