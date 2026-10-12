import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { Icon } from "../shared/Icon";
import { SectionHeading } from "../shared/SectionHeading";
import { floorplanApi } from "./api";
import { Device, FaultMode, SimulatorState, Wall } from "./types";
import { Viewer3D } from "./Viewer3D";
import { Canvas2DEditor } from "./Canvas2DEditor";
import { DeviceInspector } from "./DeviceInspector";
import { ErrorBoundary } from "./ErrorBoundary";
import { detectEnclosedRooms } from "./roomDetection";
import { 
  Box, 
  Map, 
  RotateCcw, 
  RefreshCw, 
  Maximize2, 
  Minimize2, 
  Cpu, 
  Home, 
  SlidersHorizontal,
  Layers,
  Sparkles
} from "lucide-react";

interface FloorplanPageProps {
  view?: "2d" | "3d";
}

export const FloorplanPage: React.FC<FloorplanPageProps> = ({ view = "3d" }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [currentView, setCurrentView] = useState<"2d" | "3d">(view);
  const [state, setState] = useState<SimulatorState>({
    walls: [],
    devices: [],
    faults: {},
  });
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  // Sync prop changes to view state
  useEffect(() => {
    setCurrentView(view);
  }, [view]);

  // Load simulator state from backend
  const fetchState = useCallback(async (silent = false) => {
    if (!silent) setIsRefreshing(true);
    try {
      const data = await floorplanApi.getState();
      setState(data);
    } catch (err) {
      console.warn("Lỗi tải dữ liệu mặt bằng:", err);
    } finally {
      setLoading(false);
      if (!silent) setIsRefreshing(false);
    }
  }, []);

  // Initial load and polling every 2.5s for real-time telemetry from physical ESP32
  useEffect(() => {
    fetchState(false);
    const interval = setInterval(() => {
      fetchState(true);
    }, 2500);
    return () => clearInterval(interval);
  }, [fetchState]);

  // Handle Fullscreen
  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => {});
    } else {
      document.exitFullscreen().then(() => setIsFullscreen(false)).catch(() => {});
    }
  };

  useEffect(() => {
    const handleFsChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", handleFsChange);
    return () => document.removeEventListener("fullscreenchange", handleFsChange);
  }, []);

  // Selected device object
  const selectedDevice = useMemo(() => {
    if (!selectedDeviceId) return null;
    return state.devices.find((d) => d.id === selectedDeviceId) || null;
  }, [selectedDeviceId, state.devices]);

  // Detected rooms count
  const detectedRooms = useMemo(() => {
    return detectEnclosedRooms(state.walls, state.devices);
  }, [state.walls, state.devices]);

  // Actions
  const handlePerformAction = async (deviceId: string, action: string, value?: any) => {
    // Optimistic local update
    setState((prev) => {
      const nextDevices = prev.devices.map((d) => {
        if (d.id !== deviceId) return d;
        const curState = { ...d.state };
        if (action === "toggle") {
          if (d.kind === "lock") curState.locked = !curState.locked;
          else curState.power = !curState.power;
        } else if (action === "set_speed") {
          curState.speed = Number(value);
          curState.power = Number(value) > 0;
        } else if (action === "set" && typeof value === "object") {
          Object.assign(curState, value);
        } else if (action === "lock") curState.locked = true;
        else if (action === "unlock") curState.locked = false;
        else if (action === "turn_on" || action === "on") curState.power = true;
        else if (action === "turn_off" || action === "off") curState.power = false;
        return { ...d, state: curState };
      });
      return { ...prev, devices: nextDevices };
    });

    try {
      await floorplanApi.performAction(deviceId, action, value);
    } catch (err) {
      console.error("Lỗi gửi lệnh điều khiển:", err);
      fetchState(true);
    }
  };

  const handleSetFault = async (deviceId: string, mode: FaultMode) => {
    setState((prev) => ({
      ...prev,
      faults: { ...prev.faults, [deviceId]: mode },
    }));
    await floorplanApi.setFault(deviceId, mode);
  };

  const handleUpdateDevice = async (deviceId: string, updates: Partial<Device>) => {
    setState((prev) => ({
      ...prev,
      devices: prev.devices.map((d) => (d.id === deviceId ? { ...d, ...updates } : d)),
    }));
    await floorplanApi.updateDevice(deviceId, updates);
  };

  const handleDeleteDevice = async (deviceId: string) => {
    setState((prev) => ({
      ...prev,
      devices: prev.devices.filter((d) => d.id !== deviceId),
    }));
    setSelectedDeviceId(null);
    await floorplanApi.deleteDevice(deviceId);
  };

  const handleUpdatePosition = async (deviceId: string, x: number, y: number, room?: string) => {
    setState((prev) => ({
      ...prev,
      devices: prev.devices.map((d) =>
        d.id === deviceId ? { ...d, x, y, ...(room ? { room } : {}) } : d
      ),
    }));
    await floorplanApi.updateDevice(deviceId, { x, y, ...(room ? { room } : {}) });
  };

  const handleSaveWalls = async (newWalls: Wall[]) => {
    setState((prev) => ({ ...prev, walls: newWalls }));
    await floorplanApi.saveWalls(newWalls);
  };

  const handleResetLayout = async () => {
    if (!window.confirm("Bạn có chắc muốn khôi phục mặt bằng và toạ độ thiết bị về mặc định sơ đồ 3 phòng?")) {
      return;
    }
    setLoading(true);
    try {
      const resetData = await floorplanApi.resetState();
      setState(resetData);
      setSelectedDeviceId(null);
      setStatusMessage("Đã khôi phục mặt bằng thành công!");
      setTimeout(() => setStatusMessage(null), 3000);
    } catch (err) {
      console.error("Lỗi khôi phục:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div 
      ref={containerRef}
      className={`hm-page hm-floorplan-page ${isFullscreen ? "hm-floorplan-fullscreen" : ""}`}
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "1rem",
        background: isFullscreen ? "var(--hm-bg, #1a201c)" : "transparent",
        padding: isFullscreen ? "1rem" : 0,
        height: isFullscreen ? "100vh" : "auto",
        position: "relative",
      }}
    >
      {/* Header Bar */}
      <header 
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <SectionHeading
          eyebrow="Không gian số"
          title={currentView === "3d" ? "Mô hình nhà 3D" : "Mặt bằng nhà 2D"}
        />

        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
          {/* View Mode Switcher */}
          <div 
            style={{
              display: "inline-flex",
              background: "var(--hm-card-bg, #222924)",
              borderRadius: "10px",
              padding: "3px",
              border: "1px solid rgba(255, 255, 255, 0.08)",
            }}
          >
            <button
              type="button"
              onClick={() => setCurrentView("2d")}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.4rem",
                padding: "0.4rem 0.85rem",
                borderRadius: "8px",
                border: "none",
                background: currentView === "2d" ? "var(--hm-primary, #4a7c59)" : "transparent",
                color: currentView === "2d" ? "#ffffff" : "var(--hm-muted, #94a39b)",
                fontSize: "0.85rem",
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              <Map size={15} />
              <span>Mặt bằng 2D</span>
            </button>
            <button
              type="button"
              onClick={() => setCurrentView("3d")}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.4rem",
                padding: "0.4rem 0.85rem",
                borderRadius: "8px",
                border: "none",
                background: currentView === "3d" ? "var(--hm-primary, #4a7c59)" : "transparent",
                color: currentView === "3d" ? "#ffffff" : "var(--hm-muted, #94a39b)",
                fontSize: "0.85rem",
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              <Box size={15} />
              <span>Mô hình 3D</span>
            </button>
          </div>

          {/* Action buttons */}
          <button
            type="button"
            className="hm-btn hm-btn-secondary"
            onClick={() => fetchState(false)}
            title="Làm mới trạng thái từ MQTT & ESP32"
            disabled={isRefreshing}
            style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem", padding: "0.45rem 0.75rem", fontSize: "0.85rem" }}
          >
            <RefreshCw size={15} className={isRefreshing ? "spin-animation" : ""} />
            <span>{isRefreshing ? "Đang đồng bộ..." : "Làm mới"}</span>
          </button>

          <button
            type="button"
            className="hm-btn hm-btn-secondary"
            onClick={handleResetLayout}
            title="Khôi phục mặt bằng chuẩn 3 phòng"
            style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem", padding: "0.45rem 0.75rem", fontSize: "0.85rem" }}
          >
            <RotateCcw size={15} />
            <span>Mặc định</span>
          </button>

          <button
            type="button"
            className="hm-btn hm-btn-secondary"
            onClick={toggleFullscreen}
            title={isFullscreen ? "Thoát toàn màn hình" : "Mở toàn màn hình"}
            style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem", padding: "0.45rem 0.75rem", fontSize: "0.85rem" }}
          >
            {isFullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
            <span>{isFullscreen ? "Thu nhỏ" : "Toàn màn hình"}</span>
          </button>
        </div>
      </header>

      {/* Status & Summary Badges */}
      <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap", alignItems: "center" }}>
        <div 
          className="hm-chip"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.35rem",
            padding: "0.3rem 0.7rem",
            background: "rgba(74, 124, 89, 0.15)",
            color: "var(--hm-primary, #4a7c59)",
            borderRadius: "999px",
            fontSize: "0.8rem",
            fontWeight: 600,
          }}
        >
          <Home size={13} />
          <span>{detectedRooms.length} Phòng nhận diện ({detectedRooms.map(r => r.name).join(", ") || "3 phòng"})</span>
        </div>

        <div 
          className="hm-chip"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "0.35rem",
            padding: "0.3rem 0.7rem",
            background: "rgba(59, 130, 246, 0.15)",
            color: "#3b82f6",
            borderRadius: "999px",
            fontSize: "0.8rem",
            fontWeight: 600,
          }}
        >
          <Cpu size={13} />
          <span>{state.devices.length} Thiết bị IoT</span>
        </div>

        {statusMessage && (
          <div 
            style={{
              padding: "0.3rem 0.75rem",
              background: "rgba(16, 185, 129, 0.2)",
              color: "#34d399",
              borderRadius: "6px",
              fontSize: "0.8rem",
              fontWeight: 600,
            }}
          >
            {statusMessage}
          </div>
        )}
      </div>

      {/* Main Viewport Container */}
      <div
        style={{
          position: "relative",
          width: "100%",
          height: isFullscreen ? "calc(100vh - 120px)" : "calc(100vh - 270px)",
          minHeight: "580px",
          background: "var(--hm-card-bg, #1a221d)",
          borderRadius: isFullscreen ? "12px" : "18px",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          boxShadow: "0 12px 36px rgba(0, 0, 0, 0.18)",
          overflow: "hidden",
        }}
      >
        {loading ? (
          <div style={{ display: "flex", height: "100%", alignItems: "center", justifyContent: "center", color: "var(--hm-muted, #94a39b)" }}>
            <div style={{ textAlign: "center" }}>
              <RefreshCw size={28} className="spin-animation" style={{ marginBottom: "0.5rem" }} />
              <div>Đang khởi tạo không gian số...</div>
            </div>
          </div>
        ) : (
          <ErrorBoundary
            fallbackTitle={currentView === "3d" ? "Đã xảy ra sự cố khi hiển thị Mô hình 3D" : "Đã xảy ra sự cố khi hiển thị Mặt bằng 2D"}
            onReset={() => handleResetLayout()}
          >
            {currentView === "3d" ? (
              <Viewer3D
                walls={state.walls}
                devices={state.devices}
                faults={state.faults}
                selectedDeviceId={selectedDeviceId}
                onSelectDevice={(dev) => setSelectedDeviceId(dev ? dev.id : null)}
              />
            ) : (
              <Canvas2DEditor
                walls={state.walls}
                devices={state.devices}
                faults={state.faults}
                selectedDeviceId={selectedDeviceId}
                onSelectDevice={(dev) => setSelectedDeviceId(dev ? dev.id : null)}
                onUpdateDevicePosition={handleUpdatePosition}
                onSaveWalls={handleSaveWalls}
              />
            )}
          </ErrorBoundary>
        )}

        {/* Floating Native Device Inspector Overlay */}
        {selectedDevice && (
          <div
            style={{
              position: "absolute",
              top: "16px",
              right: "16px",
              bottom: "16px",
              width: "360px",
              maxWidth: "calc(100vw - 32px)",
              zIndex: 50,
              boxShadow: "-8px 0 32px rgba(0, 0, 0, 0.35)",
              borderRadius: "16px",
              overflow: "hidden",
              background: "rgba(26, 34, 29, 0.94)",
              backdropFilter: "blur(12px)",
              border: "1px solid rgba(255, 255, 255, 0.12)",
              animation: "fadeIn 0.2s ease-out",
            }}
          >
            <DeviceInspector
              device={selectedDevice}
              onClose={() => setSelectedDeviceId(null)}
              onPerformAction={handlePerformAction}
              onUpdateDevice={handleUpdateDevice}
              onDeleteDevice={handleDeleteDevice}
            />
          </div>
        )}
      </div>
    </div>
  );
};
