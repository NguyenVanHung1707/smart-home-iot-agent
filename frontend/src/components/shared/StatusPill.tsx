import type { ApprovalStatus, HistoryStatus } from "../../types";
import { approvalStatusLabel, historyStatusLabel } from "../../utils";

export function StatusPill({ status }: { status: ApprovalStatus | HistoryStatus }) {
  const label = status === "done" || status === "declined" ? historyStatusLabel(status) : approvalStatusLabel(status);
  return (
    <span className={`hm-pill ${status}`}>
      <i />
      {label}
    </span>
  );
}
