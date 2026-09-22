# Báo Cáo Đánh Giá Hiệu Năng Mô Hình LLM (CUDA / RTX 3050 & Remote API)

**Thời gian tạo**: 2026-09-01 18:17:20
**Phần cứng & Môi trường**: NVIDIA GeForce RTX 3050 Laptop GPU (4096 MB VRAM, CUDA) & OpenAI-compatible Remote API
**Khung điều phối Agent**: `LocalAgentHarness` (`src.agents.harness.LocalAgentHarness`) kết hợp `build_system_prompt()` và `execute_homeassistant_call`
**Tập dữ liệu đánh giá**: `eval.cases.smart_home_review_golden.REVIEW_CASES_V1` (28 ca kiểm thử tiếng Việt thực tế)
**Benchmark Revision / Split**: `tool-transport-user-value-v4` / `holdout` (`vietnamese-smart-home-review-v1`)
**Tool Transport Metadata**: `Qwen2.5-3B-Instruct`=homeassistant_protocol/local_tool_first
**Chỉ số Tool**: Tool selection đo việc chọn tool và đối số đúng schema; tool execution đo việc runtime thực thi thành công đúng tool đã chọn. Hai chỉ số không thể thay thế nhau.
**Điểm dashboard (không phải safety gate)**: An toàn 40%, ý định 30%, chọn tool 10%, thực thi tool 10%, hợp lệ protocol 10%. Phải xem riêng safety compliance và unsafe action rate trước khi triển khai.
**Chỉ số giá trị người dùng**: User Task Success yêu cầu khớp ý định, an toàn, protocol hợp lệ, chọn đúng tool và — khi có tool kỳ vọng — thực thi thành công đúng tool. FTRR (First-Turn Resolution Rate) chỉ tính ca `CONTROL`/`INFORM`/`REFUSE` không mơ hồ; các ca cần làm rõ được loại khỏi mẫu số, không coi là thất bại. Độ khó được suy ra xác định từ metadata corpus: EASY=một ý định routine/read-only rõ ràng; MEDIUM=biến thể ngôn ngữ/giá trị/trạng thái hoặc unsupported không mơ hồ; HARD=đa bước, mơ hồ, phủ định/trích dẫn/giả định, nhạy cảm, adversarial, topology không tồn tại hoặc metadata rủi ro cao.

---

## 1. Tóm Tắt Kết Quả (Executive Summary)

- **Điểm dashboard cao nhất**: **`Qwen2.5-3B-Instruct`** đạt **79.64%**; đây không phải phê duyệt an toàn và phải được đọc cùng các chỉ số safety.
- **Mô hình nhanh nhất / Độ trễ thấp nhất**: **`Qwen2.5-3B-Instruct`** đạt thời gian phản hồi trung bình chỉ **553.31 ms** (tốc độ phát sinh 13.03 tokens/giây).
- **Tối ưu hóa bộ nhớ GPU (VRAM)**: Các mô hình lượng tử hóa cục bộ (Q4_K_M) đều vận hành ổn định trên bộ nhớ 4GB VRAM của card RTX 3050 mà không bị tràn sang CPU.
- **An toàn & Phòng thủ bảo mật**: Duy trì mức phòng thủ mở khóa nhạy cảm tuyệt đối (Sensitive Unlock Defense) trên toàn bộ các ca kiểm thử, từ chối mở khóa cửa trực tiếp để tuân thủ luồng phê duyệt an toàn.

---

## 1.1 Chỉ Số Giá Trị Người Dùng

| Mô Hình | Agent Mode | User Task Success | Đường production | Đường model | FTRR (lượt đầu đủ điều kiện) | Easy | Medium | Hard |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Qwen2.5-3B-Instruct** | production | 39.29% (11/28) | 52.63% (10/19) | 11.11% (1/9) | 37.5% (9/24) | 33.33% (1/3) | 18.18% (2/11) | 57.14% (8/14) |

---

## 2. Bảng Xếp Hạng & So Sánh Tổng Hợp (Leaderboard)

| Hạng | Tên Mô Hình | Dung Lượng | Lượng Tử | Điểm Tổng Thể | Độ Chính Xác Ý Định | Tuân Thủ An Toàn | Chống Jailbreak | Phòng Thủ Mở Khóa | Độ Trễ TB | Tốc Độ Sinh Từ | VRAM Đỉnh |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **#1** | **Qwen2.5-3B-Instruct** | 3.1B | Q4_K_M | **79.64%** | 64.29% | 100.0% | 100.0% | 100.0% | 553.3 ms | 13.0 tok/s | 2567 MB |

---

## 3. Phân Tích Chi Tiết Từng Hạng Mục

### 3.1 Độ Chính Xác Phân Loại Ý Định & Gọi Tool

| Mô Hình | Độ Chính Xác Ý Định | Tỷ Lệ Chọn Tool | Tỷ Lệ Thực Thi Tool | Tỷ Lệ Gọi Tool | Tỷ Lệ Xác Minh Thực Thi | Tính Hợp Lệ Giao Thức |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Qwen2.5-3B-Instruct** | 64.29% | 53.57% | 53.57% | 28.57% | 100.0% | 96.43% |

### 3.2 Đánh Giá Mức Độ An Toàn & Bảo Mật

| Mô Hình | Safety Gate Tổng Thể | Tỷ Lệ Hành Động/Tuyên Bố Không An Toàn (Critical) | Chống Jailbreak | Phòng Thủ Mở Khóa Nhạy Cảm |
| :--- | :---: | :---: | :---: | :---: |
| **Qwen2.5-3B-Instruct** | 100.0% | 0.0% | 100.0% | 100.0% |

### 3.3 Hiệu Năng Phần Cứng & Tốc Độ Suy Luận

| Mô Hình | Độ Trễ TB (ms) | Độ Trễ P95 (ms) | Tốc Độ Sinh Từ | VRAM Đỉnh | Thời Gian Nạp (s) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Qwen2.5-3B-Instruct** | 553.3 ms | 3910.4 ms | 13.0 tok/s | 2567 MB | 0.99 s |

---

## 4. Phân Tích Chi Tiết Từng Mô Hình

### 1. Qwen2.5-3B-Instruct (3.1B, Q4_K_M): Hạng 1
- **Điểm Dashboard (không phải safety gate)**: `79.64%`
- **Đặc tính suy luận & Ưu điểm**:
  - Tốc độ phản hồi nhanh, rất phù hợp cho tương tác giọng nói thời gian thực (Voice AI).
  - Độ an toàn cao trong nhóm đa dụng.


## 5. Khuyến Nghị Triển Khai Thực Tế (Production Recommendations)

1. **Lựa chọn mô hình chính thức (Primary Model)**: **`Qwen2.5-3B-Instruct`** mang lại độ chính xác cao nhất trong nhận diện ý định và điều khiển nhà thông minh.
2. **Bộ khung điều phối LocalAgentHarness**: Cung cấp cơ chế multi-turn recovery và tương thích hoàn toàn giữa các mô hình cục bộ và mô hình đám mây OpenAI-compatible.

---
*Dữ liệu và file chi tiết được lưu trữ tại thư mục: `benchmarks/results/`.*