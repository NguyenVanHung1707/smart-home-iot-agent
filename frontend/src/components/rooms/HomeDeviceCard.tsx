import type { Device } from "../../types";
import { Icon } from "../shared/Icon";
import type { CircuitKey } from "./homeCircuit";
import { deviceIcon } from "./homeCircuit";

type HomeDeviceCardProps = {
  device: Device;
  circuit: CircuitKey;
  activeCircuit: CircuitKey | null;
  onActive: (circuit: CircuitKey | null, element?: HTMLElement) => void;
};

export function HomeDeviceCard({ device, circuit, activeCircuit, onActive }: HomeDeviceCardProps) {
  const isActive = activeCircuit === circuit;
  const detail = device.detail || (device.status === "on" ? "Đang hoạt động" : "Đang nghỉ");

  return (
    <article
      className={`device-card ${isActive ? "active" : ""}`}
      tabIndex={0}
      onMouseEnter={(event) => onActive(circuit, event.currentTarget)}
      onFocus={(event) => onActive(circuit, event.currentTarget)}
      onBlur={() => onActive(null)}
      onClick={(event) => onActive(circuit, event.currentTarget)}
    >
      <div className="device-icon">
        <Icon name={deviceIcon(device.kind)} />
      </div>
      <div className="device-info">
        <h3>{device.name}</h3>
        <p>{device.room}</p>
        <strong>
          <span className="status-state">{device.status === "on" ? "ON" : device.status === "offline" ? "OFFLINE" : "IDLE"}</span>
          <span className="status-separator"> • </span>
          <span className="status-meta">{detail}</span>
        </strong>
      </div>
    </article>
  );
}
