import React, { useState } from 'react';
import { Device, FaultMode } from '../types';
import { 
  Lightbulb, 
  Wind, 
  Blinds, 
  Speaker, 
  Lock, 
  Flame, 
  Thermometer, 
  DoorOpen, 
  Footprints,
  Plus, 
  Search, 
  GripVertical,
  AlertTriangle,
  Zap
} from 'lucide-react';

interface DeviceLibraryProps {
  devices: Device[];
  faults: Record<string, FaultMode>;
  onAddNewDevice: (device: Partial<Device>) => Promise<void>;
  onSelectDevice?: (device: Device | null) => void;
  selectedDeviceId?: string | null;
}

interface DeviceTemplate {
  kind: string;
  name: string;
  room: string;
  category: 'lighting' | 'climate' | 'security' | 'sensors' | 'entertainment';
  icon: React.ReactNode;
  defaultState: Record<string, any>;
  autoSimulate?: boolean;
}

const DEVICE_TEMPLATES: DeviceTemplate[] = [
  {
    kind: 'light',
    name: 'Đèn LED Thông Minh',
    room: 'Phòng khách',
    category: 'lighting',
    icon: <Lightbulb size={18} className="text-amber-500" />,
    defaultState: { power: true, brightness: 80 },
  },
  {
    kind: 'light',
    name: 'Đèn Ngủ Ấm Áp',
    room: 'Phòng ngủ',
    category: 'lighting',
    icon: <Lightbulb size={18} className="text-amber-600" />,
    defaultState: { power: false, brightness: 40 },
  },
  {
    kind: 'aircon',
    name: 'Điều Hòa Inverter',
    room: 'Phòng khách',
    category: 'climate',
    icon: <Wind size={18} className="text-sky-500" />,
    defaultState: { power: true, target_temperature: 25, mode: 'cool' },
  },
  {
    kind: 'blind',
    name: 'Rèm Cửa Tự Động',
    room: 'Phòng khách',
    category: 'climate',
    icon: <Blinds size={18} className="text-amber-700" />,
    defaultState: { position: 0 },
  },
  {
    kind: 'speaker',
    name: 'Loa Thông Minh Homing',
    room: 'Phòng khách',
    category: 'entertainment',
    icon: <Speaker size={18} className="text-purple-500" />,
    defaultState: { power: false, volume: 50, playing: false },
  },
  {
    kind: 'lock',
    name: 'Khóa Cửa Vân Tay',
    room: 'Phòng khách',
    category: 'security',
    icon: <Lock size={18} className="text-slate-700" />,
    defaultState: { locked: true },
  },
  {
    kind: 'sensor',
    name: 'Cảm Biến Cửa Từ',
    room: 'Phòng khách',
    category: 'security',
    icon: <DoorOpen size={18} className="text-indigo-500" />,
    defaultState: { open: false, battery: 95 },
    autoSimulate: true,
  },
  {
    kind: 'sensor',
    name: 'Cảm Biến Nhiệt Ẩm',
    room: 'Phòng khách',
    category: 'sensors',
    icon: <Thermometer size={18} className="text-emerald-500" />,
    defaultState: { temperature: 26.5, humidity: 62.0, battery: 98 },
    autoSimulate: true,
  },
  {
    kind: 'sensor',
    name: 'Cảm Biến Khí Gas',
    room: 'Phòng bếp',
    category: 'sensors',
    icon: <Flame size={18} className="text-rose-500" />,
    defaultState: { gas_detected: false, ppm: 110, battery: 100 },
    autoSimulate: true,
  },
  {
    kind: 'sensor',
    name: 'Cảm Biến Chuyển Động',
    room: 'Hành lang',
    category: 'sensors',
    icon: <Footprints size={18} className="text-cyan-600" />,
    defaultState: { motion: false, battery: 90 },
    autoSimulate: true,
  },
];

