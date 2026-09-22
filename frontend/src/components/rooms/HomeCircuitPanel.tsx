import { useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent } from "react";
import type { Approval, Device, Room } from "../../types";
import { Icon } from "../shared/Icon";
import { HomeCircuitLayer } from "./HomeCircuitLayer";
import { HomeDeviceCard } from "./HomeDeviceCard";
import { HomeRoomCard } from "./HomeRoomCard";
import type { CircuitKey } from "./homeCircuit";
import { deviceCircuit, roomCircuit } from "./homeCircuit";

const pageSize = 4;

type HomeCircuitPanelProps = {
  rooms: Room[];
  devices: Device[];
  approvals?: Approval[];
  onOpenRoom: (room: Room) => void;
  onVoice: () => void;
  listening: boolean;
  onAddRoom?: () => void;
  onAddDevice?: () => void;
  onNavigateApprovals?: () => void;
};

export function HomeCircuitPanel({
  rooms,
  devices,
  approvals,
  onOpenRoom,
  onVoice,
  listening,
  onAddRoom,
  onAddDevice,
  onNavigateApprovals,
}: HomeCircuitPanelProps) {
  const [activeCircuit, setActiveCircuit] = useState<CircuitKey | null>(null);
  const [activeAnchor, setActiveAnchor] = useState<{ key: CircuitKey; cx: number; cy: number } | null>(null);
  const [roomPage, setRoomPage] = useState(0);
  const [devicePage, setDevicePage] = useState(0);
  const pendingApprovalsCount = approvals?.filter((a) => a.status === "pending").length ?? 0;
  const panelRef = useRef<HTMLElement | null>(null);
  const circuitHoverRef = useRef<HTMLDivElement | null>(null);
  const circuitPointerRef = useRef({ x: 0, y: 0 });
  const circuitFrameRef = useRef<number | null>(null);

  const roomPageCount = Math.max(1, Math.ceil(rooms.length / pageSize));
  const devicePageCount = Math.max(1, Math.ceil(devices.length / pageSize));
  const visibleRooms = useMemo(() => rooms.slice(roomPage * pageSize, roomPage * pageSize + pageSize), [roomPage, rooms]);
  const visibleDevices = useMemo(
    () => devices.slice(devicePage * pageSize, devicePage * pageSize + pageSize),
    [devicePage, devices],
  );

  useEffect(() => {
    return () => {
      if (circuitFrameRef.current !== null) {
        cancelAnimationFrame(circuitFrameRef.current);
      }
    };
  }, []);

  function trackCircuitHover(event: MouseEvent<HTMLElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    circuitPointerRef.current = {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    };
    if (circuitFrameRef.current !== null) return;
    circuitFrameRef.current = requestAnimationFrame(() => {
      circuitFrameRef.current = null;
      const layer = circuitHoverRef.current;
      if (!layer) return;
      const { x, y } = circuitPointerRef.current;
      layer.style.setProperty("--circuit-hover-x", `${x}px`);
      layer.style.setProperty("--circuit-hover-y", `${y}px`);
      layer.style.setProperty("--circuit-hover-on", "1");
    });
  }

  function clearCircuitHover() {
    circuitHoverRef.current?.style.setProperty("--circuit-hover-on", "0");
    setActiveCircuit(null);
    setActiveAnchor(null);
  }

  function activateCircuit(circuit: CircuitKey | null, element?: HTMLElement) {
    setActiveCircuit(circuit);
    if (!circuit || !element || !panelRef.current) {
      setActiveAnchor(null);
      return;
    }

    const panelRect = panelRef.current.getBoundingClientRect();
    const cardRect = element.getBoundingClientRect();
    if (panelRect.width <= 0 || panelRect.height <= 0) {
      setActiveAnchor(null);
      return;
    }

    setActiveAnchor({
      key: circuit,
      cx: ((cardRect.left + cardRect.width / 2 - panelRect.left) / panelRect.width) * 1000,
      cy: ((cardRect.bottom - panelRect.top) / panelRect.height) * 700,
    });
  }

  return (
    <section
      ref={panelRef}
      className="main-panel"
      data-circuit={activeCircuit ?? "idle"}
      aria-label="Tổng quan nhà thông minh"
      onMouseMove={trackCircuitHover}
      onMouseLeave={clearCircuitHover}
    >
      <HomeCircuitLayer activeCircuit={activeCircuit} activeAnchor={activeAnchor} hoverRef={circuitHoverRef} />

      {pendingApprovalsCount > 0 && onNavigateApprovals && (
        <div className="hm-approval-dashboard-banner" role="alert">
          <div className="hm-approval-banner-content">
            <span className="hm-approval-banner-icon">
              <Icon name="alert" />
            </span>
            <div>
              <strong>Có {pendingApprovalsCount} yêu cầu mở khóa an ninh đang chờ duyệt</strong>
              <p>Thành viên trong nhà vừa gửi yêu cầu mở khóa thiết bị. Vui lòng xác nhận.</p>
            </div>
          </div>
          <button
            type="button"
            className="hm-approval-banner-btn"
            onClick={onNavigateApprovals}
          >
            <span>Phê duyệt ngay</span>
            <Icon name="arrowRight" />
          </button>
        </div>
      )}

      <div className="section-heading">
        <div>
          <span>Không gian & thiết bị</span>
          <div className="section-title-row">
            <h2>Các phòng trong nhà</h2>
            {onAddRoom && (
              <button className="hm-btn-add-room" type="button" onClick={onAddRoom}>
                <Icon name="plus" />
                Thêm phòng
              </button>
            )}
          </div>
        </div>
        <div className="section-actions">
          <small>{rooms.length} khu vực</small>
          {rooms.length > pageSize && (
            <div className="carousel-controls" aria-label="Chuyển nhóm phòng">
              <button type="button" aria-label="Nhóm phòng trước" disabled={roomPage === 0} onClick={() => setRoomPage((page) => Math.max(0, page - 1))}>
                <Icon name="arrowLeft" />
              </button>
              <span>{roomPage + 1}/{roomPageCount}</span>
              <button
                type="button"
                aria-label="Nhóm phòng tiếp theo"
                disabled={roomPage >= roomPageCount - 1}
                onClick={() => setRoomPage((page) => Math.min(roomPageCount - 1, page + 1))}
              >
                <Icon name="arrowRight" />
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="room-grid">
        {visibleRooms.map((room, index) => (
          <HomeRoomCard
            key={room.id}
            room={room}
            circuit={roomCircuit(room, roomPage * pageSize + index)}
            activeCircuit={activeCircuit}
            onOpen={() => onOpenRoom(room)}
            onActive={activateCircuit}
          />
        ))}
      </div>

      <div className="section-heading compact">
        <div>
          <div className="section-title-row">
            <h2>Thiết bị trong nhà</h2>
            {onAddDevice && (
              <button className="hm-btn-add-device" type="button" onClick={onAddDevice}>
                <Icon name="plus" />
                Thêm thiết bị
              </button>
            )}
          </div>
        </div>
        <div className="section-actions">
          <small>{devices.length} thiết bị</small>
          {devices.length > pageSize && (
            <div className="carousel-controls" aria-label="Chuyển nhóm thiết bị">
              <button type="button" aria-label="Nhóm thiết bị trước" disabled={devicePage === 0} onClick={() => setDevicePage((page) => Math.max(0, page - 1))}>
                <Icon name="arrowLeft" />
              </button>
              <span>{devicePage + 1}/{devicePageCount}</span>
              <button
                type="button"
                aria-label="Nhóm thiết bị tiếp theo"
                disabled={devicePage >= devicePageCount - 1}
                onClick={() => setDevicePage((page) => Math.min(devicePageCount - 1, page + 1))}
              >
                <Icon name="arrowRight" />
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="device-grid">
        {visibleDevices.map((device, index) => (
          <HomeDeviceCard
            key={device.id}
            device={device}
            circuit={deviceCircuit(device, devicePage * pageSize + index)}
            activeCircuit={activeCircuit}
            onActive={activateCircuit}
          />
        ))}
      </div>

      <button
        className={`assistant-mic ${listening ? "is-listening" : ""}`}
        type="button"
        onClick={onVoice}
        aria-label="Trợ lý giọng nói"
      >
        <span className="mic-orbit">
          <span className="mic-core">
            <Icon name="mic" />
          </span>
        </span>
        <span>Trợ lý</span>
      </button>
    </section>
  );
}
