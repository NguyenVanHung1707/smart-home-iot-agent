# Môi trường Giả lập Nhà thông minh MQTT

## Tổng quan

Môi trường Giả lập Nhà thông minh (Virtual Home Lab) cung cấp môi trường kiểm thử cục bộ tích hợp dịch vụ FastAPI, broker Eclipse Mosquitto MQTT, bảng điều khiển React, sandbox mô phỏng căn hộ tương tác trên 2D Canvas cùng các runtime xử lý giọng nói và ngôn ngữ cục bộ.

## Khởi chạy Lab

Khởi chạy stack cơ bản (FastAPI, broker Mosquitto MQTT, sandbox giả lập thiết bị và dashboard React):

```bash
docker compose up --build
```

Khởi chạy toàn bộ stack kèm mô hình suy luận LLM Qwen cục bộ:

```bash
docker compose --profile local-llm up --build
```

Hoặc sử dụng script tiện ích:

```bash
bash scripts/docker.sh up full
```

## Địa chỉ dịch vụ

- Backend API: `http://localhost:8000` (Tài liệu OpenAPI tại `http://localhost:8000/docs`).
- React Dashboard (`frontend/`): `http://localhost:5173` trong chế độ phát triển, hoặc `http://localhost/` khi triển khai qua Nginx trong Docker Compose. Cung cấp thẻ điều khiển thiết bị, tương tác giọng nói, thông số cảm biến theo phòng và nhật ký kiểm toán.
- Virtual Home Sandbox (`frontend-simulator/`): `http://localhost:8001` (được phục vụ trực tiếp bởi `src/simulator.py`, với Vite dev server tại `http://localhost:5173` đóng vai trò proxy API). Hiển thị sơ đồ mặt bằng 2D Canvas tương tác đại diện cho các phòng, nút bật/tắt thiết bị, số liệu cảm biến thời gian thực và bảng điều khiển tiêm lỗi.
- MQTT Broker: Cổng 1883 cho kết nối TCP MQTT, Cổng 9001 cho kết nối WebSocket.
- Máy chủ LLM cục bộ (`llama.cpp`): `http://localhost:8080/v1`.

## Cấu hình mô hình Qwen

HomeMind sử dụng mô hình Qwen (`Qwen2.5-3B-Instruct` hoặc `Qwen2.5-1.5B` ở định dạng GGUF) được phục vụ qua `llama.cpp`.

Để kích hoạt tính năng phân tích ý định ngôn ngữ tự nhiên với Qwen, cấu hình tệp `.env`:

```env
LLM_ENABLED=true
MODEL_NAME=qwen2.5-3b-instruct-q4_k_m.gguf
LLAMA_MODEL_FILE=qwen2.5-3b-instruct-q4_k_m.gguf
LLAMA_BASE_URL=http://localhost:8080/v1
```

Các yêu cầu ngôn ngữ tự nhiên được chuyển đổi thành kế hoạch thực thi công cụ dưới dạng JSON có cấu trúc. Nếu dịch vụ Qwen không thể kết nối, trả về JSON sai định dạng hoặc gặp câu lệnh mơ hồ, hệ thống sẽ tự động chuyển sang bộ parser quy tắc tiếng Việt tất định để xử lý an toàn.

Các thao tác an ninh quan trọng như mở khóa cửa yêu cầu quy trình phê duyệt mã PIN rõ ràng (mã PIN mặc định: 2004). Lệnh mở khóa cửa sẽ được giữ ở trạng thái chờ (pending) cho đến khi người dùng nhập đúng mã PIN xác thực qua Hub.

## Hợp đồng MQTT

Mọi giao tiếp thiết bị đều tuân thủ cấu trúc topic MQTT với tiền tố đã cấu hình (`homing`):

- Lệnh điều khiển từ Hub đến thiết bị: `homing/devices/{device_id}/command`
- Cập nhật trạng thái từ thiết bị về Hub: `homing/devices/{device_id}/state`
- Xác nhận thực thi lệnh: `homing/devices/{device_id}/ack`
- Tiêm lỗi giả lập: `homing/simulator/{device_id}/fault`
- Tự động phát hiện thiết bị trên mạng: `homing/discovery`

Mỗi payload JSON chứa các trường định danh chuẩn:
- `schema_version`: Phiên bản giao thức (kiểu số nguyên).
- `event`: Tên định danh sự kiện (ví dụ: `command`, `state`, `ack`, `discovery`).
- `device_id`: Mã định danh duy nhất của thiết bị mục tiêu.
- `timestamp`: Dấu thời gian ISO-8601 theo chuẩn UTC.
- `command_id`: Mã định danh tương quan dùng chung giữa lệnh điều khiển và gói tin phản hồi ack.

## Quy trình kiểm thử thủ công

1. Điều khiển thiết bị: Bật hoặc tắt đèn (`living_light`) trên React Dashboard hoặc trong sandbox 2D Canvas. Xác minh trạng thái được đồng bộ trên cả hai giao diện và gói tin phản hồi MQTT ACK được ghi nhận thành công.
2. Tiêm lỗi quá thời gian (Timeout): Chọn một thiết bị trong trình giả lập, đặt chế độ lỗi thành `timeout`, sau đó gửi lệnh bật/tắt từ bảng điều khiển. Xác nhận rằng Hub ghi nhận lỗi quá thời gian và trạng thái thiết bị không bị thay đổi.
3. Tiêm lỗi mất kết nối (Offline): Đặt chế độ lỗi của thiết bị thành `offline`. Xác minh rằng giao diện hiển thị ngay lập tức trạng thái thiết bị bị ngắt kết nối. Đặt lại chế độ lỗi về bình thường và kiểm tra thiết bị tự động kết nối lại.
4. Xác minh bảo mật mã PIN: Gửi lệnh giọng nói hoặc văn bản yêu cầu mở khóa cửa chính (`door_lock`). Xác minh rằng Hub giữ lệnh ở trạng thái chờ phê duyệt cho đến khi nhập mã PIN 2004. Xác minh việc nhập sai mã PIN sẽ từ chối yêu cầu mở khóa.
5. Đồng bộ hóa Canvas: Xác minh rằng việc thay đổi trạng thái thiết bị thông qua lệnh MQTT hoặc gọi API REST sẽ cập nhật màu sắc chỉ báo và giá trị cảm biến trên mặt bằng 2D Canvas theo thời gian thực.
