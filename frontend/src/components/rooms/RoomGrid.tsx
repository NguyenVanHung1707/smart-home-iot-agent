import type { Room } from "../../types";
import { RoomCard } from "./RoomCard";

export function RoomGrid({
  rooms,
  emptySlots,
  onOpenRoom,
}: {
  rooms: Room[];
  emptySlots: number;
  onOpenRoom: (room: Room) => void;
}) {
  return (
    <div className="hm-room-grid">
      {rooms.map((room) => (
        <RoomCard key={room.id} room={room} onOpen={() => onOpenRoom(room)} />
      ))}
      {Array.from({ length: emptySlots }).map((_, index) => (
        <div key={index} className="hm-room-card hm-room-placeholder" aria-hidden="true" />
      ))}
    </div>
  );
}
