import type { DeviceState } from "../../types";
import { deviceStatusLabel } from "../../utils";
import { Icon } from "./Icon";

const iconByStatus = {
  on: "power",
  off: "powerOff",
  offline: "wifiOff",
  warning: "alert",
} as const;

export function DeviceStatus({ status }: { status: DeviceState }) {
  return (
    <span className={`hm-device-status ${status}`}>
      <i />
      <Icon name={iconByStatus[status]} />
      {deviceStatusLabel(status)}
    </span>
  );
}
