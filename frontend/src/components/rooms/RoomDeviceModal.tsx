import { useState } from "react";
import { defaultCommandForDevice } from "../../api/adapters";
import type { ApiDeviceCommand } from "../../api/types";
import { useDialogFocus } from "../../hooks/useDialogFocus";
import type { Device, Role, Room, UpdateDevicePayload } from "../../types";
import { DeviceStatus } from "../shared/DeviceStatus";
import { Icon } from "../shared/Icon";

export function RoomDeviceModal({
  room,
  role,
  allRooms = [],
  onClose,
  onDeviceCommand,
  onRequestPinUnlock,
  onDeleteDevice,
  onUpdateDevice,
  onRenameRoom,
  onDeleteRoom,
}: {
  room: Room | null;
  role?: Role;
  allRooms?: Room[];
  onClose: () => void;
  onDeviceCommand: (device: Device, command: ApiDeviceCommand) => Promise<void>;
  onRequestPinUnlock: (device: Device) => void;
  onDeleteDevice?: (deviceId: string) => Promise<void>;
  onUpdateDevice?: (deviceId: string, payload: UpdateDevicePayload) => Promise<void>;
  onRenameRoom?: (oldName: string, newName: string) => Promise<void>;
  onDeleteRoom?: (roomName: string) => Promise<void>;
}) {
  const dialogRef = useDialogFocus<HTMLElement>(Boolean(room), onClose);
  const [editingDeviceId, setEditingDeviceId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editRoom, setEditRoom] = useState("");
  const [saving, setSaving] = useState(false);
  const [isEditingRoomName, setIsEditingRoomName] = useState(false);
  const [isConfirmingDeleteRoom, setIsConfirmingDeleteRoom] = useState(false);
  const [roomTitleInput, setRoomTitleInput] = useState(room?.name || "");

  if (!room) return null;

  const handleDeviceAction = (device: Device) => {
    const isLock = device.kind === "lock";
    const isLocked = isLock && Boolean(device.state?.locked ?? (device.status !== "warning"));
    if (isLock) {
      if (isLocked) {
        onRequestPinUnlock(device);
      } else {
        void onDeviceCommand(device, { action: "lock" });
      }
      return;
    }
    const defaultCmd = defaultCommandForDevice(device);
    if (defaultCmd) {
      void onDeviceCommand(device, defaultCmd);
    }
  };

  const handleBrightnessChange = (device: Device, brightness: number) => {
    void onDeviceCommand(device, {
      action: "set",
      value: { brightness, power: brightness > 0 },
    });
  };

  const handleTempChange = (device: Device, delta: number) => {
    const currentTemp = (device.state?.target_temperature as number) || 24;
    const newTemp = Math.min(30, Math.max(16, currentTemp + delta));
    void onDeviceCommand(device, {
      action: "set",
      value: { target_temperature: newTemp },
    });
  };

  const handleBlindPositionChange = (device: Device, position: number) => {
    void onDeviceCommand(device, {
      action: "set",
      value: { position },
    });
  };

  const handleVolumeChange = (device: Device, volume: number) => {
    void onDeviceCommand(device, {
      action: "set",
      value: { volume },
    });
  };

  const handleStartEdit = (device: Device) => {
    setEditingDeviceId(device.id);
    setEditName(device.name);
    setEditRoom(room.name === "Chưa phân loại" ? "Phòng ngủ" : room.name);
  };

  const handleSaveEdit = async (deviceId: string) => {
    if (!onUpdateDevice) return;
    setSaving(true);
    try {
      await onUpdateDevice(deviceId, {
        name: editName.trim(),
        room: editRoom.trim() || "Chưa phân loại",
      });
      setEditingDeviceId(null);
      // Close modal if all devices moved out of this room
      if (room.devices.length <= 1) {
        onClose();
      }
    } finally {
      setSaving(false);
    }
  };

  const handleSaveRoomName = async () => {
    if (!onRenameRoom) return;
    const clean = roomTitleInput.trim();
    if (clean && clean !== room.name) {
      setSaving(true);
      try {
        await onRenameRoom(room.name, clean);
        setIsEditingRoomName(false);
      } finally {
        setSaving(false);
      }
    } else {
      setIsEditingRoomName(false);
    }
  };

  const handleDeleteRoom = async () => {
    if (!onDeleteRoom) return;
    setSaving(true);
    try {
      await onDeleteRoom(room.name);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  const standardRooms = ["Phòng ngủ", "Phòng khách", "Phòng bếp", "Lối vào", "Ban công", "Sân vườn"];
  const roomOptions = Array.from(new Set([...standardRooms, ...allRooms.map((r) => r.name)]));

  return (
    <div className="hm-modal-backdrop" role="presentation" onClick={onClose}>
      <section
        ref={dialogRef}
        className="hm-room-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="hm-room-modal-title"
        tabIndex={-1}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="hm-room-modal-head">
          <div className="hm-room-head">
            <span>
              <Icon name={room.icon} />
            </span>
            {isEditingRoomName ? (
              <div className="hm-room-name-inline-edit">
                <input
                  type="text"
                  value={roomTitleInput}
                  onChange={(e) => setRoomTitleInput(e.target.value)}
                  placeholder="Nhập tên phòng mới..."
                  autoFocus
                />
                <button
                  type="button"
                  className="hm-btn-primary-sm"
                  disabled={saving || !roomTitleInput.trim()}
                  onClick={() => void handleSaveRoomName()}
                >
                  <Icon name="check" />
                  <span>{saving ? "Lưu..." : "Lưu"}</span>
                </button>
                <button
                  type="button"
                  className="hm-btn-ghost-sm"
                  onClick={() => setIsEditingRoomName(false)}
                >
                  Hủy
                </button>
              </div>
            ) : isConfirmingDeleteRoom ? (
              <div className="hm-room-name-inline-edit">
                <span style={{ fontSize: "12px", color: "var(--hm-danger, #ef4444)", fontWeight: 600 }}>
                  Xóa phòng cùng {room.devices.length} thiết bị?
                </span>
                <button
                  type="button"
                  className="hm-btn-primary-sm"
                  style={{ background: "var(--hm-danger, #ef4444)", borderColor: "var(--hm-danger, #ef4444)" }}
                  disabled={saving}
                  onClick={() => void handleDeleteRoom()}
                >
                  <Icon name="trash" />
                  <span>{saving ? "Đang xóa..." : "Xác nhận xóa"}</span>
                </button>
                <button
                  type="button"
                  className="hm-btn-ghost-sm"
                  disabled={saving}
                  onClick={() => setIsConfirmingDeleteRoom(false)}
                >
                  Hủy
                </button>
              </div>
            ) : (
              <div>
                <div className="hm-room-title-row">
                  <strong id="hm-room-modal-title">{room.name}</strong>
                  {onRenameRoom && (
                    <button
                      type="button"
                      className="hm-room-title-edit-btn"
                      title="Đổi tên phòng này"
                      onClick={() => {
                        setRoomTitleInput(room.name);
                        setIsEditingRoomName(true);
                      }}
                    >
                      <Icon name="pencil" />
                      <span>Đổi tên</span>
                    </button>
                  )}
                  {onDeleteRoom && (
                    <button
                      type="button"
                      className="hm-room-title-delete-btn"
                      title="Xóa phòng này"
                      onClick={() => setIsConfirmingDeleteRoom(true)}
                    >
                      <Icon name="trash" />
                      <span>Xóa phòng</span>
                    </button>
                  )}
                </div>
                <small>{room.summary}</small>
              </div>
            )}
          </div>
          <button type="button" className="hm-icon-button" onClick={onClose} aria-label="Đóng danh sách thiết bị">
            <Icon name="close" />
          </button>
        </header>

        <div className="hm-room-device-list">
          {room.devices.map((device) => {
            const isLock = device.kind === "lock";
            const isLight = device.kind === "light";
            const isFan = device.kind === "fan";
            const isAircon = device.kind === "aircon";
            const isBlind = device.kind === "blind";
            const isSpeaker = device.kind === "speaker";
            const isSensor = device.kind === "sensor";

            const isLocked = isLock && Boolean(device.state?.locked ?? (device.status !== "warning"));
            const brightness = (device.state?.brightness as number) ?? 80;
            const targetTemp = (device.state?.target_temperature as number) ?? 24;
            const blindPos = (device.state?.position as number) ?? 0;
            const volume = (device.state?.volume as number) ?? 50;

            const isEditing = editingDeviceId === device.id;

            return (
              <article key={device.id} className="hm-device-item-card">
                {isEditing ? (
                  <div className="hm-device-edit-box">
                    <div className="hm-form-group">
                      <label htmlFor={`edit-name-${device.id}`}>Tên thiết bị</label>
                      <input
                        id={`edit-name-${device.id}`}
                        type="text"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        placeholder="Ví dụ: Đèn phòng ngủ"
                        autoFocus
                      />
                    </div>

                    <div className="hm-form-group">
                      <label>Chuyển đến phòng</label>
                      <div className="hm-room-select-pills">
                        {roomOptions.map((rName) => (
                          <button
                            key={rName}
                            type="button"
                            className={`hm-room-pill-btn ${editRoom === rName ? "active" : ""}`}
                            onClick={() => setEditRoom(rName)}
                          >
                            {rName}
                          </button>
                        ))}
                      </div>
                      <input
                        type="text"
                        value={editRoom}
                        onChange={(e) => setEditRoom(e.target.value)}
                        placeholder="Hoặc nhập tên phòng mới..."
                        style={{ marginTop: "8px" }}
                      />
                    </div>

                    <div className="hm-edit-action-row">
                      <button
                        type="button"
                        className="hm-btn-primary-sm"
                        disabled={saving || !editName.trim()}
                        onClick={() => void handleSaveEdit(device.id)}
                      >
                        <Icon name="check" />
                        <span>{saving ? "Đang lưu..." : "Lưu & Chuyển phòng"}</span>
                      </button>
                      <button
                        type="button"
                        className="hm-btn-ghost-sm"
                        disabled={saving}
                        onClick={() => setEditingDeviceId(null)}
                      >
                        Hủy
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="hm-device-main-row">
                      <div className="hm-device-info">
                        <strong>{device.name}</strong>
                        <small>{device.detail || "Sẵn sàng"}</small>
                      </div>
                      <div className="hm-device-actions">
                        <DeviceStatus status={device.status} />
                        {!isSensor && device.commandable && (
                          <button
                            type="button"
                            className={`hm-device-toggle-btn ${
                              isLock ? (isLocked ? "" : "unlocked") : device.status === "on" ? "active" : ""
                            }`}
                            onClick={() => handleDeviceAction(device)}
                          >
                            {isLock
                              ? isLocked
                                ? role === "member"
                                  ? "Yêu cầu mở khóa"
                                  : "Mở khóa (PIN)"
                                : "Khóa lại"
                              : isBlind
                                ? blindPos > 0
                                  ? "Đóng rèm"
                                  : "Mở rèm"
                                : device.status === "on"
                                  ? "Tắt"
                                  : "Bật"}
                          </button>
                        )}
                        {onUpdateDevice && (
                          <button
                            type="button"
                            className="hm-btn-device-edit"
                            title={`Chỉnh sửa / Đổi phòng cho ${device.name}`}
                            aria-label={`Chỉnh sửa ${device.name}`}
                            onClick={() => handleStartEdit(device)}
                          >
                            <Icon name="pencil" />
                          </button>
                        )}
                        {onDeleteDevice && (
                          <button
                            type="button"
                            className="hm-btn-device-delete"
                            title={`Xóa ${device.name}`}
                            aria-label={`Xóa ${device.name}`}
                            onClick={() => {
                              if (window.confirm(`Bạn có chắc chắn muốn xóa thiết bị "${device.name}" khỏi nhà không?`)) {
                                void onDeleteDevice(device.id);
                              }
                            }}
                          >
                            <Icon name="trash" />
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Additional controls for lights, aircon, blinds, speaker */}
                    {device.commandable && (
                      <div className="hm-device-subcontrols">
                        {isLight && (
                          <div className="hm-slider-group">
                            <span>Độ sáng ({brightness}%)</span>
                            <input
                              type="range"
                              min={0}
                              max={100}
                              value={brightness}
                              onChange={(e) => handleBrightnessChange(device, Number(e.target.value))}
                              aria-label={`Độ sáng ${device.name}`}
                            />
                          </div>
                        )}

                        {isAircon && (
                          <div className="hm-temp-group">
                            <span>Nhiệt độ mục tiêu</span>
                            <div className="hm-temp-stepper">
                              <button
                                type="button"
                                onClick={() => handleTempChange(device, -1)}
                                aria-label="Giảm 1 độ"
                              >
                                -
                              </button>
                              <b>{targetTemp}°C</b>
                              <button
                                type="button"
                                onClick={() => handleTempChange(device, 1)}
                                aria-label="Tăng 1 độ"
                              >
                                +
                              </button>
                            </div>
                          </div>
                        )}

                        {isBlind && (
                          <div className="hm-slider-group">
                            <span>Vị trí rèm ({blindPos}%)</span>
                            <input
                              type="range"
                              min={0}
                              max={100}
                              value={blindPos}
                              onChange={(e) => handleBlindPositionChange(device, Number(e.target.value))}
                              aria-label={`Vị trí rèm ${device.name}`}
                            />
                          </div>
                        )}

                        {isSpeaker && (
                          <div className="hm-slider-group">
                            <span>Âm lượng ({volume}%)</span>
                            <input
                              type="range"
                              min={0}
                              max={100}
                              value={volume}
                              onChange={(e) => handleVolumeChange(device, Number(e.target.value))}
                              aria-label={`Âm lượng ${device.name}`}
                            />
                          </div>
                        )}
                      </div>
                    )}
                  </>
                )}
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
