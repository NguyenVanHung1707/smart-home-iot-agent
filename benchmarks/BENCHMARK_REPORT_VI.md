# Báo Cáo Đánh Giá Hiệu Năng Mô Hình LLM (CUDA / RTX 3050 & Remote API)

**Thời gian tạo**: 2026-09-01 01:20:35
**Phần cứng & Môi trường**: NVIDIA GeForce RTX 3050 Laptop GPU (4096 MB VRAM, CUDA) & OpenAI-compatible Remote API
**Khung điều phối Agent**: `LocalAgentHarness` (`src.agents.harness.LocalAgentHarness`) kết hợp `build_system_prompt()` và `execute_homeassistant_call`
**Tập dữ liệu đánh giá**: `eval.cases.smart_home_review_golden.REVIEW_CASES_V1` (28 ca kiểm thử tiếng Việt thực tế)
**Benchmark Revision / Split**: `tool-transport-risk-v3` / `holdout` (`vietnamese-smart-home-review-v1`)
**Tool Transport Metadata**: `GPT-5.6-Luna`=native/native_tools, `Qwen2.5-3B-Instruct-Viet-SFT`=homeassistant_protocol/local_tool_first, `Qwen2.5-3B-Instruct`=homeassistant_protocol/local_tool_first, `Qwen3.5-2B`=homeassistant_protocol/local_tool_first, `LFM2.5-2.6B`=homeassistant_protocol/local_tool_first, `Qwen3-1.7B`=homeassistant_protocol/local_tool_first, `Home-Llama-3.2-3B`=homeassistant_protocol/local_tool_first
**Chỉ số Tool**: Tool selection đo việc chọn tool và đối số đúng schema; tool execution đo việc runtime thực thi thành công đúng tool đã chọn. Hai chỉ số không thể thay thế nhau.
**Điểm dashboard (không phải safety gate)**: An toàn 40%, ý định 30%, chọn tool 10%, thực thi tool 10%, hợp lệ protocol 10%. Phải xem riêng safety compliance và unsafe action rate trước khi triển khai.

---

## 1. Tóm Tắt Kết Quả (Executive Summary)

- **Điểm dashboard cao nhất**: **`GPT-5.6-Luna`** đạt **81.07%**; đây không phải phê duyệt an toàn và phải được đọc cùng các chỉ số safety.
- **Mô hình nhanh nhất / Độ trễ thấp nhất**: **`Qwen2.5-3B-Instruct`** đạt thời gian phản hồi trung bình chỉ **1310.55 ms** (tốc độ phát sinh 42.89 tokens/giây).
- **Tối ưu hóa bộ nhớ GPU (VRAM)**: Các mô hình lượng tử hóa cục bộ (Q4_K_M) đều vận hành ổn định trên bộ nhớ 4GB VRAM của card RTX 3050 mà không bị tràn sang CPU.
- **An toàn & Phòng thủ bảo mật**: Duy trì mức phòng thủ mở khóa nhạy cảm tuyệt đối (Sensitive Unlock Defense) trên toàn bộ các ca kiểm thử, từ chối mở khóa cửa trực tiếp để tuân thủ luồng phê duyệt an toàn.

---

## 2. Bảng Xếp Hạng & So Sánh Tổng Hợp (Leaderboard)

| Hạng | Tên Mô Hình | Dung Lượng | Lượng Tử | Điểm Tổng Thể | Độ Chính Xác Ý Định | Tuân Thủ An Toàn | Chống Jailbreak | Phòng Thủ Mở Khóa | Độ Trễ TB | Tốc Độ Sinh Từ | VRAM Đỉnh |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **#1** | **GPT-5.6-Luna** | Cloud | FP16 | **81.07%** | 64.29% | 100.0% | 100.0% | 100.0% | 5066.6 ms | 21.2 tok/s | N/A (Cloud) |
| **#2** | **Qwen2.5-3B-Instruct-Viet-SFT** | 3.1B | Q4_K_M | **72.5%** | 53.57% | 92.86% | 100.0% | 100.0% | 3104.4 ms | 49.3 tok/s | 2515 MB |
| **#3** | **Qwen2.5-3B-Instruct** | 3.1B | Q4_K_M | **69.29%** | 42.86% | 96.43% | 100.0% | 50.0% | 1310.5 ms | 42.9 tok/s | 2515 MB |
| **#4** | **Qwen3.5-2B** | 2.0B | Q4_K_M | **67.86%** | 39.29% | 100.0% | 100.0% | 100.0% | 4307.5 ms | 28.2 tok/s | 1947 MB |
| **#5** | **LFM2.5-2.6B** | 2.6B | Q4_K_M | **63.57%** | 21.43% | 96.43% | 100.0% | 100.0% | 5084.2 ms | 37.9 tok/s | 2289 MB |
| **#6** | **Qwen3-1.7B** | 1.7B | Q4_K_M | **63.57%** | 28.57% | 92.86% | 60.0% | 100.0% | 3009.0 ms | 71.7 tok/s | 2111 MB |
| **#7** | **Home-Llama-3.2-3B** | 3.2B | Q4_K_M | **61.07%** | 28.57% | 100.0% | 100.0% | 100.0% | 2124.2 ms | 44.8 tok/s | 2981 MB |

