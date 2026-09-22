# Proactive Automation Flow: Gợi ý Kịch bản Tự động hóa Chủ động

## 1. Tổng quan Quy trình

Hệ thống sử dụng tác vụ chạy ngầm định kỳ để nhận diện thói quen sử dụng thiết bị (pattern matching) từ nhật ký hoạt động. Sau khi kiểm tra quy tắc an toàn, mô hình SLM (`Qwen2.5-1.5B` lượng tử hóa Q4_K_M) sinh nội dung đề xuất và chuyển lên React Dashboard để người dùng phê duyệt.

---

## 2. Sơ đồ Luồng Gợi ý Automation

```mermaid
graph TD
    %% Khởi tạo quá trình chạy ngầm
    START(["Tác vụ chạy ngầm định kỳ<br>02:00 AM"]) --> QueryDB

    %% Bước 1: Thu thập dữ liệu
    subgraph step1 ["Bước 1: Khai phá dữ liệu (Data Mining)"]
        QueryDB["Truy vấn SQLite<br>Lịch sử lệnh 7 ngày"] --> FilterSafe
        FilterSafe["Lọc bỏ lệnh nhạy cảm<br>Loại trừ Khóa/An ninh"] --> PatternMatch
        PatternMatch{"Phát hiện mẫu<br>lặp lại liên tục?"}
    end

    %% Bước 2: Đề xuất
    subgraph step2 ["Bước 2: Sinh đề xuất"]
        PatternMatch -- "Có (VD: Bật điều hòa 22:00)" --> GeneratePrompt["Tạo Prompt & Nạp SLM"]
        GeneratePrompt --> SLMSuggest["SLM Qwen2.5-1.5B Q4_K_M<br>Sinh lời đề xuất"]
        SLMSuggest -- "Giải phóng SLM khỏi RAM" --> SaveDB["Lưu vào Database<br>Bảng pending_automations"]
        PatternMatch -- "Không" --> END_BG(["Bỏ qua & Kết thúc"])
    end

    %% Bước 3: Giao diện & Tương tác người dùng
    subgraph step3 ["Bước 3: Phê duyệt (User Interaction)"]
        SaveDB --> DashboardAlert(("Thông báo trên<br>React Dashboard"))
        DashboardAlert --> UserAction{"Người dùng phản hồi?"}
        UserAction -- "Chấp thuận (Approve)" --> SaveActive["Kích hoạt Automation chính thức"]
        UserAction -- "Từ chối (Reject)" --> DeletePending["Xóa đề xuất"]
    end

    %% Style
    classDef process fill:#e1f5fe,stroke:#03a9f4,stroke-width:2px,color:#000
    classDef decision fill:#fff3e0,stroke:#ff9800,stroke-width:2px,color:#000
    classDef terminal fill:#e8f5e9,stroke:#4caf50,stroke-width:2px,color:#000
    classDef background fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px,color:#000
    
    class QueryDB,FilterSafe,GeneratePrompt,SLMSuggest,SaveDB,SaveActive,DeletePending process
    class PatternMatch,UserAction decision
    class START,END_BG terminal
    class DashboardAlert background
```

---

## 3. Chi tiết từng Bước Thực hiện

### Bước 1: Khai phá Dữ liệu (Data Mining & Pattern Detection)
- **Tác vụ chạy ngầm định kỳ**: Lập lịch tự động kích hoạt vào khung giờ thấp điểm (02:00 AM).
- **Truy vấn Lịch sử**: Đọc lịch sử câu lệnh và nhật ký điều khiển thiết bị trong 7 ngày gần nhất từ database SQLite cục bộ.
- **Lọc lệnh an ninh**: Loại trừ các thiết bị và hành động nhạy cảm (như mở khóa cửa `entry-lock`, đổi mã PIN).
- **Phát hiện chuỗi hành vi**: Phân tích tần suất và khung giờ lặp lại (ví dụ: bật điều hòa phòng khách lúc 22:00 trong 5 trên 7 ngày gần nhất). Nếu không phát hiện chu kỳ đạt ngưỡng tin cậy, tác vụ kết thúc.

### Bước 2: Sinh Đề xuất (Recommendation Generation)
- **Tạo Prompt & Nạp SLM**: Khi phát hiện mẫu hành vi hợp lệ, hệ thống tạo context prompt và nạp mô hình `Qwen2.5-1.5B` (Q4_K_M qua `llama.cpp`) vào RAM.
- **Sinh văn bản đề xuất**: Mô hình tạo câu gợi ý trực tiếp (ví dụ: *"Hệ thống nhận thấy bạn thường bật điều hòa lúc 22:00. Bạn có muốn tạo lịch tự động hàng ngày không?"*).
- **Giải phóng SLM & Lưu Database**: Giải phóng mô hình khỏi RAM ngay sau khi tạo văn bản xong. Đề xuất được lưu vào bảng `pending_automations` trong SQLite.

### Bước 3: Phê duyệt và Tương tác Người dùng (User Approval)
- **Thông báo**: Hiển thị badge thông báo đề xuất trên thanh điều hướng của React Dashboard (`frontend/`).
- **Xử lý phản hồi**:
  - **Chấp thuận (Approve)**: Chuyển kịch bản gợi ý thành kịch bản tự động hóa chính thức và kích hoạt lịch trình điều khiển qua MQTT.
  - **Từ chối (Reject)**: Đánh dấu từ chối hoặc xóa bản ghi khỏi bảng `pending_automations`.

---

## 4. Quy tắc An toàn và Tối ưu Tài nguyên

1. **Khung giờ thấp điểm**: Tác vụ khai phá dữ liệu chạy vào 02:00 AM để tránh ảnh hưởng tài nguyên trong khung giờ người dùng thao tác.
2. **Bảo vệ an ninh**: Không tự động hóa hoặc đề xuất tự động hóa đối với khóa cửa, còi báo động hay mã PIN.
3. **Vòng đời bộ nhớ SLM**: Nạp mô hình khi sinh văn bản đề xuất và giải phóng khỏi RAM ngay sau khi lưu dữ liệu.
4. **Cơ chế User-in-the-Loop**: Kịch bản tự động hóa chỉ kích hoạt khi người dùng nhấn nút chấp thuận trên giao diện.
