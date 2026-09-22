# Nhật ký Hàng tuần: Đội ngũ P-140 (HomeMind Hub)

> Ghi lại tiến độ theo từng tuần: mục tiêu, kết quả đạt được, khó khăn và giải pháp, bài học kinh nghiệm và kế hoạch tiếp theo.

---

## Tuần 1: 2026-07-24 đến 2026-08-02

### Mục tiêu tuần này
- [x] Khởi tạo repository, cấu hình pyproject.toml và môi trường phát triển
- [x] Cài đặt hệ thống Codex lifecycle hooks và script tự động nộp session log AI
- [x] Xây dựng khung FastAPI backend và dịch vụ kết nối MQTT bất đồng bộ
- [x] Hoàn thành bộ tài liệu Gate 1 (Brief, PRD, Wireframe/UI Flow)

### Đã hoàn thành
- Thiết lập cấu hình dự án với Python 3.11+ và các thư viện cốt lõi (FastAPI, paho-mqtt, Pydantic).
- Xây dựng hooks.json hỗ trợ sự kiện UserPromptSubmit và Stop để lưu vết tương tác AI theo quy định.
- Tạo script tự động gửi session log lên grading server và gắn vào git pre-push hook.
- Xây dựng dịch vụ MQTT bất đồng bộ ban đầu để dispatch và lắng nghe trạng thái thiết bị.
- Hoàn tất hồ sơ Gate 1 gồm PRD chi tiết, kiến trúc hệ thống và wireframe luồng người dùng.

### Khó khăn và Giải pháp
| Khó khăn | Giải pháp | Kết quả |
|---|---|---|
| Cần ghi nhận đầy đủ session log AI theo quy định mà không làm chậm thao tác commit/push | Cài đặt local Codex hooks gọn nhẹ và viết script pre-push kiểm tra tính hợp lệ của log trước khi upload | Hệ thống tự động lưu vết 100% prompt và archive log hợp lệ trước mỗi đợt push |
| Kết nối MQTT client trong FastAPI nếu dùng vòng lặp blocking sẽ gây trễ các HTTP request | Sử dụng paho-mqtt client với cơ chế loop_start() chạy nền bất đồng bộ và cơ chế queue | API backend phản hồi dưới 15ms trong khi vẫn duy trì kết nối MQTT ổn định |

### Bài học kinh nghiệm
- Thiết lập quy trình kiểm soát log và kiến trúc bất đồng bộ ngay từ tuần đầu tiên giúp giảm thiểu nợ kỹ thuật cho các sprint sau.
- Tài liệu Gate 1 cần bám sát ràng buộc phần cứng thực tế để tránh thay đổi lớn về kiến trúc sau này.

### Kế hoạch tuần sau
- [ ] Tích hợp LangGraph Agent để lập kế hoạch và thực thi công cụ smart home
- [ ] Xây dựng bộ deterministic parser cho câu lệnh tiếng Việt phổ biến
- [ ] Khởi tạo mã nguồn firmware ESP32 và thiết kế sơ đồ mạch nguyên lý

---

## Tuần 2: 2026-08-03 đến 2026-08-09

### Mục tiêu tuần này
- [x] Tích hợp LangGraph Agent controller với quy trình phân tích ý định và gọi công cụ
- [x] Xây dựng bộ parser tất định (deterministic parser) xử lý nhanh câu lệnh tiếng Việt
- [x] Khởi tạo firmware ESP32 cho các node điều khiển thiết bị và thu thập cảm biến
- [x] Cập nhật sơ đồ nguyên lý mạch phần cứng smart home

### Đã hoàn thành
- Cài đặt Agent state graph trên LangGraph kết nối LLM planning với bộ công cụ điều khiển thiết bị.
- Phát triển bộ deterministic regex parser ưu tiên xử lý các câu lệnh bật/tắt đèn, điều chỉnh nhiệt độ, quạt gió mà không cần qua LLM.
- Xây dựng firmware ESP32 kết nối mạng WiFi và giao thức MQTT gửi/nhận bản tin JSON.
- Vẽ và cập nhật sơ đồ nguyên lý mạch điện tử cho 2 nút ESP32 điều khiển relay và cảm biến DHT11/MQ-2.
- Hoàn thiện mô hình simulator thiết bị phục vụ kiểm thử lập trình local.

### Khó khăn và Giải pháp
| Khó khăn | Giải pháp | Kết quả |
|---|---|---|
| LLM phát sinh độ trễ cao (1-3s) và có thể sinh JSON không hợp lệ khi thực hiện các lệnh đơn giản | Xây dựng tầng deterministic parser bắt cấu trúc câu trước; chỉ chuyển sang LangGraph LLM khi câu lệnh phức tạp hoặc mang tính suy luận | Các lệnh thông dụng đạt thời gian phản hồi dưới 50ms với độ chính xác 100% |
| Firmware ESP32 dễ bị treo nếu mạng WiFi bị mất kết nối đột ngột | Cài đặt cơ chế non-blocking reconnect với watchdog timer kiểm tra định kỳ | Node ESP32 tự động khôi phục kết nối trong vòng 3 giây sau khi sóng mạng ổn định |

