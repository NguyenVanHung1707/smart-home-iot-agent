import { useState } from "react";
import { useDialogFocus } from "../../hooks/useDialogFocus";
import type { CreateDevicePayload, DeviceKind, DiscoveredDevice, Room } from "../../types";
import { Icon } from "../shared/Icon";

function slugify(text: string): string {
  return text
    .toString()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

const KIND_OPTIONS: { kind: DeviceKind; label: string; icon: string }[] = [
  { kind: "light", label: "Đèn chiếu sáng", icon: "sunrise" },
  { kind: "aircon", label: "Quạt / Điều hòa", icon: "sliders" },
  { kind: "lock", label: "Khóa cửa an ninh", icon: "lock" },
  { kind: "blind", label: "Rèm cửa / Cửa sổ", icon: "house" },
  { kind: "sensor", label: "Cảm biến môi trường", icon: "sparkles" },
  { kind: "speaker", label: "Loa thông minh", icon: "mic" },
  { kind: "display", label: "Màn hình OLED / LCD", icon: "cpu" },
];

export function AddDeviceModal({
  open,
  rooms,
  discoveredDevices,
  onClose,
  onAddDevice,
  onPairDiscovered,
  onDismissDiscovered,
  onScanDevices,
}: {
  open: boolean;
  rooms: Room[];
  discoveredDevices: DiscoveredDevice[];
  onClose: () => void;
  onAddDevice: (payload: CreateDevicePayload) => Promise<void>;
  onPairDiscovered: (deviceId: string, name?: string, room?: string) => Promise<void>;
  onDismissDiscovered: (deviceId: string) => Promise<void>;
  onScanDevices?: () => Promise<void>;
}) {
  const dialogRef = useDialogFocus<HTMLElement>(open, onClose);
  const [activeTab, setActiveTab] = useState<"discovery" | "manual">(
    discoveredDevices.length > 0 ? "discovery" : "manual"
  );
  const [scanning, setScanning] = useState(false);
  const [scanNotice, setScanNotice] = useState("");

  // Manual form state
  const [name, setName] = useState("");
  const [customId, setCustomId] = useState("");
  const [idTouched, setIdTouched] = useState(false);
  const [kind, setKind] = useState<DeviceKind>("light");
  const [roomName, setRoomName] = useState(rooms[0]?.name || "Phòng khách");
  const [isNewRoom, setIsNewRoom] = useState(false);
  const [newRoomName, setNewRoomName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

  // Discovery pairing state
  const [pairingOverrides, setPairingOverrides] = useState<
    Record<string, { name?: string; room?: string }>
  >({});

  if (!open) return null;

  const handleScan = async () => {
    if (!onScanDevices || scanning) return;
    setScanning(true);
    setScanNotice("");
    try {
      await onScanDevices();
      setScanNotice("Đã phát sóng lệnh quét! Các bo mạch ESP32 đang phản hồi danh sách thiết bị...");
    } catch {
      setScanNotice("Không thể gửi lệnh quét.");
    } finally {
      setTimeout(() => setScanning(false), 2000);
      setTimeout(() => setScanNotice(""), 6000);
    }
  };

  const handleNameChange = (val: string) => {
    setName(val);
    if (!idTouched) {
      setCustomId(slugify(val));
    }
  };

  const handleSubmitManual = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    const trimmedName = name.trim();
    const finalId = (customId.trim() || slugify(trimmedName)).toLowerCase();
    const finalRoom = (isNewRoom ? newRoomName.trim() : roomName.trim()) || "Phòng khách";

    if (!trimmedName) {
      setFormError("Vui lòng nhập tên thiết bị.");
      return;
    }
    if (!finalId) {
      setFormError("Vui lòng nhập mã MQTT ID hợp lệ.");
      return;
    }

    setSubmitting(true);
    try {
      await onAddDevice({
        id: finalId,
        name: trimmedName,
        room: finalRoom,
        kind,
        state: kind === "light" ? { power: false, brightness: 100 } : { power: false },
      });
      onClose();
      // Reset form
      setName("");
      setCustomId("");
      setIdTouched(false);
      setFormError("");
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Không thể tạo thiết bị.");
    } finally {
      setSubmitting(false);
    }
  };

  const handlePair = async (device: DiscoveredDevice) => {
    const override = pairingOverrides[device.device_id] || {};
    try {
      await onPairDiscovered(
        device.device_id,
        override.name || device.name,
        override.room || device.room || "Phòng khách"
      );
    } catch (caught) {
      alert(caught instanceof Error ? caught.message : "Ghép nối thiết bị thất bại.");
    }
  };

  return (
    <div className="hm-modal-backdrop" role="presentation" onClick={onClose}>
      <section
        ref={dialogRef}
        className="hm-room-modal hm-add-device-modal"
        role="dialog"
        aria-modal="true"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="hm-room-modal-head">
          <div className="hm-room-head">
            <span className="hm-badge-icon">
              <Icon name="plus" />
            </span>
            <div>
              <strong>Thêm thiết bị mới</strong>
              <p className="hm-text-subtle">
                Tự động nhận diện thiết bị MQTT hoặc khai báo thủ công
              </p>
            </div>
          </div>
          <button className="hm-close-btn" onClick={onClose} aria-label="Đóng">
            <Icon name="close" />
          </button>
        </header>

        {/* Modal Tabs */}
        <div className="hm-add-tabs">
          <button
            type="button"
            className={`hm-add-tab ${activeTab === "discovery" ? "active" : ""}`}
            onClick={() => setActiveTab("discovery")}
          >
            <Icon name="mqtt" />
            <span>Tự động phát hiện</span>
            {discoveredDevices.length > 0 && (
              <span className="hm-tab-badge">{discoveredDevices.length}</span>
            )}
          </button>
          <button
            type="button"
            className={`hm-add-tab ${activeTab === "manual" ? "active" : ""}`}
            onClick={() => setActiveTab("manual")}
          >
            <Icon name="sliders" />
            <span>Khai báo thủ công</span>
          </button>
        </div>

        {/* Tab 1: Auto Discovery */}
        {activeTab === "discovery" && (
          <div className="hm-discovery-section">
            {discoveredDevices.length === 0 ? (
              <div className="hm-discovery-empty">
                <div className={`hm-radar-pulse ${scanning ? "scanning-active" : ""}`}>
                  <div className="hm-radar-ring" />
                  <div className="hm-radar-ring" />
                  <Icon name="wifi" />
                </div>
                <h4>{scanning ? "Đang phát sóng quét toàn bộ ESP32..." : "Đang chờ phát hiện thiết bị MQTT..."}</h4>
                <p>
                  Bấm nút <strong>"Quét thiết bị ngay"</strong> để Hub gửi yêu cầu tới tất cả ESP32 đang kết nối, hoặc bấm Reset trên board ESP32 mới.
                </p>
                {scanNotice && <div className="hm-scan-notice">{scanNotice}</div>}
                <div className="hm-discovery-empty-actions">
                  {onScanDevices && (
                    <button
                      type="button"
                      className={`hm-btn-primary hm-btn-scan ${scanning ? "scanning" : ""}`}
                      onClick={() => void handleScan()}
                      disabled={scanning}
                    >
                      <Icon name={scanning ? "sparkles" : "wifi"} />
                      <span>{scanning ? "Đang gửi lệnh quét..." : "Quét thiết bị ngay"}</span>
                    </button>
                  )}
                  <button
                    type="button"
                    className="hm-btn-secondary"
                    onClick={() => setActiveTab("manual")}
                  >
                    <Icon name="plus" />
                    <span>Khai báo thủ công</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="hm-discovery-list">
                <div className="hm-discovery-alert">
                  <div className="hm-discovery-alert-left">
                    <Icon name="sparkles" />
                    <span>Tìm thấy {discoveredDevices.length} thiết bị mới sẵn sàng kết nối:</span>
                  </div>
                  {onScanDevices && (
                    <button
                      type="button"
                      className={`hm-btn-scan-sm ${scanning ? "scanning" : ""}`}
                      onClick={() => void handleScan()}
                      disabled={scanning}
                      title="Gửi lệnh quét lại toàn mạng"
                    >
                      <Icon name="wifi" />
                      <span>{scanning ? "Đang quét..." : "Quét lại"}</span>
                    </button>
                  )}
                </div>
                {discoveredDevices.map((dev) => {
                  const override = pairingOverrides[dev.device_id] || {};
                  return (
                    <div key={dev.device_id} className="hm-discovery-card">
                      <div className="hm-discovery-header">
                        <div className="hm-disc-info">
                          <span className="hm-disc-kind-tag">{dev.kind || "Thiết bị"}</span>
                          <strong className="hm-disc-id">Mã: {dev.device_id}</strong>
                        </div>
                        <span className="hm-disc-time">
                          Vừa phát hiện: {new Date(dev.discovered_at).toLocaleTimeString("vi-VN")}
                        </span>
                      </div>

                      <div className="hm-discovery-form-row">
                        <div className="hm-field-group">
                          <label>Tên hiển thị:</label>
                          <input
                            type="text"
                            defaultValue={dev.name}
                            placeholder="Ví dụ: Đèn sân thượng"
                            onChange={(e) =>
                              setPairingOverrides((prev) => ({
                                ...prev,
                                [dev.device_id]: { ...prev[dev.device_id], name: e.target.value },
                              }))
                            }
                          />
                        </div>
                        <div className="hm-field-group">
                          <label>Gán vào phòng:</label>
                          <select
                            defaultValue={dev.room || rooms[0]?.name || "Phòng khách"}
                            onChange={(e) =>
                              setPairingOverrides((prev) => ({
                                ...prev,
                                [dev.device_id]: { ...prev[dev.device_id], room: e.target.value },
                              }))
                            }
                          >
                            {rooms.map((r) => (
                              <option key={r.id} value={r.name}>
                                {r.name}
                              </option>
                            ))}
                            <option value="Sân thượng">Sân thượng</option>
                            <option value="Sân vườn">Sân vườn</option>
                            <option value="Ban công">Ban công</option>
                            <option value="Hành lang">Hành lang</option>
                          </select>
                        </div>
                      </div>

                      <div className="hm-discovery-actions">
                        <button
                          type="button"
                          className="hm-btn-primary"
                          onClick={() => void handlePair(dev)}
                        >
                          <Icon name="check" />
                          <span>Ghép nối vào nhà</span>
                        </button>
                        <button
                          type="button"
                          className="hm-btn-ghost"
                          onClick={() => void onDismissDiscovered(dev.device_id)}
                        >
                          <Icon name="close" />
                          <span>Bỏ qua</span>
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Manual Entry Form */}
        {activeTab === "manual" && (
          <form className="hm-manual-form" onSubmit={(e) => void handleSubmitManual(e)}>
            {formError && <div className="hm-form-error">{formError}</div>}

            <div className="hm-form-grid">
              <div className="hm-form-field">
                <label htmlFor="device-name">Tên thiết bị *</label>
                <input
                  id="device-name"
                  type="text"
                  placeholder="Ví dụ: Đèn ban công, Quạt trần..."
                  value={name}
                  onChange={(e) => handleNameChange(e.target.value)}
                  required
                />
              </div>

              <div className="hm-form-field">
                <label htmlFor="device-id">Mã MQTT ID (Topic Slug) *</label>
                <input
                  id="device-id"
                  type="text"
                  placeholder="balcony-light"
                  value={customId}
                  onChange={(e) => {
                    setIdTouched(true);
                    setCustomId(e.target.value);
                  }}
                  required
                />
                <span className="hm-field-hint">
                  Topic MQTT: <code>homing/devices/{customId || "device-id"}/set</code>
                </span>
              </div>
            </div>

            <div className="hm-form-field">
              <label>Loại thiết bị</label>
              <div className="hm-kind-grid">
                {KIND_OPTIONS.map((item) => (
                  <button
                    key={item.kind}
                    type="button"
                    className={`hm-kind-btn ${kind === item.kind ? "active" : ""}`}
                    onClick={() => setKind(item.kind)}
                  >
                    <Icon name={item.icon as any} />
                    <span>{item.label}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="hm-form-field">
              <label>Vị trí phòng / Khu vực</label>
              {!isNewRoom ? (
                <div className="hm-room-select-row">
                  <select
                    value={roomName}
                    onChange={(e) => setRoomName(e.target.value)}
                  >
                    {rooms.map((r) => (
                      <option key={r.id} value={r.name}>
                        {r.name}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="hm-btn-secondary"
                    onClick={() => setIsNewRoom(true)}
                  >
                    + Tạo phòng mới
                  </button>
                </div>
              ) : (
                <div className="hm-room-select-row">
                  <input
                    type="text"
                    placeholder="Tên phòng mới (Ví dụ: Sân thượng, Ban công...)"
                    value={newRoomName}
                    onChange={(e) => setNewRoomName(e.target.value)}
                    autoFocus
                  />
                  <button
                    type="button"
                    className="hm-btn-secondary"
                    onClick={() => setIsNewRoom(false)}
                  >
                    Chọn phòng có sẵn
                  </button>
                </div>
              )}
            </div>

            <footer className="hm-modal-foot">
              <button
                type="button"
                className="hm-btn-ghost"
                onClick={onClose}
                disabled={submitting}
              >
                Hủy
              </button>
              <button
                type="submit"
                className="hm-btn-primary"
                disabled={submitting}
              >
                <Icon name="plus" />
                <span>{submitting ? "Đang tạo..." : "Tạo thiết bị"}</span>
              </button>
            </footer>
          </form>
        )}
      </section>
    </div>
  );
}
