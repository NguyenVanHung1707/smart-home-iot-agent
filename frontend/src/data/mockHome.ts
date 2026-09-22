import type { ActivityItem, HistoryItem, NavItem } from "../types";
import type { ApiApproval, ApiDevice, ApiSimulatorEvent } from "../api/types";

export const roomsPerPage = 6;

export const memberNav: NavItem[] = [
  { page: "Rooms", label: "Phòng & Thiết bị", icon: "house" },
  { page: "History", label: "Lịch sử điều khiển", icon: "clock" },
  { page: "Requests", label: "Yêu cầu an ninh", icon: "shield" },
];

export const adminNav: NavItem[] = [
  { page: "Rooms", label: "Phòng & Thiết bị", icon: "house" },
  { page: "History", label: "Lịch sử điều khiển", icon: "clock" },
  { page: "Approvals", label: "Phê duyệt (An ninh)", icon: "shield" },
  { page: "Activity", label: "Nhật ký hệ thống", icon: "list" },
  { page: "Performance", label: "Hiệu năng & Mô hình", icon: "chart" },
  { page: "MQTT", label: "Giám sát MQTT", icon: "mqtt" },
  { page: "Settings", label: "Cấu hình hệ thống", icon: "settings" },
];

export const recentCommands: HistoryItem[] = [
  {
    id: "h-1",
    status: "done",
    command: "“Bật đèn phòng khách”",
    result: "Đã bật Đèn trần phòng khách thành công.",
    time: "22:15",
  },
  {
    id: "h-2",
    status: "done",
    command: "“Tắt điều hòa phòng ngủ”",
    result: "Đã tắt Điều hòa phòng ngủ Master.",
    time: "21:40",
  },
];

export const fallbackDevices: ApiDevice[] = [
  {
    id: "living-light",
    name: "Đèn phòng khách",
    room: "Phòng khách",
    kind: "light",
    online: true,
    state: { power: true, brightness: 80 },
  },
  {
    id: "bedroom-light",
    name: "Đèn phòng ngủ",
    room: "Phòng ngủ",
    kind: "light",
    online: true,
    state: { power: false, brightness: 45 },
  },
  {
    id: "kitchen-light",
    name: "Đèn phòng bếp",
    room: "Phòng bếp",
    kind: "light",
    online: true,
    state: { power: true, brightness: 90 },
  },
  {
    id: "living-aircon",
    name: "Điều hòa phòng khách",
    room: "Phòng khách",
    kind: "aircon",
    online: true,
    state: { power: true, target_temperature: 25, mode: "cool" },
  },
  {
    id: "living-blind",
    name: "Rèm phòng khách",
    room: "Phòng khách",
    kind: "blind",
    online: true,
    state: { position: 0 },
  },
  {
    id: "hub-speaker",
    name: "Loa Homing",
    room: "Phòng khách",
    kind: "speaker",
    online: true,
    state: { power: false, volume: 45, playing: false },
  },
  {
    id: "entry-lock",
    name: "Khóa cửa chính",
    room: "Phòng khách",
    kind: "lock",
    online: true,
    state: { locked: true },
  },
  {
    id: "entry-sensor",
    name: "Cảm biến cửa",
    room: "Phòng khách",
    kind: "sensor",
    online: true,
    state: { open: false, battery: 92 },
  },
  {
    id: "living-temperature",
    name: "Cảm biến nhiệt độ",
    room: "Phòng khách",
    kind: "sensor",
    online: true,
    state: { temperature: 27.0, humidity: 65.0, battery: 98 },
  },
  {
    id: "kitchen-gas",
    name: "Cảm biến khí gas",
    room: "Phòng bếp",
    kind: "sensor",
    online: true,
    state: { gas_detected: false, ppm: 120, battery: 100 },
  },
  {
    id: "living-motion",
    name: "Cảm biến chuyển động",
    room: "Phòng khách",
    kind: "sensor",
    online: true,
    state: { motion: false, battery: 94 },
  },
];

export const fallbackApprovals: ApiApproval[] = [
  {
    id: "appr-01",
    device_id: "entry-lock",
    command: { action: "unlock" },
    status: "pending",
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 300000).toISOString(),
  },
];

export const fallbackEvents: ApiSimulatorEvent[] = [
  {
    type: "command",
    device_id: "living-light",
    action: "on",
    topic: "homing/devices/living-light/command",
    timestamp: new Date().toISOString(),
    status: "ok",
  },
];

export const fallbackActivity: ActivityItem[] = [
  {
    id: "act-1",
    time: "22:15",
    text: "BẬT · Đèn phòng khách",
    status: "Thành công",
  },
];
