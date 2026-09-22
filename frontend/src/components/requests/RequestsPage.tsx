import type { Approval } from "../../types";
import { approvalStatusLabel } from "../../utils";
import { Icon } from "../shared/Icon";
import { SectionHeading } from "../shared/SectionHeading";

export function RequestsPage({
  approvals = [],
  onCancelApproval,
  cancelled,
  onCancel,
}: {
  approvals?: Approval[];
  onCancelApproval?: (id: string) => Promise<void> | void;
  cancelled?: boolean;
  onCancel?: () => void;
}) {
  const pendingCount = approvals.filter((item) => item.status === "pending").length;

  return (
    <section className="hm-requests-page" aria-label="Yêu cầu an ninh của bạn">
      <SectionHeading
        eyebrow="Chế độ Gia đình"
        title="Yêu cầu phê duyệt an ninh"
        aside={<span className="hm-count">{pendingCount} Chờ xử lý</span>}
      />
      <p className="hm-page-intro">
        Theo dõi trạng thái những hành động nhạy cảm (như mở khóa cửa) cần sự chấp thuận của Home Owner trước khi gửi lệnh tới thiết bị.
      </p>

      {approvals.length > 0 ? (
        <div className="hm-approval-list">
          {approvals.map((item) => (
            <article key={item.id} className="hm-approval-card hm-request-card">
              <div className="hm-approval-info">
                <span className={`hm-pill ${item.status}`}>
                  <i />
                  {approvalStatusLabel(item.status)}
                </span>
                <h2>{item.action}</h2>
                <p>
                  Thiết bị: <strong>{item.target}</strong>
                </p>
                <small>
                  {item.status === "pending"
                    ? `Thời hạn xử lý còn: ${item.expires} · Đang chờ Home Owner xác nhận`
                    : item.status === "approved"
                      ? "Yêu cầu đã được Quản trị viên chấp thuận và thực thi."
                      : item.status === "rejected"
                        ? "Yêu cầu đã bị Quản trị viên từ chối hoặc bạn đã hủy."
                        : "Yêu cầu đã hết hạn và tự động hủy."}
                </small>
              </div>
              {item.status === "pending" && onCancelApproval ? (
                <div className="hm-approval-actions">
                  <button
                    type="button"
                    className="danger"
                    onClick={() => void onCancelApproval(item.id)}
                  >
                    Hủy yêu cầu
                  </button>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <div className="hm-empty-state">
          <Icon name="shield" />
          <p>Bạn chưa có yêu cầu an ninh nào.</p>
        </div>
      )}
    </section>
  );
}
