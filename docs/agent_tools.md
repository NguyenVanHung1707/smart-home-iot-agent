# 🛠️ Tài Liệu Chi Tiết Về Các Tool Của AI Agent (HomeMind)

> **Dự án**: VinAI Smart Home System (P-140 / Homing Hub)  
> **Package**: `src/agents/tools`  
> **Framework**: LangChain Structured Tools + Pydantic v2  
> **Ngôn ngữ xử lý**: Tiếng Việt (Vietnamese-first)

---

## 📑 Mục lục

1. [Tổng quan kiến trúc Tools](#1-tổng-quan-kiến-trúc-tools)
2. [Cơ chế phân giải thiết bị & Xử lý lỗi](#2-cơ-chế-phân-giải-thiết-bị--xử-lý-lỗi)
3. [Danh mục Tools chi tiết](#3-danh-mục-tools-chi-tiết)
   - [3.1. Nhóm điều khiển thiết bị đơn lẻ](#31-nhóm-điều-khiển-thiết-bị-đơn-lẻ-device-control)
   - [3.2. Nhóm điều khiển hàng loạt & Kịch bản](#32-nhóm-điều-khiển-hàng-loạt--kịch-bản-batch--scenes)
   - [3.3. Nhóm quản lý hẹn giờ đếm ngược](#33-nhóm-quản-lý-hẹn-giờ-đếm-ngược-countdown-timers)
   - [3.4. Nhóm an ninh & Phê duyệt mở khóa](#34-nhóm-an-ninh--phê-duyệt-mở-khóa-security--approval)
   - [3.5. Nhóm tra cứu thông tin & Cảm biến](#35-nhóm-tra-cứu-thông-tin--cảm-biến-inspection--sensors)
   - [3.6. Nhóm tra cứu tri thức RAG](#36-nhóm-tra-cứu-tri-thức-rag-knowledge-search)
   - [3.7. Nhóm Dynamic Runtime Tools](#37-nhóm-dynamic-runtime-tools)
4. [Quy chuẩn an toàn & Luồng hoạt động](#4-quy-chuẩn-an-toàn--luồng-hoạt-động)
5. [Tổng kết bảng tham chiếu nhanh](#5-tổng-kết-bảng-tham-chiếu-nhanh)

---

## 1. Tổng quan kiến trúc Tools

Trong hệ thống nhà thông minh Homing Hub, **HomeMind AI Agent** sử dụng tập hợp các LangChain Structured Tools để tương tác với phần cứng thiết bị (thực tế hoặc giả lập MQTT).

```
                      ┌───────────────────────────────────────────────┐
                      │              HomeMind AI Agent                │
                      │           (LangGraph State Machine)           │
                      └──────────────────────┬────────────────────────┘
                                             │
                       Tool Call (Arguments via Pydantic Schema)
                                             │
                                             ▼
                      ┌───────────────────────────────────────────────┐
                      │           src/agents/tools Package            │
                      │  - Pydantic Validation (_StrictToolInput)     │
                      │  - Fuzzy Resolver (_resolve_device)           │
                      │  - Device Controller Bridge (_execute_control)│
                      └──────────────────────┬────────────────────────┘
                                             │
                                             ▼
                      ┌───────────────────────────────────────────────┐
                      │               Device Registry                 │
                      │   (Simulator Storage / Hardware Registry)     │
                      └──────────────────────┬────────────────────────┘
                                             │
                         MQTT / Direct Device Driver / State
                                             │
                                             ▼
                      ┌───────────────────────────────────────────────┐
                      │            Smart Home Hardware / Hub          │
                      │ (Đèn, Quạt, Điều hòa, Rèm, Khóa, Cảm biến...) │
                      └───────────────────────────────────────────────┘
```

### Các đặc điểm kỹ thuật cốt lõi:
- **Type Safety nghiêm ngặt**: Tất cả Input Schema kế thừa từ `_StrictToolInput` (`ConfigDict(extra="forbid")`), ngăn chặn các tham số lạ gây lỗi mô hình ngôn ngữ.
- **Phản hồi chuẩn JSON**: Mọi tool đều trả về chuỗi JSON chuẩn hóa qua hàm `_tool_result(status, ...)` giúp Agent phân tích kết quả chính xác và đưa ra câu trả lời trung thực.
- **Tương thích đa môi trường**: Tự động chuyển đổi giữa dữ liệu giả lập (`runtime/devices.json`) và dữ liệu phần cứng thực tế (`data/devices_real.json`).

---

## 2. Cơ chế phân giải thiết bị & Xử lý lỗi

### 2.1. Phân giải thông minh (`_resolve_device`)
Khi người dùng ra lệnh bằng ngôn ngữ tự nhiên tiếng Việt, Agent không cần nhớ chính xác ID kỹ thuật của thiết bị mà có thể phân giải thông qua:
1. **`device_id` trực tiếp**: Nếu được chỉ định cụ thể.
2. **`room` (Tên phòng)**: Khử dấu tiếng Việt (`_normalize_text`), không phân biệt chữ hoa/thường (ví dụ: `"phong khach"`, `"Phòng Khách"`, `"Khách"`).
3. **`kind` (Loại thiết bị)**: Tự động hỗ trợ cơ chế fallback thông minh cho thiết bị làm mát khí hậu (ví dụ: tìm `aircon` có thể match với `fan` nếu phòng chỉ có quạt).
4. **`name` (Tên thiết bị)**: Khớp chuỗi con tên thiết bị.

### 2.2. Trạng thái phản hồi chuẩn (`status`)
| Trạng thái (`status`) | Ý nghĩa kỹ thuật | Phản hồi của Agent tới người dùng |
| :--- | :--- | :--- |
| `success` | Thực thi thành công, trạng thái thiết bị đã cập nhật. | Xác nhận hành động đã hoàn thành. |
| `not_found` | Không tìm thấy thiết bị, phòng hoặc tài liệu phù hợp. | Thông báo rõ đối tượng không tồn tại, gợi ý danh sách hiện có. |
| `invalid_request` | Tham số không hợp lệ (ví dụ: thiếu độ sáng khi `action='set'`). | Yêu cầu người dùng cung cấp thêm thông số cần thiết. |
| `timeout` / `ack_timeout` | Thiết bị không phản hồi xác nhận sau thời gian chờ. | Báo thiết bị chưa phản hồi, trạng thái chưa được xác nhận. |
| `offline` | Thiết bị đang mất kết nối mạng / ngoại tuyến. | Báo thiết bị đang offline, kiểm tra nguồn/kết nối. |
| `unavailable` | Hub điều khiển trung tâm tạm thời không khả dụng. | Báo lỗi hệ thống trung tâm. |
| `denied` | Thao tác bị từ chối do chính sách bảo mật. | Hướng dẫn luồng phê duyệt an toàn. |
| `failed` | Lệnh gửi thất bại hoặc Hub không trả về trạng thái. | Báo lỗi thực thi kỹ thuật. |

---

## 3. Danh mục Tools chi tiết

### 3.1. Nhóm điều khiển thiết bị đơn lẻ (Device Control)

---

#### 💡 `control_light`
- **File**: [`src/agents/tools/light.py`](file:///e:/hung/VinAI/Prj/P-140/src/agents/tools/light.py)
- **Mục đích**: Bật, tắt, đổi trạng thái hoặc điều chỉnh độ sáng đèn chiếu sáng trong phòng.
- **Input Parameters**:
  - `room` (*string*, bắt buộc): Tên phòng (ví dụ: `"Phòng khách"`, `"Phòng ngủ"`, `"Bếp"`).
  - `action` (*string*, bắt buộc): `"on"` (bật), `"off"` (tắt), `"toggle"` (đảo trạng thái), `"set"` (chỉnh độ sáng).
  - `brightness` (*integer*, tùy chọn): Độ sáng từ `0` đến `100`% (bắt buộc khi `action="set"`).
  - `device_id` (*string*, tùy chọn): ID thiết bị nếu muốn chỉ định trực tiếp.
- **Ví dụ gọi**:
  ```json
  {"room": "Phòng khách", "action": "set", "brightness": 75}
  ```

---

#### ❄️ `control_aircon`
- **File**: [`src/agents/tools/aircon.py`](file:///e:/hung/VinAI/Prj/P-140/src/agents/tools/aircon.py)
- **Mục đích**: Điều khiển điều hòa nhiệt độ hoặc quạt làm mát trong phòng.
- **Input Parameters**:
  - `room` (*string*, bắt buộc): Tên phòng chứa điều hòa / quạt.
  - `action` (*string*, bắt buộc): `"on"`, `"off"`, `"toggle"`, `"set"`.
  - `target_temperature` (*float*, tùy chọn): Nhiệt độ cài đặt từ `16.0`°C đến `30.0`°C (dùng khi `action="set"`).
  - `mode` (*string*, tùy chọn): Chế độ làm mát (`"auto"`, `"cool"`, `"dry"`, `"fan"`).
  - `device_id` (*string*, tùy chọn): ID chính xác của thiết bị.
- **Ví dụ gọi**:
  ```json
  {"room": "Phòng ngủ", "action": "set", "target_temperature": 24.5, "mode": "cool"}
  ```

---

#### 🪟 `control_blind`
- **File**: [`src/agents/tools/blind.py`](file:///e:/hung/VinAI/Prj/P-140/src/agents/tools/blind.py)
- **Mục đích**: Điều khiển độ mở rèm cửa hoặc cửa sổ tự động.
- **Input Parameters**:
  - `room` (*string*, bắt buộc): Tên phòng có rèm cửa.
  - `position` (*integer*, bắt buộc): Mức độ mở từ `0`% (đóng hoàn toàn) đến `100`% (mở hoàn toàn).
  - `device_id` (*string*, tùy chọn): ID chính xác của rèm cửa.
- **Ví dụ gọi**:
  ```json
  {"room": "Phòng khách", "position": 50}
  ```

---

#### 🔊 `control_speaker`
- **File**: [`src/agents/tools/speaker.py`](file:///e:/hung/VinAI/Prj/P-140/src/agents/tools/speaker.py)
- **Mục đích**: Bật, tắt phát âm thanh hoặc điều chỉnh âm lượng loa thông minh.
- **Input Parameters**:
  - `room` (*string*, bắt buộc): Tên phòng có loa thông minh.
  - `action` (*string*, bắt buộc): `"on"`, `"off"`, `"toggle"`, `"set"`.
  - `volume` (*integer*, tùy chọn): Âm lượng từ `0` đến `100`% (dùng khi `action="set"`).
  - `device_id` (*string*, tùy chọn): ID chính xác của loa.
- **Ví dụ gọi**:
  ```json
  {"room": "Phòng khách", "action": "set", "volume": 30}
  ```

---

#### 🖥️ `control_display`
- **File**: [`src/agents/tools/display.py`](file:///e:/hung/VinAI/Prj/P-140/src/agents/tools/display.py)
- **Mục đích**: Bật/tắt màn hình hiển thị hoặc cập nhật bảng tin/thông điệp văn bản.
- **Input Parameters**:
  - `room` (*string*, bắt buộc): Tên phòng có màn hình.
  - `action` (*string*, bắt buộc): `"on"`, `"off"`, `"toggle"`, `"set"`.
  - `message` (*string*, tùy chọn): Nội dung thông điệp cần hiển thị (tối đa 200 ký tự).
  - `device_id` (*string*, tùy chọn): ID chính xác của màn hình.
- **Ví dụ gọi**:
  ```json
  {"room": "Lối vào", "action": "set", "message": "Chào mừng bạn về nhà!"}
  ```

---

#### 🔒 `control_lock`
- **File**: [`src/agents/tools/lock.py`](file:///e:/hung/VinAI/Prj/P-140/src/agents/tools/lock.py)
- **Mục đích**: Khóa cửa thông minh an toàn.
- **Input Parameters**:
  - `room` (*string*, bắt buộc): Vị trí khóa cửa (ví dụ: `"Lối vào"`, `"Cửa chính"`).
  - `action` (*string*, bắt buộc): Chỉ chấp nhận duy nhất giá trị `"lock"`.
  - `device_id` (*string*, tùy chọn): ID chính xác của khóa cửa.
- **Lưu ý bảo mật đặc biệt**: **Tuyệt đối không hỗ trợ hành động mở khóa (`unlock`) qua tool này**. Khi người dùng yêu cầu mở cửa, Agent bắt buộc phải chuyển sang sử dụng tool `request_unlock_approval`.
- **Ví dụ gọi**:
  ```json
  {"room": "Lối vào", "action": "lock"}
  ```

---

#### ⚡ `control_smart_device`
- **File**: [`src/agents/tools/smart_device.py`](file:///e:/hung/VinAI/Prj/P-140/src/agents/tools/smart_device.py)
- **Mục đích**: Tool điều khiển cấp thấp dùng trực tiếp `device_id` chính xác. Tích hợp sẵn validator từ chối lệnh `unlock`.
- **Input Parameters**:
  - `device_id` (*string*, bắt buộc): ID định danh của thiết bị trong hệ thống.
  - `action` (*string*, bắt buộc): Hành động điều khiển (`"on"`, `"off"`, `"set"`, v.v.).
  - `value` (*object*, tùy chọn): Từ điển chứa các thông số cài đặt.
- **Ví dụ gọi**:
  ```json
  {"device_id": "living-light", "action": "on"}
  ```

---

### 3.2. Nhóm điều khiển hàng loạt & Kịch bản (Batch & Scenes)

---

#### 📦 `batch_control_devices`
- **File**: [`src/agents/tools/batch_control.py`](file:///e:/hung/VinAI/Prj/P-140/src/agents/tools/batch_control.py)
- **Mục đích**: Thực thi đồng thời lệnh cho nhiều thiết bị cùng loại hoặc trong cùng một phạm vi phòng/toàn nhà.
- **Input Parameters**:
  - `action` (*string*, bắt buộc): `"on"`, `"off"`, `"toggle"`, `"set"`.
  - `kind` (*string*, tùy chọn): Loại thiết bị (`"light"`, `"fan"`, `"aircon"`, `"blind"`, `"speaker"`, `"display"`). Để `null` nếu muốn áp dụng cho mọi loại thiết bị trong phòng.
  - `room` (*string*, tùy chọn): Tên phòng cần áp dụng. Để `null` để áp dụng toàn bộ ngôi nhà.
  - `value` (*object*, tùy chọn): Cấu hình bổ sung (ví dụ: `{"brightness": 50}`).
- **Nguyên tắc an toàn**: Không bao giờ áp dụng batch control cho khóa cửa (`lock`).
- **Ví dụ gọi**:
  ```json
  {"action": "off", "kind": "light", "room": null}
  ```

---

#### 🎬 `activate_scene`
- **File**: [`src/agents/tools/scene.py`](file:///e:/hung/VinAI/Prj/P-140/src/agents/tools/scene.py)
- **Mục đích**: Kích hoạt ngữ cảnh tự động hóa nhà thông minh đã được thiết lập sẵn.
- **Input Parameters**:
  - `scene` (*string*, bắt buộc): Tên kịch bản:
    - `"good_night"`: Tắt toàn bộ đèn, đóng toàn bộ rèm, khóa cửa an toàn, bật điều hòa phòng ngủ 26°C.
    - `"leave_home"`: Tắt toàn bộ đèn, quạt, điều hòa, loa, màn hình; đóng rèm và khóa cửa.
    - `"welcome_home"`: Bật đèn phòng khách, bật điều hòa 24°C, mở rèm 80%, hiển thị lời chào trên màn hình.
    - `"movie_mode"`: Giảm sáng đèn còn 20%, đóng toàn bộ rèm, điều hòa 23°C dễ chịu.
    - `"all_off"`: Tắt tất cả thiết bị tiêu thụ điện (đèn, quạt, điều hòa, loa, màn hình).
  - `room` (*string*, tùy chọn): Giới hạn kịch bản cho một phòng cụ thể.
- **Ví dụ gọi**:
  ```json
  {"scene": "good_night"}
  ```

---

### 3.3. Nhóm quản lý hẹn giờ đếm ngược (Countdown Timers)

---

#### ⏱️ `set_device_timer`
- **File**: [`src/agents/tools/timer.py`](file:///e:/hung/VinAI/Prj/P-140/src/agents/tools/timer.py)
- **Mục đích**: Thiết lập bộ đếm ngược để tự động thực hiện hành động sau một khoảng thời gian (phút).
- **Input Parameters**:
  - `duration_minutes` (*float*, bắt buộc): Số phút đếm ngược (từ `0.01` đến `1440.0` phút, ví dụ: `0.5` = 30 giây, `30`, `60`).
  - `action` (*string*, bắt buộc): Hành động khi hết giờ (`"on"`, `"off"`, `"toggle"`, `"set"`).
  - `room` (*string*, tùy chọn): Tên phòng chứa thiết bị.
  - `kind` (*string*, tùy chọn): Loại thiết bị (`"light"`, `"aircon"`, `"blind"`, `"speaker"`, `"display"`).
  - `device_id` (*string*, tùy chọn): ID thiết bị chính xác.
  - `value` (*object*, tùy chọn): Giá trị thiết lập khi `action="set"`.
  - `label` (*string*, tùy chọn): Nhãn mô tả cho hẹn giờ.
- **Ví dụ gọi**:
  ```json
  {"room": "Phòng khách", "kind": "aircon", "action": "off", "duration_minutes": 30}
  ```

---

#### 📋 `list_device_timers`
- **File**: [`src/agents/tools/timer.py`](file:///e:/hung/VinAI/Prj/P-140/src/agents/tools/timer.py)
- **Mục đích**: Tra cứu danh sách các bộ hẹn giờ đang đếm ngược hoặc lịch sử hẹn giờ.
- **Input Parameters**:
  - `active_only` (*boolean*, mặc định `true`): `true` để chỉ lấy các timer đang chạy, `false` để lấy toàn bộ lịch sử.
- **Ví dụ gọi**:
  ```json
  {"active_only": true}
  ```

---

#### ❌ `cancel_device_timer`
- **File**: [`src/agents/tools/timer.py`](file:///e:/hung/VinAI/Prj/P-140/src/agents/tools/timer.py)
- **Mục đích**: Hủy bỏ một hoặc nhiều bộ hẹn giờ đang hoạt động.
- **Input Parameters**:
  - `timer_id` (*string*, tùy chọn): ID của bộ hẹn giờ cần hủy cụ thể.
  - `room` (*string*, tùy chọn): Hủy toàn bộ hẹn giờ trong phòng này.
  - `kind` (*string*, tùy chọn): Hủy toàn bộ hẹn giờ cho loại thiết bị này.
  - `device_id` (*string*, tùy chọn): Hủy toàn bộ hẹn giờ của thiết bị này.
- **Ví dụ gọi**:
  ```json
  {"room": "Phòng khách", "kind": "aircon"}
  ```

---

### 3.4. Nhóm an ninh & Phê duyệt mở khóa (Security & Approval)

---

#### 🛡️ `request_unlock_approval`
- **File**: [`src/agents/tools/unlock_approval.py`](file:///e:/hung/VinAI/Prj/P-140/src/agents/tools/unlock_approval.py)
- **Mục đích**: Tạo vé yêu cầu phê duyệt mở khóa cửa trên ứng dụng Homing Hub khi người dùng muốn mở cửa.
- **Cơ chế Human-in-the-loop**:
  1. AI Agent **không bao giờ tự ý gửi lệnh unlock** xuống phần cứng khóa.
  2. Tool tạo một ticket trong `ApprovalStore` với thời hạn hiệu lực 2 phút.
  3. Chủ nhà nhận được thông báo xác thực trên ứng dụng di động để nhấn Approve/Deny.
- **Input Parameters**:
  - `reason` (*string*, bắt buộc): Lý do hoặc tên người yêu cầu mở khóa (ví dụ: `"Chủ nhà yêu cầu mở cửa"`, `"Khách đến chơi"`).
  - `room` (*string*, tùy chọn): Vị trí khóa cửa (mặc định `"Lối vào"`).
  - `device_id` (*string*, tùy chọn): ID khóa cửa cụ thể.
- **Ví dụ gọi**:
  ```json
  {"reason": "Chủ nhà nhờ mở cửa chính qua giọng nói", "room": "Lối vào"}
  ```

---

#### 🚨 `get_security_report`
- **File**: [`src/agents/tools/security.py`](file:///e:/hung/VinAI/Prj/P-140/src/agents/tools/security.py)
- **Mục đích**: Tổng hợp toàn bộ tình trạng an ninh và các mối nguy hại tiềm ẩn trong ngôi nhà.
- **Các tiêu chí kiểm tra tự động**:
  - **Khóa cửa**: Kiểm tra cửa đang mở hay đã khóa, thiết bị khóa có trực tuyến không.
  - **Rò rỉ khí Gas**:
    - Gas $\ge 300\text{ ppm}$: Báo động khẩn cấp (`ALERT`) - nguy cơ cháy nổ.
    - Gas $\ge 150\text{ ppm}$: Cảnh báo bất thường (`WARNING`).
  - **Nguy cơ cháy / Quá nhiệt**: Nhiệt độ $\ge 50^\circ\text{C}$ kích hoạt cảnh báo cháy (`ALERT`).
  - **Cảm biến chuyển động & Ngoại tuyến**: Phát hiện chuyển động bất thường và thiết bị mất tín hiệu.
- **Input Parameters**:
  - `include_sensors` (*boolean*, mặc định `true`): Kiểm tra cảm biến an ninh & môi trường.
  - `include_locks` (*boolean*, mặc định `true`): Kiểm tra trạng thái khóa cửa.
- **Ví dụ gọi**:
  ```json
  {"include_sensors": true, "include_locks": true}
  ```

---

### 3.5. Nhóm tra cứu thông tin & Cảm biến (Inspection & Sensors)

---

#### 🏠 `get_room_devices`
- **File**: [`src/agents/tools/room_devices.py`](file:///e:/hung/VinAI/Prj/P-140/src/agents/tools/room_devices.py)
- **Mục đích**: Tra cứu sơ đồ nhà (topology), danh sách các phòng và danh sách thiết bị chi tiết kèm trạng thái `online`, `state`.
- **Input Parameters**:
  - `room` (*string*, tùy chọn): Tên phòng cần tra cứu cụ thể. Để `null` để lấy toàn bộ danh sách phòng và thiết bị trong nhà.
- **Ví dụ gọi**:
  ```json
  {"room": "Phòng bếp"}
  ```

---

#### 🌡️ `get_sensor_data`
- **File**: [`src/agents/tools/sensor_data.py`](file:///e:/hung/VinAI/Prj/P-140/src/agents/tools/sensor_data.py)
- **Mục đích**: Đọc dữ liệu từ các cảm biến môi trường kèm phân tích đánh giá chỉ số tiện nghi (`assessment`).
- **Đánh giá sức khỏe môi trường tự động**:
  - *Nhiệt độ*: $\ge 50^\circ\text{C}$ (nguy hiểm cháy), $\ge 32^\circ\text{C}$ (nóng), $24-31^\circ\text{C}$ (dễ chịu), $18-23^\circ\text{C}$ (mát mẻ), $<18^\circ\text{C}$ (lạnh).
  - *Độ ẩm*: $\ge 75\%$ (nồm ẩm cao), $40-74\%$ (lý tưởng), $<40\%$ (khô hanh).
  - *Khí gas*: $\ge 300\text{ ppm}$ (nguy hiểm), $\ge 150\text{ ppm}$ (cảnh báo), $<150\text{ ppm}$ (an toàn).
- **Input Parameters**:
  - `room` (*string*, tùy chọn): Tên phòng cần đọc dữ liệu. Để `null` để đọc toàn bộ.
  - `sensor_type` (*string*, tùy chọn): Loại cảm biến (`"temperature"`, `"humidity"`, `"gas"`, `"motion"`, `"light"`).
  - `device_id` (*string*, tùy chọn): ID cảm biến cụ thể.
- **Ví dụ gọi**:
  ```json
  {"room": "Phòng khách", "sensor_type": "temperature"}
  ```

---

#### 📅 `get_schedules`
- **File**: [`src/agents/tools/schedules.py`](file:///e:/hung/VinAI/Prj/P-140/src/agents/tools/schedules.py)
- **Mục đích**: Tra cứu danh sách các lịch trình tự động hóa (Automations / Routines) định kỳ đã được thiết lập trong hệ thống Homing Hub.
- **Input Parameters**:
  - `room` (*string*, tùy chọn): Lọc theo phòng.
  - `kind` (*string*, tùy chọn): Lọc theo loại thiết bị (`"light"`, `"blind"`, `"lock"`, `"aircon"`, `"sensor"`).
- **Ví dụ gọi**:
  ```json
  {"room": null, "kind": null}
  ```

---

### 3.6. Nhóm tra cứu tri thức RAG (Knowledge Search)

---

#### 📚 `search_home_guides`
- **File**: [`src/agents/tools/home_guides.py`](file:///e:/hung/VinAI/Prj/P-140/src/agents/tools/home_guides.py)
- **Mục đích**: Tìm kiếm trong kho tài liệu hướng dẫn sử dụng, thông số kỹ thuật, cách bảo trì và quy trình khắc phục sự cố thiết bị.
- **Input Parameters**:
  - `query` (*string*, bắt buộc, độ dài 2-500 ký tự): Câu hỏi hoặc từ khóa tìm kiếm tiếng Việt.
- **Ví dụ gọi**:
  ```json
  {"query": "cách vệ sinh lưới lọc điều hòa khi có mùi lạ"}
  ```

---

### 3.7. Nhóm Dynamic Runtime Tools

---

#### 🔄 `get_runtime_tools` & `_control_for_kind`
- **File**: [`src/agents/tools/runtime.py`](file:///e:/hung/VinAI/Prj/P-140/src/agents/tools/runtime.py)
- **Mục đích**: Cơ chế mở rộng động (dynamic extensibility). Khi hệ thống thêm các loại thiết bị mới trong tương lai (ví dụ: `purifier`, `heater`, `curtain`, `water_heater`) chưa có static tool tương ứng, hàm `get_runtime_tools()` sẽ tự động sinh thêm các tool dạng `control_<kind>` tại runtime.

---

## 4. Quy chuẩn an toàn & Luồng hoạt động

HomeMind AI Agent vận hành dựa trên các nguyên tắc an toàn nghiêm ngặt sau:

```
                          Yêu cầu từ người dùng
                                   │
                                   ▼
                  ┌──────────────────────────────────┐
                  │   Phân tích ý định tiếng Việt    │
                  │ (Phủ định, Nghi vấn, Giả định)   │
                  └────────────────┬─────────────────┘
                                   │
                                   ▼
                  ┌──────────────────────────────────┐
                  │    Kiểm tra chính sách an ninh   │
                  └────────────────┬─────────────────┘
                                   │
                  ┌────────────────┴────────────────┐
                  ▼                                 ▼
         [Yêu cầu mở khóa cửa]              [Điều khiển thiết bị khác]
                  │                                 │
                  ▼                                 ▼
   ┌─────────────────────────────┐   ┌─────────────────────────────┐
   │   request_unlock_approval   │   │     Gọi Tool tương ứng      │
   │  (Tạo ticket xác thực 2p)   │   │  (Giới hạn tối đa 5 lệnh)   │
   └──────────────┬──────────────┘   └──────────────┬──────────────┘
                  │                                 │
                  ▼                                 ▼
   ┌─────────────────────────────┐   ┌─────────────────────────────┐
   │ Hướng dẫn duyệt trên App    │   │ Kiểm tra status="success"   │
   └─────────────────────────────┘   └──────────────┬──────────────┘
                                                    │
                                                    ▼
                                     ┌─────────────────────────────┐
                                     │  Trả lời người dùng tự nhiên │
                                     │  & hoàn toàn trung thực     │
                                     └─────────────────────────────┘
```

1. **Giới hạn số lệnh**: Tối đa 5 thay đổi trạng thái thiết bị trong 1 lượt thoại. Nếu vượt quá, Agent sẽ từ chối thực hiện một phần và hướng dẫn người dùng dùng `batch_control_devices` hoặc `activate_scene`.
2. **Không tự suy đoán trạng thái**: Agent chỉ khẳng định thiết bị đã thay đổi khi tool trả về `status: "success"`.
3. **Phân biệt lệnh điều khiển và câu hỏi tra cứu**: 
   - `"Đèn phòng khách đang bật à?"` $\rightarrow$ Tra cứu trạng thái (`get_room_devices`), **không** bật/tắt thiết bị.
   - `"Đừng có bật quạt"` $\rightarrow$ Phát hiện phủ định, không gọi tool.
4. **Bảo vệ khóa cửa vật lý**: Không cho phép AI tự động mở khóa cửa trực tiếp. Bắt buộc tạo phê duyệt 2 lớp qua điện thoại chủ nhà.

---

## 5. Tổng kết bảng tham chiếu nhanh

| Tên Tool | Loại thao tác | Mục đích chính | Tham số quan trọng |
| :--- | :--- | :--- | :--- |
| `control_light` | Control | Bật/tắt/chỉnh độ sáng đèn | `room`, `action`, `brightness` |
| `control_aircon` | Control | Bật/tắt/chỉnh nhiệt độ điều hòa & quạt | `room`, `action`, `target_temperature`, `mode` |
| `control_blind` | Control | Chỉnh độ mở rèm / cửa sổ | `room`, `position` (0-100%) |
| `control_speaker` | Control | Bật/tắt/chỉnh âm lượng loa | `room`, `action`, `volume` |
| `control_display` | Control | Đổi thông điệp màn hình | `room`, `action`, `message` |
| `control_lock` | Control (Safe) | Khóa cửa an toàn (chỉ `"lock"`) | `room`, `action="lock"` |
| `control_smart_device`| Control (Direct)| Điều khiển trực tiếp theo `device_id` | `device_id`, `action`, `value` |
| `batch_control_devices`| Batch | Điều khiển hàng loạt theo loại/phòng | `action`, `kind`, `room`, `value` |
| `activate_scene` | Scene | Kích hoạt kịch bản tự động (`good_night`, v.v.) | `scene`, `room` |
| `set_device_timer` | Timer | Hẹn giờ đếm ngược theo phút | `duration_minutes`, `action`, `room`, `kind` |
| `list_device_timers` | Timer | Xem danh sách hẹn giờ đang chạy | `active_only` |
| `cancel_device_timer`| Timer | Hủy bỏ bộ hẹn giờ | `timer_id`, `room`, `kind`, `device_id` |
| `request_unlock_approval`| Security | Tạo yêu cầu phê duyệt mở cửa an toàn | `reason`, `room` |
| `get_security_report`| Security | Báo cáo an ninh, rò rỉ gas, quá nhiệt | `include_sensors`, `include_locks` |
| `get_room_devices` | Inspection | Xem sơ đồ phòng và danh sách thiết bị | `room` |
| `get_sensor_data` | Inspection | Đọc cảm biến nhiệt, ẩm, gas, chuyển động | `room`, `sensor_type` |
| `get_schedules` | Inspection | Tra cứu các lịch trình tự động hóa | `room`, `kind` |
| `search_home_guides` | RAG Search | Tra cứu hướng dẫn sử dụng & sửa chữa | `query` |