### Bài học kinh nghiệm
- Mô hình lai (hybrid architecture) giữa rule-based deterministic parser và LLM agent mang lại sự cân bằng giữa tốc độ xử lý và khả năng hiểu ngôn ngữ linh hoạt.

### Kế hoạch tuần sau
- [ ] Tích hợp runtime giọng nói offline với Sherpa-ONNX Zipformer int8 và Piper TTS
- [ ] Phát triển cơ chế xác thực mã PIN bảo mật cho thao tác mở khóa cửa
- [ ] Chuẩn bị hồ sơ nghiệm thu Gate 2

---

## Tuần 3: 2026-08-10 đến 2026-08-16

### Mục tiêu tuần này
- [x] Chuyển đổi STT sang mô hình Zipformer int8 chạy trên CPU nhẹ và ổn định
- [x] Tích hợp Piper neural TTS tiếng Việt phát âm thanh phản hồi
- [x] Cài đặt cơ chế Voice Activity Detection (VAD) trên cả browser và backend
- [x] Xây dựng quy trình xác thực mã PIN an toàn cho thao tác mở khóa cửa
- [x] Hoàn tất hồ sơ và báo cáo Gate 2

### Đã hoàn thành
- Tích hợp sherpa-onnx Zipformer int8 tiếng Việt, loại bỏ Whisper giúp tiết kiệm 70% bộ nhớ RAM trên thiết bị biên.
- Triển khai container Piper TTS với giọng đọc tiếng Việt vi_VN-vais1000-medium.
- Cài đặt dual VAD: client-side VAD tự động ngắt ghi âm sau 2 giây im lặng và backend energy VAD loại bỏ khoảng lặng.
- Xây dựng quy trình xác thực mã PIN 2004 cho lệnh mở cửa: lệnh mở khóa được giữ ở trạng thái pending cho đến khi nhập đúng PIN.
- Hiệu chỉnh phần cứng 2 mạch ESP32 đồng bộ với hệ thống broker và hoàn thành báo cáo Gate 2.

### Khó khăn và Giải pháp
| Khó khăn | Giải pháp | Kết quả |
|---|---|---|
| Whisper chiếm nhiều RAM và có độ trễ vượt quá 3 giây trên Raspberry Pi | Thay thế bằng Sherpa-ONNX Zipformer int8 được lượng tử hóa | STT chạy trực tiếp trên CPU với độ trễ < 500ms và chỉ chiếm chưa đầy 300MB RAM |
| Thao tác mở cửa nhà có thể bị kích hoạt ngoài ý muốn qua giọng nói hoặc ảo giác của mô hình | Thiết kế quy trình phê duyệt mã PIN hai bước: phát sinh pending approval và bắt buộc người dùng nhập mã PIN 2004 qua giao diện/API | Ngăn chặn rủi ro mở cửa trái phép |

### Bài học kinh nghiệm
- Tính an toàn của nhà thông minh phải được bảo vệ ở cấp kiến trúc (architectural guardrail), không phụ thuộc vào suy luận của mô hình ngôn ngữ.

### Kế hoạch tuần sau
- [ ] Phát triển cơ chế network-wide auto-discovery cho thiết bị ESP32
- [ ] Tái thiết kế giao diện người dùng theo bố cục circuit panel và summary rail
- [ ] Giải quyết các vấn đề kết nối và độ ổn định mạng trên firmware

---

## Tuần 4: 2026-08-17 đến 2026-08-23

### Mục tiêu tuần này
- [x] Xây dựng giao thức tự động phát hiện thiết bị trên mạng (auto-discovery)
- [x] Khắc phục lỗi tràn bộ đệm socket WiFi trên firmware ESP32
- [x] Nâng cấp giao diện dashboard với bố cục circuit panel và summary rail
- [x] Xây dựng dynamic room topology resolver để phục vụ truy vấn ngữ cảnh

### Đã hoàn thành
- Phát triển tính năng auto-discovery scan trên Hub với topic MQTT homing/discovery và giao diện quét mạng trực quan.
- Tối ưu firmware ESP32 với cơ chế broadcast bất đồng bộ, triệt tiêu lỗi tràn socket WiFi.
- Xây dựng dynamic room topology resolver hỗ trợ truy vấn cảm biến (nhiệt độ, độ ẩm, khí gas) theo phòng.
- Tái cấu trúc layout HomeDashboard với circuit panel hiển thị nguồn điện và summary rail tổng hợp thông số.
- Thêm bộ lọc thiết bị theo phòng và cảnh báo kết nối mạng theo thời gian thực.

