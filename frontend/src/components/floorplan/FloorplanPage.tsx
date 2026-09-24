import { useRef, useState, useEffect } from "react";
import { Icon } from "../shared/Icon";
import { SectionHeading } from "../shared/SectionHeading";

export function FloorplanPage({ view = "3d" }: { view?: "2d" | "3d" }) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isReloading, setIsReloading] = useState(false);

  const targetSrc = `/simulator/?view=${view}`;

  // Khi chuyển giữa tab 2D và 3D, cập nhật src iframe
  useEffect(() => {
    if (iframeRef.current) {
      iframeRef.current.src = targetSrc;
    }
  }, [view, targetSrc]);

  const handleReload = () => {
    setIsReloading(true);
    if (iframeRef.current) {
      iframeRef.current.src = targetSrc;
    }
    setTimeout(() => setIsReloading(false), 600);
  };

  const handleToggleFullscreen = () => {
    if (!iframeRef.current) return;
    if (!document.fullscreenElement) {
      iframeRef.current.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => {});
    } else {
      document.exitFullscreen().then(() => setIsFullscreen(false)).catch(() => {});
    }
  };

  const handleOpenNewTab = () => {
    window.open(targetSrc, "_blank", "noopener,noreferrer");
  };

  const is2D = view === "2d";

  return (
    <div className="hm-page hm-floorplan-page" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <header className="hm-page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
        <SectionHeading
          eyebrow={is2D ? "Mặt bằng kiến trúc" : "Không gian số"}
          title={is2D ? "Mặt bằng nhà 2D (Interactive Floorplan)" : "Mô hình kiến trúc nhà 3D (Three.js WebGL)"}
        />

        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
          <button
            type="button"
            className="hm-btn hm-btn-secondary"
            onClick={handleReload}
            title="Tải lại mô hình"
            style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem", padding: "0.5rem 0.85rem" }}
          >
            <Icon name="refresh" />
            <span>{isReloading ? "Đang tải..." : "Làm mới"}</span>
          </button>

          <button
            type="button"
            className="hm-btn hm-btn-secondary"
            onClick={handleToggleFullscreen}
            title="Toàn màn hình"
            style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem", padding: "0.5rem 0.85rem" }}
          >
            <Icon name="tv" />
            <span>Toàn màn hình</span>
          </button>

          <button
            type="button"
            className="hm-btn hm-btn-primary"
            onClick={handleOpenNewTab}
            title="Mở tab độc lập"
            style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem", padding: "0.5rem 0.85rem" }}
          >
            <Icon name="door" />
            <span>Mở tab riêng</span>
          </button>
        </div>
      </header>

      {/* Feature Badges */}
      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
        <div className="hm-chip" style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", padding: "0.35rem 0.75rem", background: "rgba(74, 124, 89, 0.12)", color: "var(--hm-primary, #4a7c59)", borderRadius: "999px", fontSize: "0.82rem", fontWeight: 600 }}>
          <Icon name={is2D ? "desk" : "box"} />
          <span>{is2D ? "Chế độ: 2D Floorplan & Vẽ tường" : "Chế độ: 3D Orbit & Không gian thực tế ảo"}</span>
        </div>
        <div className="hm-chip" style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", padding: "0.35rem 0.75rem", background: "rgba(59, 130, 246, 0.12)", color: "#2563eb", borderRadius: "999px", fontSize: "0.82rem", fontWeight: 600 }}>
          <Icon name="mqtt" />
          <span>Đồng bộ 2 chiều MQTT</span>
        </div>
        <div className="hm-chip" style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", padding: "0.35rem 0.75rem", background: "rgba(245, 158, 11, 0.12)", color: "#d97706", borderRadius: "999px", fontSize: "0.82rem", fontWeight: 600 }}>
          <Icon name="sun" />
          <span>{is2D ? "Kéo thả thiết bị tự do" : "Hiệu ứng Ngày / Đêm & Cảm biến HUD"}</span>
        </div>
      </div>

      {/* Embedded Viewport Frame */}
      <div
        className="hm-card"
        style={{
          padding: 0,
          overflow: "hidden",
          borderRadius: "16px",
          border: "1px solid rgba(120, 140, 130, 0.25)",
          boxShadow: "0 10px 30px rgba(0, 0, 0, 0.08)",
          position: "relative",
          background: "#1e2421",
        }}
      >
        <iframe
          ref={iframeRef}
          src={targetSrc}
          title={is2D ? "Mặt bằng 2D Smart Home" : "Mô hình 3D Smart Home"}
          style={{
            width: "100%",
            height: "calc(100vh - 270px)",
            minHeight: "560px",
            border: "none",
            display: "block",
          }}
          allow="fullscreen; accelerometer; gyroscope"
        />
      </div>

      {/* Guide Info */}
      <div
        className="hm-card"
        style={{
          padding: "1rem 1.25rem",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: "1rem",
          fontSize: "0.88rem",
          lineHeight: 1.5,
        }}
      >
        {is2D ? (
          <>
            <div>
              <strong style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.35rem", color: "var(--hm-primary, #4a7c59)" }}>
                <Icon name="sparkles" />
                <span>Vẽ và Tùy chỉnh phòng</span>
              </strong>
              <p style={{ margin: 0, opacity: 0.85 }}>
                Sử dụng công cụ vẽ tường để chia tách các phòng ngủ 1, 2, 3, phòng khách và bếp theo kích thước kiến trúc thực tế của nhà bạn.
              </p>
            </div>
            <div>
              <strong style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.35rem", color: "var(--hm-primary, #4a7c59)" }}>
                <Icon name="desk" />
                <span>Kéo thả thiết bị thông minh</span>
              </strong>
              <p style={{ margin: 0, opacity: 0.85 }}>
                Kéo các biểu tượng đèn, quạt, cảm biến cửa, cảm biến gas từ thư viện thiết bị đặt vào từng vị trí mong muốn trên mặt bằng.
              </p>
            </div>
            <div>
              <strong style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.35rem", color: "var(--hm-primary, #4a7c59)" }}>
                <Icon name="refresh" />
                <span>Tự động đồng bộ 3D</span>
              </strong>
              <p style={{ margin: 0, opacity: 0.85 }}>
                Mọi thay đổi về vị trí tường và thiết bị trên mặt bằng 2D sẽ được cập nhật tự động sang trang <strong>Mô hình 3D</strong> ngay lập tức.
              </p>
            </div>
          </>
        ) : (
          <>
            <div>
              <strong style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.35rem", color: "var(--hm-primary, #4a7c59)" }}>
                <Icon name="box" />
                <span>Điều hướng Camera 360°</span>
              </strong>
              <p style={{ margin: 0, opacity: 0.85 }}>
                Giữ chuột trái để xoay không gian 360°, giữ chuột phải để di chuyển góc nhìn (Pan), lăn con trỏ để phóng to/thu nhỏ từng căn phòng.
              </p>
            </div>
            <div>
              <strong style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.35rem", color: "var(--hm-primary, #4a7c59)" }}>
                <Icon name="bulb" />
                <span>Tương tác thiết bị trực tiếp</span>
              </strong>
              <p style={{ margin: 0, opacity: 0.85 }}>
                Nhấp chuột trực tiếp vào bóng đèn, quạt trần, rèm cửa hoặc khóa cổng trong không gian 3D để bật/tắt hoặc điều khiển tức thì.
              </p>
            </div>
            <div>
              <strong style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.35rem", color: "var(--hm-primary, #4a7c59)" }}>
                <Icon name="thermo" />
                <span>Bảng HUD Cảm biến 3D</span>
              </strong>
              <p style={{ margin: 0, opacity: 0.85 }}>
                Theo dõi nhiệt độ (°C), độ ẩm (%), khí gas (ppm) và chuyển động hiển thị nổi trên từng phòng theo thời gian thực.
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
