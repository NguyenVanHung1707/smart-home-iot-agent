import { useEffect, useState } from "react";
import type { ActivityItem, HistoryItem } from "../../types";
import { Icon } from "../shared/Icon";
import { SectionHeading } from "../shared/SectionHeading";
import { HistoryDetail } from "./HistoryDetail";
import { HistoryList } from "./HistoryList";

export function HistoryPage({
  history,
  selectedId,
  onSelect,
  activity = [],
  initialTab = "commands",
}: {
  history: HistoryItem[];
  selectedId: string | null;
  onSelect: (item: HistoryItem) => void;
  activity?: ActivityItem[];
  initialTab?: "commands" | "system";
}) {
  const [activeTab, setActiveTab] = useState<"commands" | "system">(initialTab);

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  const selected = history.find((item) => item.id === selectedId) ?? (history.length ? history[0] : null);

  return (
    <section className="hm-history-page" aria-label="Lịch sử & Nhật ký hoạt động">
      <SectionHeading
        eyebrow="Audit & Commands"
        title="Lịch Sử & Nhật Ký Hoạt Động"
        aside={
          <span className="hm-count">
            {activeTab === "commands" ? `${history.length} Lệnh` : `${activity.length} Sự kiện`}
          </span>
        }
      />
      <p className="hm-page-intro">
        Theo dõi lịch sử câu lệnh điều khiển (giọng nói / bàn phím) và toàn bộ chuỗi sự kiện, phản hồi của các thiết bị trong nhà.
      </p>

      {/* Tab Switcher */}
      <div className="hm-tab-switcher">
        <button
          type="button"
          className={`hm-tab-btn ${activeTab === "commands" ? "active" : ""}`}
          onClick={() => setActiveTab("commands")}
        >
          <Icon name="clock" />
          <span>Lịch sử lệnh cá nhân ({history.length})</span>
        </button>
        <button
          type="button"
          className={`hm-tab-btn ${activeTab === "system" ? "active" : ""}`}
          onClick={() => setActiveTab("system")}
        >
          <Icon name="list" />
          <span>Nhật ký hệ thống toàn nhà ({activity.length})</span>
        </button>
      </div>

      {activeTab === "commands" ? (
        <div className="hm-history-layout">
          <HistoryList history={history} selectedId={selected?.id ?? null} onSelect={onSelect} />
          <HistoryDetail item={selected} />
        </div>
      ) : (
        <div className="hm-panel" style={{ marginTop: 10 }}>
          <div className="hm-activity-list">
            {activity.map((item) => (
              <div key={item.id} className="hm-activity-row">
                <time>{item.time}</time>
                <p>{item.text}</p>
                <span
                  className={`hm-activity-badge ${
                    item.status.toLowerCase().includes("lỗi") || item.status.toLowerCase().includes("từ chối")
                      ? "error"
                      : "ok"
                  }`}
                >
                  {item.status}
                </span>
              </div>
            ))}
            {!activity.length && <p className="hm-empty-note">Chưa có nhật ký hoạt động nào.</p>}
          </div>
        </div>
      )}
    </section>
  );
}
