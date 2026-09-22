import type { ApprovalStatus, DataMode, DeviceState, HistoryStatus, Role } from "./types";

export function historyStorageKey(role: Role, dataMode: DataMode = "simulator") {
  return `homemind-${role}-${dataMode}-history`;
}

export function formatTime(date = new Date()) {
  return date.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

export function assistantReply(message: string) {
  const normalized = message.toLowerCase();
  if (normalized.includes("mở") && (normalized.includes("cửa") || normalized.includes("khóa"))) {
    return "Yêu cầu mở khóa cửa an toàn cần xác thực mã PIN hoặc quản trị viên phê duyệt.";
  }
  if (normalized.includes("đèn")) {
    return "Đã thực hiện điều chỉnh hệ thống đèn theo yêu cầu.";
  }
  if (normalized.includes("điều hòa") || normalized.includes("nhiệt độ")) {
    return "Đã điều chỉnh nhiệt độ điều hòa phù hợp với không gian.";
  }
  if (normalized.includes("rèm")) {
    return "Đã điều khiển đóng/mở rèm cửa.";
  }
  return "Đã ghi nhận và xử lý yêu cầu của bạn tại HomeMind Hub.";
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
