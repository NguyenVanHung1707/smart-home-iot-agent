import React, { useEffect, useState } from "react";
import {
  connectCloudMqtt,
  disconnectCloudMqtt,
  getCloudMqttConfig,
  getMqttCurrentStatus,
  onCloudMqttStatus,
  publishDeviceCommand,
  saveCloudMqttConfig,
  type CloudMqttConfig,
  type MqttConnectionStatus,
} from "../../api/cloudMqtt";
import { Icon } from "../shared/Icon";

export function CloudMqttCard() {
  const [config, setConfig] = useState<CloudMqttConfig>(getCloudMqttConfig);
  const [status, setStatus] = useState<MqttConnectionStatus>(getMqttCurrentStatus);
  const [savedNotice, setSavedNotice] = useState(false);
  const [testSent, setTestSent] = useState(false);

  useEffect(() => {
    const unsub = onCloudMqttStatus((newStatus) => {
      setStatus(newStatus);
    });
    return unsub;
  }, []);

  function handleSaveAndConnect(e: React.FormEvent) {
    e.preventDefault();
    saveCloudMqttConfig(config);
    setSavedNotice(true);
    setTimeout(() => setSavedNotice(false), 2500);

    connectCloudMqtt(config);
  }

  function handleSendTest() {
    publishDeviceCommand("living-light", "toggle", 1);
    setTestSent(true);
    setTimeout(() => setTestSent(false), 2000);
  }

  const statusColor =
    status === "connected"
      ? "#10b981"
      : status === "connecting"
        ? "#f59e0b"
        : status === "error"
          ? "#ef4444"
          : "#6b7280";

  const statusText =
    status === "connected"
      ? "Đã kết nối WSS (Online)"
      : status === "connecting"
        ? "Đang kết nối..."
        : status === "error"
          ? "Lỗi kết nối WSS"
          : "Đã ngắt kết nối";

  return (
    <div
      className="hm-card hm-cloud-mqtt-card"
      style={{
        padding: "18px 20px",
        borderRadius: "12px",
        border: "1px solid var(--border-color, #333)",
        background: "var(--card-bg, rgba(255,255,255,0.03))",
        marginBottom: "20px",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "14px",
          flexWrap: "wrap",
          gap: "8px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ color: "#6366f1" }}>
            <Icon name="mqtt" />
          </span>
          <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 600 }}>
            Cấu hình Cloud MQTT (WSS Serverless)
          </h3>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "4px 10px",
              borderRadius: "20px",
              fontSize: "12px",
              fontWeight: 500,
              backgroundColor: `${statusColor}20`,
              color: statusColor,
              border: `1px solid ${statusColor}40`,
            }}
          >
            <span
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                backgroundColor: statusColor,
                boxShadow: status === "connected" ? `0 0 8px ${statusColor}` : "none",
              }}
            />
            {statusText}
          </span>
        </div>
      </div>

      <p style={{ fontSize: "13px", opacity: 0.8, marginTop: 0, marginBottom: "16px", lineHeight: "1.4" }}>
        Trình duyệt Web kết nối trực tiếp tới <strong>HiveMQ Cloud / EMQX Cloud</strong> qua giao thức{" "}
        <code>wss://</code> (WebSocket Secure). Bạn có thể điều khiển 3 bo mạch ESP32 từ xa bằng 4G mà{" "}
        <strong>không cần bật máy tính hay chạy Docker ở nhà</strong>.
      </p>

      <form onSubmit={handleSaveAndConnect} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "12px" }}>
          <div>
            <label style={{ display: "block", fontSize: "12px", marginBottom: "4px", opacity: 0.8 }}>
              Broker WSS URL (Cổng WebSocket 8884/443):
            </label>
            <input
              type="text"
              value={config.brokerUrl}
              onChange={(e) => setConfig({ ...config, brokerUrl: e.target.value })}
              placeholder="wss://xxxx.s1.eu.hivemq.cloud:8884/mqtt"
              style={{
                width: "100%",
                padding: "8px 10px",
                borderRadius: "6px",
                border: "1px solid var(--border-color, #444)",
                background: "rgba(0,0,0,0.15)",
                color: "inherit",
                fontSize: "13px",
              }}
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "12px", marginBottom: "4px", opacity: 0.8 }}>
              Topic Prefix (Mặc định: homing):
            </label>
            <input
              type="text"
              value={config.topicPrefix}
              onChange={(e) => setConfig({ ...config, topicPrefix: e.target.value })}
              placeholder="homing"
              style={{
                width: "100%",
                padding: "8px 10px",
                borderRadius: "6px",
                border: "1px solid var(--border-color, #444)",
                background: "rgba(0,0,0,0.15)",
                color: "inherit",
                fontSize: "13px",
              }}
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "12px", marginBottom: "4px", opacity: 0.8 }}>
              Username:
            </label>
            <input
              type="text"
              value={config.username}
              onChange={(e) => setConfig({ ...config, username: e.target.value })}
              placeholder="homing_user"
              style={{
                width: "100%",
                padding: "8px 10px",
                borderRadius: "6px",
                border: "1px solid var(--border-color, #444)",
                background: "rgba(0,0,0,0.15)",
                color: "inherit",
                fontSize: "13px",
              }}
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "12px", marginBottom: "4px", opacity: 0.8 }}>
              Password:
            </label>
            <input
              type="password"
              value={config.password}
              onChange={(e) => setConfig({ ...config, password: e.target.value })}
              placeholder="••••••••"
              style={{
                width: "100%",
                padding: "8px 10px",
                borderRadius: "6px",
                border: "1px solid var(--border-color, #444)",
                background: "rgba(0,0,0,0.15)",
                color: "inherit",
                fontSize: "13px",
              }}
            />
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginTop: "4px", flexWrap: "wrap" }}>
          <button
            type="submit"
            style={{
              padding: "8px 16px",
              borderRadius: "6px",
              border: "none",
              backgroundColor: "#6366f1",
              color: "#fff",
              fontWeight: 500,
              fontSize: "13px",
              cursor: "pointer",
            }}
          >
            Lưu & Kết nối lại WSS
          </button>

          <button
            type="button"
            onClick={handleSendTest}
            disabled={status !== "connected"}
            style={{
              padding: "8px 16px",
              borderRadius: "6px",
              border: "1px solid var(--border-color, #444)",
              background: "rgba(255,255,255,0.05)",
              color: "inherit",
              fontSize: "13px",
              cursor: status === "connected" ? "pointer" : "not-allowed",
              opacity: status === "connected" ? 1 : 0.5,
            }}
          >
            {testSent ? "✓ Đã gửi lệnh!" : "Gửi lệnh Test Đèn (Toggle)"}
          </button>

          {status === "connected" && (
            <button
              type="button"
              onClick={disconnectCloudMqtt}
              style={{
                padding: "8px 12px",
                borderRadius: "6px",
                border: "none",
                background: "rgba(239,68,68,0.15)",
                color: "#ef4444",
                fontSize: "13px",
                cursor: "pointer",
              }}
            >
              Ngắt kết nối
            </button>
          )}

          {savedNotice && (
            <span style={{ fontSize: "12px", color: "#10b981", fontWeight: 500 }}>
              ✓ Đã lưu cấu hình Cloud MQTT!
            </span>
          )}
        </div>
      </form>
    </div>
  );
}
