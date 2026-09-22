import React, { useState } from 'react';
import { Device, FaultMode } from '../types';
import { 
  Power, 
  Sun, 
  Lock, 
  Unlock, 
  Volume2, 
  Play, 
  Pause, 
  Thermometer, 
  Flame, 
  Footprints, 
  DoorOpen, 
  BatteryCharging, 
  AlertTriangle, 
  Trash2, 
  X, 
  Sparkles,
  Edit2,
  Check
} from 'lucide-react';

interface DeviceInspectorProps {
  device: Device;
  fault: FaultMode;
  onClose: () => void;
  onPerformAction: (deviceId: string, action: string, value?: any) => Promise<void>;
  onSetFault: (deviceId: string, mode: FaultMode) => Promise<void>;
  onUpdateDevice: (deviceId: string, updates: Partial<Device>) => Promise<void>;
  onDeleteDevice: (deviceId: string) => Promise<void>;
}

export const DeviceInspector: React.FC<DeviceInspectorProps> = ({
  device,
  fault,
  onClose,
  onPerformAction,
  onSetFault,
  onUpdateDevice,
  onDeleteDevice,
}) => {
  const [isEditingInfo, setIsEditingInfo] = useState(false);
  const [editName, setEditName] = useState(device.name);
  const [editRoom, setEditRoom] = useState(device.room);
  const [isBusy, setIsBusy] = useState(false);

  const state = device.state || {};
  const isPowerOn = state.power === true;
  const isLocked = state.locked === true;

  const handleTogglePower = async () => {
    setIsBusy(true);
    try {
      await onPerformAction(device.id, 'toggle');
    } finally {
      setIsBusy(false);
    }
  };

  const handleBrightnessChange = async (val: number) => {
    await onPerformAction(device.id, 'set', { brightness: val });
  };

  const handleTargetTempChange = async (delta: number) => {
    const current = state.target_temperature ?? 25;
    const next = Math.max(16, Math.min(32, current + delta));
    await onPerformAction(device.id, 'set', { target_temperature: next });
  };

  const handleModeChange = async (mode: string) => {
    await onPerformAction(device.id, 'set', { mode });
  };

  const handleLockToggle = async () => {
    setIsBusy(true);
    try {
      await onPerformAction(device.id, isLocked ? 'unlock' : 'lock');
    } finally {
      setIsBusy(false);
    }
  };

  const handleBlindPosition = async (val: number) => {
    await onPerformAction(device.id, 'set', { position: val });
  };

  const handleVolumeChange = async (val: number) => {
    await onPerformAction(device.id, 'set', { volume: val });
  };

  const handlePlayToggle = async () => {
    await onPerformAction(device.id, 'set', { playing: !state.playing });
  };

  const handleFaultChange = async (mode: FaultMode) => {
    await onSetFault(device.id, mode);
  };

  const handleAutoSimToggle = async () => {
    await onUpdateDevice(device.id, { auto_simulate: !device.auto_simulate });
  };

  const handleSaveInfo = async () => {
    if (!editName.trim()) return;
    await onUpdateDevice(device.id, {
      name: editName.trim(),
      room: editRoom.trim() || 'Phòng khách',
    });
    setIsEditingInfo(false);
  };

  const handleDelete = async () => {
    if (confirm(`Bạn có chắc muốn xóa thiết bị "${device.name}"?`)) {
      await onDeleteDevice(device.id);
      onClose();
    }
  };

  return (
    <div className="flex flex-col h-full bg-surface border-l border-outline-variant select-none">
      {/* Header */}
      <div className="p-4 border-b border-outline-variant bg-surface-container/50">
        <div className="flex items-start justify-between">
          <div className="flex-1 mr-2">
            {isEditingInfo ? (
              <div className="space-y-2">
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full px-2 py-1 text-xs bg-surface border border-outline-variant rounded-lg font-bold text-earth-dark"
                  placeholder="Tên thiết bị"
                />
                <input
                  type="text"
                  value={editRoom}
                  onChange={(e) => setEditRoom(e.target.value)}
                  className="w-full px-2 py-1 text-xs bg-surface border border-outline-variant rounded-lg text-earth-dark"
                  placeholder="Phòng"
                />
                <div className="flex items-center space-x-2">
                  <button
                    onClick={handleSaveInfo}
                    className="flex items-center space-x-1 px-2.5 py-1 bg-primary text-white text-xs font-bold rounded-lg"
                  >
                    <Check size={12} />
                    <span>Lưu</span>
                  </button>
                  <button
                    onClick={() => {
                      setEditName(device.name);
                      setEditRoom(device.room);
                      setIsEditingInfo(false);
                    }}
                    className="px-2.5 py-1 bg-surface-variant text-earth-dark text-xs rounded-lg"
                  >
                    Hủy
                  </button>
                </div>
              </div>
            ) : (
              <div>
                <div className="flex items-center space-x-2">
                  <h2 className="font-headline font-bold text-base text-earth-dark">
                    {device.name}
                  </h2>
                  <button
                    onClick={() => setIsEditingInfo(true)}
                    className="p-1 hover:bg-surface-variant text-earth-muted hover:text-earth-dark rounded-lg transition-colors"
                    title="Chỉnh sửa tên và phòng"
                  >
                    <Edit2 size={13} />
                  </button>
                </div>
                <div className="text-xs text-earth-muted mt-0.5">
                  <span>{device.room}</span> · <span className="font-mono">{device.id}</span>
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center space-x-1">
            <button
              onClick={handleDelete}
              className="p-1.5 text-earth-muted hover:text-rose-600 hover:bg-rose-50 rounded-xl transition-colors"
              title="Xóa thiết bị"
            >
              <Trash2 size={16} />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-earth-muted hover:text-earth-dark hover:bg-surface-variant rounded-xl transition-colors"
              title="Đóng bảng điều khiển"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Fault Status Banner if any */}
        {fault !== 'none' && (
          <div className="mt-3 p-2 bg-rose-50 border border-rose-200 rounded-xl flex items-center space-x-2 text-rose-700 text-xs font-semibold">
            <AlertTriangle size={15} className="flex-shrink-0" />
            <span>
              Đang ở chế độ lỗi: <strong className="uppercase">{fault}</strong>
            </span>
          </div>
        )}
      </div>

      {/* Main Control Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {/* General Power Switch (for light, aircon, speaker) */}
        {['light', 'aircon', 'speaker'].includes(device.kind) && (
          <div className="bg-surface-container/60 p-3.5 rounded-xl border border-outline-variant flex items-center justify-between">
            <div className="flex items-center space-x-2.5">
              <div
                className={`p-2 rounded-xl transition-colors ${
                  isPowerOn ? 'bg-primary text-white shadow-sm' : 'bg-surface text-earth-muted'
                }`}
              >
                <Power size={18} />
              </div>
              <div>
                <div className="text-xs font-bold text-earth-dark">Nguồn điện thiết bị</div>
                <div className="text-[11px] text-earth-muted">
                  {isPowerOn ? 'Đang hoạt động (ON)' : 'Đã ngắt nguồn (OFF)'}
                </div>
              </div>
            </div>

            <button
              onClick={handleTogglePower}
              disabled={isBusy}
              className={`px-4 py-2 text-xs font-bold rounded-xl transition-all ${
                isPowerOn
                  ? 'bg-primary hover:bg-primary-hover text-white shadow-sm'
                  : 'bg-surface border border-outline text-earth-dark hover:bg-surface-variant'
              }`}
            >
              {isPowerOn ? 'Tắt Thiết Bị' : 'Bật Thiết Bị'}
            </button>
          </div>
        )}

        {/* Light Controls */}
        {device.kind === 'light' && (
          <div className="bg-surface-container/60 p-3.5 rounded-xl border border-outline-variant space-y-3">
            <div className="flex items-center justify-between text-xs font-bold text-earth-dark">
              <span className="flex items-center space-x-1.5">
                <Sun size={15} className="text-amber-500" />
                <span>Độ sáng (Brightness)</span>
              </span>
              <span className="font-mono font-bold text-primary">
                {state.brightness ?? 80}%
              </span>
            </div>

            <input
              type="range"
              min="0"
              max="100"
              value={state.brightness ?? 80}
              onChange={(e) => handleBrightnessChange(Number(e.target.value))}
              className="w-full accent-primary cursor-pointer h-2 bg-outline-variant rounded-lg"
            />

            <div className="flex justify-between text-[10px] text-earth-muted font-mono pt-1">
              <div className="flex flex-col items-start">
                <span className="font-bold text-earth-dark">0%</span>
                <span className="text-[9px] text-earth-muted">Tối</span>
              </div>
              <div className="flex flex-col items-center">
                <span className="font-bold text-earth-dark">50%</span>
              </div>
              <div className="flex flex-col items-end">
                <span className="font-bold text-earth-dark">100%</span>
                <span className="text-[9px] text-earth-muted">Sáng tối đa</span>
              </div>
            </div>
          </div>
        )}

        {/* Aircon Controls */}
        {device.kind === 'aircon' && (
          <div className="bg-surface-container/60 p-3.5 rounded-xl border border-outline-variant space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-earth-dark flex items-center space-x-1.5">
                <Thermometer size={15} className="text-sky-500" />
                <span>Nhiệt độ cài đặt</span>
              </span>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleTargetTempChange(-1)}
                  className="w-7 h-7 rounded-lg bg-surface border border-outline-variant flex items-center justify-center font-bold text-earth-dark hover:bg-surface-variant"
                >
                  -
                </button>
                <span className="text-base font-bold font-headline text-primary w-12 text-center">
                  {state.target_temperature ?? 25}°C
                </span>
                <button
                  onClick={() => handleTargetTempChange(1)}
                  className="w-7 h-7 rounded-lg bg-surface border border-outline-variant flex items-center justify-center font-bold text-earth-dark hover:bg-surface-variant"
                >
                  +
                </button>
              </div>
            </div>

            <div className="pt-1">
              <div className="text-[11px] font-bold text-earth-muted mb-1.5">Chế độ vận hành</div>
              <div className="grid grid-cols-4 gap-1 text-xs">
                {['cool', 'heat', 'fan', 'dry'].map((m) => (
                  <button
                    key={m}
                    onClick={() => handleModeChange(m)}
                    className={`py-1.5 rounded-lg font-bold capitalize transition-all ${
                      (state.mode || 'cool') === m
                        ? 'bg-primary text-white shadow-sm'
                        : 'bg-surface text-earth-dark hover:bg-surface-variant'
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Lock Controls */}
        {device.kind === 'lock' && (
          <div className="bg-surface-container/60 p-3.5 rounded-xl border border-outline-variant flex items-center justify-between">
            <div className="flex items-center space-x-2.5">
              <div
                className={`p-2 rounded-xl ${
                  isLocked ? 'bg-primary text-white' : 'bg-amber-100 text-amber-700'
                }`}
              >
                {isLocked ? <Lock size={18} /> : <Unlock size={18} />}
              </div>
              <div>
                <div className="text-xs font-bold text-earth-dark">Trạng thái khóa</div>
                <div className="text-[11px] text-earth-muted">
                  {isLocked ? 'Cửa đang Khóa An Toàn' : 'Cửa đang Mở Khóa'}
                </div>
              </div>
            </div>

            <button
              onClick={handleLockToggle}
              disabled={isBusy}
              className={`px-4 py-2 text-xs font-bold rounded-xl transition-all ${
                isLocked
                  ? 'bg-amber-600 hover:bg-amber-700 text-white shadow-sm'
                  : 'bg-primary hover:bg-primary-hover text-white shadow-sm'
              }`}
            >
              {isLocked ? 'Mở Khóa' : 'Khóa Cửa'}
            </button>
          </div>
        )}

        {/* Blind Controls */}
        {device.kind === 'blind' && (
          <div className="bg-surface-container/60 p-3.5 rounded-xl border border-outline-variant space-y-3">
            <div className="flex items-center justify-between text-xs font-bold text-earth-dark">
              <span>Độ mở rèm cửa</span>
              <span className="font-mono font-bold text-primary">
                {state.position ?? 0}%
              </span>
            </div>

            <input
              type="range"
              min="0"
              max="100"
              value={state.position ?? 0}
              onChange={(e) => handleBlindPosition(Number(e.target.value))}
              className="w-full accent-primary cursor-pointer h-2 bg-outline-variant rounded-lg"
            />

            <div className="flex justify-between text-[10px] text-earth-muted font-mono">
              <span>0% (Đóng kín)</span>
              <span>50%</span>
              <span>100% (Mở hoàn toàn)</span>
            </div>
          </div>
        )}

        {/* Speaker Controls */}
        {device.kind === 'speaker' && (
          <div className="bg-surface-container/60 p-3.5 rounded-xl border border-outline-variant space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-earth-dark">Phát âm thanh</span>
              <button
                onClick={handlePlayToggle}
                className="flex items-center space-x-1.5 px-3 py-1.5 bg-primary text-white text-xs font-bold rounded-xl shadow-sm hover:bg-primary-hover"
              >
                {state.playing ? <Pause size={13} /> : <Play size={13} />}
                <span>{state.playing ? 'Tạm Dừng' : 'Phát Nhạc'}</span>
              </button>
            </div>

            <div className="pt-2">
              <div className="flex items-center justify-between text-xs font-bold text-earth-dark mb-1">
                <span className="flex items-center space-x-1">
                  <Volume2 size={14} className="text-earth-muted" />
                  <span>Âm lượng</span>
                </span>
                <span className="font-mono text-primary">{state.volume ?? 50}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={state.volume ?? 50}
                onChange={(e) => handleVolumeChange(Number(e.target.value))}
                className="w-full accent-primary cursor-pointer h-2 bg-outline-variant rounded-lg"
              />
            </div>
          </div>
        )}

        {/* Sensor Telemetry Cards */}
        {device.kind === 'sensor' && (
          <div className="space-y-2">
            <div className="text-[11px] font-bold text-earth-muted uppercase tracking-wider">
              Dữ liệu Telemetry Cảm biến
            </div>

            <div className="grid grid-cols-2 gap-2">
              {state.temperature !== undefined && (
                <div className="bg-surface-container/60 p-3 rounded-xl border border-outline-variant">
                  <div className="text-xs text-earth-muted flex items-center space-x-1">
                    <Thermometer size={13} className="text-emerald-600" />
                    <span>Nhiệt độ</span>
                  </div>
                  <div className="text-lg font-bold font-headline text-earth-dark mt-1">
                    {state.temperature}°C
                  </div>
                </div>
              )}

              {state.humidity !== undefined && (
                <div className="bg-surface-container/60 p-3 rounded-xl border border-outline-variant">
                  <div className="text-xs text-earth-muted flex items-center space-x-1">
                    <Thermometer size={13} className="text-sky-600" />
                    <span>Độ ẩm</span>
                  </div>
                  <div className="text-lg font-bold font-headline text-earth-dark mt-1">
                    {state.humidity}%
                  </div>
                </div>
              )}

              {state.ppm !== undefined && (
                <div className="bg-surface-container/60 p-3 rounded-xl border border-outline-variant">
                  <div className="text-xs text-earth-muted flex items-center space-x-1">
                    <Flame size={13} className="text-rose-600" />
                    <span>Mức Gas / Khói</span>
                  </div>
                  <div className="text-lg font-bold font-headline text-earth-dark mt-1">
                    {state.ppm} <span className="text-xs font-normal text-earth-muted">PPM</span>
                  </div>
                </div>
              )}

              {state.gas_detected !== undefined && (
                <div className={`p-3 rounded-xl border ${
                  state.gas_detected
                    ? 'bg-rose-50 border-rose-300 text-rose-800'
                    : 'bg-surface-container/60 border-outline-variant text-earth-dark'
                }`}>
                  <div className="text-xs">Cảnh báo Gas</div>
                  <div className="text-sm font-bold mt-1">
                    {state.gas_detected ? '⚠️ Phát Hiện Rò Rỉ' : '✅ Bình Thường'}
                  </div>
                </div>
              )}

              {state.motion !== undefined && (
                <div className="bg-surface-container/60 p-3 rounded-xl border border-outline-variant">
                  <div className="text-xs text-earth-muted flex items-center space-x-1">
                    <Footprints size={13} className="text-purple-600" />
                    <span>Chuyển động</span>
                  </div>
                  <div className="text-sm font-bold font-headline text-earth-dark mt-1">
                    {state.motion ? '🏃 Có người' : 'Tĩnh lặng'}
                  </div>
                </div>
              )}

              {state.open !== undefined && (
                <div className="bg-surface-container/60 p-3 rounded-xl border border-outline-variant">
                  <div className="text-xs text-earth-muted flex items-center space-x-1">
                    <DoorOpen size={13} className="text-indigo-600" />
                    <span>Cửa đóng / mở</span>
                  </div>
                  <div className="text-sm font-bold font-headline text-earth-dark mt-1">
                    {state.open ? 'Đang Mở' : 'Đang Đóng'}
                  </div>
                </div>
              )}

              {state.battery !== undefined && (
                <div className="bg-surface-container/60 p-3 rounded-xl border border-outline-variant">
                  <div className="text-xs text-earth-muted flex items-center space-x-1">
                    <BatteryCharging size={13} className="text-primary" />
                    <span>Dung lượng Pin</span>
                  </div>
                  <div className="text-lg font-bold font-headline text-earth-dark mt-1">
                    {state.battery}%
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Auto Simulation Switch */}
        <div className="p-3.5 bg-surface-container/60 rounded-xl border border-outline-variant flex items-center justify-between">
          <div>
            <div className="text-xs font-bold text-earth-dark flex items-center space-x-1.5">
              <Sparkles size={14} className="text-primary" />
              <span>Tự động mô phỏng (Auto-Simulate)</span>
            </div>
            <div className="text-[11px] text-earth-muted">
              Tự sinh dao động telemetry cảm biến ngẫu nhiên
            </div>
          </div>

          <button
            onClick={handleAutoSimToggle}
            className={`w-11 h-6 rounded-full transition-colors relative p-0.5 ${
              device.auto_simulate ? 'bg-primary' : 'bg-outline'
            }`}
          >
            <div
              className={`w-5 h-5 rounded-full bg-white shadow-sm transform transition-transform ${
                device.auto_simulate ? 'translate-x-5' : 'translate-x-0'
              }`}
            />
          </button>
        </div>

        {/* Fault Injection Panel */}
        <div className="p-3.5 bg-surface-container/60 rounded-xl border border-outline-variant space-y-3">
          <div>
            <div className="text-xs font-bold text-earth-dark flex items-center space-x-1.5">
              <AlertTriangle size={14} className="text-rose-600" />
              <span>Tiêm Lỗi Thử Nghiệm (Fault Injection)</span>
            </div>
            <div className="text-[11px] text-earth-muted">
              Kiểm tra tính ổn định của hệ thống khi thiết bị gặp sự cố
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs">
            <button
              onClick={() => handleFaultChange('none')}
              className={`p-2 rounded-xl font-bold border transition-all text-left ${
                fault === 'none'
                  ? 'bg-primary text-white border-primary shadow-sm'
                  : 'bg-surface text-earth-dark border-outline-variant hover:bg-surface-variant'
              }`}
            >
              <div>Bình thường (None)</div>
              <div className="text-[10px] font-normal opacity-80">Hoạt động chuẩn xác</div>
            </button>

            <button
              onClick={() => handleFaultChange('offline')}
              className={`p-2 rounded-xl font-bold border transition-all text-left ${
                fault === 'offline'
                  ? 'bg-rose-600 text-white border-rose-600 shadow-sm'
                  : 'bg-surface text-rose-700 border-outline-variant hover:bg-rose-50'
              }`}
            >
              <div>Mất mạng (Offline)</div>
              <div className="text-[10px] font-normal opacity-80">Bỏ qua lệnh điều khiển</div>
            </button>

            <button
              onClick={() => handleFaultChange('timeout')}
              className={`p-2 rounded-xl font-bold border transition-all text-left ${
                fault === 'timeout'
                  ? 'bg-amber-600 text-white border-amber-600 shadow-sm'
                  : 'bg-surface text-amber-700 border-outline-variant hover:bg-amber-50'
              }`}
            >
              <div>Timeout (Mất ACK)</div>
              <div className="text-[10px] font-normal opacity-80">Không gửi phản hồi</div>
            </button>

            <button
              onClick={() => handleFaultChange('error')}
              className={`p-2 rounded-xl font-bold border transition-all text-left ${
                fault === 'error'
                  ? 'bg-purple-600 text-white border-purple-600 shadow-sm'
                  : 'bg-surface text-purple-700 border-outline-variant hover:bg-purple-50'
              }`}
            >
              <div>Lỗi (Hardware Err)</div>
              <div className="text-[10px] font-normal opacity-80">Trả mã lỗi ACK error</div>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
