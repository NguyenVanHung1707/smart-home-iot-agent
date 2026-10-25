import { useState } from "react";
import type { ApiDevice, ApiSimulatorEvent } from "../../api/types";
import type { DataMode, Device } from "../../types";
import { SectionHeading } from "../shared/SectionHeading";
import { Icon } from "../shared/Icon";
import { CloudMqttCard } from "./CloudMqttCard";

function FlowNode({ label, detail, tone }: { label: string; detail: string; tone: string }) {
  return (
    <div className={`hm-flow-node ${tone}`}>
      <strong>{label}</strong>
      <small>{detail}</small>
    </div>
  );
}

function MqttEventCard({ event }: { event: ApiSimulatorEvent }) {
  const type = event.type ?? "state";
  const label =
    type === "command"
      ? "PUBLISH"
      : type === "ack"
        ? "ACK"
        : type === "timeout"
          ? "TIMEOUT"
          : "STATE";

  const detail =
    type === "command"
      ? `${event.action ?? "lệnh"} ➔ ${event.device_id}`
      : type === "ack"
        ? `${event.device_id} ${event.status === "ok" ? "đã xác nhận thành công" : "từ chối"}`
        : type === "timeout"
          ? `${event.device_id} quá hạn chờ phản hồi (504 Timeout)`
          : `${event.device_id} ${event.error ?? event.event ?? "cập nhật trạng thái"}`;

  return (
    <article className={`hm-mqtt-event-card ${type}`}>
      <span className={`hm-mqtt-badge ${type}`}>{label}</span>
      <div className="hm-mqtt-event-body">
        <strong>{detail}</strong>
        <code>{event.topic ?? `homing/devices/${event.device_id}/${type === "ack" ? "ack" : "state"}`}</code>
      </div>
      <time>
        {event.timestamp
          ? new Date(event.timestamp).toLocaleTimeString("vi-VN", {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })
          : "Vừa xong"}
      </time>
    </article>
  );
}

