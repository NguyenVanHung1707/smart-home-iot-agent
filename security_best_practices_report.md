# Báo Cáo Rà Soát & Gia Cố Bảo Mật (Security Best Practices Report)
## Hệ Thống Terra Smart Simulator Sandbox (Backend & Frontend)

---

### 1. Tổng Quan Thực Thi (Executive Summary)

Báo cáo này tổng hợp quá trình rà soát an ninh, triển khai các biện pháp gia cố bảo mật chuyên sâu (Security Hardening) và xây dựng hệ thống kiểm thử tự động toàn diện (E2E Playwright & Pytest Unit Tests) cho **Terra Smart Device Simulator Sandbox**.

* **Môi trường & Phạm vi:**
  * **Backend:** FastAPI, Paho MQTT Client, Simulator Storage Engine (`src/simulator.py`, `src/simulator_storage.py`).
  * **Frontend:** React 18, Vite 5, Tailwind CSS, Three.js 3D & HTML5 Canvas 2D Editor (`frontend-simulator/`).
  * **Kiểm thử E2E:** Playwright Test Suite (`frontend-simulator/playwright.config.ts`, `frontend-simulator/e2e/`).
  * **Kiểm thử Backend:** Pytest Test Suite (`tests/test_simulator.py`).

* **Kết Quả Kiểm Thử Đạt Được:**
  * **Playwright E2E Tests:** `21 / 21` test cases **PASS 100%** trên toàn bộ ma trận thiết bị (Desktop Chrome, Mobile Chrome Pixel 5, Mobile Safari / iPhone 13).
  * **Backend Unit Tests:** `17 / 17` test cases **PASS 100%**.

---

### 2. Chi Tiết Lỗ Hổng & Các Biện Pháp Gia Cố (Security Hardening Details)

#### 2.1. Phòng Chống MQTT Topic Injection
* **Mối đe dọa:** MQTT Broker định tuyến bản tin dựa trên cấu trúc topic (phân cách bởi `/`). Nếu `device_id` chứa ký tự wildcard (`+`, `#`), phân cấp thư mục (`/`), ký tự điều khiển hoặc path traversal (`../../`), kẻ tấn công có thể chèn ép các topic điều khiển hệ thống (`homing/devices/+/command`, `homing/broadcast/#`), gây tràn bản tin hoặc nghe lén/ghi đè trạng thái toàn bộ ngôi nhà.
* **Biện pháp triển khai:**
  * Xây dựng hàm kiểm tra định dạng nghiêm ngặt `validate_device_id`:
    ```python
    DEVICE_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
    
    def validate_device_id(device_id: Any) -> str:
        if not isinstance(device_id, str):
            raise ValueError("invalid_device_id: must be a string")
        dev_id = device_id.strip()
        if not dev_id or not DEVICE_ID_REGEX.match(dev_id):
            raise ValueError("invalid_device_id: only alphanumeric, '-', and '_' are allowed")
        return dev_id
    ```
  * Tích hợp kiểm tra tại tất cả API endpoints (`POST /api/devices`, `PUT /api/devices/{id}`, `DELETE /api/devices/{id}`, `POST /api/devices/{id}/action`, `POST /api/devices/{id}/fault`) và trong bộ phân giải MQTT `on_message`.

#### 2.2. Kiểm Tra Giới Hạn Tọa Độ & Chống Tấn Công DoS / Render Crash
* **Mối đe dọa:** Dữ liệu tọa độ không hợp lệ (như số âm, `NaN`, `Infinity`, `-Infinity` hoặc giá trị cực lớn > 1,000,000) có thể gây lỗi phép toán hình học trong HTML5 Canvas 2D và Three.js WebGL Raycaster, dẫn đến treo trình duyệt (Client DoS) hoặc tràn bộ nhớ.
* **Biện pháp triển khai:**
  * Xây dựng hàm `validate_coordinate` với kiểm tra tính hữu hạn `math.isfinite` và ràng buộc tọa độ trong khoảng hợp lệ `[0.0, 5000.0]`:
    ```python
    MIN_COORD = 0.0
    MAX_COORD = 5000.0

    def validate_coordinate(val: Any, name: str = "coordinate") -> float:
        try:
            fval = float(val)
        except (TypeError, ValueError):
            raise ValueError(f"invalid_{name}: must be a number")
        if not math.isfinite(fval):
            raise ValueError(f"invalid_{name}: must be a finite number")
        if not (MIN_COORD <= fval <= MAX_COORD):
            raise ValueError(f"invalid_{name}: out of bounds [{MIN_COORD}, {MAX_COORD}]")
        return round(fval, 2)
    ```
  * Áp dụng kiểm tra đồng bộ cho tọa độ thiết bị (`x, y`) và tọa độ các đoạn tường (`x1, y1, x2, y2`).

