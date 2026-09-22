# Danh sách Công việc: HomeMind Hub (P-140)

## Giai đoạn 1: Nền tảng Cốt lõi và MVP

- [x] Thiết lập cấu hình repository, môi trường ảo và các phụ thuộc trong pyproject.toml
- [x] Cài đặt hệ thống Codex lifecycle hooks (UserPromptSubmit, Stop) và công cụ nộp session log
- [x] Xây dựng cấu trúc backend bất đồng bộ FastAPI với các định tuyến REST và endpoint kiểm tra sức khỏe
- [x] Cấu hình broker Eclipse Mosquitto MQTT và client pub/sub bất đồng bộ không gây nghẽn
- [x] Xây dựng giao diện dashboard React ban đầu để bật/tắt thiết bị và hiển thị dữ liệu cảm biến
- [x] Lập trình bộ giả lập thiết bị cục bộ và registry trạng thái bằng Python

## Giai đoạn 2: Bộ não Agent và Phần cứng

- [x] Xây dựng bộ điều phối agent trên LangGraph với quy trình lập kế hoạch LLM và liên kết công cụ
- [x] Phát triển bộ parser quy tắc tất định tiếng Việt để thực thi lệnh dưới 50ms
- [x] Viết firmware C++ cho vi điều khiển ESP32 điều khiển relay và đọc thông số cảm biến DHT/MQ
- [x] Hoàn thiện sơ đồ nguyên lý mạch điện tử cho 2 node phần cứng ESP32
- [x] Cài đặt cơ chế lưu trữ bền vững trạng thái registry thiết bị qua tệp JSON sau khi khởi động lại

## Giai đoạn 3: Runtime Giọng nói Biên

- [x] Tích hợp mô hình nhận dạng giọng nói Sherpa-ONNX Zipformer int8 tiếng Việt trên CPU
- [x] Thiết lập container tổng hợp giọng nói Piper neural TTS với mô hình vi_VN-vais1000-medium
- [x] Cài đặt VAD phía trình duyệt (tự động ngắt thu âm sau 2 giây im lặng dựa trên năng lượng)
- [x] Thêm backend energy VAD để cắt bỏ các khung âm thanh im lặng trước và sau khi xử lý STT
- [x] Thiết lập chốt xác thực mã PIN (PIN 2004) cho thao tác mở khóa cửa nhạy cảm
- [x] Hoàn thiện tài liệu nghiệm thu Gate 2, cập nhật PRD và hồ sơ đánh giá cột mốc

## Giai đoạn 4: Tự động Phát hiện Thiết bị và Bảng điều khiển

- [x] Triển khai giao thức tự động quét và phát hiện thiết bị trên topic MQTT homing/discovery
- [x] Tái cấu trúc luồng broadcast phát hiện trên ESP32 sang dạng bất đồng bộ non-blocking để ngăn tràn socket WiFi
- [x] Xây dựng bộ phân giải cấu trúc phòng động kèm tổng hợp dữ liệu cảm biến (nhiệt độ, độ ẩm, chất lượng không khí)
- [x] Thiết kế lại giao diện người dùng với bố cục HomeDashboard, panel mạch điện và thanh tóm tắt thời gian thực
- [x] Thêm cảnh báo kết nối mạng thời gian thực, bảng điều khiển tiêm lỗi và hỗ trợ hiển thị trên thiết bị di động

## Giai đoạn 5: Môi trường Giả lập và Sẵn sàng Triển khai

- [x] Phát triển sandbox Web Simulator độc lập (frontend-simulator/) với mặt bằng căn hộ trên 2D Canvas
- [x] Tích hợp góc nhìn 3D trực quan và bộ kiểm thử tự động đầu cuối Playwright
- [x] Viết script chạy benchmark GPU CUDA (benchmarks/benchmark_models.py) cho các mô hình Qwen cục bộ
- [x] Đánh giá hiệu năng Qwen2.5-3B-Instruct và Qwen2.5-1.5B trong giới hạn phần cứng 4GB VRAM
- [x] Biên soạn bộ dữ liệu đánh giá chuẩn 134 ca kiểm thử tiếng Việt kèm mẫu bẫy ảo giác và thang điểm
- [x] Module hóa smart_home_tools thành các tệp chuyên biệt (công cụ đèn, nhiệt độ, an ninh, ngữ cảnh, hẹn giờ)
- [x] Bổ sung các công cụ hẹn giờ đếm ngược cho thiết bị (set_device_timer, list_device_timers, cancel_device_timer)
- [x] Thiết lập luồng CI/CD GitHub Actions cho self-hosted runner và triển khai tự động lên Raspberry Pi
- [x] Tích hợp MQTT Last Will and Testament (LWT) và tách biệt heartbeat watchdog để theo dõi kết nối thiết bị