### Khó khăn và Giải pháp
| Khó khăn | Giải pháp | Kết quả |
|---|---|---|
| Khi Hub phát yêu cầu quét thiết bị, ESP32 gửi broadcast đồng bộ gây tràn socket WiFi (socket overflow) và ngắt kết nối | Chuyển luồng phản hồi discovery trên ESP32 sang dạng asynchronous non-blocking và chèn cơ chế backoff | ESP32 gửi bản tin phát hiện ổn định 100%, không còn hiện tượng rớt WiFi khi quét mạng |
| Giao diện ban đầu chưa thể hiện rõ ràng trạng thái từng phòng và tính sẵn sàng của các nút mạch điện | Thiết kế lại Dashboard với circuit panel và summary rail giúp người dùng quan sát hệ thống trên một màn hình | Giao diện rõ ràng, trực quan và hỗ trợ hiển thị tốt trên cả thiết bị di động |

### Bài học kinh nghiệm
- Lập trình nhúng trên vi điều khiển có bộ nhớ hạn chế như ESP32 yêu cầu phải cẩn thận với mọi thao tác I/O mạng; không được gọi socket đồng bộ trong vòng lặp sự kiện.

### Kế hoạch tuần sau
- [ ] Xây dựng sandbox Web Simulator 2D Canvas độc lập cho kiểm thử ảo
- [ ] Chuẩn hóa bộ dữ liệu đánh giá 134 mẫu câu tiếng Việt (golden dataset)
- [ ] Benchmark mô hình Qwen dưới giới hạn 4GB VRAM và thiết lập CI/CD tự động lên Raspberry Pi

---

## Tuần 5: 2026-08-24 đến 2026-08-29

### Mục tiêu tuần này
- [x] Xây dựng Web Simulator sandbox với 2D Canvas và tích hợp Three.js 3D view
- [x] Xây dựng bộ dữ liệu golden evaluation 134 mẫu câu kèm hallucination probes
- [x] Benchmark hiệu năng các mô hình Qwen (Qwen2.5-3B, Qwen2.5-1.5B) với GPU CUDA và 4GB VRAM
- [x] Module hóa các công cụ smart home thành từng file chuyên biệt
- [x] Thiết lập pipeline CI/CD GitHub Actions cho self-hosted runner và deploy tự động lên Raspberry Pi
- [x] Xử lý ngắt kết nối thiết bị đột ngột với MQTT LWT và watchdog riêng biệt

### Đã hoàn thành
- Xây dựng ứng dụng frontend-simulator độc lập trên nền 2D Canvas mô phỏng căn hộ và hỗ trợ Playwright E2E tests.
- Biên soạn bộ dữ liệu đánh giá chuẩn gồm 134 ca kiểm thử tiếng Việt bao gồm các tình huống thực thi, mơ hồ và chống ảo giác.
- Viết script benchmark tự động (benchmarks/benchmark_models.py) đánh giá tốc độ và độ chính xác của các biến thể Qwen.
- Refactor toàn bộ smart_home_tools thành các module độc lập (light, climate, security, scene, timer tools).
- Cài đặt công cụ hẹn giờ đếm ngược cho thiết bị (set_device_timer, list_device_timers, cancel_device_timer).
- Cấu hình GitHub Actions CI/CD sử dụng self-hosted runner kết hợp Cloudflare Tunnel triển khai tự động lên Raspberry Pi.
- Tích hợp MQTT Last Will and Testament (LWT) giúp phát hiện ngay lập tức khi node phần cứng mất nguồn đột ngột.

### Khó khăn và Giải pháp
| Khó khăn | Giải pháp | Kết quả |
|---|---|---|
| Chạy benchmark mô hình LLM trên phần cứng giới hạn 4GB VRAM dễ bị Out-Of-Memory (OOM) | Sử dụng lượng tử hóa 4-bit (Q4_K_M), giới hạn context window 8192 token và cấu hình server llama.cpp với thread pinning tối ưu | Qwen2.5-3B-Instruct hoạt động ổn định với ~2.2GB VRAM, đạt tốc độ 28+ tokens/s trên GPU và xử lý tốt bộ 134 test cases |
| Pipeline CI/CD cần deploy tự động lên Raspberry Pi nằm sau mạng NAT nội bộ mà không mở port router | Cấu hình Cloudflare Tunnel (cloudflared) kết hợp GitHub Actions self-hosted runner | Pipeline tự động build, test và deploy lên Pi ổn định và an toàn |
| Khi thiết bị phần cứng bị rút nguồn đột ngột, hệ thống vẫn giữ trạng thái online trong vài phút | Tích hợp MQTT LWT vào broker và tách riêng heartbeat watchdog để đánh dấu offline sau 15 giây | Hub cập nhật trạng thái thiết bị mất kết nối gần như tức thì |

### Bài học kinh nghiệm
- Xây dựng sandbox mô phỏng 2D song song với phần cứng thật giúp đẩy nhanh tiến độ kiểm thử tự động mà không phụ thuộc vào việc có mặt trực tiếp tại phòng lab.
- Việc module hóa công cụ và có bộ test case chuẩn giúp hệ thống dễ bảo trì và mở rộng tính năng mới an toàn.
