import type { ApiDeviceCommand } from "../../api/types";
import { defaultCommandForDevice } from "../../api/adapters";
import type { Device } from "../../types";
import { Icon } from "../shared/Icon";
import type { CircuitKey } from "./homeCircuit";
import { deviceIcon } from "./homeCircuit";

type HomeDeviceCardProps = {
  device: Device;
  circuit: CircuitKey;
  activeCircuit: CircuitKey | null;
  onActive: (circuit: CircuitKey | null, element?: HTMLElement) => void;
  onDeviceCommand?: (device: Device, command: ApiDeviceCommand) => Promise<void> | void;
  onRequestPinUnlock?: (device: Device) => void;
};

export function HomeDeviceCard({
  device,
  circuit,
  activeCircuit,
  onActive,
  onDeviceCommand,
  onRequestPinUnlock,
}: HomeDeviceCardProps) {
  const isActive = activeCircuit === circuit;
  const detail = device.detail || (device.status === "on" ? "Đang hoạt động" : "Đang nghỉ");
  const isOnline = device.status !== "offline";
  const isLock = device.kind === "lock";
  const isLocked = isLock && Boolean(device.state?.locked ?? (device.status !== "warning"));

  const handleToggle = (e?: React.MouseEvent) => {
    if (e) {
      e.stopPropagation();
    }
    if (!onDeviceCommand || !device.commandable || !isOnline) return;

    if (isLock) {
      if (isLocked) {
        if (onRequestPinUnlock) {
          onRequestPinUnlock(device);
        } else {
          void onDeviceCommand(device, { action: "unlock" });
        }
      } else {
        void onDeviceCommand(device, { action: "lock" });
      }
      return;
    }

    const defaultCmd = defaultCommandForDevice(device);
    if (defaultCmd) {
      void onDeviceCommand(device, defaultCmd);
    }
  };

  return (
    <article
      className={`device-card ${isActive ? "active" : ""} ${device.status === "on" ? "is-powered-on" : ""}`}
      tabIndex={0}
      onMouseEnter={(event) => onActive(circuit, event.currentTarget)}
      onFocus={(event) => onActive(circuit, event.currentTarget)}
      onBlur={() => onActive(null)}
      onClick={(event) => {
        onActive(circuit, event.currentTarget);
        handleToggle();
      }}
      title={device.commandable ? `Nhấp để ${device.status === "on" ? "Tắt" : "Bật"} ${device.name}` : undefined}
      style={{ cursor: device.commandable ? "pointer" : "default" }}
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

      {device.commandable && isOnline && (
        <button
          type="button"
          className={`device-quick-toggle ${device.status === "on" ? "active" : ""} ${isLock ? (isLocked ? "locked" : "unlocked") : ""}`}
          onClick={handleToggle}
          aria-label={
            isLock
              ? isLocked
                ? `Mở khóa ${device.name}`
                : `Khóa ${device.name}`
              : device.status === "on"
                ? `Tắt ${device.name}`
                : `Bật ${device.name}`
          }
          title={
            isLock
              ? isLocked
                ? "Bấm để mở khóa"
                : "Bấm để khóa lại"
              : device.status === "on"
                ? "Bấm để tắt"
                : "Bấm để bật"
          }
        >
          <span className="toggle-switch-track">
            <span className="toggle-switch-thumb" />
          </span>
          <span className="toggle-switch-text">
            {isLock ? (isLocked ? "KHÓA" : "MỞ") : device.status === "on" ? "BẬT" : "TẮT"}
          </span>
        </button>
      )}
    </article>
  );
}
