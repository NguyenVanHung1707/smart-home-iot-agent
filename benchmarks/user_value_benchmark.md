# Benchmark giá trị người dùng

## Thông điệp slide

**HomeMind được đánh giá bằng việc người dùng có hoàn tất đúng việc nhà thông minh của mình hay không — không chỉ bằng việc model có tạo được tool call.**

## KPI tiêu đề: End-to-End User Task Success Rate

Đây là tỷ lệ yêu cầu hợp lệ mà người dùng nhận được kết quả đúng, đã được Hub xác nhận, qua toàn bộ luồng: hiểu yêu cầu → chọn đúng thiết bị → thực thi an toàn → phản hồi đúng kết quả.

KPI này là chỉ số chính vì nó phản ánh kết quả người dùng thực sự nhận được, thay vì chỉ đo một thành phần như chọn tool hoặc đúng cú pháp.

### FTRR: First-Turn Resolution Rate

FTRR là KPI trải nghiệm bổ sung, đo tỷ lệ yêu cầu hợp lệ được hoàn tất đúng ngay trong **lượt tương tác đầu tiên**, không cần người dùng diễn đạt lại, trả lời câu hỏi làm rõ, hoặc thử lại.

`FTRR = (số yêu cầu hợp lệ hoàn tất đúng trong lượt tương tác đầu tiên / tổng số yêu cầu hợp lệ) × 100%`

End-to-End User Task Success Rate cho biết luồng cuối cùng có thành công hay không. FTRR nghiêm ngặt hơn ở góc nhìn trải nghiệm: người dùng có đạt kết quả ngay từ lượt đầu không.

Sau một lần benchmark mới, các giá trị được sinh tự động trong `benchmark_summary.csv`: `user_task_success_rate`, `user_task_success_cases`, `ftrr`, `first_turn_eligible_cases`, `first_turn_resolved_cases`, cùng các trường rate/tử số/mẫu số theo độ khó `easy`, `medium`, `hard`. Mỗi dòng ca trong CSV chi tiết có `difficulty`, `user_task_success`, `first_turn_eligible` và `first_turn_resolved` để kiểm toán.

## Kết quả benchmark mới nhất

> Kết quả mới nhất là **production-v9** của `Qwen2.5-3B-Instruct` (3.1B, Q4_K_M), chạy trên tập **holdout** `vietnamese-smart-home-review-v1` gồm **28 ca**. Agent dùng `local_tool_first` với `homeassistant_protocol`, cùng registry, safety và evaluator của benchmark.

### KPI giá trị người dùng

| KPI | Kết quả thực nghiệm |
|---|---:|
| End-to-End User Task Success | **71,43% (20/28)** |
| FTRR | **75,0% (18/24)** |
| Production path | **72,0% (18/25)** |
| Model path | **66,67% (2/3)** |

### Phân theo độ khó

| Mức độ | Số ca thành công | Tổng số ca | Tỷ lệ |
|---|---:|---:|---:|
| EASY | 3 | 3 | **100,0%** |
| MEDIUM | 8 | 11 | **72,73%** |
| HARD | 9 | 14 | **64,29%** |

### Tool, safety và hiệu năng

| Chỉ số | Kết quả |
|---|---:|
| Độ chính xác intent | 78,57% |
| Chọn tool đúng | 78,57% |
| Thực thi tool đúng | 78,57% |
| Protocol hợp lệ | 100,0% |
| Safety compliance | **100%** |
| Unsafe action rate | **0%** |
| Adversarial defense | **100%** |
| Sensitive unlock defense | **100%** |
| Độ trễ trung bình | 282,65 ms |
| Độ trễ P95 | 2.743,77 ms |
| Tốc độ sinh | 3,61 tok/s |
| VRAM đỉnh | 2.557 MB |

Đây là số đo thực nghiệm của lần chạy production-v9, không phải mục tiêu hay cam kết chất lượng. Khi trình bày, nên nêu đồng thời **71,43% hoàn tất tác vụ**, **100% safety compliance** và phạm vi đo 28 ca; không dùng điểm dashboard 89,29% thay cho KPI người dùng.

### Lịch sử các lần chạy user-value

Bảng dưới đây cho thấy tiến triển qua các lần chạy trên cùng corpus holdout 28 ca. **Production-v9 là kết quả hiện tại và được dùng khi thuyết trình**; các bản trước chỉ dùng để minh họa tiến triển, không phải kết quả triển khai hiện hành.

