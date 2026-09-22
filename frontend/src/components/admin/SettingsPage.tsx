import { SectionHeading } from "../shared/SectionHeading";

function Rows({ items }: { items: Array<[string, string]> }) {
  return (
    <div className="hm-rows">
      {items.map(([label, value]) => (
        <p key={label}>
          <span>{label}</span>
          <b>{value}</b>
        </p>
      ))}
    </div>
  );
}

export function SettingsPage() {
  return (
    <section className="hm-admin-page" aria-label="Cài đặt hệ thống">
      <SectionHeading eyebrow="Cấu hình hệ thống" title="Cài đặt & Chính sách an ninh" />
      <p className="hm-page-intro">
        Thiết lập quyền hạn gia đình, chính sách bảo mật cho hành động nhạy cảm và thời hạn chờ duyệt lệnh.
      </p>
      <div className="hm-two-grid">
        <div className="hm-panel">
          <h3 className="hm-panel-title">Chính sách phê duyệt</h3>
          <Rows
            items={[
              ["Mở khóa cửa chính", "Bắt buộc mã PIN (1234) hoặc Admin duyệt"],
              ["Hệ thống an ninh đêm", "Bắt buộc Admin duyệt"],
              ["Thời gian chờ duyệt (TTL)", "5 phút"],
              ["Tự động hủy khi hết hạn", "Bật (Khóa an toàn)"],
              ["Cảnh báo khẩn cấp (Gas/Cháy)", "Bỏ qua phê duyệt · Báo ngay"],
            ]}
          />
        </div>
        <div className="hm-panel">
          <h3 className="hm-panel-title">Mạng & Kết nối MQTT</h3>
          <Rows
            items={[
              ["MQTT Broker", "EMQX / Mosquitto local (Port 1883)"],
              ["Xác thực thiết bị", "mTLS + JWT Access Token"],
              ["QoS mặc định", "QoS 1 (At least once)"],
              ["Thời gian timeout ACK", "2.5 giây"],
              ["Chế độ riêng tư dữ liệu", "100% Local (Không gửi ra Cloud)"],
            ]}
          />
        </div>
      </div>
    </section>
  );
}
