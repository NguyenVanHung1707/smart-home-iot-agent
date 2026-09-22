# HomeMind Hub - Định hướng thiết kế giao diện

## 1. Định hướng phong cách thiết kế

HomeMind Hub nên theo phong cách **Calm Smart Home**: hiện đại, nhẹ nhàng, an toàn, rõ ràng và thân thiện với gia đình. Giao diện cần tạo cảm giác đây là một trung tâm điều khiển nhà riêng tư, chạy cục bộ, đáng tin cậy và dễ tiếp cận cho mọi thành viên trong nhà.

Thiết kế ưu tiên sự yên tĩnh và dễ hiểu hơn cảm giác kỹ thuật. Người dùng cần nhanh chóng biết nhà đang ổn không, thiết bị nào đang hoạt động, lệnh nào đang chạy, lệnh nào cần hỏi lại và hành động nào đang chờ phê duyệt.

Nguyên tắc chính:

- Giao diện sáng, sạch, dễ đọc.
- Bố cục có khoảng trắng rộng, phân nhóm rõ ràng.
- Card mềm mại, bo góc 12-16px, shadow nhẹ.
- Icon đơn giản, dễ nhận biết, đi kèm nhãn văn bản khi biểu thị trạng thái.
- Nội dung tiếng Việt gần gũi, ngắn gọn, tránh thuật ngữ kỹ thuật với Family Member.
- Thông tin kỹ thuật chỉ xuất hiện khi cần, ưu tiên đặt trong card phụ, tab chi tiết hoặc khu vực mở rộng.
- Không chỉ dùng màu để biểu thị trạng thái; luôn có icon và nhãn văn bản đi kèm.

## 2. Bảng màu chính và cách sử dụng

| Token | Màu | Cách sử dụng |
| --- | --- | --- |
| `--primary` | `#0F766E` | Màu thương hiệu chính, dùng cho nút chính, trạng thái được chọn, active navigation, điểm nhấn quan trọng. |
| `--primary-hover` | `#0D9488` | Trạng thái hover/focus của nút chính, toggle đang bật hoặc tương tác tích cực. |
| `--primary-light` | `#CCFBF1` | Nền nhẹ cho chip trạng thái an toàn, card assistant, badge local/private, vùng được chọn. |
| `--accent` | `#F97316` | Microphone, scene buổi tối, thiết bị đang hoạt động, nội dung cần chú ý nhưng chưa nguy hiểm. |
| `--accent-light` | `#FFEDD5` | Nền nhẹ cho trạng thái đang hoạt động, gợi ý scene, assistant listening hoặc warning mềm. |
| `--background` | `#F8FAFC` | Nền toàn ứng dụng. |
| `--surface` | `#FFFFFF` | Card, panel, modal, input, bottom sheet. |
| `--text-primary` | `#0F172A` | Tiêu đề, nhãn quan trọng, nội dung chính. |
| `--text-secondary` | `#475569` | Mô tả, metadata, timestamp, helper text. |
| `--border` | `#CBD5E1` | Viền card, input, divider, table row. |
| `--success` | `#15803D` | Lệnh hoàn tất, thiết bị online, approval đã duyệt. |
| `--warning` | `#B45309` | Cần chú ý, gần hết hạn, dữ liệu cũ, thiết bị phản hồi chậm. |
| `--danger` | `#B91C1C` | Hành động nguy hiểm, từ chối, lỗi nghiêm trọng, xóa, mở khóa/tắt an ninh cần xác nhận. |
| `--info` | `#0369A1` | Thông tin hệ thống, clarification, command đang xử lý. |
| `--offline` | `#64748B` | Thiết bị offline, Hub mất kết nối, trạng thái không xác định. |

Cách dùng màu:

- Teal là màu chủ đạo để tạo cảm giác an toàn, đáng tin cậy, hiện đại và phù hợp với sản phẩm bảo vệ quyền riêng tư.
- Cam ấm chỉ dùng như màu nhấn, không dùng làm màu nền chính của toàn trang.
- Đỏ chỉ dùng cho lỗi, cảnh báo nguy hiểm hoặc hành động phá hủy.
- Trạng thái cần có đủ 3 yếu tố: màu, icon và nhãn. Ví dụ: icon cảnh báo + chữ "Chờ duyệt" + nền cam nhạt.
- Không dùng nhiều màu rực cùng lúc trong một khu vực; ưu tiên nền sáng và điểm nhấn có kiểm soát.

## 3. Typography

Font ưu tiên:

- `Be Vietnam Pro` cho giao diện tiếng Việt có cảm giác gần gũi và hiện đại.
- `Inter` hoặc `Roboto` là lựa chọn thay thế nếu cần tính phổ biến và dễ tích hợp.

Hệ thống chữ đề xuất:

| Vai trò chữ | Kích thước | Độ đậm | Cách dùng |
| --- | --- | --- | --- |
| Page title | 28-32px | 700 | Tên màn hình chính như Dashboard, Assistant, Approvals. |
| Section title | 20-24px | 650-700 | Tiêu đề nhóm nội dung hoặc khu vực chính. |
| Card title | 16-18px | 600 | Tên phòng, tên thiết bị, tên scene, tiêu đề approval. |
| Body | 14-16px | 400-500 | Nội dung mô tả, phản hồi assistant, thông tin trạng thái. |
| Helper text | 12-14px | 400 | Timestamp, ghi chú phụ, lý do disabled. |
| Button label | 14-16px | 600 | Nút điều khiển, submit, approve/reject. |

Nguyên tắc typography:

- Không dùng chữ quá nhỏ cho điều khiển thiết bị; Family Member cần đọc nhanh trên mobile.
- Tiêu đề trong card nên gọn, không dùng kiểu hero quá lớn trong dashboard hoặc tool surface.
- Nội dung trạng thái nên dùng câu ngắn: "Đang chờ Admin duyệt", "Thiết bị offline", "Đã bật đèn phòng khách".
- Với Admin, mã lệnh hoặc ID chỉ nên xuất hiện ở vùng chi tiết, không cạnh tranh với nội dung chính.

## 4. Border radius, spacing và shadow

Border radius:

- Card chính: 12-16px.
- Button: 10-12px.
- Input: 10-12px.
- Badge/chip: 999px nếu là nhãn ngắn.
- Modal/bottom sheet: 16px.

Spacing:

- Khoảng cách trong card: 16-24px.
- Khoảng cách giữa các card: 16-24px.
- Khoảng cách section: 32-48px.
- Trên mobile, ưu tiên padding 16px và các vùng chạm tối thiểu 44px.
- Dashboard nên có layout thoáng, không nén quá nhiều chỉ số trong một hàng.

Shadow:

- Dùng shadow nhẹ để tách surface khỏi nền: `0 4px 16px rgba(15, 23, 42, 0.06)`.
- Với card tương tác, hover có thể tăng shadow nhẹ: `0 8px 24px rgba(15, 23, 42, 0.08)`.
- Không dùng shadow đậm, glow màu, neon hoặc glassmorphism.

## 5. Phong cách button, card, input và icon

### Button

- Primary button dùng nền teal `--primary`, chữ trắng, icon bên trái nếu hành động có biểu tượng rõ.
- Secondary button dùng nền trắng, viền `--border`, chữ `--text-primary`.
- Accent button dùng cam cho microphone, scene đang chạy hoặc lệnh cần chú ý.
- Danger button dùng đỏ cho xóa, từ chối, emergency stop, mở khóa/tắt an ninh khi cần xác nhận.
- Disabled button cần giảm opacity, đổi cursor và có helper text giải thích lý do.
- Hành động nhạy cảm phải có xác nhận rõ ràng, không chỉ đổi màu nút.

### Card

- Card là đơn vị chính cho thiết bị, phòng, scene, approval và trạng thái Hub.
- Mỗi card cần có tiêu đề rõ, icon đại diện, trạng thái bằng icon + nhãn, và hành động chính dễ thấy.
- Device Card của Family Member nên ưu tiên toggle lớn, trạng thái hiện tại và thông tin phòng.
- Card của Admin có thể thêm metadata nhưng nên đặt dưới dạng dòng phụ, tab hoặc expandable detail.
- Không lồng nhiều card trong card; nếu cần phân tách, dùng divider hoặc section con.

### Input

- Input có nền trắng, viền `--border`, bo góc 10-12px.
- Focus state dùng viền teal và outline nhẹ để dễ nhận biết.
- Assistant input nên nổi bật hơn input thông thường, có nút microphone và nút gửi dễ chạm.
- Lỗi input phải có icon, text giải thích và màu đỏ; không chỉ đổi viền đỏ.
- Với PIN hoặc xác nhận bảo mật, không hiển thị giá trị thật và luôn nói rõ hành động sắp thực hiện.

### Icon

- Icon nên đơn giản, nét đều, dễ nhận biết: nhà, phòng, đèn, điều hòa, rèm, loa, khóa, shield, microphone, check, warning.
- Icon trạng thái luôn đi cùng nhãn văn bản.
- Icon thiết bị đang hoạt động có thể dùng accent cam, nhưng không nên làm toàn bộ card thành màu cam.
- Icon offline dùng xám `--offline` kèm nhãn như "Offline" hoặc "Không kết nối".

## 6. Khác biệt giao diện giữa Home Admin và Family Member