export const DeviceLibrary: React.FC<DeviceLibraryProps> = ({
  devices,
  faults,
  onAddNewDevice,
}) => {
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Form State
  const [formName, setFormName] = useState('');
  const [formKind, setFormKind] = useState('light');
  const [formRoom, setFormRoom] = useState('Phòng khách');
  const [formId, setFormId] = useState('');
  const [formAutoSim, setFormAutoSim] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Statistics
  const activeCount = devices.filter(
    (d) => d.state?.power === true || d.state?.locked === true || (d.kind === 'sensor' && (faults[d.id] || 'none') === 'none')
  ).length;
  const faultCount = devices.filter((d) => (faults[d.id] || 'none') !== 'none').length;

  const filteredTemplates = DEVICE_TEMPLATES.filter((tpl) => {
    const matchCategory = activeCategory === 'all' || tpl.category === activeCategory;
    const matchSearch = tpl.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                        tpl.room.toLowerCase().includes(searchQuery.toLowerCase());
    return matchCategory && matchSearch;
  });

  const handleDragStart = (e: React.DragEvent, tpl: DeviceTemplate) => {
    const uniqueSuffix = Math.random().toString(36).substring(2, 6);
    const item = {
      id: `${tpl.kind}-${uniqueSuffix}`,
      name: tpl.name,
      kind: tpl.kind,
      room: tpl.room,
      state: tpl.defaultState,
      auto_simulate: tpl.autoSimulate ?? false,
    };
    e.dataTransfer.setData('application/json', JSON.stringify(item));
    e.dataTransfer.effectAllowed = 'copy';
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim()) return;
    setIsSubmitting(true);
    try {
      const generatedId = formId.trim() || `${formKind}-${Math.random().toString(36).substring(2, 7)}`;
      let defaultState: Record<string, any> = {};
      if (formKind === 'light') defaultState = { power: true, brightness: 80 };
      else if (formKind === 'aircon') defaultState = { power: true, target_temperature: 25, mode: 'cool' };
      else if (formKind === 'blind') defaultState = { position: 0 };
      else if (formKind === 'lock') defaultState = { locked: true };
      else if (formKind === 'speaker') defaultState = { power: false, volume: 50, playing: false };
      else defaultState = { temperature: 27.0, humidity: 65.0, battery: 100 };

      await onAddNewDevice({
        id: generatedId,
        name: formName.trim(),
        kind: formKind,
        room: formRoom.trim() || 'Phòng khách',
        x: 180 + Math.random() * 80,
        y: 180 + Math.random() * 80,
        state: defaultState,
        auto_simulate: formAutoSim,
      });

      setIsModalOpen(false);
      setFormName('');
      setFormId('');
    } catch (err) {
      alert(`Lỗi khi tạo thiết bị: ${err}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-surface border-l border-outline-variant select-none">
      {/* Header & Quick Stats */}
      <div className="p-4 border-b border-outline-variant bg-surface-container/50">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-base font-bold font-headline text-earth-dark">Thư viện Thiết bị</h2>
            <p className="text-xs text-earth-muted">Kéo thả thiết bị vào bản vẽ mặt bằng</p>
          </div>
          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-primary hover:bg-primary-hover text-white text-xs font-semibold rounded-xl shadow-sm transition-all"
          >
            <Plus size={14} />
            <span>Thêm Mới</span>
          </button>
        </div>

        {/* Stats Pill Row */}
        <div className="grid grid-cols-3 gap-2">
          <div className="bg-surface p-2 rounded-xl border border-outline-variant text-center">
            <div className="text-xs text-earth-muted">Tổng số</div>
            <div className="text-sm font-bold text-earth-dark font-headline">{devices.length}</div>
          </div>
          <div className="bg-surface p-2 rounded-xl border border-outline-variant text-center">
            <div className="text-xs text-primary flex items-center justify-center space-x-0.5">
              <Zap size={10} />
              <span>Đang bật</span>
            </div>
            <div className="text-sm font-bold text-primary font-headline">{activeCount}</div>
          </div>
          <div className="bg-surface p-2 rounded-xl border border-outline-variant text-center">
            <div className="text-xs text-rose-600 flex items-center justify-center space-x-0.5">
              <AlertTriangle size={10} />
              <span>Cảnh báo</span>
            </div>
            <div className="text-sm font-bold text-rose-600 font-headline">{faultCount}</div>
          </div>
        </div>
      </div>

      {/* Category Pills & Search */}
      <div className="p-3 border-b border-outline-variant space-y-2">
        <div className="relative">
          <Search size={14} className="absolute left-2.5 top-2.5 text-earth-muted" />
          <input
            type="text"
            placeholder="Tìm theo tên hoặc phòng..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-surface-container border border-outline-variant rounded-xl focus:outline-none focus:border-primary text-earth-dark placeholder-earth-muted"
          />
        </div>

        <div className="flex items-center space-x-1 overflow-x-auto pb-1 text-xs">
          {[
            { id: 'all', label: 'Tất cả' },
            { id: 'lighting', label: 'Chiếu sáng' },
            { id: 'climate', label: 'Khí hậu' },
            { id: 'sensors', label: 'Cảm biến' },
            { id: 'security', label: 'An ninh' },
          ].map((cat) => (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat.id)}
              className={`px-2.5 py-1 rounded-lg font-medium whitespace-nowrap transition-all ${
                activeCategory === cat.id
                  ? 'bg-primary text-white'
                  : 'bg-surface-container hover:bg-surface-variant text-earth-dark'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Templates List (Draggable) */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        <div className="text-[11px] font-bold text-earth-muted uppercase tracking-wider px-1">
          Mẫu Thiết Bị Sẵn Sàng (Kéo Thả)
        </div>
        {filteredTemplates.map((tpl, idx) => (
          <div
            key={idx}
            draggable
            onDragStart={(e) => handleDragStart(e, tpl)}
            className="group flex items-center justify-between p-2.5 bg-surface-container/60 hover:bg-surface border border-outline-variant rounded-xl cursor-grab active:cursor-grabbing hover:shadow-soft transition-all"
          >
            <div className="flex items-center space-x-2.5">
              <div className="p-2 bg-surface rounded-lg shadow-sm border border-outline-variant">
                {tpl.icon}
              </div>
              <div>
                <div className="text-xs font-bold text-earth-dark group-hover:text-primary transition-colors">
                  {tpl.name}
                </div>
                <div className="text-[11px] text-earth-muted">
                  Gợi ý: {tpl.room} · {tpl.kind}
                </div>
              </div>
            </div>
            <GripVertical size={16} className="text-earth-muted group-hover:text-primary" />
          </div>
        ))}
      </div>

      {/* Modal: Thêm Thiết Bị Mới */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-earth-dark/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-surface w-full max-w-md rounded-2xl shadow-soft-lg border border-outline-variant overflow-hidden">
            <div className="p-4 border-b border-outline-variant bg-surface-container flex items-center justify-between">
              <h3 className="font-headline font-bold text-base text-earth-dark">
                Tạo Thiết Bị Mới
              </h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-earth-muted hover:text-earth-dark text-sm p-1 rounded-lg"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="p-5 space-y-4">
              <div>
                <label className="block text-xs font-bold text-earth-dark mb-1">
                  Tên thiết bị *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ví dụ: Đèn Trần Bàn Ăn"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="w-full px-3 py-2 text-xs bg-surface-container border border-outline-variant rounded-xl focus:outline-none focus:border-primary text-earth-dark"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-earth-dark mb-1">
                    Loại thiết bị
                  </label>
                  <select
                    value={formKind}
                    onChange={(e) => setFormKind(e.target.value)}
                    className="w-full px-3 py-2 text-xs bg-surface-container border border-outline-variant rounded-xl focus:outline-none focus:border-primary text-earth-dark"
                  >
                    <option value="light">Đèn Chiếu Sáng (Light)</option>
                    <option value="aircon">Điều Hòa (Aircon)</option>
                    <option value="blind">Rèm Cửa (Blind)</option>
                    <option value="lock">Khóa Thông Minh (Lock)</option>
                    <option value="speaker">Loa Thông Minh (Speaker)</option>
                    <option value="sensor">Cảm Biến (Sensor)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-earth-dark mb-1">
                    Phòng lắp đặt
                  </label>
                  <input
                    type="text"
                    placeholder="Phòng khách, Bếp..."
                    value={formRoom}
                    onChange={(e) => setFormRoom(e.target.value)}
                    className="w-full px-3 py-2 text-xs bg-surface-container border border-outline-variant rounded-xl focus:outline-none focus:border-primary text-earth-dark"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-earth-dark mb-1">
                  Device ID (Tùy chọn)
                </label>
                <input
                  type="text"
                  placeholder="Để trống để tự động sinh ID"
                  value={formId}
                  onChange={(e) => setFormId(e.target.value)}
                  className="w-full px-3 py-2 text-xs bg-surface-container border border-outline-variant rounded-xl focus:outline-none focus:border-primary text-earth-dark font-mono"
                />
              </div>

              <div className="flex items-center space-x-2 pt-1">
                <input
                  type="checkbox"
                  id="autoSim"
                  checked={formAutoSim}
                  onChange={(e) => setFormAutoSim(e.target.checked)}
                  className="w-4 h-4 text-primary rounded border-outline focus:ring-primary"
                />
                <label htmlFor="autoSim" className="text-xs text-earth-dark">
                  Kích hoạt Auto-simulate (Tự sinh dữ liệu cảm biến)
                </label>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-3 border-t border-outline-variant">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold rounded-xl text-earth-dark hover:bg-surface-variant"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 text-xs font-bold rounded-xl bg-primary hover:bg-primary-hover text-white shadow-sm"
                >
                  {isSubmitting ? 'Đang tạo...' : 'Tạo Thiết Bị'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
