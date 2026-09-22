# Nhật ký Công việc: Đội ngũ P-140 (HomeMind Hub)

> Ghi lại toàn bộ công việc đã làm theo ngày của từng thành viên, kèm theo kết quả đầu ra và commit/PR tương ứng.

---

## 2026-08-02

| Thành viên | Công việc | Trạng thái | Đầu ra | Thời gian |
|---|---|---|---|---|
| cronusnd1404 (Bùi Ngọc Đạt) | Cài đặt project-local Codex lifecycle hooks (UserPromptSubmit, Stop), script nộp session log và pre-push hook | Hoàn thành | Commits `fadeff8`, `00a2d11`, `b628c47`, `3fc1652`, `ca7d24f` | 3.5h |
| minhpq-vn (Phạm Quốc Minh) | Soạn thảo hồ sơ Gate 1 gồm Project Brief, PRD và Wireframe/UI Flow | Hoàn thành | Commits `468c235`, `1233d92`, docs/brief.md, docs/prd.md | 3.0h |
| buithutrang90412 (Bùi Thu Trang) | Thiết lập tài liệu repository, branch docs và khởi tạo worklog | Hoàn thành | Commit `c83f4c9` | 1.0h |
| cronusnd1404 (Bùi Ngọc Đạt) | Xây dựng non-blocking MQTT service và khởi tạo ứng dụng React ban đầu | Hoàn thành | Commits `a405187`, `41bd8a8`, `f83364b` | 2.5h |

**Tổng kết ngày:** Hoàn thành khởi tạo repo, hệ thống Codex AI logging tự động và hồ sơ nghiệm thu Gate 1.

---

## 2026-08-05

| Thành viên | Công việc | Trạng thái | Đầu ra | Thời gian |
|---|---|---|---|---|
| cronusnd1404 (Bùi Ngọc Đạt) | Bổ sung tài liệu MQTT simulator report, tích hợp container llama.cpp server và cấu hình AI logging | Hoàn thành | PR #4, commits `513137f`, `06dde03`, `144fe74` | 3.0h |
| minhpq-vn (Phạm Quốc Minh) | Cải tiến script logging AI, sửa lỗi CLI và merge đồng bộ branch develop | Hoàn thành | Commits `497d496`, `73c6871`, `59ee038`, `afbfc08` | 2.5h |
| NguyenVanHung1707 (Nguyễn Văn Hùng) | Thiết kế sơ đồ luồng điều khiển AI agent và proactive automation flow | Hoàn thành | Commit `adb3453`, docs/ai_agent_flow.md, docs/proactive_automation_flow.md | 2.0h |

**Tổng kết ngày:** Ổn định hệ thống AI logging, bổ sung sơ đồ kiến trúc Agent và tích hợp llama.cpp vào Docker stack.

---

## 2026-08-06

| Thành viên | Công việc | Trạng thái | Đầu ra | Thời gian |
|---|---|---|---|---|
| cronusnd1404 (Bùi Ngọc Đạt) | Xây dựng LangGraph-based agent controller tích hợp LLM planning và gọi smart-home tools | Hoàn thành | Commit `92a5bfc` | 4.0h |
| buithutrang90412 (Bùi Thu Trang) | Xây dựng giao diện role-based frontend mock cho HomeMind | Hoàn thành | Commit `ecb0ef7` | 3.0h |
| NguyenVanHung1707 (Nguyễn Văn Hùng) | Thiết kế và cập nhật sơ đồ nguyên lý mạch phần cứng 2 ESP32 | Hoàn thành | Commits `4182e39`, `df5a49f` | 2.5h |

**Tổng kết ngày:** Tích hợp thành công Agent state graph trên LangGraph và cập nhật sơ đồ mạch phần cứng 2 ESP32.

---

## 2026-08-08

| Thành viên | Công việc | Trạng thái | Đầu ra | Thời gian |
|---|---|---|---|---|
| cronusnd1404 (Bùi Ngọc Đạt) | Cài đặt bộ parser tất định (deterministic parser) cho các câu lệnh tiếng Việt thông dụng | Hoàn thành | Commits `a833f2a`, `2a40217` | 3.5h |
| NguyenVanHung1707 (Nguyễn Văn Hùng) | Phát triển firmware ESP32 kết nối MQTT, đọc cảm biến và điều khiển relay | Hoàn thành | Commit `78a9bc1` | 3.5h |

**Tổng kết ngày:** Hoàn thiện firmware cơ sở cho ESP32 và giảm độ trễ xử lý lệnh tiếng Việt với deterministic parser.

---

## 2026-08-10

| Thành viên | Công việc | Trạng thái | Đầu ra | Thời gian |
|---|---|---|---|---|
| cronusnd1404 (Bùi Ngọc Đạt) | Chuyển đổi STT sang Sherpa-ONNX Zipformer int8, tích hợp Piper TTS và tối ưu xử lý tiếng Việt | Hoàn thành | Commits `b8baba3`, `9e52333`, `3f5bc34`, `e5454f7`, `a31c4e6` | 4.5h |

