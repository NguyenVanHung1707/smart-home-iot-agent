import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { api } from './services/api';
import { Device, FaultMode, MqttLogMessage, SimulatorState, Wall } from './types';
import { Canvas2DEditor } from './components/Canvas2DEditor';
import { Viewer3D } from './components/Viewer3D';
import { DeviceLibrary } from './components/DeviceLibrary';
import { DeviceInspector } from './components/DeviceInspector';
import { MqttConsole } from './components/MqttConsole';
import { 
  Home, 
  Box, 
  Map, 
  RotateCcw, 
  Radio, 
  ChevronRight,
  Terminal,
} from 'lucide-react';

export const App: React.FC = () => {
  // Simulator State
  const [state, setState] = useState<SimulatorState>({
    walls: [],
    devices: [],
    faults: {},
  });
  const [healthInfo, setHealthInfo] = useState<{
    status: string;
    mqtt_connected: boolean;
    broker: string;
    topic_prefix: string;
  } | null>(null);

  // UI State
  const [activeTab, setActiveTab] = useState<'2d' | '3d'>('2d');
  const [mobileTab, setMobileTab] = useState<'canvas' | 'rooms' | 'library' | 'logs'>('canvas');
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [selectedRoom, setSelectedRoom] = useState<string>('all');
  const [isResetting, setIsResetting] = useState<boolean>(false);
  const [logs, setLogs] = useState<MqttLogMessage[]>([]);
  const [consolePosition, setConsolePosition] = useState<'bottom' | 'side'>('bottom');
  const [isConsoleOpen, setIsConsoleOpen] = useState<boolean>(false);

  // Append a message to MQTT console
  const addLog = useCallback(
    (
      topic: string,
      payload: any,
      direction: 'in' | 'out' = 'out',
      type: MqttLogMessage['type'] = 'state'
    ) => {
      const newMsg: MqttLogMessage = {
        id: Math.random().toString(36).substring(2, 9),
        timestamp: new Date().toLocaleTimeString(),
        topic,
        payload,
        direction,
        type,
      };
      setLogs((prev) => [...prev.slice(-150), newMsg]);
    },
    []
  );

  // Fetch Simulator State from Backend
  const fetchState = useCallback(async () => {
    try {
      const data = await api.getState();
      setState(data);
    } catch (err) {
      console.error('Failed to fetch simulator state:', err);
    }
  }, []);

  // Fetch Health
  const fetchHealth = useCallback(async () => {
    try {
      const h = await api.getHealth();
      setHealthInfo(h);
    } catch (err) {
      console.warn('Backend health unreachable');
    }
  }, []);

  // Polling loop for state & health
  useEffect(() => {
    fetchState();
    fetchHealth();
    const interval = setInterval(() => {
      fetchState();
      fetchHealth();
    }, 2500);
    return () => clearInterval(interval);
  }, [fetchState, fetchHealth]);

  // Selected device object
  const selectedDevice = useMemo(() => {
    if (!selectedDeviceId) return null;
    return state.devices.find((d) => d.id === selectedDeviceId) || null;
  }, [state.devices, selectedDeviceId]);

  // Rooms list derived from devices
  const rooms = useMemo(() => {
    const set = new Set<string>();
    state.devices.forEach((d) => {
      if (d.room) set.add(d.room);
    });
    return Array.from(set);
  }, [state.devices]);

  // Filtered devices by selected room
  const filteredDevicesByRoom = useMemo(() => {
    if (selectedRoom === 'all') return state.devices;
    return state.devices.filter((d) => d.room === selectedRoom);
  }, [state.devices, selectedRoom]);

  // Handlers
  const handleSelectDevice = (device: Device | null) => {
    setSelectedDeviceId(device ? device.id : null);
  };

  const handleUpdateDevicePosition = async (deviceId: string, x: number, y: number, room?: string) => {
    // Optimistic update
    setState((prev) => ({
      ...prev,
      devices: prev.devices.map((d) => (d.id === deviceId ? { ...d, x, y, ...(room ? { room } : {}) } : d)),
    }));
    try {
      await api.updateDevice(deviceId, { x, y, ...(room ? { room } : {}) });
    } catch (err) {
      console.error('Failed to update position:', err);
    }
  };

  const handleSaveWalls = async (newWalls: Wall[]) => {
    setState((prev) => ({ ...prev, walls: newWalls }));
    try {
      const saved = await api.saveWalls(newWalls);
      setState((prev) => ({ ...prev, walls: saved }));
    } catch (err) {
      console.error('Failed to save walls:', err);
    }
  };

  const handleDropNewDevice = async (
    kind: string,
    name: string,
    room: string,
    x: number,
    y: number
  ) => {
    const id = `${kind}-${Math.random().toString(36).substring(2, 6)}`;
    let defaultState: Record<string, any> = {};
    if (kind === 'light') defaultState = { power: true, brightness: 80 };
    else if (kind === 'aircon') defaultState = { power: true, target_temperature: 25, mode: 'cool' };
    else if (kind === 'blind') defaultState = { position: 0 };
    else if (kind === 'lock') defaultState = { locked: true };
    else if (kind === 'speaker') defaultState = { power: false, volume: 50, playing: false };
    else defaultState = { temperature: 26.5, humidity: 60.0, battery: 100 };

    const newDev: Partial<Device> = {
      id,
      name,
      kind,
      room,
      x,
      y,
      state: defaultState,
      auto_simulate: kind === 'sensor',
    };

    try {
      const added = await api.addDevice(newDev);
      setState((prev) => ({ ...prev, devices: [...prev.devices, added] }));
      setSelectedDeviceId(added.id);
      addLog(`homing/discovery`, added, 'out', 'discovery');
    } catch (err) {
      alert(`Không thể tạo thiết bị: ${err}`);
    }
  };

  const handleAddNewDevice = async (dev: Partial<Device>) => {
    const added = await api.addDevice(dev);
    setState((prev) => ({ ...prev, devices: [...prev.devices, added] }));
    setSelectedDeviceId(added.id);
    addLog(`homing/discovery`, added, 'out', 'discovery');
  };

  const handlePerformAction = async (deviceId: string, action: string, value?: any) => {
    addLog(`homing/devices/${deviceId}/command`, { action, value }, 'in', 'command');
    try {
      const updated = await api.performAction(deviceId, action, value);
      setState((prev) => ({
        ...prev,
        devices: prev.devices.map((d) => (d.id === deviceId ? updated : d)),
      }));
      addLog(`homing/devices/${deviceId}/ack`, { status: 'ok', state: updated.state }, 'out', 'ack');
      addLog(`homing/devices/${deviceId}/state`, { state: updated.state }, 'out', 'state');
    } catch (err) {
      addLog(`homing/devices/${deviceId}/ack`, { status: 'error', error: String(err) }, 'out', 'ack');
    }
  };

  const handleSetFault = async (deviceId: string, mode: FaultMode) => {
    addLog(`homing/simulator/${deviceId}/fault`, { mode }, 'in', 'fault');
    try {
      const res = await api.setDeviceFault(deviceId, mode);
      setState((prev) => ({
        ...prev,
        faults: { ...prev.faults, [deviceId]: res.fault },
      }));
      addLog(`homing/devices/${deviceId}/state`, { fault: res.fault, online: res.fault !== 'offline' }, 'out', 'state');
    } catch (err) {
      console.error('Failed to set fault:', err);
    }
  };

  const handleUpdateDevice = async (deviceId: string, updates: Partial<Device>) => {
    const updated = await api.updateDevice(deviceId, updates);
    setState((prev) => ({
      ...prev,
      devices: prev.devices.map((d) => (d.id === deviceId ? updated : d)),
    }));
  };

  const handleDeleteDevice = async (deviceId: string) => {
    await api.deleteDevice(deviceId);
    setState((prev) => ({
      ...prev,
      devices: prev.devices.filter((d) => d.id !== deviceId),
    }));
    if (selectedDeviceId === deviceId) setSelectedDeviceId(null);
  };

  const handleTriggerScan = async () => {
    addLog('homing/broadcast/scan', { action: 'scan' }, 'in', 'command');
    const res = await api.triggerScan();
    addLog('homing/discovery/scan_response', res, 'out', 'discovery');
    fetchState();
  };

  const handleReset = async () => {
    if (!confirm('Đặt lại toàn bộ trạng thái căn hộ về mặc định ban đầu?')) return;
    setIsResetting(true);
    try {
      const reset = await api.resetState();
      setState(reset);
      setSelectedDeviceId(null);
      addLog('homing/simulator/reset', { status: 'reset_completed' }, 'out', 'info');
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-background overflow-hidden font-body">
      {/* Top Application Header */}
      <header className="min-h-14 bg-surface border-b border-outline-variant px-2.5 md:px-5 py-1.5 flex flex-wrap items-center justify-between gap-2 z-30 shadow-soft flex-shrink-0">
        <div className="flex items-center space-x-2 md:space-x-3 truncate">
          <div className="w-8 h-8 rounded-xl bg-primary text-white flex items-center justify-center shadow-sm flex-shrink-0">
            <Home size={18} />
          </div>
          <div className="truncate">
            <h1 className="font-headline font-bold text-sm md:text-base text-earth-dark flex items-center space-x-1.5 md:space-x-2 leading-none truncate">
              <span className="truncate">SmartHome Rebuild</span>
              <span className="hidden sm:inline-block text-[10px] font-sans font-semibold bg-primary-light text-primary px-2 py-0.5 rounded-full border border-primary/20 flex-shrink-0">
                Sandbox 2D & 3D
              </span>
            </h1>
            <p className="text-[10px] md:text-[11px] text-earth-muted mt-0.5 truncate hidden sm:block">
              Hệ thống mô phỏng IoT & Thiết bị thông minh Homing
            </p>
          </div>
        </div>

        {/* View Tab Switcher */}
        <div className="flex items-center bg-surface-container p-1 rounded-xl border border-outline-variant shadow-inner">
          <button
            onClick={() => setActiveTab('2d')}
            className={`flex items-center space-x-1.5 px-2.5 md:px-4 py-1.5 min-h-[36px] md:min-h-[38px] rounded-lg text-xs font-bold transition-all ${
              activeTab === '2d'
                ? 'bg-primary text-white shadow-sm'
                : 'text-earth-dark hover:bg-surface-variant'
            }`}
          >
            <Map size={14} />
            <span>Mặt bằng 2D</span>
          </button>

          <button
            onClick={() => setActiveTab('3d')}
            className={`flex items-center space-x-1.5 px-2.5 md:px-4 py-1.5 min-h-[36px] md:min-h-[38px] rounded-lg text-xs font-bold transition-all ${
              activeTab === '3d'
                ? 'bg-primary text-white shadow-sm'
                : 'text-earth-dark hover:bg-surface-variant'
            }`}
          >
            <Box size={14} />
            <span>Không gian 3D</span>
          </button>
        </div>

        {/* Status & Quick Actions */}
        <div className="flex items-center space-x-1.5 md:space-x-2.5 flex-shrink-0">
          {/* MQTT Status Badge */}
          <div className="hidden sm:flex items-center space-x-1.5 px-2.5 md:px-3 py-1.5 bg-surface-container rounded-xl border border-outline-variant text-xs">
            <span
              className={`w-2 h-2 rounded-full ${
                healthInfo?.mqtt_connected ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'
              }`}
            />
            <span className="font-bold text-earth-dark">
              {healthInfo?.mqtt_connected ? 'MQTT Connected' : 'MQTT Standby'}
            </span>
          </div>

          {/* MQTT Console Header Button */}
          <button
            onClick={() => setIsConsoleOpen((open) => !open)}
            className={`hidden sm:flex items-center space-x-1.5 px-2.5 md:px-3 py-1.5 min-h-[36px] rounded-xl border text-xs font-bold transition-all ${
              isConsoleOpen
                ? 'bg-surface-container border-outline-variant text-earth-dark hover:bg-surface-variant'
                : 'bg-primary-light border-primary/40 text-primary shadow-sm'
            }`}
            title={isConsoleOpen ? 'Thu gọn / Ẩn MQTT Console' : 'Mở MQTT Console'}
          >
            <Terminal size={14} className={isConsoleOpen ? 'text-primary' : 'text-primary animate-pulse'} />
            <span className="hidden lg:inline">MQTT Console</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface-variant text-earth-muted font-mono">
              {logs.length}
            </span>
          </button>

          <button
            onClick={handleTriggerScan}
            className="flex items-center space-x-1 px-2.5 md:px-3 py-1.5 min-h-[36px] bg-surface-container hover:bg-surface-variant text-earth-dark text-xs font-bold rounded-xl border border-outline-variant transition-all"
            title="Quét danh sách thiết bị phát hiện"
          >
            <Radio size={14} className="text-primary" />
            <span className="hidden md:inline">Discovery Scan</span>
          </button>

          <button
            onClick={handleReset}
            disabled={isResetting}
            className="flex items-center space-x-1 px-2.5 md:px-3 py-1.5 min-h-[36px] bg-surface-container hover:bg-rose-50 text-earth-dark hover:text-rose-700 text-xs font-bold rounded-xl border border-outline-variant transition-all"
            title="Khôi phục trạng thái mặc định của ngôi nhà"
          >
            <RotateCcw size={14} className={isResetting ? 'animate-spin' : ''} />
            <span className="hidden md:inline">Reset Demo</span>
          </button>
        </div>
      </header>

      {/* Main Workspace Body */}
      <div className="flex-1 flex overflow-hidden relative min-h-0 min-w-0">
        {/* Left Navigation: Room Selector & Device Explorer */}
        <aside
          className={`${
            mobileTab === 'rooms' ? 'flex absolute inset-0 z-20' : 'hidden'
          } md:flex md:relative md:inset-auto w-full md:w-64 bg-surface border-r border-outline-variant flex-col flex-shrink-0 select-none`}
        >
          <div className="p-3.5 border-b border-outline-variant bg-surface-container/40">
            <div className="text-xs font-bold font-headline text-earth-dark mb-2">
              Khu Vực & Phòng Ở
            </div>

            <div className="space-y-1">
              <button
                onClick={() => setSelectedRoom('all')}
                className={`w-full flex items-center justify-between px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                  selectedRoom === 'all'
                    ? 'bg-primary text-white shadow-sm'
                    : 'text-earth-dark hover:bg-surface-variant'
                }`}
              >
                <span>Toàn Bộ Ngôi Nhà</span>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                    selectedRoom === 'all' ? 'bg-white/20' : 'bg-surface-variant'
                  }`}
                >
                  {state.devices.length}
                </span>
              </button>

              {rooms.map((room) => {
                const count = state.devices.filter((d) => d.room === room).length;
                return (
                  <button
                    key={room}
                    onClick={() => setSelectedRoom(room)}
                    className={`w-full flex items-center justify-between px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                      selectedRoom === room
                        ? 'bg-primary text-white shadow-sm'
                        : 'text-earth-dark hover:bg-surface-variant'
                    }`}
                  >
                    <span>{room}</span>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                        selectedRoom === room ? 'bg-white/20' : 'bg-surface-variant'
                      }`}
                    >
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Device Quick List in selected room */}
          <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
            <div className="text-[11px] font-bold text-earth-muted uppercase tracking-wider px-1">
              Thiết bị ({filteredDevicesByRoom.length})
            </div>

            {filteredDevicesByRoom.map((dev) => {
              const isSelected = selectedDeviceId === dev.id;
              const fault = state.faults[dev.id] || 'none';
              const isFaulty = fault !== 'none';
              const isPowerOn =
                dev.state?.power === true ||
                dev.state?.locked === true ||
                (dev.kind === 'sensor' && fault === 'none');

              return (
                <button
                  key={dev.id}
                  onClick={() => {
                    setSelectedDeviceId(dev.id);
                    if (window.innerWidth < 768) {
                      setMobileTab('library');
                    }
                  }}
                  className={`w-full flex items-center justify-between p-2 rounded-xl text-left border transition-all ${
                    isSelected
                      ? 'bg-primary-light border-primary text-earth-dark shadow-sm'
                      : 'bg-surface hover:bg-surface-container border-outline-variant text-earth-dark'
                  }`}
                >
                  <div className="flex items-center space-x-2 truncate mr-1">
                    <span
                      className={`w-2 h-2 rounded-full flex-shrink-0 ${
                        isFaulty
                          ? 'bg-rose-500'
                          : isPowerOn
                          ? 'bg-primary'
                          : 'bg-outline'
                      }`}
                    />
                    <div className="truncate">
                      <div className="text-xs font-bold truncate">{dev.name}</div>
                      <div className="text-[10px] text-earth-muted">{dev.room}</div>
                    </div>
                  </div>

                  <ChevronRight
                    size={14}
                    className={`flex-shrink-0 ${
                      isSelected ? 'text-primary' : 'text-earth-muted'
                    }`}
                  />
                </button>
              );
            })}
          </div>
        </aside>

        {/* Center Canvas Area: 2D or 3D */}
        <main
          className={`${
            mobileTab === 'canvas' ? 'flex' : 'hidden md:flex'
          } flex-1 p-2 md:p-3.5 flex-col overflow-hidden bg-background min-h-0 min-w-0`}
        >
          {activeTab === '2d' ? (
            <Canvas2DEditor
              walls={state.walls}
              devices={state.devices}
              faults={state.faults}
              selectedDeviceId={selectedDeviceId}
              onSelectDevice={(d) => {
                handleSelectDevice(d);
                if (d && window.innerWidth < 768) {
                  setMobileTab('library');
                }
              }}
              onUpdateDevicePosition={handleUpdateDevicePosition}
              onSaveWalls={handleSaveWalls}
              onDropNewDevice={handleDropNewDevice}
            />
          ) : (
            <Viewer3D
              walls={state.walls}
              devices={state.devices}
              faults={state.faults}
              selectedDeviceId={selectedDeviceId}
              onSelectDevice={(d) => {
                handleSelectDevice(d);
                if (d && window.innerWidth < 768) {
                  setMobileTab('library');
                }
              }}
            />
          )}
        </main>

        {/* Right Sidebar: Device Inspector or Device Library */}
        <aside
          className={`${
            mobileTab === 'library' || (selectedDevice && mobileTab !== 'rooms' && mobileTab !== 'logs')
              ? 'flex absolute inset-0 z-20'
              : 'hidden'
          } md:flex md:relative md:inset-auto w-full md:w-80 bg-surface flex-col flex-shrink-0 border-l border-outline-variant`}
        >
          {selectedDevice ? (
            <DeviceInspector
              device={selectedDevice}
              fault={state.faults[selectedDevice.id] || 'none'}
              onClose={() => {
                setSelectedDeviceId(null);
                if (window.innerWidth < 768) {
                  setMobileTab('canvas');
                }
              }}
              onPerformAction={handlePerformAction}
              onSetFault={handleSetFault}
              onUpdateDevice={handleUpdateDevice}
              onDeleteDevice={handleDeleteDevice}
            />
          ) : (
            <DeviceLibrary
              devices={state.devices}
              faults={state.faults}
              onAddNewDevice={handleAddNewDevice}
            />
          )}
        </aside>

        {/* Right Docked Side Panel: MQTT Console (Desktop Side Docking Mode) */}
        {isConsoleOpen && consolePosition === 'side' && (
          <aside className="hidden md:flex w-80 lg:w-96 flex-col flex-shrink-0 border-l border-outline-variant bg-earth-dark">
            <MqttConsole
              logs={logs}
              onClearLogs={() => setLogs([])}
              onTriggerScan={handleTriggerScan}
              brokerInfo={healthInfo || undefined}
              position="side"
              onTogglePosition={() => setConsolePosition('bottom')}
              onClose={() => setIsConsoleOpen(false)}
            />
          </aside>
        )}

        {/* Mobile Log View Overlay */}
        {mobileTab === 'logs' && (
          <div className="md:hidden absolute inset-0 z-20 bg-earth-dark flex flex-col">
            <MqttConsole
              logs={logs}
              onClearLogs={() => setLogs([])}
              onTriggerScan={handleTriggerScan}
              brokerInfo={healthInfo || undefined}
            />
          </div>
        )}
      </div>

      {/* Mobile Bottom Navigation Bar */}
      <nav className="md:hidden h-12 bg-surface border-t border-outline-variant flex items-center justify-around z-30 shadow-soft flex-shrink-0">
        <button
          onClick={() => setMobileTab('canvas')}
          className={`flex flex-col items-center justify-center flex-1 py-1 text-[11px] font-bold ${
            mobileTab === 'canvas' ? 'text-primary' : 'text-earth-muted'
          }`}
        >
          <Map size={16} />
          <span>Mặt Bằng</span>
        </button>
        <button
          onClick={() => setMobileTab('rooms')}
          className={`flex flex-col items-center justify-center flex-1 py-1 text-[11px] font-bold ${
            mobileTab === 'rooms' ? 'text-primary' : 'text-earth-muted'
          }`}
        >
          <Home size={16} />
          <span>Phòng Ở</span>
        </button>
        <button
          onClick={() => setMobileTab('library')}
          className={`flex flex-col items-center justify-center flex-1 py-1 text-[11px] font-bold ${
            mobileTab === 'library' ? 'text-primary' : 'text-earth-muted'
          }`}
        >
          <Box size={16} />
          <span>{selectedDevice ? 'Chi Tiết' : 'Thư Viện'}</span>
        </button>
        <button
          onClick={() => setMobileTab('logs')}
          className={`flex flex-col items-center justify-center flex-1 py-1 text-[11px] font-bold ${
            mobileTab === 'logs' ? 'text-primary' : 'text-earth-muted'
          }`}
        >
          <Radio size={16} />
          <span>MQTT Log</span>
        </button>
      </nav>

      {/* Desktop Bottom Panel: MQTT Console Sandbox */}
      {isConsoleOpen && consolePosition === 'bottom' && (
        <footer className="hidden md:block flex-shrink-0">
          <MqttConsole
            logs={logs}
            onClearLogs={() => setLogs([])}
            onTriggerScan={handleTriggerScan}
            brokerInfo={healthInfo || undefined}
            position="bottom"
            onTogglePosition={() => setConsolePosition('side')}
            onClose={() => setIsConsoleOpen(false)}
          />
        </footer>
      )}

      {/* Floating Reopen Pill when Console is closed on desktop */}
      {!isConsoleOpen && (
        <button
          onClick={() => setIsConsoleOpen(true)}
          className="hidden md:flex fixed bottom-3 right-4 z-40 items-center space-x-2 px-3 py-1.5 bg-earth-dark text-white rounded-xl shadow-lg border border-[#3f4d46] hover:bg-[#2a342f] text-xs font-bold transition-all animate-bounce"
          title="Mở lại MQTT Console"
        >
          <span
            className={`w-2 h-2 rounded-full ${
              healthInfo?.mqtt_connected ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
            }`}
          />
          <Terminal size={13} className="text-primary-light" />
          <span>MQTT Console ({logs.length})</span>
        </button>
      )}
    </div>
  );
};
