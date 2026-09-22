import { useState } from "react";
import { useDialogFocus } from "../../hooks/useDialogFocus";
import type { Device, IconName } from "../../types";
import { Icon } from "../shared/Icon";

const AVAILABLE_ICONS: Array<{ name: IconName; label: string }> = [
  { name: "house", label: "Nhà chung" },
  { name: "sofa", label: "Phòng khách" },
  { name: "bed", label: "Phòng ngủ" },
  { name: "door", label: "Cửa / Lối vào" },
  { name: "sunrise", label: "Ban công / Sân" },
  { name: "settings", label: "Kỹ thuật / Kho" },
  { name: "sliders", label: "Giải trí / Studio" },
];

export function AddRoomModal({
  open,
  allDevices = [],
  onClose,
  onAddRoom,
}: {
  open: boolean;
  allDevices?: Device[];
  onClose: () => void;
  onAddRoom: (name: string, icon: IconName, deviceIds: string[]) => Promise<void>;
}) {
  const dialogRef = useDialogFocus<HTMLElement>(open, onClose);
  const [roomName, setRoomName] = useState("");
  const [selectedIcon, setSelectedIcon] = useState<IconName>("house");
  const [selectedDeviceIds, setSelectedDeviceIds] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  const toggleDevice = (devId: string) => {
    setSelectedDeviceIds((prev) =>
      prev.includes(devId) ? prev.filter((id) => id !== devId) : [...prev, devId],
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const clean = roomName.trim();
    if (!clean) {
      setError("Vui lòng nhập tên phòng.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await onAddRoom(clean, selectedIcon, selectedDeviceIds);
      setRoomName("");
      setSelectedDeviceIds([]);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể tạo phòng.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="hm-modal-backdrop" role="presentation" onClick={onClose}>
      <section
        ref={dialogRef}
        className="hm-room-modal hm-add-device-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="hm-add-room-title"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="hm-room-modal-head">
          <div className="hm-room-head">
            <span className="hm-badge-icon" style={{ background: "#dbeafe", color: "#0284c7" }}>
              <Icon name="plus" />
            </span>
            <div>
              <strong id="hm-add-room-title">Thêm phòng mới</strong>
              <p className="hm-text-subtle">Tạo khu vực hoặc phòng mới trong ngôi nhà của bạn</p>
            </div>
          </div>
          <button type="button" className="hm-close-btn" onClick={onClose} aria-label="Đóng">
            <Icon name="close" />
          </button>
        </header>

        <form className="hm-add-device-form" onSubmit={handleSubmit}>
          {error && <div className="hm-form-error">{error}</div>}

          <div className="hm-form-group">
            <label htmlFor="add-room-name">Tên phòng *</label>
            <input
              id="add-room-name"
              type="text"
              required
              value={roomName}
              onChange={(e) => setRoomName(e.target.value)}
              placeholder="Ví dụ: Phòng làm việc, Sân thượng, Gara..."
              autoFocus
            />
          </div>

          <div className="hm-form-group">
            <label>Biểu tượng phòng</label>
            <div className="hm-icon-picker-grid">
              {AVAILABLE_ICONS.map((item) => (
                <button
                  key={item.name}
                  type="button"
                  className={`hm-icon-picker-btn ${selectedIcon === item.name ? "active" : ""}`}
                  onClick={() => setSelectedIcon(item.name)}
                >
                  <Icon name={item.name} />
                  <span>{item.label}</span>
                </button>
              ))}
            </div>
          </div>

          {allDevices.length > 0 && (
            <div className="hm-form-group">
              <label>Chuyển thiết bị vào phòng này (Tùy chọn)</label>
              <div className="hm-device-select-list">
                {allDevices.map((dev) => (
                  <label key={dev.id} className="hm-device-checkbox-row">
                    <input
                      type="checkbox"
                      checked={selectedDeviceIds.includes(dev.id)}
                      onChange={() => toggleDevice(dev.id)}
                    />
                    <div className="hm-device-cb-info">
                      <strong>{dev.name}</strong>
                      <small>Hiện tại ở: {dev.room}</small>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          )}

          <footer className="hm-form-actions">
            <button type="button" className="hm-btn-secondary" onClick={onClose}>
              Hủy
            </button>
            <button type="submit" className="hm-btn-primary" disabled={submitting || !roomName.trim()}>
              <Icon name="check" />
              <span>{submitting ? "Đang tạo..." : "Tạo phòng mới"}</span>
            </button>
          </footer>
        </form>
      </section>
    </div>
  );
}
