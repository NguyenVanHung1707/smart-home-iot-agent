import type { Approval } from "../../types";
import { approvalStatusLabel } from "../../utils";
import { SectionHeading } from "../shared/SectionHeading";

function ApprovalCard({
  item,
  onApprove,
  onReject,
}: {
  item: Approval;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}) {
  return (
    <article className="hm-approval-card">
      <div className="hm-approval-info">
        <span className={`hm-pill ${item.status}`}>
          <i />
          {approvalStatusLabel(item.status)}
        </span>
        <h2>{item.action}</h2>
        <p>
          Mục tiêu: <strong>{item.target}</strong> · Yêu cầu bởi: <strong>{item.by}</strong>
        </p>
        <small>
          {item.status === "pending"
            ? `Thời hạn xử lý còn: ${item.expires}`
            : "Quyết định phê duyệt đã được lưu vào nhật ký bảo mật."}
        </small>
      </div>
      {item.status === "pending" ? (
        <div className="hm-approval-actions">
          <button type="button" className="primary" onClick={() => onApprove(item.id)}>
            Duyệt
          </button>
          <button type="button" className="danger" onClick={() => onReject(item.id)}>
            Từ chối
          </button>
        </div>
      ) : null}
    </article>
  );
}

export function ApprovalsPage({
  approvals,
  onApprove,
  onReject,
}: {
  approvals: Approval[];
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}) {
  const pendingCount = approvals.filter((item) => item.status === "pending").length;

  return (
    <section className="hm-admin-page" aria-label="Phê duyệt an ninh">
      <SectionHeading
        eyebrow="Quản trị an ninh"
        title="Yêu cầu phê duyệt"
        aside={<span className="hm-count">{pendingCount} Chờ xử lý</span>}
      />
      <p className="hm-page-intro">
        Xác nhận các hành động nhạy cảm (như mở khóa cửa chính, tắt an ninh, mở cửa gara) trước khi HomeMind Hub phát lệnh qua MQTT.
      </p>
      <div className="hm-approval-list">
        {approvals.map((item) => (
          <ApprovalCard key={item.id} item={item} onApprove={onApprove} onReject={onReject} />
        ))}
        {!approvals.length && (
          <p className="hm-empty-note">Không có yêu cầu phê duyệt nào.</p>
        )}
      </div>
    </section>
  );
}
