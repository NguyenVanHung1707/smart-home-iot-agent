import type { Approval, Role, Room } from "../../types";

function Stat({ label, value, detail, tone }: { label: string; value: string | number; detail: string; tone: string }) {
  return (
    <article className={`hm-stat ${tone}`}>
      <small>{label}</small>
      <strong>{value}</strong>
      <span>{detail}</span>
    </article>
  );
}

export function OverviewStats({ role, rooms, approvals }: { role: Role; rooms: Room[]; approvals: Approval[] }) {
  const devices = rooms.flatMap((room) => room.devices);
  const online = devices.filter((device) => device.status !== "offline").length;
  const active = devices.filter((device) => device.status === "on").length;
  const pendingApprovals = approvals.filter((item) => item.status === "pending").length;

  return (
    <section className={`hm-overview ${role === "homeadmin" ? "admin-role" : "member-role"}`} aria-label="Tổng quan ngôi nhà">
      <Stat label="Thiết bị kết nối" value={`${online}/${devices.length}`} detail="MQTT Live Ack" tone="ok" />
      <Stat label="Đang hoạt động" value={active} detail="Đèn, AC, rèm, loa" tone="accent" />
      {role === "homeadmin" ? (
        <Stat label="Chờ phê duyệt" value={pendingApprovals} detail="Mở khóa & an ninh" tone="warn" />
      ) : null}
      <Stat label="Edge Node" value="61°C" detail="Pi 4 · Qwen Q4 local" tone="info" />
    </section>
  );
}
