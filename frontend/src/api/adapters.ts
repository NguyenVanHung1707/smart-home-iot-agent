import type { ActivityItem, Approval, Device, DeviceCommandAction, DeviceKind, DeviceState, IconName, Room } from "../types";
import { formatTime } from "../utils";
import type { ApiApproval, ApiDevice, ApiDeviceCommand, ApiSimulatorEvent } from "./types";

const roomIcons: Array<[string, IconName]> = [
  ["khách", "sofa"],
  ["ngủ", "bed"],
  ["lối", "door"],
  ["cửa", "door"],
  ["bếp", "kitchen"],
  ["làm việc", "desk"],
  ["office", "desk"],
  ["ban công", "sunrise"],
];

const actionLabels: Record<DeviceCommandAction, string> = {
  on: "Bật",
  off: "Tắt",
  toggle: "Đổi trạng thái",
  set: "Điều chỉnh",
  lock: "Khóa",
  unlock: "Mở khóa",
};

export function roomId(name: string) {
  return name
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/đ/g, "d")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "") || "room";
}

export function roomIcon(name: string): IconName {
  const lower = name.toLowerCase();
  return roomIcons.find(([needle]) => lower.includes(needle))?.[1] ?? "house";
}

function boolState(state: Record<string, unknown>, key: string) {
  return typeof state[key] === "boolean" ? Boolean(state[key]) : undefined;
}

function numberState(state: Record<string, unknown>, key: string) {
  return typeof state[key] === "number" ? Number(state[key]) : undefined;
}

export function deviceStatus(device: ApiDevice): DeviceState {
  if (!device.online) return "offline";
  if (device.kind === "sensor") {
    const battery = numberState(device.state, "battery");
    if (boolState(device.state, "open") || (battery !== undefined && battery < 20)) return "warning";
    return "on";
  }
  if (device.kind === "lock") return boolState(device.state, "locked") === false ? "warning" : "on";
  if (device.kind === "blind") return (numberState(device.state, "position") ?? 0) > 0 ? "on" : "off";
  return boolState(device.state, "power") ? "on" : "off";
}

export function deviceDetail(device: ApiDevice) {
  const { state } = device;
  if (!device.online) return "Mất kết nối";
  if (device.kind === "light") {
    const bri = numberState(state, "brightness");
    return `${boolState(state, "power") ? "Đang bật" : "Đã tắt"}${bri !== undefined ? ` · ${bri}%` : ""}`;
  }
  if (device.kind === "fan") {
    const speed = numberState(state, "speed");
    return `${boolState(state, "power") ? "Đang bật" : "Đã tắt"}${speed !== undefined && speed > 0 ? ` · Mức ${speed}` : ""}`;
  }
  if (device.kind === "aircon") {
    const temp = numberState(state, "target_temperature");
    return `${boolState(state, "power") ? "Đang bật" : "Đã tắt"}${temp !== undefined ? ` · ${temp}°C` : ""}`;
  }
  if (device.kind === "blind") {
    const pos = numberState(state, "position") ?? 0;
    return pos > 0 ? `Đang mở ${pos}%` : "Đã đóng";
  }
  if (device.kind === "speaker") {
    const vol = numberState(state, "volume");
    return `${boolState(state, "power") ? "Đang phát" : "Đã tắt"}${vol !== undefined ? ` · ${vol}%` : ""}`;
  }
  if (device.kind === "display") {
    return typeof state.message === "string" ? `Hiển thị: "${state.message}"` : "Hiển thị sẵn sàng";
  }
  if (device.kind === "lock") return boolState(state, "locked") === false ? "Đang mở" : "Đã khóa";
  if (device.kind === "sensor") {
    if (typeof state.temperature === "number") {
      const humidityStr = typeof state.humidity === "number" ? ` · Độ ẩm ${state.humidity}%` : "";
      return `${state.temperature}°C${humidityStr}`;
    }
    if (typeof state.gas_level === "number") {
      return `Khí gas: ${state.gas_level}${state.alert ? " (CẢNH BÁO!)" : " (An toàn)"}`;
    }
    if (typeof state.motion === "boolean") {
      return state.motion ? "Phát hiện chuyển động" : "Không có chuyển động";
    }
    if (typeof state.light_level === "number" || typeof state.is_dark === "boolean") {
      const darkStr = state.is_dark ? "Trời tối" : "Trời sáng";
      return typeof state.light_level === "number" ? `${darkStr} (${state.light_level} lux)` : darkStr;
    }
    if (typeof state.open === "boolean") return state.open ? "Đang mở" : "Đã đóng";
  }
  return "Sẵn sàng";
}

export function mapDevice(device: ApiDevice): Device {
  return {
    id: device.id,
    name: device.name,
    room: device.room,
    status: deviceStatus(device),
    detail: deviceDetail(device),
    kind: device.kind,
    state: device.state,
    commandable: device.kind !== "sensor" && device.online,
  };
}

function roomSummary(devices: Device[]) {
  const active = devices.filter((device) => device.status === "on").length;
  const warnings = devices.filter((device) => device.status === "warning" || device.status === "offline").length;
  if (warnings) return `${warnings} thiết bị cần chú ý`;
  if (active) return `${active} thiết bị đang hoạt động`;
  return "Tất cả đang nghỉ";
}

