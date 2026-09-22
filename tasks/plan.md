# Kế hoạch Triển khai Dự án: HomeMind Hub (P-140)

## Tổng quan

Lộ trình kỹ thuật phát triển nền tảng nhà thông minh tại biên HomeMind Hub. Kế hoạch gồm 5 giai đoạn phát triển bao gồm dịch vụ lõi, luồng quyết định agent, runtime giọng nói cục bộ, bảng điều khiển tự động phát hiện thiết bị và môi trường mô phỏng sẵn sàng vận hành.

## Lộ trình 5 Giai đoạn phát triển

### Giai đoạn 1: Nền tảng Cốt lõi và MVP

- [x] Xây dựng khung backend bất đồng bộ FastAPI với các endpoint RESTful.
- [x] Cấu hình broker Eclipse Mosquitto MQTT với schema JSON định kiểu cho command, state và ack.
- [x] Phát triển giao diện React ban đầu (`frontend/`) để giám sát và điều khiển trạng thái thiết bị.
- [x] Cài đặt hệ thống Codex lifecycle hooks (`UserPromptSubmit`, `Stop`) và công cụ nộp log tự động qua pre-push hook.
- [x] Xây dựng bộ giả lập thiết bị ban đầu và registry lưu trên bộ nhớ phục vụ kiểm thử cục bộ.

### Giai đoạn 2: Bộ não Agent và Phần cứng

- [x] Triển khai điều phối agent trên LangGraph hỗ trợ gọi công cụ và quản lý ngữ cảnh hội thoại.
- [x] Phát triển bộ parser tất định (deterministic parser) cho câu lệnh tiếng Việt giúp xử lý nhanh với độ trễ thấp.
- [x] Lập trình kiến trúc firmware vi điều khiển ESP32 giao tiếp với relay và cảm biến.
- [x] Hoàn thiện sơ đồ nguyên lý mạch điện tử cho 2 node phần cứng ESP32.
- [x] Cài đặt cơ chế lưu trữ trạng thái thiết bị vào tệp dữ liệu duy trì qua các lần khởi động lại.

### Giai đoạn 3: Runtime Giọng nói Biên

- [x] Tích hợp mô hình nhận dạng giọng nói Sherpa-ONNX Zipformer int8 cho tiếng Việt chạy offline trên CPU.
- [x] Triển khai container Piper neural TTS với mô hình giọng đọc `vi_VN-vais1000-medium` để phát phản hồi âm thanh.
- [x] Cài đặt cơ chế Voice Activity Detection kép: client-side VAD trên trình duyệt và backend energy VAD.
- [x] Thiết lập chốt chặn an toàn mã PIN (PIN 2004) bắt buộc phê duyệt cho các hành động nhạy cảm như mở khóa cửa.
- [x] Hoàn tất tài liệu kiến trúc Gate 2, đối soát PRD và đánh giá các cột mốc dự án.

### Giai đoạn 4: Tự động Phát hiện Thiết bị và Bảng điều khiển

- [x] Phát triển giao thức tự động quét và phát hiện thiết bị (auto-discovery) bất đồng bộ giữa backend và ESP32.
- [x] Sửa lỗi tràn socket WiFi trên ESP32 bằng cách tách biệt luồng broadcast phát hiện khỏi vòng lặp mạng.
- [x] Xây dựng bộ phân giải cấu trúc phòng động (dynamic room topology resolver) kèm tổng hợp dữ liệu cảm biến (nhiệt độ, độ ẩm, khí gas).
- [x] Tái thiết kế giao diện với bố cục HomeDashboard, panel mạch điện và thanh tóm tắt thông số theo thời gian thực.
- [x] Bổ sung cảnh báo trạng thái kết nối thời gian thực và bảng điều khiển tiêm lỗi MQTT.

### Giai đoạn 5: Môi trường Giả lập và Sẵn sàng Triển khai

- [x] Xây dựng ứng dụng sandbox Web Simulator độc lập (`frontend-simulator/`) với 2D Canvas tương tác và hiển thị 3D.
- [x] Triển khai bộ kiểm thử tự động đầu cuối (E2E) bằng Playwright cho simulator và luồng điều khiển.
- [x] Xây dựng bộ công cụ benchmark GPU CUDA và CPU đánh giá các mô hình Qwen cục bộ (Qwen2.5-3B, Qwen2.5-1.5B) trong giới hạn 4GB VRAM.
- [x] Xây dựng bộ dữ liệu đánh giá chuẩn gồm 134 ca kiểm thử tiếng Việt với các mẫu bẫy ảo giác và tiêu chí chấm điểm.
- [x] Tách mã nguồn smart_home_tools thành các mô-đun chức năng riêng biệt (`light_tools.py`, `climate_tools.py`, `security_tools.py`, `scene_tools.py`, `timer_tools.py`).
- [x] Cấu hình pipeline CI/CD GitHub Actions sử dụng self-hosted runner và triển khai tự động lên Raspberry Pi.
- [x] Triển khai MQTT Last Will and Testament (LWT) kết hợp cơ chế heartbeat watchdog độc lập để xử lý ngắt kết nối thiết bị.

## Điểm Kiểm định Chất lượng

- [x] Toàn bộ test backend lõi, adapter giả lập và REST routes chạy thành công.
- [x] Runtime giọng nói tại biên nhận dạng âm thanh tiếng Việt đạt độ trễ mục tiêu (< 500ms trên CPU).
- [x] Quy trình xác thực mã PIN bảo vệ an toàn cho yêu cầu mở khóa cửa trước các lệnh chưa xác thực.
- [x] Cơ chế quét phát hiện tự động nhận diện chính xác các node ESP32 mà không gây nghẽn socket WiFi.
- [x] Sandbox 2D Canvas đồng bộ hai chiều trạng thái MQTT không xảy ra mất gói tin.
- [x] Điểm số trên tập dữ liệu đánh giá chuẩn vượt ngưỡng yêu cầu về độ chính xác gọi công cụ và khả năng kháng ảo giác.
- [x] Bộ kiểm thử tự động chạy thành công không có lỗi phát sinh (`463 passed, 1 skipped`).
