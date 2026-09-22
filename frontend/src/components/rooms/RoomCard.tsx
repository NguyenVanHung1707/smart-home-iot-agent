import type { Room } from "../../types";
import { Icon } from "../shared/Icon";

export function RoomCard({ room, onOpen }: { room: Room; onOpen: () => void }) {
  const activeCount = room.devices.filter((d) => d.status === "on").length;
  const totalCount = room.devices.length;

  return (
    <button type="button" className="hm-room-card" onClick={onOpen} aria-label={`Xem thiết bị trong ${room.name}`}>
      <div className="hm-room-head">
        <span>
          <Icon name={room.icon} />
        </span>
        <div>
          <strong>{room.name}</strong>
          <small>{room.summary}</small>
        </div>
      </div>
      <div className="hm-room-meta">
        <span className="hm-room-device-pill">
          {activeCount > 0 ? `${activeCount}/${totalCount} đang bật` : `${totalCount} thiết bị`}
        </span>
        <small className="hm-room-cta">Chi tiết ➔</small>
      </div>
    </button>
  );
}
