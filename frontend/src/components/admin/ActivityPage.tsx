import type { ActivityItem } from "../../types";
import { SectionHeading } from "../shared/SectionHeading";

export function ActivityPage({ activity }: { activity: ActivityItem[] }) {
  return (
    <section className="hm-admin-page" aria-label="Nhật ký hoạt động">
      <SectionHeading eyebrow="Audit Log" title="Nhật ký hoạt động toàn nhà" />
      <p className="hm-page-intro">
        Theo dõi toàn bộ chuỗi sự kiện, lệnh người dùng và trạng thái phản hồi của các thiết bị trong nhà.
      </p>
      <div className="hm-panel">
        <div className="hm-activity-list">
          {activity.map((item) => (
            <div key={item.id} className="hm-activity-row">
              <time>{item.time}</time>
              <p>{item.text}</p>
              <span className={`hm-activity-badge ${item.status.toLowerCase().includes("lỗi") || item.status.toLowerCase().includes("từ chối") ? "error" : "ok"}`}>
                {item.status}
              </span>
            </div>
          ))}
          {!activity.length && (
            <p className="hm-empty-note">Chưa có nhật ký hoạt động nào.</p>
          )}
        </div>
      </div>
    </section>
  );
}