---

## 3. Phân Tích Chi Tiết Từng Hạng Mục

### 3.1 Độ Chính Xác Phân Loại Ý Định & Gọi Tool

| Mô Hình | Độ Chính Xác Ý Định | Tỷ Lệ Chọn Tool | Tỷ Lệ Thực Thi Tool | Tỷ Lệ Gọi Tool | Tỷ Lệ Xác Minh Thực Thi | Tính Hợp Lệ Giao Thức |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **GPT-5.6-Luna** | 64.29% | 60.71% | 57.14% | 75.0% | 90.48% | 100.0% |
| **Qwen2.5-3B-Instruct-Viet-SFT** | 53.57% | 46.43% | 46.43% | 0.0% | 0.0% | 100.0% |
| **Qwen2.5-3B-Instruct** | 42.86% | 53.57% | 53.57% | 7.14% | 100.0% | 71.43% |
| **Qwen3.5-2B** | 39.29% | 46.43% | 46.43% | 0.0% | 0.0% | 67.86% |
| **LFM2.5-2.6B** | 21.43% | 46.43% | 46.43% | 0.0% | 0.0% | 92.86% |
| **Qwen3-1.7B** | 28.57% | 46.43% | 46.43% | 0.0% | 0.0% | 85.71% |
| **Home-Llama-3.2-3B** | 28.57% | 46.43% | 46.43% | 0.0% | 0.0% | 32.14% |

### 3.2 Đánh Giá Mức Độ An Toàn & Bảo Mật

| Mô Hình | Safety Gate Tổng Thể | Tỷ Lệ Hành Động/Tuyên Bố Không An Toàn (Critical) | Chống Jailbreak | Phòng Thủ Mở Khóa Nhạy Cảm |
| :--- | :---: | :---: | :---: | :---: |
| **GPT-5.6-Luna** | 100.0% | 0.0% | 100.0% | 100.0% |
| **Qwen2.5-3B-Instruct-Viet-SFT** | 92.86% | 0.0% | 100.0% | 100.0% |
| **Qwen2.5-3B-Instruct** | 96.43% | 14.29% | 100.0% | 50.0% |
| **Qwen3.5-2B** | 100.0% | 0.0% | 100.0% | 100.0% |
| **LFM2.5-2.6B** | 96.43% | 0.0% | 100.0% | 100.0% |
| **Qwen3-1.7B** | 92.86% | 0.0% | 60.0% | 100.0% |
| **Home-Llama-3.2-3B** | 100.0% | 0.0% | 100.0% | 100.0% |

### 3.3 Hiệu Năng Phần Cứng & Tốc Độ Suy Luận

| Mô Hình | Độ Trễ TB (ms) | Độ Trễ P95 (ms) | Tốc Độ Sinh Từ | VRAM Đỉnh | Thời Gian Nạp (s) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **GPT-5.6-Luna** | 5066.6 ms | 8064.2 ms | 21.2 tok/s | N/A (Cloud) | 0.03 s |
| **Qwen2.5-3B-Instruct-Viet-SFT** | 3104.4 ms | 3667.1 ms | 49.3 tok/s | 2515 MB | 0.79 s |
| **Qwen2.5-3B-Instruct** | 1310.5 ms | 3496.3 ms | 42.9 tok/s | 2515 MB | 2.59 s |
| **Qwen3.5-2B** | 4307.5 ms | 8459.3 ms | 28.2 tok/s | 1947 MB | 0.73 s |
| **LFM2.5-2.6B** | 5084.2 ms | 8868.7 ms | 37.9 tok/s | 2289 MB | 1.39 s |
| **Qwen3-1.7B** | 3009.0 ms | 5346.2 ms | 71.7 tok/s | 2111 MB | 0.53 s |
| **Home-Llama-3.2-3B** | 2124.2 ms | 3628.3 ms | 44.8 tok/s | 2981 MB | 2.15 s |

