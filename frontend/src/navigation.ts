import type { NavItem, Page, Role } from "./types";

export const adminNav: NavItem[] = [
  { page: "Rooms", label: "Phòng & Thiết bị", icon: "house" },
  { page: "AISettings", label: "AI Voice & Ngữ cảnh", icon: "sparkles" },
  { page: "AIConversations", label: "Lịch sử Hội thoại AI", icon: "mic" },
  { page: "History", label: "Lịch sử & Nhật ký", icon: "clock" },
];

export const memberNav: NavItem[] = adminNav;

export const adminAllowedPages = new Set<Page>([...adminNav.map((item) => item.page), "Activity", "MQTT", "Approvals", "Presets"]);
export const memberAllowedPages = adminAllowedPages;

export const defaultPageByRole: Record<Role, Page> = {
  homeadmin: "Rooms",
  member: "Rooms",
};

export function navItemsForRole(_role: Role): NavItem[] {
  return adminNav;
}

export function isPageAllowedForRole(_role: Role, page: Page): boolean {
  return adminAllowedPages.has(page);
}
