import { useMemo, useState } from "react";
import type { ApiDeviceCommand } from "../../api/types";
import { useDialogFocus } from "../../hooks/useDialogFocus";
import { cloneDefaultPresets } from "../../presets";
import type { Device, DeviceCommandAction, HomePreset, PresetAction } from "../../types";
import { Icon } from "../shared/Icon";

const newId = (prefix: string) => `${prefix}-${Math.random().toString(36).slice(2, 9)}`;
const actionOptions: Array<{ value: DeviceCommandAction; label: string }> = [
  { value: "on", label: "Bật" },
  { value: "off", label: "Tắt" },
  { value: "set", label: "Thiết lập" },
  { value: "toggle", label: "Đổi trạng thái" },
  { value: "lock", label: "Khóa" },
  { value: "unlock", label: "Mở khóa" },
];

export function labelForPresetAction(action: PresetAction, device?: Device) {
  const command = actionOptions.find((item) => item.value === action.action)?.label ?? action.action;
  const value = action.action === "set" && action.value
    ? ` · ${Object.entries(action.value).map(([key, val]) => `${key}: ${String(val)}`).join(", ")}`
    : "";
  return `${command} ${device?.name ?? action.deviceId}${value}`;
}

export function PresetPanel({
  devices,
  canEdit,
  onDeviceCommand,
  presets,
  onPresetsChange,
  variant = "widget",
}: {
  devices: Device[];
  canEdit: boolean;
  onDeviceCommand: (device: Device, command: ApiDeviceCommand) => Promise<void>;
  presets: HomePreset[];
  onPresetsChange: (next: HomePreset[]) => void;
  variant?: "widget" | "page";
}) {
  const [editing, setEditing] = useState<HomePreset | null>(null);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const deviceById = useMemo(() => new Map(devices.map((device) => [device.id, device])), [devices]);

  const runPreset = async (preset: HomePreset) => {
    const available = preset.actions
      .map((action) => ({ action, device: deviceById.get(action.deviceId) }))
      .filter((item): item is { action: PresetAction; device: Device } => Boolean(item.device));
    if (!available.length) {
      setNotice("Preset chưa có thiết bị hợp lệ để chạy.");
      return;
    }
    setRunningId(preset.id);
    setNotice("");
    const results = await Promise.allSettled(
      available.map(({ action, device }) => onDeviceCommand(device, {
        action: action.action,
        ...(action.value ? { value: action.value } : {}),
      })),
    );
    const submitted = results.filter((result) => result.status === "fulfilled").length;
    const missing = preset.actions.length - available.length;
    setNotice(
      submitted === preset.actions.length
        ? `Đã gửi “${preset.name}” (${submitted} hành động).`
        : `Đã gửi “${preset.name}”: ${submitted}/${preset.actions.length} hành động${missing ? `, ${missing} thiết bị không còn tồn tại` : ""}.`,
    );
    setRunningId(null);
  };

  return (
    <section className={variant === "page" ? "hm-presets-page" : "widget scenes-card"} aria-label="Preset tự động hóa">
      {variant === "page" && (
        <div className="preset-page-intro">
          <p>NGỮ CẢNH & TỰ ĐỘNG HÓA</p>
          <h1>Preset nhà thông minh</h1>
          <span>Chạy nhanh hoặc điều chỉnh từng lệnh thiết bị. Thay đổi ở đây xuất hiện ngay trong widget Dashboard.</span>
        </div>
      )}
      <div className="preset-heading">
        <h2>Ngữ cảnh hôm nay</h2>
        {canEdit && (
          <button type="button" className="preset-edit" onClick={() => setEditing({
            id: newId("preset"), name: "Preset mới", icon: "sparkles", actions: [],
          })}>
            + Thêm
          </button>
        )}
      </div>
      {presets.map((preset) => (
        <div className={variant === "page" ? "preset-page-card" : "preset-item"} key={preset.id}>
          <div className="preset-row">
            <button
              className={runningId === preset.id ? "active" : ""}
              type="button"
              disabled={runningId !== null || preset.actions.length === 0}
              onClick={() => void runPreset(preset)}
              title={`${preset.actions.length} hành động`}
            >
              <span><Icon name={preset.icon} />{preset.name}</span>
              <Icon name="power" />
            </button>
            {canEdit && (
              <button className="preset-config" type="button" title={`Chỉnh cấu hình ${preset.name}`} onClick={() => setEditing(JSON.parse(JSON.stringify(preset)) as HomePreset)}>
                <Icon name="pencil" />
              </button>
            )}
          </div>
          {variant === "page" && (
            <div className="preset-page-actions">
              <span>{preset.actions.length} hành động</span>
              <ul>{preset.actions.map((action) => <li key={action.id}>{labelForPresetAction(action, deviceById.get(action.deviceId))}</li>)}</ul>
            </div>
          )}
        </div>
      ))}
      {notice && <p className="preset-notice" role="status">{notice}</p>}
      {editing && (
        <PresetEditor
          preset={editing}
          devices={devices}
          onClose={() => setEditing(null)}
          onSave={(saved) => {
            const exists = presets.some((preset) => preset.id === saved.id);
            onPresetsChange(exists ? presets.map((preset) => preset.id === saved.id ? saved : preset) : [...presets, saved]);
            setEditing(null);
            setNotice(`Đã lưu cấu hình “${saved.name}”.`);
          }}
          onDelete={() => {
            onPresetsChange(presets.filter((preset) => preset.id !== editing.id));
            setEditing(null);
            setNotice("Đã xóa preset.");
          }}
          onRestoreDefaults={() => {
            onPresetsChange(cloneDefaultPresets());
            setEditing(null);
            setNotice("Đã khôi phục các preset mặc định.");
          }}
        />
      )}
    </section>
  );
}