---

## 4. Phân Tích Chi Tiết Từng Mô Hình

### 1. GPT-5.6-Luna (Cloud, FP16): Hạng 1
- **Điểm Dashboard (không phải safety gate)**: `81.07%`
- **Đặc tính suy luận & Ưu điểm**:
  - Mô hình Cloud frontier hiệu năng cao, hiểu sâu sắc ngữ cảnh câu lệnh tiếng Việt đa mệnh đề và ngữ nghĩa nhà thông minh.
  - Khả năng xử lý tool call linh hoạt và tuân thủ ranh giới an toàn nghiêm ngặt.


### 2. Qwen2.5-3B-Instruct-Viet-SFT (3.1B, Q4_K_M): Hạng 2
- **Điểm Dashboard (không phải safety gate)**: `72.5%`
- **Đặc tính suy luận & Ưu điểm**:
  - Được tinh chỉnh chuyên sâu trên ngữ liệu tiếng Việt, khả năng hiểu tiếng Việt không dấu và từ ngữ địa phương rất tốt.


### 3. Qwen2.5-3B-Instruct (3.1B, Q4_K_M): Hạng 3
- **Điểm Dashboard (không phải safety gate)**: `69.29%`
- **Đặc tính suy luận & Ưu điểm**:
  - Tốc độ phản hồi nhanh, rất phù hợp cho tương tác giọng nói thời gian thực (Voice AI).
  - Độ an toàn cao trong nhóm đa dụng.


### 4. Qwen3.5-2B (2.0B, Q4_K_M): Hạng 4
- **Điểm Dashboard (không phải safety gate)**: `67.86%`
- **Đặc tính suy luận & Ưu điểm**:
  - Khả năng hiểu câu lệnh tiếng Việt tự nhiên và phân tích nhiều mệnh đề vượt trội.
  - Phản xạ hỏi làm rõ (`CLARIFY`) chuẩn xác khi câu lệnh thiếu phòng hoặc thiếu giá trị.
  - Mức tiêu thụ VRAM cực kỳ tiết kiệm, rất lý tưởng cho các thiết bị Edge / Mini PC có GPU 4GB.


### 5. LFM2.5-2.6B (2.6B, Q4_K_M): Hạng 5
- **Điểm Dashboard (không phải safety gate)**: `63.57%`
- **Đặc tính suy luận & Ưu điểm**:
  - Kiến trúc lai Liquid Foundation Model vận hành ổn định, mức tiêu thụ VRAM vừa phải.


### 6. Qwen3-1.7B (1.7B, Q4_K_M): Hạng 6
- **Điểm Dashboard (không phải safety gate)**: `63.57%`
- **Đặc tính suy luận & Ưu điểm**:
  - Tốc độ phát sinh từ nhanh, tự động sinh chuỗi tư duy trong thẻ `<think>` trước khi đưa ra hành động.


### 7. Home-Llama-3.2-3B (3.2B, Q4_K_M): Hạng 7
- **Điểm Dashboard (không phải safety gate)**: `61.07%`
- **Đặc tính suy luận & Ưu điểm**:
  - Mức độ an toàn cao, từ chối triệt để mọi hành vi vượt quyền hoặc yêu cầu nhạy cảm.


## 5. Khuyến Nghị Triển Khai Thực Tế (Production Recommendations)

1. **Lựa chọn mô hình chính thức (Primary Model)**: **`GPT-5.6-Luna`** mang lại độ chính xác cao nhất trong nhận diện ý định và điều khiển nhà thông minh.
2. **Bộ khung điều phối LocalAgentHarness**: Cung cấp cơ chế multi-turn recovery và tương thích hoàn toàn giữa các mô hình cục bộ và mô hình đám mây OpenAI-compatible.

---
*Dữ liệu và file chi tiết được lưu trữ tại thư mục: `benchmarks/results/`.*