**Tổng kết ngày:** Hoàn tất chuyển đổi sang Zipformer int8 offline trên CPU và tích hợp TTS tiếng Việt Piper cho voice runtime.

---

## 2026-08-11

| Thành viên | Công việc | Trạng thái | Đầu ra | Thời gian |
|---|---|---|---|---|
| cronusnd1404 (Bùi Ngọc Đạt) | Thêm backend VAD lọc khoảng lặng, hiển thị runtime Zipformer trên UI và chuẩn bị Docker models | Hoàn thành | PR #10, commits `aca73a7`, `8a621d7`, `1552a89`, `695bd10`, `ce81e1a` | 3.5h |
| NguyenVanHung1707 (Nguyễn Văn Hùng) | Đồng bộ và hiệu chỉnh phần cứng 2 mạch ESP32 smart home giao tiếp MQTT | Hoàn thành | PR #8, PR #9, commit `b8b3401` | 3.0h |
| minhpq-vn (Phạm Quốc Minh) | Review và merge PR #7, PR #8, PR #9, PR #10 vào develop | Hoàn thành | Commits `886f17a`, `cf8fc5a`, `f6d6ba6`, `3e9c2ff` | 1.5h |

**Tổng kết ngày:** Kiểm thử đồng bộ phần cứng ESP32 và hệ thống voice local Zipformer + Piper trên Docker.

---

## 2026-08-15

| Thành viên | Công việc | Trạng thái | Đầu ra | Thời gian |
|---|---|---|---|---|
| NguyenVanHung1707 (Nguyễn Văn Hùng) | Tích hợp mô hình phần cứng ESP32, xác thực PIN cho mở khóa cửa, định dạng dữ liệu cảm biến | Hoàn thành | Commits `013ed74`, `f6b9fd0`, `4a2b4bb` | 4.0h |
| buithutrang90412 (Bùi Thu Trang) | Phát triển mock frontend application với data hooks, điều khiển thiết bị và voice interaction | Hoàn thành | Commits `66d7c69`, `3a5dc26`, `2d712c1` | 3.5h |
| minhpq-vn (Phạm Quốc Minh) | Soạn thảo hồ sơ Gate 2, nâng cấp giao diện UI v2 và tinh chỉnh cấu hình CI | Hoàn thành | Commits `b5d6506`, `6c57fea`, `943d96f` | 2.5h |

**Tổng kết ngày:** Hoàn thành cột mốc Gate 2, bổ sung bảo mật mã PIN cho cửa và hoàn thiện firmware non-blocking trên ESP32.

---

## 2026-08-21

| Thành viên | Công việc | Trạng thái | Đầu ra | Thời gian |
|---|---|---|---|---|
| NguyenVanHung1707 (Nguyễn Văn Hùng) | Thêm quản lý thiết bị/phòng, nút quét auto-discovery và broadcast listener trên ESP32 | Hoàn thành | Commits `e8decd0`, `d8999ef`, `94718b7` | 3.5h |
| cronusnd1404 (Bùi Ngọc Đạt) | Xây dựng typed rollout orchestration, canonical control services và rollout safety gates | Hoàn thành | Commits `cc314e4`, `8158d7c`, `102168e`, `45ea08d` | 4.0h |

**Tổng kết ngày:** Bổ sung kiến trúc phát hiện thiết bị tự động và tầng bảo vệ an toàn cho rollout agent.

---

## 2026-08-22

| Thành viên | Công việc | Trạng thái | Đầu ra | Thời gian |
|---|---|---|---|---|
| NguyenVanHung1707 (Nguyễn Văn Hùng) | Sửa lỗi tràn socket WiFi trên ESP32 bằng broadcast bất đồng bộ, gửi broadcast payload và sửa settings.app_env | Hoàn thành | PR #16, commits `63db266`, `78bb577`, `a6b6d97` | 3.5h |
| minhpq-vn (Phạm Quốc Minh) | Review và merge PR #16 cho tính năng thêm thiết bị và ổn định firmware ESP32 | Hoàn thành | Commit `f9d391f` | 1.0h |

**Tổng kết ngày:** Khắc phục lỗi tràn socket WiFi trên ESP32 trong quá trình auto-discovery scan.

---

## 2026-08-24

| Thành viên | Công việc | Trạng thái | Đầu ra | Thời gian |
|---|---|---|---|---|
| buithutrang90412 (Bùi Thu Trang) | Xây dựng HomeDashboard layout với circuit panel, summary rail, responsive CSS và tách luồng Admin/Member | Hoàn thành | PR #17, PR #20, commits `5cffca1`, `31a4d47`, `1ba9a69`, `22ced2a`, `12666a8`, `8e1c371`, `55e0acf`, `19388e4`, `f3783ee` | 5.0h |
| NguyenVanHung1707 (Nguyễn Văn Hùng) | Cài đặt device-type specific tools và dynamic room topology resolver cho cảm biến | Hoàn thành | PR #18, commits `c3f9420`, `86895c8`, `c525e2b`, `0d1dd75` | 4.0h |
| cronusnd1404 (Bùi Ngọc Đạt) | Củng cố runtime safety contracts và bộ test đánh giá rollout agent | Hoàn thành | PR #19, commits `fa33976`, `d8bf7a4`, `53694ee`, `290a6ff` | 3.5h |