export function MqttPage({
  devices,
  events,
  dataMode = "real",
  onDeviceCommand,
  onSetFault,
}: {
  devices: ApiDevice[];
  events: ApiSimulatorEvent[];
  dataMode?: DataMode;
  onDeviceCommand: (device: Device) => void;
  onSetFault: (deviceId: string, mode: "none" | "offline" | "timeout") => Promise<void>;
}) {
  const [filterType, setFilterType] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState<string>("");

  const filteredEvents = events.filter((e) => {
    if (filterType !== "all" && e.type !== filterType) return false;
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      return (
        (e.device_id ?? "").toLowerCase().includes(term) ||
        (e.topic ?? "").toLowerCase().includes(term) ||
        (e.action ?? "").toLowerCase().includes(term) ||
        (e.event ?? "").toLowerCase().includes(term)
      );
    }
    return true;
  });

  const isReal = true;
  const topicPrefix = "homing/devices/#";
  const deviceNodeLabel = "Bo mạch ESP32 thật";

  return (
    <section className="hm-mqtt-page" aria-label="MQTT Observatory">
      <SectionHeading
        eyebrow="LIVE MESSAGE OBSERVATORY"
        title="Luồng giao tiếp MQTT · Phần cứng ESP32"
        aside={
          <span className="hm-count">
            {events.length} Gói tin
          </span>
        }
      />
      <p className="hm-page-intro">
        Quan sát lộ trình gói tin trực tiếp từ AI Agent tới MQTT Broker và phản hồi ACK từ các bo mạch ESP32 thật.
      </p>

      {/* Cloud MQTT (WSS Serverless) Configuration */}
      <CloudMqttCard />

      {/* MQTT Route Architecture Flow */}
      <section className="hm-mqtt-route-panel" aria-label="Lộ trình tin nhắn MQTT">
        <div className="hm-route-title">
          <Icon name="mqtt" />
          <span>Kiến trúc luồng thông điệp (Chế độ Phần cứng thật)</span>
        </div>
        <div className="hm-mqtt-flow">
          <FlowNode label="AGENT" detail="Kế hoạch JSON" tone="blue" />
          <div className="hm-flow-arrow">
            <span>PUBLISH</span>
            <i>➔</i>
          </div>
          <FlowNode label="MQTT BROKER" detail={topicPrefix} tone="orange" />
          <div className="hm-flow-arrow">
            <span>DELIVER</span>
            <i>➔</i>
          </div>
          <FlowNode label="THIẾT BỊ" detail={deviceNodeLabel} tone="green" />
          <div className="hm-flow-arrow">
            <span>ACK / STATE</span>
            <i>➔</i>
          </div>
          <FlowNode label="HUB MIRROR" detail="Dashboard live" tone="blue" />
        </div>
      </section>

      {/* Two-Column Grid: Message Stream Console + Device Lab */}
      <div className="hm-mqtt-grid">
        {/* Left Column: Live Message Stream */}
        <section className="hm-mqtt-console">
          <header className="hm-console-header">
            <div>
              <h3>Message Stream</h3>
              <small>QoS 1 · ESP32 Hardware Buffer</small>
            </div>
            <div className="hm-console-filters">
              <input
                type="text"
                placeholder="Lọc device / topic..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="hm-console-search"
                aria-label="Lọc thông điệp MQTT"
              />
              <div className="hm-filter-buttons">
                {["all", "command", "ack", "state", "timeout"].map((f) => (
                  <button
                    key={f}
                    type="button"
                    className={`hm-f-btn ${filterType === f ? "active" : ""}`}
                    onClick={() => setFilterType(f)}
                  >
                    {f.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
          </header>

          <div className="hm-console-stream">
            {filteredEvents.slice(0, 30).map((evt, idx) => (
              <MqttEventCard key={`${evt.command_id ?? evt.timestamp ?? "evt"}-${idx}`} event={evt} />
            ))}
            {!filteredEvents.length && (
              <div className="hm-empty-console">
                <Icon name="info" />
                <p>Chưa có gói tin nào phù hợp bộ lọc. Hãy bấm gửi lệnh bên phải để thử nghiệm.</p>
              </div>
            )}
          </div>
        </section>

        {/* Right Column: Device Simulator / Hardware Nodes */}
        <section className="hm-device-lab">
          <header className="hm-console-header">
            <div>
              <h3>{isReal ? "Thiết bị phần cứng ESP32" : "Thiết bị mô phỏng"}</h3>
              <small>{isReal ? "Giám sát & Điều khiển Trực tiếp" : "Fault Injection & Resilience Test"}</small>
            </div>
            <span className="hm-count">{devices.length} Nodes</span>
          </header>

          <div className="hm-device-lab-list">
            {devices.map((device) => {
              const devUi: Device = {
                id: device.id,
                name: device.name,
                room: device.room,
                kind: device.kind,
                status: device.online ? "on" : "offline",
                state: device.state,
                commandable: device.kind !== "sensor" && device.online,
              };

              return (
                <article key={device.id} className={`hm-lab-card ${!device.online ? "is-offline" : ""}`}>
                  <div className="hm-lab-info">
                    <div className="hm-lab-header">
                      <strong>{device.name}</strong>
                      <span className={`hm-status-tag ${device.online ? "online" : "offline"}`}>
                        {device.online ? "ONLINE" : "OFFLINE"}
                      </span>
                    </div>
                    <code>{device.id} · {device.room} ({device.kind})</code>
                  </div>

                  <div className="hm-lab-actions">
                    {device.kind !== "sensor" && (
                      <button
                        type="button"
                        className="hm-btn-cmd"
                        disabled={!device.online}
                        onClick={() => onDeviceCommand(devUi)}
                      >
                        Gửi lệnh
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      </div>
    </section>
  );
}
