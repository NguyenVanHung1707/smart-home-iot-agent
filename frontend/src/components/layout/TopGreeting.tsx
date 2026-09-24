import type { DataMode, Role, ThemeMode } from "../../types";
import { Icon } from "../shared/Icon";

export function TopGreeting({
  role,
  userName,
  sidebarOpen,
  notificationCount,
  dataMode,
  theme,
  onToggleDataMode,
  onToggleTheme,
  onToggleSidebar,
  onOpenNotifications,
  onOpenXiaozhi,
  onSignOut,
}: {
  role: Role;
  userName: string;
  sidebarOpen: boolean;
  notificationCount: number;
  dataMode: DataMode;
  theme: ThemeMode;
  onToggleDataMode: (mode: DataMode) => void;
  onToggleTheme: () => void;
  onToggleSidebar: () => void;
  onOpenNotifications?: () => void;
  onOpenXiaozhi?: () => void;
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
        {/* Xiaozhi AI Assistant Button */}
        {onOpenXiaozhi ? (
          <button
            type="button"
            onClick={onOpenXiaozhi}
            title="Trò chuyện với Trợ lý ảo Xiaozhi trên Web"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "7px 14px",
              borderRadius: "20px",
              border: "1px solid rgba(168, 85, 247, 0.4)",
              background: "linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(168, 85, 247, 0.2))",
              color: "inherit",
              cursor: "pointer",
              fontWeight: 500,
              fontSize: "13px",
              boxShadow: "0 2px 8px rgba(99, 102, 241, 0.15)",
            }}
          >
            <span style={{ color: "#a855f7" }}><Icon name="sparkles" /></span>
            <span>Xiaozhi AI</span>
          </button>
        ) : null}

        {/* Prominent Data Mode Switcher Toggle */}
        <div className="hm-mode-switcher" title="Chuyển đổi chế độ hoạt động giữa Nhà mô phỏng và Mô hình nhà thông minh">
          <button
            type="button"
            className={`hm-mode-btn ${dataMode === "simulator" ? "active" : ""}`}
            onClick={() => onToggleDataMode("simulator")}
            aria-pressed={dataMode === "simulator"}
          >
            <Icon name="cpu" />
            <span>Nhà mô phỏng</span>
          </button>
          <button
            type="button"
            className={`hm-mode-btn ${dataMode === "real" ? "active" : ""}`}
            onClick={() => onToggleDataMode("real")}
            aria-pressed={dataMode === "real"}
          >
            <Icon name="mqtt" />
            <span>Mô hình nhà thông minh</span>
          </button>
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
