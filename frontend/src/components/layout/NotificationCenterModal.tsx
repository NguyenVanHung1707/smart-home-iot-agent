import { useDialogFocus } from "../../hooks/useDialogFocus";
import type { AppNotification, Approval } from "../../types";
import { Icon } from "../shared/Icon";

export function NotificationCenterModal({
  open,
  notifications,
  approvals,
  onClose,
  onMarkAllRead,
  onClearAll,
  onDismissNotification,
  onOpenApprovals,
  onOpenAddDevice,
}: {
  open: boolean;
  notifications: AppNotification[];
  approvals: Approval[];
  onClose: () => void;
  onMarkAllRead: () => void;
  onClearAll: () => void;
  onDismissNotification: (id: string) => void;
  onOpenApprovals?: () => void;
  onOpenAddDevice?: () => void;
}) {
  const dialogRef = useDialogFocus<HTMLElement>(open, onClose);
  if (!open) return null;

  const pendingApprovals = onOpenApprovals ? approvals.filter((a) => a.status === "pending") : [];
  const unreadCount = notifications.filter((n) => !n.read).length + pendingApprovals.length;

  return (
    <div className="hm-modal-backdrop" role="presentation" onClick={onClose}>
      <section
        ref={dialogRef}
        className="hm-room-modal hm-notif-center-modal"
        role="dialog"
        aria-modal="true"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="hm-room-modal-head">
          <div className="hm-room-head">
            <span className="hm-badge-icon notif-bell">
              <Icon name="bell" />
            </span>
            <div>
              <strong>Trung tâm thông báo</strong>
              <p className="hm-text-subtle">
                {unreadCount > 0
                  ? `Bạn có ${unreadCount} thông báo và sự kiện mới`
                  : "Tất cả thiết bị và thông báo đều đã cập nhật"}
              </p>
            </div>
          </div>
          <div className="hm-notif-head-actions">
            {notifications.length > 0 && (
              <>
                <button
                  type="button"
                  className="hm-btn-ghost-sm"
                  onClick={onMarkAllRead}
                  title="Đánh dấu tất cả đã đọc"
                >
                  <Icon name="check" />
                  <span>Đã đọc hết</span>
                </button>
                <button
                  type="button"
                  className="hm-btn-ghost-sm danger"
                  onClick={onClearAll}
                  title="Xóa danh sách thông báo"
                >
                  <Icon name="trash" />
                  <span>Xóa hết</span>
                </button>
              </>
            )}
            <button className="hm-close-btn" onClick={onClose} aria-label="Đóng">
              <Icon name="close" />
            </button>
          </div>
        </header>

        <div className="hm-notif-body">
          {/* Pending Approvals Section */}
          {pendingApprovals.length > 0 && (
            <div className="hm-notif-group">
              <div className="hm-notif-group-title">
                <Icon name="shield" />
                <span>Yêu cầu phê duyệt an ninh ({pendingApprovals.length})</span>
              </div>
              {pendingApprovals.map((appr) => (
                <div key={appr.id} className="hm-notif-card approval">
                  <div className="hm-notif-icon-box approval">
                    <Icon name="lock" />
                  </div>
                  <div className="hm-notif-content">
                    <strong>Yêu cầu mở khóa: {appr.target}</strong>
                    <p>Người yêu cầu: {appr.by} · Hết hạn trong {appr.expires}</p>
                    <span className="hm-notif-time">Cần quản trị viên duyệt</span>
                  </div>
                  {onOpenApprovals && (
                    <button
                      type="button"
                      className="hm-btn-notif-action"
                      onClick={() => {
                        onClose();
                        onOpenApprovals();
                      }}
                    >
                      Xem duyệt
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* System & Device Notifications */}
          <div className="hm-notif-group">
            <div className="hm-notif-group-title">
              <Icon name="sliders" />
              <span>Trạng thái kết nối & Thiết bị ({notifications.length})</span>
            </div>

            {notifications.length === 0 ? (
              <div className="hm-notif-empty">
                <Icon name="check" />
                <p>Không có sự cố hoặc thông báo mới nào.</p>
                <small>Mọi thiết bị đang hoạt động ổn định.</small>
              </div>
            ) : (
              notifications.map((n) => {
                const isOffline = n.type === "offline";
                const isOnline = n.type === "online";
                const isDiscovery = n.type === "discovery";

                return (
                  <div
                    key={n.id}
                    className={`hm-notif-card ${n.type} ${n.read ? "read" : "unread"}`}
                  >
                    <div className={`hm-notif-icon-box ${n.type}`}>
                      <Icon
                        name={
                          isOffline
                            ? "wifiOff"
                            : isOnline
                              ? "wifi"
                              : isDiscovery
                                ? "sparkles"
                                : "info"
                        }
                      />
                    </div>
                    <div className="hm-notif-content">
                      <div className="hm-notif-title-row">
                        <strong>{n.title}</strong>
                        {!n.read && <span className="hm-notif-unread-dot" />}
                      </div>
                      <p>{n.message}</p>
                      <span className="hm-notif-time">{n.time}</span>
                    </div>

                    <div className="hm-notif-card-actions">
                      {isDiscovery && onOpenAddDevice && (
                        <button
                          type="button"
                          className="hm-btn-notif-action primary"
                          onClick={() => {
                            onClose();
                            onOpenAddDevice();
                          }}
                        >
                          Ghép nối
                        </button>
                      )}
                      <button
                        type="button"
                        className="hm-notif-dismiss-btn"
                        onClick={() => onDismissNotification(n.id)}
                        title="Bỏ qua"
                      >
                        <Icon name="close" />
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
