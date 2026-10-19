import { Icon } from "../shared/Icon";

export function SimulatorPage() {
  function handleOpenNewTab() {
    if (typeof window !== "undefined") {
      window.open("/simulator/", "_blank", "noopener,noreferrer");
    }
  }

  return (
    <div
      className="hm-simulator-page"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "16px",
        height: "calc(100vh - 120px)",
        minHeight: "650px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "12px",
          padding: "16px 20px",
          background: "var(--hm-card-bg, rgba(20,24,33,0.7))",
          borderRadius: "16px",
          border: "1px solid var(--hm-border-soft)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "10px",
              background: "rgba(18, 216, 193, 0.15)",
              color: "var(--hm-primary)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Icon name="box" />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 700, color: "var(--hm-text)" }}>
              Mô phỏng Thiết bị (Virtual Home Simulator)
            </h2>
            <p style={{ margin: "2px 0 0", fontSize: "13px", color: "var(--hm-muted)" }}>
              Giao diện 2D Mặt bằng, Mô hình 3D Canvas và Giả lập lỗi phần cứng qua MQTT
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={handleOpenNewTab}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            padding: "10px 18px",
            borderRadius: "10px",
            background: "var(--hm-primary, #0f8778)",
            color: "#ffffff",
            fontWeight: 700,
            fontSize: "14px",
            border: "none",
            cursor: "pointer",
            boxShadow: "0 4px 14px rgba(18, 216, 193, 0.25)",
            transition: "all 0.2s ease",
          }}
        >
          <span>Mở toàn màn hình trong tab mới</span>
          <span style={{ fontSize: "16px" }}>↗</span>
        </button>
      </div>

      <div
        style={{
          flex: 1,
          borderRadius: "16px",
          overflow: "hidden",
          border: "1px solid var(--hm-border-soft)",
          background: "#05070a",
        }}
      >
        <iframe
          src="/simulator/"
          title="Home Simulator Sandbox"
          style={{ width: "100%", height: "100%", border: "none" }}
        />
      </div>
    </div>
  );
}
