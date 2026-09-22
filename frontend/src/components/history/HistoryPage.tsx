import type { HistoryItem } from "../../types";
import { SectionHeading } from "../shared/SectionHeading";
import { HistoryDetail } from "./HistoryDetail";
import { HistoryList } from "./HistoryList";

export function HistoryPage({
  history,
  selectedId,
  onSelect,
}: {
  history: HistoryItem[];
  selectedId: string | null;
  onSelect: (item: HistoryItem) => void;
}) {
  const selected = history.find((item) => item.id === selectedId) ?? (history.length ? history[0] : null);

  return (
    <section className="hm-history-page" aria-label="Lịch sử điều khiển">
      <SectionHeading
        eyebrow="Lịch sử cá nhân"
        title="Nhật ký lệnh của bạn"
        aside={<span className="hm-count">{history.length} Lệnh</span>}
      />
      <p className="hm-page-intro">
        Xem lại những câu lệnh bạn đã yêu cầu (bằng giọng nói hoặc bàn phím) và kế hoạch xử lý tương ứng của Hub.
      </p>
      <div className="hm-history-layout">
        <HistoryList history={history} selectedId={selected?.id ?? null} onSelect={onSelect} />
        <HistoryDetail item={selected} />
      </div>
    </section>
  );
}
