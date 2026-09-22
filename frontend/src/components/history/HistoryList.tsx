import type { HistoryItem } from "../../types";
import { historyStatusLabel } from "../../utils";
import { Icon } from "../shared/Icon";

const statusIcon = {
  done: "check",
  pending: "clock",
  declined: "x",
} as const;

export function HistoryList({
  history,
  selectedId,
  onSelect,
}: {
  history: HistoryItem[];
  selectedId: string | null;
  onSelect: (item: HistoryItem) => void;
}) {
  return (
    <div className="hm-history-list">
      {history.map((item) => (
        <button
          key={item.id}
          type="button"
          className={`hm-history-item ${item.status} ${selectedId === item.id ? "selected" : ""}`}
          onClick={() => onSelect(item)}
        >
          <span className={`hm-hist-icon ${item.status}`}>
            <Icon name={statusIcon[item.status]} />
          </span>
          <div className="hm-hist-body">
            <strong>{item.command}</strong>
            <small>{item.result}</small>
          </div>
          <time className="hm-hist-time">
            <b>{historyStatusLabel(item.status)}</b>
            <span>{item.time}</span>
          </time>
        </button>
      ))}
      {!history.length && (
        <div className="hm-empty-note">Chưa có lịch sử lệnh nào. Hãy thử ra lệnh bằng giọng nói hoặc nhập câu lệnh.</div>
      )}
    </div>
  );
}
