import React, { useState, useEffect, useRef } from 'react';
import { MqttLogMessage } from '../types';
import { 
  Terminal, 
  Trash2, 
  Copy, 
  Radio, 
  Search, 
  ChevronUp, 
  ChevronDown,
  Check,
  ArrowUpRight,
  ArrowDownLeft,
  PanelRight,
  PanelBottom,
  X
} from 'lucide-react';

export interface MqttConsoleProps {
  logs: MqttLogMessage[];
  onClearLogs: () => void;
  onTriggerScan: () => Promise<void>;
  brokerInfo?: { broker: string; topic_prefix: string; mqtt_connected: boolean };
  position?: 'bottom' | 'side';
  onTogglePosition?: () => void;
  onClose?: () => void;
}

export const MqttConsole: React.FC<MqttConsoleProps> = ({
  logs,
  onClearLogs,
  onTriggerScan,
  brokerInfo,
  position = 'bottom',
  onTogglePosition,
  onClose,
}) => {
  const [filterType, setFilterType] = useState<string>('all');
  const [search, setSearch] = useState<string>('');
  const [isCopied, setIsCopied] = useState<boolean>(false);
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [isScanning, setIsScanning] = useState<boolean>(false);
  const logEndRef = useRef<HTMLDivElement | null>(null);

  const filteredLogs = logs.filter((log) => {
    const matchType = filterType === 'all' || log.type === filterType;
    const matchSearch =
      search === '' ||
      log.topic.toLowerCase().includes(search.toLowerCase()) ||
      JSON.stringify(log.payload).toLowerCase().includes(search.toLowerCase());
    return matchType && matchSearch;
  });

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handleCopyLogs = () => {
    const text = logs
      .map(
        (l) =>
          `[${l.timestamp}] [${l.direction.toUpperCase()}] ${l.topic}\n${JSON.stringify(l.payload, null, 2)}`
      )
      .join('\n\n');
    navigator.clipboard.writeText(text);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const handleScan = async () => {
    setIsScanning(true);
    try {
      await onTriggerScan();
    } finally {
      setIsScanning(false);
    }
  };

  const isSide = position === 'side';

  return (
    <div
      className={`flex flex-col bg-earth-dark text-earth-light transition-all duration-200 ${
        isSide
          ? 'h-full w-full border-l border-outline-variant'
          : `border-t border-outline-variant ${isExpanded ? 'h-96' : 'h-48'}`
      }`}
    >
      {/* Console Top Bar */}
      <div className="flex items-center justify-between px-3 md:px-4 py-2 bg-[#1f2623] border-b border-[#2e3833] text-xs gap-2 flex-wrap sm:flex-nowrap">
        <div className="flex items-center space-x-2 sm:space-x-3 truncate">
          <div className="flex items-center space-x-1.5 font-mono font-bold text-white flex-shrink-0">
            <Terminal size={14} className="text-primary-light" />
            <span className="truncate">MQTT Sandbox Console</span>
          </div>

          <div className="hidden sm:flex items-center space-x-2 text-[11px] text-gray-400 truncate">
            <span className="flex items-center space-x-1 flex-shrink-0">
              <span
                className={`w-2 h-2 rounded-full ${
                  brokerInfo?.mqtt_connected ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
                }`}
              />
              <span className="truncate">{brokerInfo?.broker || 'mqtt:1883'}</span>
            </span>
            <span>·</span>
            <span className="font-mono text-gray-300 truncate">Prefix: {brokerInfo?.topic_prefix || 'homing'}</span>
          </div>
        </div>

        {/* Console Controls */}
        <div className="flex items-center space-x-1 sm:space-x-1.5 flex-shrink-0 ml-auto">
          <button
            onClick={handleScan}
            disabled={isScanning}
            className="flex items-center space-x-1 px-2.5 py-1 bg-primary hover:bg-primary-hover text-white text-[11px] font-bold rounded-lg transition-all flex-shrink-0"
            title="Gửi bản tin quét Discovery Scan tới toàn bộ thiết bị"
          >
            <Radio size={12} className={isScanning ? 'animate-spin' : ''} />
            <span className={isSide ? 'hidden lg:inline' : 'hidden sm:inline'}>
              {isScanning ? 'Đang quét...' : 'Quét Thiết Bị (Scan)'}
            </span>
            <span className={isSide ? 'inline lg:hidden' : 'inline sm:hidden'}>Scan</span>
          </button>

          <div className="h-4 w-px bg-[#39453f] mx-0.5 sm:mx-1 hidden sm:block" />

          {/* Filter Types */}
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="bg-[#2a342f] text-gray-200 border border-[#3f4d46] text-[11px] rounded-lg px-1.5 py-1 focus:outline-none max-w-[90px] sm:max-w-none"
          >
            <option value="all">Tất cả sự kiện</option>
            <option value="state">Trạng thái (state)</option>
            <option value="command">Lệnh (command)</option>
            <option value="discovery">Discovery</option>
            <option value="fault">Fault</option>
            <option value="ack">ACK</option>
          </select>

          {/* Search Box */}
          <div className="relative">
            <Search size={11} className="absolute left-2 top-2 text-gray-400" />
            <input
              type="text"
              placeholder="Lọc topic..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className={`pl-6 pr-2 py-0.5 text-[11px] bg-[#2a342f] border border-[#3f4d46] rounded-lg text-white placeholder-gray-400 focus:outline-none ${
                isSide ? 'w-20 sm:w-24' : 'w-20 sm:w-28'
              }`}
            />
          </div>

          <button
            onClick={handleCopyLogs}
            className="p-1 text-gray-300 hover:text-white hover:bg-[#2a342f] rounded-lg transition-colors"
            title="Sao chép toàn bộ log"
          >
            {isCopied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
          </button>

          <button
            onClick={onClearLogs}
            className="p-1 text-gray-300 hover:text-rose-400 hover:bg-[#2a342f] rounded-lg transition-colors"
            title="Xóa màn hình log"
          >
            <Trash2 size={14} />
          </button>

          {/* Expand/Collapse (only when bottom docked) */}
          {!isSide && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-1 text-gray-300 hover:text-white hover:bg-[#2a342f] rounded-lg transition-colors"
              title={isExpanded ? 'Thu gọn độ cao' : 'Mở rộng độ cao'}
            >
              {isExpanded ? <ChevronDown size={15} /> : <ChevronUp size={15} />}
            </button>
          )}

          {/* Dock Position Switcher */}
          {onTogglePosition && (
            <button
              onClick={onTogglePosition}
              className="p-1 text-gray-300 hover:text-white hover:bg-[#2a342f] rounded-lg transition-colors hidden md:block"
              title={isSide ? 'Chuyển xuống dưới đáy (Dock to Bottom)' : 'Chuyển sang panel bên phải (Dock to Side)'}
            >
              {isSide ? <PanelBottom size={14} /> : <PanelRight size={14} />}
            </button>
          )}

          {/* Close/Minimize Button */}
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 text-gray-300 hover:text-rose-400 hover:bg-[#2a342f] rounded-lg transition-colors"
              title="Ẩn MQTT Console"
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Log Output Area */}
      <div className="flex-1 overflow-y-auto p-3 font-mono text-[11px] space-y-1.5 selection:bg-primary">
        {filteredLogs.length === 0 ? (
          <div className="text-gray-400 italic py-4 text-center">
            Chưa có thông điệp MQTT nào. Nhấn "Quét Thiết Bị" hoặc tương tác với thiết bị trên bản vẽ.
          </div>
        ) : (
          filteredLogs.map((log) => (
            <div
              key={log.id}
              className="flex items-start space-x-2 p-1.5 rounded hover:bg-[#252f2a] transition-colors border-l-2"
              style={{
                borderLeftColor:
                  log.type === 'command'
                    ? '#38bdf8'
                    : log.type === 'state'
                    ? '#4ade80'
                    : log.type === 'fault'
                    ? '#f87171'
                    : log.type === 'discovery'
                    ? '#fbbf24'
                    : '#a78bfa',
              }}
            >
              <span className="text-gray-400 whitespace-nowrap">{log.timestamp}</span>

              <span
                className={`px-1 rounded text-[10px] font-bold uppercase flex items-center space-x-0.5 ${
                  log.direction === 'in'
                    ? 'bg-sky-950 text-sky-400 border border-sky-800'
                    : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                }`}
              >
                {log.direction === 'in' ? <ArrowDownLeft size={10} /> : <ArrowUpRight size={10} />}
                <span>{log.direction}</span>
              </span>

              <span className="font-bold text-gray-200">{log.topic}</span>

              <span className="text-gray-400 flex-1 break-all">
                {typeof log.payload === 'object'
                  ? JSON.stringify(log.payload)
                  : String(log.payload)}
              </span>
            </div>
          ))
        )}
        <div ref={logEndRef} />
      </div>
    </div>
  );
};
