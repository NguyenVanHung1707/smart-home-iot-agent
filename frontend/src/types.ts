export type Role = "member" | "homeadmin";
export type Page = "Rooms" | "Presets" | "History" | "Requests" | "Approvals" | "Activity" | "Performance" | "MQTT" | "Settings";
export type ThemeMode = "dark" | "light";
export type DeviceState = "on" | "off" | "offline" | "warning";
export type HistoryStatus = "done" | "pending" | "declined";
export type ApprovalStatus = "pending" | "approved" | "rejected" | "expired";
export type VoiceMode = "command" | "chat";
export type DeviceKind = "light" | "fan" | "aircon" | "blind" | "speaker" | "lock" | "sensor" | "display";
export type DeviceCommandAction = "on" | "off" | "toggle" | "set" | "lock" | "unlock";
export type DataMode = "simulator" | "real";

export type IconName =
  | "alert" | "arrowLeft" | "arrowRight" | "arrowUp" | "bed" | "bell" | "chart" | "check"
  | "clock" | "close" | "door" | "house" | "info" | "list" | "menu" | "mic" | "micOff"
  | "power" | "powerOff" | "settings" | "shield" | "sofa" | "sparkles" | "sun" | "sunrise" | "moon"
  | "wifi" | "wifiOff" | "x" | "mqtt" | "cpu" | "lock" | "unlock" | "sliders" | "refresh"
  | "plus" | "trash" | "pencil" | "kitchen" | "desk" | "bulb" | "tv" | "fan"
  | "ac" | "drop" | "thermo";

export interface DiscoveredDevice {
  device_id: string;
  name: string;
  room?: string;
  kind?: DeviceKind;
  state?: Record<string, unknown>;
  discovered_at: string;
}

export interface CreateDevicePayload {
  id: string;
  name: string;
  room: string;
  kind: DeviceKind;
  state?: Record<string, unknown>;
}

export interface UpdateDevicePayload {
  name?: string;
  room?: string;
  state?: Record<string, unknown>;
}

export interface AppNotification {
  id: string;
  type: "offline" | "online" | "discovery" | "approval" | "info";
  title: string;
  message: string;
  time: string;
  timestamp: number;
  read: boolean;
  deviceId?: string;
}

export interface Device {
  id: string;
  name: string;
  room: string;
  status: DeviceState;
  detail?: string;
  kind?: DeviceKind;
  state?: Record<string, unknown>;
  commandable?: boolean;
}

/** Một lệnh được chạy khi người dùng kích hoạt preset/ngữ cảnh. */
export interface PresetAction {
  id: string;
  deviceId: string;
  action: DeviceCommandAction;
  value?: Record<string, unknown>;
}

/** Preset được lưu riêng cho mỗi chế độ Simulator hoặc thiết bị thật. */
export interface HomePreset {
  id: string;
  name: string;
  icon: "house" | "sparkles" | "bed" | "lock";
  actions: PresetAction[];
}

export interface Room {
  id: string;
  name: string;
  summary: string;
  icon: IconName;
  devices: Device[];
}

export interface HistoryItem {
  id: string;
  status: HistoryStatus;
  command: string;
  result: string;
  time: string;
}

export interface Approval {
  id: string;
  by: string;
  target: string;
  action: string;
  status: ApprovalStatus;
  expires: string;
}

export interface ActivityItem {
  id: string;
  time: string;
  text: string;
  status: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
}

export interface NavItem {
  page: Page;
  label: string;
  icon: IconName;
}

export interface VoiceState {
  open: boolean;
  mode: VoiceMode;
  listening: boolean;
  error: string;
  finalTranscript: string;
  interimTranscript: string;
}

export interface SpeechRecognitionResultLike {
  isFinal: boolean;
  0: { transcript: string };
}

export interface SpeechRecognitionEventLike extends Event {
  results: ArrayLike<SpeechRecognitionResultLike>;
}

export interface SpeechRecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onstart: (() => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

export interface SpeechRecognitionWindow extends Window {
  SpeechRecognition?: new () => SpeechRecognitionLike;
  webkitSpeechRecognition?: new () => SpeechRecognitionLike;
}
