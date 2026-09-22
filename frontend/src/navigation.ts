import type { NavItem, Page, Role } from "./types";

export const memberNav: NavItem[] = [
  { page: "Rooms", label: "Phòng & Thiết bị", icon: "house" },
  { page: "Presets", label: "Ngữ cảnh", icon: "sparkles" },
  { page: "History", label: "Lịch sử điều khiển", icon: "clock" },
  { page: "Requests", label: "Yêu cầu (An ninh)", icon: "shield" },
];

export const adminNav: NavItem[] = [
  { page: "Rooms", label: "Phòng & Thiết bị", icon: "house" },
  { page: "Presets", label: "Ngữ cảnh & Preset", icon: "sparkles" },
  { page: "History", label: "Lịch sử điều khiển", icon: "clock" },
  { page: "Approvals", label: "Phê duyệt (An ninh)", icon: "shield" },
  { page: "Activity", label: "Nhật ký hệ thống", icon: "list" },
  { page: "Performance", label: "Hiệu năng & Mô hình", icon: "chart" },
  { page: "MQTT", label: "Giám sát MQTT", icon: "mqtt" },
  { page: "Settings", label: "Cấu hình hệ thống", icon: "settings" },
];

export const adminAllowedPages = new Set<Page>(adminNav.map((item) => item.page));
export const memberAllowedPages = new Set<Page>(memberNav.map((item) => item.page));

export const defaultPageByRole: Record<Role, Page> = {
  homeadmin: "Rooms",
  member: "Rooms",
};

export function navItemsForRole(role: Role): NavItem[] {
  return role === "homeadmin" ? adminNav : memberNav;
}

export function isPageAllowedForRole(role: Role, page: Page): boolean {
  return role === "homeadmin" ? adminAllowedPages.has(page) : memberAllowedPages.has(page);
}
