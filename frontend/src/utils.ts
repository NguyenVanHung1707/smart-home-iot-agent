import type { ApprovalStatus, DataMode, DeviceState, HistoryStatus, Role } from "./types";

export function historyStorageKey(role: Role, dataMode: DataMode = "real") {
  return `homemind-${role}-${dataMode}-history`;
}

export function formatTime(date = new Date()) {
  return date.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

export function assistantReply(message: string, dataMode: DataMode = "real") {
  const isReal = dataMode === "real";
  const normalized = message.toLowerCase();
  if (normalized.includes("mở") && (normalized.includes("cửa") || normalized.includes("khóa"))) {
    return "Trợ lý Xiaozhi: Yêu cầu mở khóa cửa ESP32 an toàn cần xác thực mã PIN hoặc thẻ RFID.";
  }
  if (normalized.includes("đèn")) {
    return "Trợ lý Xiaozhi: Đã gửi lệnh điều khiển Relay đèn ESP32.";
  }
  if (normalized.includes("quạt")) {
    return "Trợ lý Xiaozhi: Đã gửi lệnh điều khiển quạt phần cứng thật.";
  }
  if (normalized.includes("điều hòa") || normalized.includes("nhiệt độ")) {
    return "Trợ lý Xiaozhi: Cảm biến nhiệt độ phòng khách đang hoạt động ổn định.";
  }
  if (normalized.includes("rèm")) {
    return "Trợ lý Xiaozhi: Đã gửi lệnh rèm cửa qua sóng ESP-NOW.";
  }
  return "Trợ lý Xiaozhi đã ghi nhận và điều phối tới hệ thống phần cứng ESP32.";
}

export function historyStatusLabel(status: HistoryStatus) {
  return { done: "Đã thực hiện", pending: "Đang chờ", declined: "Bị từ chối" }[status];
}

export function approvalStatusLabel(status: ApprovalStatus) {
  return { pending: "Chờ duyệt", approved: "Đã duyệt", rejected: "Đã từ chối", expired: "Đã hết hạn" }[status];
}

export function deviceStatusLabel(status: DeviceState) {
  return { on: "Đang bật", off: "Đã tắt", offline: "Mất kết nối", warning: "Cần chú ý" }[status];
}
