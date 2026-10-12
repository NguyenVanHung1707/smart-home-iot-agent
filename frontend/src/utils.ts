import type { ApprovalStatus, DataMode, DeviceState, HistoryStatus, Role } from "./types";

export function historyStorageKey(role: Role, dataMode: DataMode = "simulator") {
  return `homemind-${role}-${dataMode}-history`;
}

export function formatTime(date = new Date()) {
  return date.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

export function assistantReply(message: string, dataMode: DataMode = "simulator") {
  const isReal = dataMode === "real";
  const normalized = message.toLowerCase();
  if (normalized.includes("mở") && (normalized.includes("cửa") || normalized.includes("khóa"))) {
    return isReal
      ? "Trợ lý Xiaozhi: Yêu cầu mở khóa cửa ESP32 an toàn cần xác thực mã PIN hoặc thẻ RFID."
      : "Local Model: Yêu cầu mở khóa cửa cần xác thực mã PIN hoặc phê duyệt.";
  }
  if (normalized.includes("đèn")) {
    return isReal
      ? "Trợ lý Xiaozhi: Đã gửi lệnh điều khiển Relay đèn ESP32."
      : "Local Model: Đã điều chỉnh trạng thái đèn mô phỏng.";
  }
  if (normalized.includes("quạt")) {
    return isReal
      ? "Trợ lý Xiaozhi: Đã gửi lệnh điều khiển quạt phần cứng thật."
      : "Local Model: Đã điều chỉnh quạt mô phỏng.";
  }
  if (normalized.includes("điều hòa") || normalized.includes("nhiệt độ")) {
    return isReal
      ? "Trợ lý Xiaozhi: Cảm biến nhiệt độ phòng khách đang hoạt động ổn định."
      : "Local Model: Đã điều chỉnh nhiệt độ điều hòa mô phỏng.";
  }
  if (normalized.includes("rèm")) {
    return isReal
      ? "Trợ lý Xiaozhi: Đã gửi lệnh rèm cửa qua sóng ESP-NOW."
      : "Local Model: Đã điều khiển rèm cửa ảo.";
  }
  return isReal
    ? "Trợ lý Xiaozhi đã ghi nhận và điều phối tới hệ thống phần cứng ESP32."
    : "Local Model đã ghi nhận và cập nhật trạng thái mô phỏng.";
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
