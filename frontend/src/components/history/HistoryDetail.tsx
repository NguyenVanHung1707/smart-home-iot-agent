import type { HistoryItem } from "../../types";
import { historyStatusLabel } from "../../utils";
import { EmptyState } from "../shared/EmptyState";
import { Icon } from "../shared/Icon";

export function HistoryDetail({ item }: { item: HistoryItem | null }) {
  if (!item) {
    return <EmptyState title="Chưa chọn câu lệnh" text="Nhấp vào một dòng lịch sử bên trái để xem phân tích chi tiết của HomeMind Hub." />;
  }

  return (
    <aside className="hm-history-detail">
      <div className="hm-detail-header">
        <Icon name="sparkles" />
        <p className="hm-eyebrow">Chi tiết lệnh & Thực thi</p>
      </div>
      <strong className="hm-detail-cmd">{item.command}</strong>
      <div className="hm-detail-reply-box">
        <span>Kết quả trả về:</span>
        <p>{item.result}</p>
      </div>
      <div className="hm-detail-meta">
        <span className={`hm-detail-badge ${item.status}`}>{historyStatusLabel(item.status)}</span>
        <small>Thời gian: {item.time} · Chỉ lưu trữ trên Hub của bạn</small>
      </div>
    </aside>
  );
}
