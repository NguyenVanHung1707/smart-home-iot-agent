import { Icon } from "../shared/Icon";

export function ApprovalAlert({ cancelled, onCancel }: { cancelled: boolean; onCancel: () => void }) {
  if (cancelled) {
    return (
      <section className="hm-alert info" role="alert">
        <Icon name="info" />
        <div>
          <strong>Yêu cầu đã được hủy</strong>
          <p>Yêu cầu mở khóa an toàn đã được bạn hủy trước khi quản trị viên duyệt.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="hm-alert info" role="alert">
      <Icon name="info" />
      <div className="hm-alert-body">
        <strong>Đang chờ xác nhận từ Home Owner</strong>
        <p>
          Yêu cầu <span>“Mở khóa cửa chính”</span> của bạn đang được gửi tới điện thoại của quản trị viên để duyệt an ninh.
        </p>
        <small>
          <Icon name="clock" /> Vừa gửi · Thường được duyệt trong 1-2 phút
        </small>
      </div>
      <button type="button" className="hm-alert-cancel-btn" onClick={onCancel}>
        Hủy yêu cầu
      </button>
    </section>
  );
}