#### 2.3. Rà Soát & Khử Khuẩn Chống Tấn Công XSS (Cross-Site Scripting)
* **Mối đe dọa:** Người dùng nhập các chuỗi độc hại chứa mã JavaScript trong tên thiết bị hoặc tên phòng (ví dụ: `<script>alert('xss')</script>`, `<img src=x onerror=alert(1)>`). Nếu không được escape/sanitize, mã độc có thể được thực thi khi hiển thị trên danh sách thiết bị hoặc cửa sổ điều khiển.
* **Biện pháp triển khai:**
  * Thực hiện sanitize chuỗi văn bản đầu vào bằng `html.escape()` trước khi lưu vào storage:
    ```python
    def sanitize_text(text: Any, max_length: int = 100) -> str:
        if text is None:
            return ""
        clean = html.escape(str(text).strip())
        return clean[:max_length]
    ```
  * Thiết lập độ dài tối đa (100 ký tự) để chống tấn công Buffer Overflow / Storage Exhaustion.

#### 2.4. Whitelist Chế Độ Tiêm Lỗi (Fault Injection Validation)
* **Mối đe dọa:** Nhập các chế độ lỗi không xác định vào hệ thống mô phỏng gây sai lệch trạng thái thiết bị.
* **Biện pháp triển khai:**
  * Giới hạn `fault` mode chỉ nhận các giá trị hợp lệ trong danh sách trắng: `{"none", "offline", "timeout", "error"}`. Bất kỳ giá trị nào ngoài danh sách sẽ bị từ chối với lỗi `HTTP 400 Bad Request`.

---

### 3. Cấu Trúc Kiểm Thử Tự Động Playwright E2E

#### 3.1. Cấu Hình `playwright.config.ts`
Hệ thống tự động kích hoạt backend FastAPI và frontend Vite thông qua cấu hình `webServer`:
```typescript
webServer: [
  {
    command: 'cd .. && .venv/bin/python -m src.simulator',
    url: 'http://127.0.0.1:8001/health',
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
  {
    command: 'npm run dev -- --host 127.0.0.1 --port 5173',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
]
```

#### 3.2. Ma Trận Thiết Bị Kiểm Thử (Projects Matrix)
1. **Desktop Chrome:** Độ phân giải chuẩn màn hình máy tính `1280 x 800`.
2. **Mobile Chrome (Pixel 5):** Màn hình di động Android `393 x 851`, cảm ứng `isMobile: true`.
3. **Mobile Safari / iPhone (iPhone 13):** Màn hình iOS `390 x 844`, cảm ứng `isMobile: true`.

#### 3.3. Các Kịch Bản Kiểm Thử Đã Viết
* **`e2e/desktop.spec.ts`:**
  * Kiểm tra đầy đủ giao diện Desktop: TopAppBar, NavigationDrawer, 2D Canvas Editor, Device Library, Device Inspector, MQTT Console Sandbox.
  * Thao tác chuyển đổi qua lại giữa Mặt bằng 2D và Không gian 3D Three.js.
  * Tương tác chọn thiết bị, bật/tắt nguồn điện, điều chỉnh thanh trượt độ sáng và kiểm tra log MQTT tức thời.
* **`e2e/mobile.spec.ts`:**
  * Kiểm tra tính responsive trên màn hình điện thoại, co giãn giao diện, thanh điều hướng đáy (Bottom Navigation Bar) linh hoạt, không bị vỡ bố cục hay tràn thanh cuộn ngang.
  * Điều hướng chọn phòng, chọn thiết bị và thao tác điều khiển thiết bị trên giao diện mobile.
  * Chuyển đổi tab 2D / 3D trên mobile và xem log MQTT.
