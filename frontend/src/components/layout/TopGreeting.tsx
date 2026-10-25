import type { DataMode, Role, ThemeMode } from "../../types";
import { Icon } from "../shared/Icon";

export function TopGreeting({
  role,
  userName,
  sidebarOpen,
  notificationCount,
  dataMode,
  theme,
  onToggleTheme,
  onToggleSidebar,
  onOpenNotifications,
  onSignOut,
}: {
  role: Role;
  userName: string;
  sidebarOpen: boolean;
  notificationCount: number;
  dataMode?: DataMode;
  theme: ThemeMode;
  onToggleTheme: () => void;
  onToggleSidebar: () => void;
  onOpenNotifications?: () => void;
  onSignOut?: () => void;
}) {
  const nextThemeLabel = theme === "dark" ? "Chuyen sang light mode" : "Chuyen sang dark mode";
  const displayName = userName.trim() || "bạn";

  return (
    <header className="hm-top-greeting">
      <div className="hm-top-title">
        <button
          type="button"
          className="hm-menu-button"
          onClick={onToggleSidebar}
          aria-label={sidebarOpen ? "Ẩn menu" : "Mở menu"}
        >
          <Icon name="menu" />
        </button>
        <span className="hm-house-badge">
          <Icon name="house" />
        </span>
        <div>
          <p>Chào buổi tối,</p>
          <h1>
            {role === "homeadmin"
              ? `${displayName} ơi, nhà của bạn đã sẵn sàng`
              : `${displayName} ơi, ngôi nhà đang yên bình`}
          </h1>
        </div>
      </div>

      <div className="hm-top-status">
        {/* Real Smart Home Mode Badge */}
        <div className="hm-connected-mode" title="Hệ thống đang hoạt động với Mô hình nhà thông minh (Phần cứng thật)">
          <Icon name="mqtt" />
          <span>Mô hình nhà thông minh</span>
        </div>

        <button
          type="button"
          className="hm-theme-toggle"
          onClick={onToggleTheme}
          aria-label={nextThemeLabel}
          title={nextThemeLabel}
        >
          <Icon name={theme === "dark" ? "sun" : "moon"} />
          <span>{theme === "dark" ? "Light" : "Dark"}</span>
        </button>

        <button
          type="button"
          className={`hm-notification ${notificationCount ? "has-alerts" : ""}`}
          aria-label={`Xem thông báo, ${notificationCount} thông báo mới`}
          onClick={onOpenNotifications}
        >
          <Icon name="bell" />
          <span>Thông báo</span>
          <b>{notificationCount}</b>
        </button>

        {onSignOut ? (
          <button
            type="button"
            className="hm-theme-toggle"
            onClick={onSignOut}
            aria-label="Đăng xuất khỏi Hub"
            title="Đăng xuất khỏi Hub"
          >
            <Icon name="power" />
            <span>Đăng xuất</span>
          </button>
        ) : null}
      </div>
    </header>
  );
}