function PresetEditor({
  preset,
  devices,
  onClose,
  onSave,
  onDelete,
  onRestoreDefaults,
}: {
  preset: HomePreset;
  devices: Device[];
  onClose: () => void;
  onSave: (preset: HomePreset) => void;
  onDelete: () => void;
  onRestoreDefaults: () => void;
}) {
  const dialogRef = useDialogFocus<HTMLElement>(true, onClose);
  const [draft, setDraft] = useState(preset);
  const [jsonErrors, setJsonErrors] = useState<Record<string, string>>({});
  const updateAction = (id: string, patch: Partial<PresetAction>) => setDraft((current) => ({
    ...current,
    actions: current.actions.map((action) => action.id === id ? { ...action, ...patch } : action),
  }));

  const save = () => {
    if (!draft.name.trim() || Object.keys(jsonErrors).length) return;
    onSave({ ...draft, name: draft.name.trim() });
  };

  return (
    <div className="hm-modal-backdrop" role="presentation" onClick={onClose}>
      <section ref={dialogRef} className="hm-preset-modal" role="dialog" aria-modal="true" aria-labelledby="preset-editor-title" tabIndex={-1} onClick={(event) => event.stopPropagation()}>
        <header className="hm-preset-modal-head">
          <div>
            <p>PRESET TỰ ĐỘNG HÓA</p>
            <h2 id="preset-editor-title">Chỉnh cấu hình preset</h2>
          </div>
          <button type="button" className="hm-modal-close" onClick={onClose} aria-label="Đóng">×</button>
        </header>
        <div className="hm-preset-modal-body">
          <label className="preset-field">
            <span>Tên preset</span>
            <input value={draft.name} maxLength={60} onChange={(event) => setDraft({ ...draft, name: event.target.value })} placeholder="Ví dụ: Đi ngủ" />
          </label>
          <div className="preset-actions-heading">
            <strong>Hành động khi chạy</strong>
            <button type="button" className="hm-btn-ghost-sm" onClick={() => setDraft((current) => ({
              ...current,
              actions: [...current.actions, { id: newId("action"), deviceId: devices[0]?.id || "", action: "on" }],
            }))}>+ Thêm hành động</button>
          </div>
          {!draft.actions.length && <p className="preset-empty">Thêm ít nhất một hành động để preset có thể chạy.</p>}
          <div className="preset-actions-list">
            {draft.actions.map((action, index) => (
              <div className="preset-action-editor" key={action.id}>
                <div className="preset-action-title">Hành động {index + 1}</div>
                <label className="preset-field"><span>Thiết bị</span>
                  <select value={action.deviceId} onChange={(event) => updateAction(action.id, { deviceId: event.target.value })}>
                    {!devices.length && <option value="">Chưa có thiết bị</option>}
                    {devices.map((device) => <option key={device.id} value={device.id}>{device.name} · {device.room}</option>)}
                  </select>
                </label>
                <label className="preset-field"><span>Lệnh</span>
                  <select value={action.action} onChange={(event) => updateAction(action.id, { action: event.target.value as DeviceCommandAction, ...(event.target.value === "set" ? {} : { value: undefined }) })}>
                    {actionOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                </label>
                {action.action === "set" && (
                  <label className="preset-field preset-json"><span>Giá trị cấu hình (JSON)</span>
                    <input
                      value={JSON.stringify(action.value || {})}
                      placeholder={'{"brightness": 50}'}
                      onChange={(event) => {
                        try {
                          const parsed: unknown = JSON.parse(event.target.value);
                          if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error();
                          updateAction(action.id, { value: parsed as Record<string, unknown> });
                          setJsonErrors((current) => { const next = { ...current }; delete next[action.id]; return next; });
                        } catch {
                          setJsonErrors((current) => ({ ...current, [action.id]: "JSON phải là một đối tượng, ví dụ {\"brightness\": 50}" }));
                        }
                      }}
                    />
                    {jsonErrors[action.id] && <small className="preset-error">{jsonErrors[action.id]}</small>}
                  </label>
                )}
                <button type="button" className="preset-remove-action" onClick={() => setDraft((current) => ({ ...current, actions: current.actions.filter((item) => item.id !== action.id) }))}>Xóa hành động</button>
              </div>
            ))}
          </div>
        </div>
        <footer className="hm-preset-modal-foot">
          <button type="button" className="preset-danger" onClick={onDelete}>Xóa preset</button>
          <button type="button" className="preset-restore" onClick={onRestoreDefaults}>Khôi phục mặc định</button>
          <div className="preset-foot-actions"><button type="button" className="hm-btn-ghost-sm" onClick={onClose}>Hủy</button><button type="button" className="hm-btn-primary-sm" disabled={!draft.name.trim() || Object.keys(jsonErrors).length > 0} onClick={save}>Lưu preset</button></div>
        </footer>
      </section>
    </div>
  );
}
