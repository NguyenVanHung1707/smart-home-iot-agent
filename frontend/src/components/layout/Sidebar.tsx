import type { NavItem, Page, Role } from "../../types";
import { Icon } from "../shared/Icon";

export function Sidebar({
  role,
  navItems,
  page,
  open,
  onNavigate,
}: {
  role: Role;
  navItems: NavItem[];
  page: Page;
  open: boolean;
  onNavigate: (page: Page) => void;
}) {
  return (
    <aside className="hm-sidebar" aria-label="Điều hướng HomeMind" data-open={open}>
      <div className="hm-sidebar-brand">
        <span>
          <Icon name="house" />
        </span>
        <div>
          <strong>HomeMind Hub</strong>
          <small>Chủ nhà (Admin)</small>
        </div>
      </div>

      <p className="hm-sidebar-section">Điều khiển</p>
      <nav>
        {navItems.map((item) =>
          item.isExternal ? (
            <a
              key={item.label}
              href={item.href || "#"}
              target="_blank"
              rel="noopener noreferrer"
              className="hm-sidebar-nav-btn hm-sidebar-external-btn"
              title={item.label}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
              <span className="hm-sidebar-external-badge" aria-hidden="true">↗</span>
            </a>
          ) : (
            <button
              key={item.page}
              type="button"
              className={page === item.page ? "active" : ""}
              aria-current={page === item.page ? "page" : undefined}
              onClick={() => onNavigate(item.page)}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </button>
          )
        )}
      </nav>

      <div className="hm-sidebar-note">
        <Icon name="shield" />
        <p>AI & MQTT vận hành nội bộ (Local Edge).</p>
      </div>
    </aside>
  );
}