| Lần chạy | Agent mode | User Task Success | FTRR | EASY | MEDIUM | HARD | Dashboard* |
|---|---|---:|---:|---:|---:|---:|---:|
| v1 | model-only | 14,29% (4/28) | 16,67% (4/24) | 0/5 (0%) | 1/9 (11,11%) | 3/14 (21,43%) | 72,14% |
| v2 | model-only | 21,43% (6/28) | 25% (6/24) | 1/3 (33,33%) | 3/11 (27,27%) | 2/14 (14,29%) | 76,07% |
| production-v2 | production | 32,14% (9/28) | 29,17% (7/24) | 1/3 (33,33%) | 2/11 (18,18%) | 6/14 (42,86%) | 77,86% |
| production-v3 | production | 39,29% (11/28) | 37,5% (9/24) | 1/3 (33,33%) | 2/11 (18,18%) | 8/14 (57,14%) | 79,64% |
| **production-v9 (hiện tại)** | **production** | **71,43% (20/28)** | **75,0% (18/24)** | **3/3 (100,0%)** | **8/11 (72,73%)** | **9/14 (64,29%)** | **89,29%** |

\* Điểm dashboard chỉ là chỉ số tổng hợp tham khảo, không thay thế User Task Success hoặc safety gate. Ở production-v2, production path đạt 44,44% (8/18) và model path 10% (1/10); ở production-v3 là 52,63% (10/19) và 11,11% (1/9); production-v9 tương ứng 72,0% (18/25) và 66,67% (2/3).

### Lịch sử các lần chạy user-value

| Phiên bản | Chế độ | User Task Success | FTRR | Điểm dashboard | Ghi chú |
|---|---|---:|---:|---:|---|
| v1 | model-only | 14,29% (4/28) | 16,67% (4/24) | 72,14% | Bản đầu, trước runtime isolation |
| v2 | model-only | 21,43% (6/28) | 25,0% (6/24) | 76,07% | Đã sửa context và isolation |
| production-v2 | production | 32,14% (9/28) | 29,17% (7/24) | 77,86% | Bổ sung deterministic router |
| production-v3 | production | 39,29% (11/28) | 37,5% (9/24) | 79,64% | Trước parser patch |
| **production-v9** | **production** | **71,43% (20/28)** | **75,0% (18/24)** | **89,29%** | **Kết quả mới nhất sau parser/routing patch** |

Các báo cáo chi tiết: [production-v3](../benchmarks/results/user-value-qwen25-3b-production-v3/BENCHMARK_REPORT_VI.md), [production-v9](../benchmarks/results/user-value-qwen25-3b-production-v9/BENCHMARK_REPORT_VI.md).

## Các chỉ số người dùng nhìn thấy

| Chỉ số | Cách tính | Lợi ích với người dùng |
|---|---|---|
| Hiểu đúng ý định | Số yêu cầu có intent/action đúng trên tổng yêu cầu hợp lệ | Không phải sửa câu lệnh vì trợ lý hiểu sai “bật”, “tắt”, hỏi trạng thái hay hẹn giờ. |
| Grounding thiết bị | Số thao tác tham chiếu đúng thiết bị/phòng có thật trong registry trên tổng thao tác | Không điều khiển nhầm phòng hoặc báo thiếu một thiết bị đang tồn tại. |
| Hoàn tất đa ý định | Số yêu cầu nhiều thao tác hoàn tất đủ, đúng thứ tự trên tổng yêu cầu nhiều thao tác | Có thể nói một câu tự nhiên để xử lý nhiều việc, không cần chia nhỏ thủ công. |
| Chất lượng làm rõ | Số câu hỏi làm rõ chỉ xuất hiện khi thiếu hoặc mơ hồ tham số trên tổng câu hỏi làm rõ | Trợ lý hỏi lại khi thật sự cần, thay vì bắt người dùng lặp lại thông tin đã nói. |
| Tỷ lệ lỗi an toàn | Số hành động không an toàn/không được phép/không đúng capability trên tổng yêu cầu có rủi ro | Không tự mở khóa, không thực thi lệnh mơ hồ hoặc bị prompt injection dẫn dắt. |
| Thời gian hoàn tất | Thời gian từ lúc người dùng gửi yêu cầu đến khi Hub xác nhận và trả lời cuối | Phản hồi đủ nhanh để sử dụng như một điều khiển nhà thông minh hằng ngày. |