**Tổng kết ngày:** Nâng cấp giao diện Dashboard, hoàn tất dynamic topology resolver và chốt chặn safety contracts.

---

## 2026-08-25

| Thành viên | Công việc | Trạng thái | Đầu ra | Thời gian |
|---|---|---|---|---|
| minhpq-vn (Phạm Quốc Minh) | Xây dựng Web Simulator sandbox (frontend-simulator/) với 2D Canvas, Three.js 3D, Playwright E2E, PIN 2004 | Hoàn thành | PR #22, commits `76239ce`, `04020a3`, `a447ba8`, `ec2b8ae` | 5.5h |
| buithutrang90412 (Bùi Thu Trang) | Hoàn thiện auth, routing, layout responsive và stylesheet MQTT observatory | Hoàn thành | PR #21, commits `de17455`, `a296bb3`, `7a512d9` | 3.5h |
| NguyenVanHung1707 (Nguyễn Văn Hùng) | Chuyển đổi MQTT ESP32 sang Cloud WSS port 443 SSL/TLS và sửa header WebSocket chống lặp | Hoàn thành | PR #23, commits `1be3e17`, `975f6a9`, `4b4fa3f` | 3.5h |

**Tổng kết ngày:** Triển khai frontend-simulator sandbox 2D/3D và chuyển đổi firmware ESP32 sang giao thức bảo mật WebSocket WSS.

---

## 2026-08-26

| Thành viên | Công việc | Trạng thái | Đầu ra | Thời gian |
|---|---|---|---|---|
| minhpq-vn (Phạm Quốc Minh) | Cấu hình GitHub Actions CI/CD cho self-hosted runner và deploy lên Pi, căn chỉnh simulator và giao diện di động | Hoàn thành | PR #25, commits `5d2addd`, `263b444`, `7e77ae2`, `071cc34` | 4.5h |
| NguyenVanHung1707 (Nguyễn Văn Hùng) | Tách module smart_home_tools, thêm scenes, batch control, unlock approval, security report, countdown timer | Hoàn thành | PR #24, commits `65ebc40`, `a87485e`, `e3c29d0` | 4.0h |

**Tổng kết ngày:** Thiết lập CI/CD deploy lên Pi và module hóa các công cụ nhà thông minh của agent.

---

## 2026-08-27

| Thành viên | Công việc | Trạng thái | Đầu ra | Thời gian |
|---|---|---|---|---|
| minhpq-vn (Phạm Quốc Minh) | Thêm hàng đợi yêu cầu AI (AI request queue), ẩn thông tin đăng nhập demo và cải thiện giao diện xác thực | Hoàn thành | Commit `26897fd` | 3.0h |
| buithutrang90412 (Bùi Thu Trang) | Xây dựng bộ dữ liệu golden evaluation 129/134 mẫu câu tiếng Việt kèm hallucination probes và scoring spec | Hoàn thành | Commits `d68d6a1`, `c44ecc5` | 4.0h |

**Tổng kết ngày:** Nâng cao tính an toàn của API request và xây dựng bộ dữ liệu golden evaluation 134 test cases.

---

## 2026-08-28

| Thành viên | Công việc | Trạng thái | Đầu ra | Thời gian |
|---|---|---|---|---|
| cronusnd1404 (Bùi Ngọc Đạt) | Xây dựng GPU CUDA benchmark runner, báo cáo Qwen dưới 4GB VRAM, tối ưu system prompt và harness | Hoàn thành | PR #27, PR #28, commits `2403895`, `8ea6101`, `3d2792d`, `8ea6415`, `c0f3cd8` | 5.5h |
| minhpq-vn (Phạm Quốc Minh) | Khắc phục CI frontend data tracking, sửa lỗi linter và đồng bộ test suite theo benchmark updates | Hoàn thành | Commit `68a5808` | 3.0h |

**Tổng kết ngày:** Hoàn thành báo cáo benchmark cho Qwen2.5 dưới ngưỡng 4GB VRAM và đồng bộ toàn bộ test suite.

---

## 2026-08-29

| Thành viên | Công việc | Trạng thái | Đầu ra | Thời gian |
|---|---|---|---|---|
| NguyenVanHung1707 (Nguyễn Văn Hùng) | Xử lý ngắt kết nối đột ngột với MQTT LWT và tách biệt heartbeat watchdog giám sát | Hoàn thành | PR #30, commit `d076a35` | 3.5h |
| minhpq-vn (Phạm Quốc Minh) | Review và merge PR #30, kiểm thử hệ thống (463 passed), rà soát tài liệu sẵn sàng Gate 3 | Hoàn thành | Commit `c3c95aa`, verify test suite | 2.5h |

**Tổng kết ngày:** Hoàn tất cơ chế MQTT LWT phát hiện ngắt kết nối phần cứng và xác nhận 463 test cases đều passed.