* **`e2e/security.spec.ts`:**
  * Test Anti-XSS: Tạo thiết bị với script payload & img onerror payload, kiểm tra mã độc bị khử khuẩn an toàn, không có alert popup nào được kích hoạt.
  * Test Anti-MQTT Topic Injection: Kiểm tra backend từ chối tạo thiết bị với `device_id` chứa ký tự cấm (`/`, `+`, `#`, `..`, khoảng trắng, dấu chấm phẩy).
  * Test Bounds & Type Checking: Kiểm tra backend từ chối tọa độ âm, NaN, Infinity hoặc ngoài giới hạn.
  * Test Fault Validation: Kiểm tra backend chấp nhận đúng 4 chế độ hợp lệ và từ chối các chế độ bất hợp pháp.

---

### 4. Kết Quả Kiểm Thử Chi Tiết (Test Execution Metrics)

#### 4.1. Playwright E2E Test Results
```text
Running 21 tests using 1 worker

[Desktop Chrome]
  ✓ desktop.spec.ts: Full Desktop UI components check (1.3s)
  ✓ desktop.spec.ts: 2D Plan <-> 3D View Three.js rendering (4.3s)
  ✓ desktop.spec.ts: Device selection, control & MQTT logs (801ms)
  ✓ security.spec.ts: Anti-XSS payload sanitization (1.1s)
  ✓ security.spec.ts: Anti-MQTT Topic Injection rejection (754ms)
  ✓ security.spec.ts: Bounds & Type Checking (815ms)
  ✓ security.spec.ts: Fault Mode Whitelisting (707ms)

[Mobile Chrome - Pixel 5]
  ✓ mobile.spec.ts: Responsive mobile layout & bottom nav (816ms)
  ✓ mobile.spec.ts: Room navigation, device selection & control (789ms)
  ✓ mobile.spec.ts: 2D/3D toggle on mobile & MQTT log view (2.8s)
  ✓ security.spec.ts: Anti-XSS payload sanitization (1.1s)
  ✓ security.spec.ts: Anti-MQTT Topic Injection rejection (679ms)
  ✓ security.spec.ts: Bounds & Type Checking (653ms)
  ✓ security.spec.ts: Fault Mode Whitelisting (732ms)

[Mobile Safari / iPhone 13]
  ✓ mobile.spec.ts: Responsive mobile layout & bottom nav (1.2s)
  ✓ mobile.spec.ts: Room navigation, device selection & control (757ms)
  ✓ mobile.spec.ts: 2D/3D toggle on mobile & MQTT log view (2.1s)
  ✓ security.spec.ts: Anti-XSS payload sanitization (1.0s)
  ✓ security.spec.ts: Anti-MQTT Topic Injection rejection (663ms)
  ✓ security.spec.ts: Bounds & Type Checking (657ms)
  ✓ security.spec.ts: Fault Mode Whitelisting (654ms)

============================== 21 passed (26.8s) ==============================
```

#### 4.2. Pytest Backend Simulator Unit Tests
```text
============================= test session starts ==============================
platform linux -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0
rootdir: /home/blask/code/VinAI20K/Pi-P140
configfile: pyproject.toml

tests/test_simulator.py .................                                [100%]

============================== 17 passed in 1.13s ==============================
```

---

### 5. Kết Luận & Đánh Giá An Ninh

1. **Tính Toàn Vẹn Dữ Liệu:** Hệ thống đã được bảo vệ khỏi các vector tấn công MQTT Topic Injection và XSS Stored.
2. **Khả Năng Phục Hồi & Chống DoS:** Giới hạn tọa độ và kiểm tra kiểu số thực ngăn chặn việc phá hỏng render canvas và engine Three.js.
3. **Trải Nghiệm Đa Nền Tảng:** Giao diện đáp ứng mượt mà trên cả máy tính bàn và các thiết bị di động chuẩn iOS / Android.
4. **Tính Tự Động Hóa:** Quy trình kiểm thử Playwright và Pytest được tích hợp hoàn chỉnh, sẵn sàng cho CI/CD.