export function devicesToRooms(devices: ApiDevice[]): Room[] {
  const grouped = new Map<string, Device[]>();
  for (const device of devices) {
    const current = grouped.get(device.room) ?? [];
    current.push(mapDevice(device));
    grouped.set(device.room, current);
  }
  return [...grouped.entries()].map(([name, roomDevices]) => ({
    id: roomId(name),
    name,
    summary: roomSummary(roomDevices),
    icon: roomIcon(name),
    devices: roomDevices,
  }));
}

export function commandLabel(command: ApiDeviceCommand, target: string) {
  const detail = command.action === "set" && command.value && typeof command.value === "object"
    ? Object.entries(command.value as Record<string, unknown>)
      .map(([key, value]) => `${key} ${value}`)
      .join(", ")
    : "";
  return `${actionLabels[command.action] ?? command.action} ${target}${detail ? ` · ${detail}` : ""}`;
}

export function approvalsToUi(approvals: ApiApproval[], devices: ApiDevice[]): Approval[] {
  const deviceNames = new Map(devices.map((device) => [device.id, device.name]));
  return approvals.map((approval) => {
    const target = deviceNames.get(approval.device_id) ?? approval.device_id;
    return {
      id: approval.id,
      by: approval.requested_by || "Thành viên nhà",
      target,
      action: commandLabel(approval.command, target),
      status: approval.status,
      expires: approval.expires_at ? relativeTime(approval.expires_at) : "Đang chờ",
    };
  });
}

function extractStateDetail(stateObj: Record<string, unknown>, status?: string, online?: boolean): string {
  if (status === "offline" || online === false) return "Mất kết nối";
  if (typeof stateObj.temperature === "number") {
    return `Nhiệt độ ${stateObj.temperature}°C${typeof stateObj.humidity === "number" ? ` · Ẩm ${stateObj.humidity}%` : ""}`;
  }
  if (typeof stateObj.gas_level === "number") {
    return `Khí gas: ${stateObj.gas_level}${stateObj.alert ? " (CẢNH BÁO)" : " ppm"}`;
  }
  if (typeof stateObj.ppm === "number") return `Khí gas: ${stateObj.ppm} ppm`;
  if (typeof stateObj.motion === "boolean") return stateObj.motion ? "Phát hiện chuyển động" : "Không có chuyển động";
  if (typeof stateObj.power === "boolean") return stateObj.power ? "Bật nguồn" : "Tắt nguồn";
  if (typeof stateObj.position === "number") return `Mở ${stateObj.position}%`;
  if (typeof stateObj.locked === "boolean") return stateObj.locked ? "Đã khóa" : "Đang mở";
  return "";
}

export function eventsToActivity(events: ApiSimulatorEvent[], devices: ApiDevice[]): ActivityItem[] {
  const deviceNames = new Map(devices.map((device) => [device.id, device.name]));
  const items: ActivityItem[] = [];
  const lastStateDigest = new Map<string, string>();

  for (const event of events.slice(-60)) {
    const deviceId = event.device_id;
    const deviceName = deviceId ? deviceNames.get(deviceId) ?? deviceId : "Hub";
    const type = event.type ?? "state";

    if (type === "state") {
      const stateObj = (event.state as Record<string, unknown>) || {};
      const detail = extractStateDetail(stateObj, event.status, event.online);
      if (deviceId && lastStateDigest.get(deviceId) === detail && !event.action && event.status !== "offline") {
        continue;
      }
      if (deviceId) {
        lastStateDigest.set(deviceId, detail);
      }

      items.push({
        id: event.command_id ?? `${event.timestamp ?? "event"}-${items.length}`,
        time: event.timestamp ? formatTime(new Date(event.timestamp)) : "Bây giờ",
        text: detail ? `${deviceName} · ${detail}` : `${deviceName}`,
        status: event.status === "offline" ? "Mất kết nối" : "Cập nhật",
      });
    } else {
      const status =
        type === "ack"
          ? event.status === "ok"
            ? "Hoàn tất"
            : "Từ chối"
          : type === "timeout"
            ? "Quá hạn"
            : type === "command"
              ? "Đã gửi"
              : "Cập nhật";
      const action = event.action ? `${event.action} · ` : "";
      items.push({
        id: event.command_id ?? `${event.timestamp ?? "event"}-${items.length}`,
        time: event.timestamp ? formatTime(new Date(event.timestamp)) : "Bây giờ",
        text: `${action}${deviceName}`,
        status,
      });
    }
  }

  return items.slice(-30).reverse();
}

export function relativeTime(value: string) {
  const expires = new Date(value).getTime();
  if (!Number.isFinite(expires)) return value;
  const seconds = Math.max(0, Math.round((expires - Date.now()) / 1000));
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

export function defaultCommandForDevice(device: Device): ApiDeviceCommand | null {
  if (!device.kind || device.status === "offline") return null;
  if (device.kind === "lock") return { action: device.status === "warning" ? "lock" : "unlock" };
  if (device.kind === "blind") {
    const pos = (device.state?.position as number) ?? 0;
    return { action: "set", value: { position: pos > 0 ? 0 : 70 } };
  }
  if (device.kind === "light") return { action: device.status === "on" ? "off" : "on" };
  if (device.kind === "fan") return { action: device.status === "on" ? "off" : "on" };
  if (device.kind === "aircon") return { action: device.status === "on" ? "off" : "on" };
  if (device.kind === "speaker") return { action: device.status === "on" ? "off" : "on" };
  return null;
}

export function commandActionLabel(command: ApiDeviceCommand | null) {
  if (!command) return "";
  return actionLabels[command.action] ?? command.action;
}