## Quy tắc đo lường

1. Chỉ tính yêu cầu **hợp lệ và có kỳ vọng xác định được**; loại các yêu cầu mơ hồ cố ý, ngoài capability, hoặc chỉ mang tính hội thoại.
2. Thành công chỉ được ghi nhận khi có kết quả Hub/tool đã xác minh; model nói “đã xong” không phải bằng chứng.
3. Với yêu cầu đa ý định, mọi thao tác cần hoàn tất đúng thiết bị, đúng thứ tự và không có thao tác thừa.
4. FTRR chỉ tính thành công nếu không có lượt làm rõ, diễn đạt lại, hay retry từ người dùng trước khi hoàn tất.
5. Báo cáo rõ cỡ mẫu, split đánh giá, môi trường (simulator/thiết bị thật), model, protocol gọi tool và phiên bản registry.
6. Không công bố tỷ lệ phần trăm trước khi có tập đánh giá đã chốt, nhãn kỳ vọng và log xác minh. Cần phân biệt **KPI đề xuất** (khung đo lường và công thức) với **số đo thực nghiệm** (kết quả của một lần chạy cụ thể, có model, split, cấu hình và cỡ mẫu đi kèm). Các con số trong mục “Kết quả benchmark mới nhất” là số đo production-v9 trên holdout 28 ca.
7. Taxonomy độ khó do evaluator suy ra từ metadata corpus, không theo case ID hay model: **EASY** là routine/read-only một ý định rõ ràng; **MEDIUM** là biến thể ngôn ngữ, giá trị, trạng thái hoặc unsupported không mơ hồ; **HARD** là đa lệnh, mơ hồ, phủ định/trích dẫn/giả định, nhạy cảm, adversarial, topology không tồn tại hoặc metadata rủi ro cao.

## Hai câu chuyện demo đã xác minh

### 1. Đọc telemetry khí gas

- Trước: câu hỏi về cảm biến khí gas có thể trả về “không tìm thấy cảm biến”, dù simulator có cảm biến đang online với dữ liệu `ppm`.
- Sau: tầng semantic telemetry đọc metric gas theo capability mapping hoặc contract state tương thích; trợ lý trả lời `114 ppm` và trạng thái an toàn.
- Giá trị người dùng: người dùng nhận được trạng thái an toàn thực tế của nhà, không phải thông báo thiếu thiết bị sai.

### 2. Hai lệnh liên tiếp trong một câu

- Trước: “tắt đèn phòng ngủ bật đèn phòng bếp” bị xem là mơ hồ và hỏi lại.
- Sau: parser tách các mệnh lệnh theo ranh giới hành động, giữ thứ tự: tắt đèn phòng ngủ → bật đèn phòng bếp.
- Giá trị người dùng: hoàn tất một tác vụ nhiều bước trong một lượt nói tự nhiên, giảm thao tác lặp lại.

## Gợi ý bố cục một slide

**Tiêu đề:** “Đo thành công theo kết quả người dùng, không chỉ theo tool call”

- Cột trái: KPI chính `End-to-End User Task Success Rate` và công thức FTRR.
- Cột phải: ba lợi ích ngắn: “Đúng thiết bị”, “Xong nhiều việc trong một lượt”, “An toàn đã xác minh”.
- Dải dưới: hai before/after ngắn — Gas: “không tìm thấy” → “114 ppm, an toàn”; Lệnh kép: “hỏi lại” → “tắt phòng ngủ, bật phòng bếp”.
- Chân slide: “Production-v9: 71,43% hoàn tất tác vụ trên 28 ca; KPI có log xác minh và safety 100%.”

## Kịch bản nói trong 30 giây

“Chúng tôi không chỉ đo model có gọi đúng tool hay không. Chỉ số chính là End-to-End User Task Success Rate: người dùng có nhận được kết quả đúng, đã được Hub xác minh, qua toàn bộ luồng hay không. Trên holdout 28 ca, production-v9 đạt 71,43% hoàn tất tác vụ và FTRR 75,0%, đồng thời safety compliance đạt 100%. Theo độ khó, EASY đạt 3/3, MEDIUM 8/11 và HARD 9/14. Các con số này là kết quả thực nghiệm có log xác minh của bản baseline mới.”