| Khía cạnh | Home Admin | Family Member |
| --- | --- | --- |
| Mục tiêu | Giám sát, phê duyệt, quản trị an toàn, kiểm soát toàn bộ nhà. | Điều khiển nhanh, xem trạng thái, dùng Assistant và scene quen thuộc. |
| Navigation | Đầy đủ: Dashboard, Assistant, Rooms, Scenes, Approvals, Activity, Performance, Admin Settings. | Tối giản: Dashboard, Assistant, Rooms, Scenes, Approvals của mình, Activity của mình. |
| Dashboard | Có cảnh báo, pending approval, Hub status, thiết bị, phòng, resource phụ. | Tóm tắt nhà, thiết bị quan trọng, scene hay dùng, nút Assistant lớn. |
| Assistant | Hiển thị plan chi tiết, command status, latency hoặc thông tin kỹ thuật trong vùng phụ. | Hiển thị các bước dễ hiểu, phản hồi rõ, câu hỏi làm rõ đơn giản. |
| Device Card | Có thêm quản trị thiết bị, alias, sensitivity, lý do offline, trạng thái chi tiết. | Nút điều khiển lớn, ít thông tin kỹ thuật, chỉ hiện thiết bị được phép. |
| Approval | Có quyền duyệt/từ chối, thấy đầy đủ ngữ cảnh, PIN/xác nhận bảo mật. | Chỉ xem yêu cầu của mình, trạng thái chờ duyệt, không có approve/reject. |
| Activity | Có filter, audit toàn hệ thống, export khi cần. | Chỉ thấy lịch sử lệnh cá nhân bằng ngôn ngữ dễ hiểu. |
| Hành động nguy hiểm | Luôn dùng danger style, confirmation, mô tả tác động trước khi xác nhận. | Thường chuyển thành yêu cầu chờ Admin, giải thích rõ hành động chưa được gửi tới thiết bị. |

## 7. Ví dụ áp dụng màu sắc

### Dashboard

- Nền trang dùng `--background`.
- Các khối tổng quan dùng card trắng `--surface`, border `--border`, shadow nhẹ.
- Trạng thái "Hub đang chạy cục bộ" dùng nền `--primary-light`, icon shield/check màu `--primary`, nhãn rõ ràng.
- Thiết bị offline dùng icon disconnect màu `--offline`, nhãn "Offline" và mô tả ngắn.
- Pending approval dùng nền `--accent-light`, icon cảnh báo màu `--accent`, nhãn "2 yêu cầu chờ duyệt".
- Lỗi nghiêm trọng như Hub mất kết nối dùng `--danger`, icon alert và CTA rõ ràng.

### Assistant

- Khung nhập lệnh là surface trắng, focus viền teal.
- Nút gửi dùng `--primary`.
- Nút microphone dùng `--accent`; khi đang nghe dùng nền `--accent-light`, icon microphone và nhãn "Đang nghe".
- Clarification dùng `--info` với nhãn "Cần hỏi thêm".
- Command hoàn tất dùng `--success` với icon check và nhãn "Hoàn tất".
- Command chờ duyệt dùng accent cam và câu rõ ràng: "Đang chờ Admin duyệt. Hành động chưa được gửi tới thiết bị."

### Device Card

- Card nền trắng, bo góc 12-16px, shadow nhẹ.
- Thiết bị đang bật dùng icon hoặc indicator màu `--accent`, nhãn "Đang bật".
- Thiết bị tắt dùng text-secondary và nhãn "Đang tắt".
- Thiết bị online dùng `--success` kèm icon check và nhãn "Online".
- Thiết bị offline dùng `--offline`, control disabled và helper text "Không thể điều khiển khi thiết bị offline".
- Toggle chính dùng teal khi bật, xám khi tắt; không chỉ dựa vào màu mà cần có text trạng thái.

### Approval Card

- Approval pending dùng nền trắng với badge `--accent-light`, icon warning màu `--accent`, nhãn "Chờ duyệt".
- Approval đã duyệt dùng `--success`, icon check và nhãn "Đã duyệt".
- Approval bị từ chối dùng `--danger`, icon x và nhãn "Đã từ chối".
- Approval hết hạn dùng `--offline`, icon clock và nhãn "Hết hạn".
- Với Admin, nút "Duyệt" dùng teal và nút "Từ chối" dùng danger style. Trước khi duyệt cần hiển thị người yêu cầu, thiết bị, hành động, thời gian hết hạn và câu xác nhận.
- Với Family Member, card chỉ có trạng thái, mô tả và nút hủy nếu còn được phép; không hiển thị PIN input hoặc nút duyệt.

## 8. Những phong cách cần tránh

- Không thiết kế như dashboard kỹ thuật, server monitoring hoặc DevOps console.
- Không lạm dụng bảng số liệu, biểu đồ, log, command ID ở màn hình dành cho Family Member.
- Không dùng gradient mạnh, glassmorphism, neon glow hoặc hiệu ứng thị giác phức tạp.
- Không dùng animation phức tạp cho thiết bị, approval hoặc assistant; chỉ nên có transition nhẹ.
- Không dùng màu đỏ cho cảnh báo nhẹ hoặc nội dung không nguy hiểm.
- Không chỉ dùng màu để biểu thị trạng thái.
- Không đặt hành động nguy hiểm cạnh hành động thường mà thiếu phân tách hoặc xác nhận.
- Không hiển thị password, token, PIN, raw audio hoặc credential trong bất kỳ UI/log/detail nào.
- Không dùng thuật ngữ như schema, MQTT, policy hash, quantization với Family Member nếu không có giải thích thân thiện.
- Không làm giao diện quá tối, quá tương phản hoặc mang cảm giác hệ thống máy chủ.
