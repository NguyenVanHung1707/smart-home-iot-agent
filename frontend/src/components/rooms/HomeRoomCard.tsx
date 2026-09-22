import type { Room } from "../../types";
import { Icon } from "../shared/Icon";
import type { CircuitKey } from "./homeCircuit";

type HomeRoomCardProps = {
  room: Room;
  circuit: CircuitKey;
  activeCircuit: CircuitKey | null;
  onOpen: () => void;
  onActive: (circuit: CircuitKey | null, element?: HTMLElement) => void;
};

export function HomeRoomCard({ room, circuit, activeCircuit, onOpen, onActive }: HomeRoomCardProps) {
  const activeDevices = room.devices.filter((device) => device.status === "on").length;
  const warnings = room.devices.filter((device) => device.status === "warning" || device.status === "offline").length;
  const sensor = room.devices.find((device) => typeof device.state?.temperature === "number");
  const temperature = sensor?.state?.temperature;
  const humidity = sensor?.state?.humidity;
  const isActive = activeCircuit === circuit;

  return (
    <button
      type="button"
      className={`room-card ${isActive ? "active" : ""}`}
      onClick={(event) => {
        onActive(circuit, event.currentTarget);
        onOpen();
      }}
      onMouseEnter={(event) => onActive(circuit, event.currentTarget)}
      onFocus={(event) => onActive(circuit, event.currentTarget)}
      onBlur={() => onActive(null)}
    >
      <span className="card-topline">
        <span>
          <h3>{room.name}</h3>
          <p>{room.devices.length} thiết bị</p>
        </span>
        <span className={`light-dot ${activeDevices > 0 && warnings === 0 ? "is-lit" : ""}`}>
          <Icon name="bulb" />
        </span>
      </span>
      <span className="room-line">
        <Icon name={room.icon} />
      </span>
      <span className="metrics">
        <span>
          <Icon name="thermo" />
          {typeof temperature === "number" ? `${temperature}°C` : "--"}
        </span>
        <span>
          <Icon name="drop" />
          {typeof humidity === "number" ? `${humidity}%` : "--"}
        </span>
      </span>
    </button>
  );
}
