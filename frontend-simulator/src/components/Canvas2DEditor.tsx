import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { Device, Wall, FaultMode } from '../types';
import { 
  Trash2, 
  Move, 
  PenTool, 
  ZoomIn, 
  ZoomOut, 
  RotateCcw, 
  Sparkles, 
  Layers 
} from 'lucide-react';

import { 
  DetectedRoom, 
  isPointInPolygon, 
  detectEnclosedRooms 
} from '../utils/roomDetection';

interface Canvas2DEditorProps {
  walls: Wall[];
  devices: Device[];
  faults: Record<string, FaultMode>;
  selectedDeviceId: string | null;
  onSelectDevice: (device: Device | null) => void;
  onUpdateDevicePosition: (deviceId: string, x: number, y: number, room?: string) => void;
  onSaveWalls: (walls: Wall[]) => void;
  onDropNewDevice?: (kind: string, name: string, room: string, x: number, y: number) => void;
}

export const Canvas2DEditor: React.FC<Canvas2DEditorProps> = ({
  walls,
  devices,
  faults,
  selectedDeviceId,
  onSelectDevice,
  onUpdateDevicePosition,
  onSaveWalls,
  onDropNewDevice,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const sizeRef = useRef<{ width: number; height: number; dpr: number }>({
    width: 800,
    height: 600,
    dpr: 1,
  });

  const [toolMode, setToolMode] = useState<'select' | 'wall' | 'deleteWall'>('select');
  const [zoom, setZoom] = useState<number>(1.0);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 20, y: 20 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Custom room names map
  const [customRoomNames, setCustomRoomNames] = useState<Record<string, string>>({});

  // Wall drawing state
  const [isDrawingWall, setIsDrawingWall] = useState(false);
  const [wallStart, setWallStart] = useState<{ x: number; y: number } | null>(null);
  const [wallCurrent, setWallCurrent] = useState<{ x: number; y: number } | null>(null);

  // Device dragging state
  const [draggingDeviceId, setDraggingDeviceId] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Hover state
  const [hoveredDeviceId, setHoveredDeviceId] = useState<string | null>(null);
  const [hoveredWallIndex, setHoveredWallIndex] = useState<number | null>(null);

  // Touch gesture state
  const touchStateRef = useRef<{
    type: 'none' | 'single' | 'pinch';
    startDist: number;
    startZoom: number;
    startPan: { x: number; y: number };
    startCenter: { x: number; y: number };
  }>({
    type: 'none',
    startDist: 0,
    startZoom: 1,
    startPan: { x: 0, y: 0 },
    startCenter: { x: 0, y: 0 },
  });

  // Snap to grid helper (10px grid)
  const snap = (val: number, gridSize = 10) => Math.round(val / gridSize) * gridSize;

  // Coordinate transformation helper
  const toWorldCoords = useCallback(
    (screenX: number, screenY: number) => {
      return {
        x: (screenX - pan.x) / zoom,
        y: (screenY - pan.y) / zoom,
      };
    },
    [pan, zoom]
  );

  // Detected Rooms memoized
  const detectedRooms = useMemo(() => {
    return detectEnclosedRooms(walls, devices, customRoomNames);
  }, [walls, devices, customRoomNames]);

  // Find containing room for world position
  const findContainingRoom = useCallback(
    (x: number, y: number): DetectedRoom | null => {
      const containing = detectedRooms.filter((r) => isPointInPolygon({ x, y }, r.corners));
      if (containing.length === 0) return null;
      containing.sort((a, b) => a.area - b.area);
      return containing[0];
    },
    [detectedRooms]
  );

  // Find room badge under world point
  const getRoomBadgeAt = useCallback(
    (worldX: number, worldY: number): DetectedRoom | null => {
      for (let i = detectedRooms.length - 1; i >= 0; i--) {
        const room = detectedRooms[i];
        const b = room.badgeBounds;
        if (
          b &&
          worldX >= b.x &&
          worldX <= b.x + b.width &&
          worldY >= b.y &&
          worldY <= b.y + b.height
        ) {
          return room;
        }
      }
      return null;
    },
    [detectedRooms]
  );

  // Rename room handler
  const handleRenameRoom = useCallback(
    (room: DetectedRoom) => {
      const newName = window.prompt(`Đổi tên phòng "${room.name}":`, room.name);
      if (newName && newName.trim() && newName.trim() !== room.name) {
        const trimmed = newName.trim();
        setCustomRoomNames((prev) => ({ ...prev, [room.id]: trimmed }));
        // Propagate to devices inside this room
        devices.forEach((dev) => {
          if (isPointInPolygon({ x: dev.x, y: dev.y }, room.corners)) {
            onUpdateDevicePosition(dev.id, dev.x, dev.y, trimmed);
          }
        });
      }
    },
    [devices, onUpdateDevicePosition]
  );

  // Find device under point
  const getDeviceAt = useCallback(
    (worldX: number, worldY: number, radius = 24) => {
      for (let i = devices.length - 1; i >= 0; i--) {
        const dev = devices[i];
        const dx = dev.x - worldX;
        const dy = dev.y - worldY;
        if (Math.hypot(dx, dy) <= radius) {
          return dev;
        }
      }
      return null;
    },
    [devices]
  );

  // Find wall under point
  const getWallAt = useCallback(
    (worldX: number, worldY: number, threshold = 8) => {
      for (let i = 0; i < walls.length; i++) {
        const w = walls[i];
        const l2 = (w.x2 - w.x1) ** 2 + (w.y2 - w.y1) ** 2;
        if (l2 === 0) continue;
        let t = ((worldX - w.x1) * (w.x2 - w.x1) + (worldY - w.y1) * (w.y2 - w.y1)) / l2;
        t = Math.max(0, Math.min(1, t));
        const projX = w.x1 + t * (w.x2 - w.x1);
        const projY = w.y1 + t * (w.y2 - w.y1);
        const dist = Math.hypot(worldX - projX, worldY - projY);
        if (dist <= threshold) {
          return i;
        }
      }
      return null;
    },
    [walls]
  );

  // Draw Canvas on demand
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { width, height, dpr } = sizeRef.current;
    if (width <= 0 || height <= 0) return;

    // Configure high-quality smoothing for sharp vectors & text
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';

    // Clear background: Warm cream (#faf6f0)
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = '#faf6f0';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.save();
    // Scale by DPR to map CSS pixels to high-resolution backing buffer
    ctx.scale(dpr, dpr);
    ctx.translate(pan.x, pan.y);
    ctx.scale(zoom, zoom);

    // Draw Warm Dot Grid
    const gridSize = 20;
    const startX = Math.floor(-pan.x / zoom / gridSize) * gridSize - 40;
    const endX = Math.ceil((width - pan.x) / zoom / gridSize) * gridSize + 40;
    const startY = Math.floor(-pan.y / zoom / gridSize) * gridSize - 40;
    const endY = Math.ceil((height - pan.y) / zoom / gridSize) * gridSize + 40;

    ctx.fillStyle = '#e4dfd5';
    for (let x = startX; x <= endX; x += gridSize) {
      for (let y = startY; y <= endY; y += gridSize) {
        ctx.beginPath();
        ctx.arc(x, y, 1.2, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Draw Detected Rooms (Floor Tint, Soft Dashed Border & Centroid Room Badge)
    detectedRooms.forEach((room) => {
      // 1. Soft Floor Tint
      ctx.fillStyle = 'rgba(74, 124, 89, 0.08)';
      ctx.beginPath();
      ctx.moveTo(room.corners[0].x, room.corners[0].y);
      for (let i = 1; i < room.corners.length; i++) {
        ctx.lineTo(room.corners[i].x, room.corners[i].y);
      }
      ctx.closePath();
      ctx.fill();

      // 2. Soft dashed border
      ctx.strokeStyle = 'rgba(74, 124, 89, 0.35)';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([6, 4]);
      ctx.stroke();
      ctx.setLineDash([]);

      // 3. Centroid Room Badge
      const nameText = room.name;
      const areaText = `${Math.round(room.area / 100)} m²`;

      ctx.font = 'bold 12px "Nunito Sans", sans-serif';
      const nameWidth = ctx.measureText(nameText).width;
      ctx.font = '10px "Nunito Sans", sans-serif';
      const areaWidth = ctx.measureText(areaText).width;

      const badgeWidth = Math.max(nameWidth, areaWidth) + 32;
      const badgeHeight = 36;
      const badgeX = room.centroid.x - badgeWidth / 2;
      const badgeY = room.centroid.y - badgeHeight / 2;

      room.badgeBounds = { x: badgeX, y: badgeY, width: badgeWidth, height: badgeHeight };

      // Badge Card
      ctx.fillStyle = 'rgba(255, 255, 255, 0.94)';
      ctx.strokeStyle = 'rgba(74, 124, 89, 0.4)';
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.roundRect(badgeX, badgeY, badgeWidth, badgeHeight, 10);
      ctx.fill();
      ctx.stroke();

      // Badge Name
      ctx.fillStyle = '#242826';
      ctx.font = 'bold 11px "Nunito Sans", sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(nameText, room.centroid.x, badgeY + 12);

      // Badge Area / subtitle
      ctx.fillStyle = '#707772';
      ctx.font = '9px "Nunito Sans", sans-serif';
      ctx.fillText(areaText, room.centroid.x, badgeY + 25);
    });

    // Draw Walls
    walls.forEach((wall, idx) => {
      const isHovered = hoveredWallIndex === idx && toolMode === 'deleteWall';
      ctx.strokeStyle = isHovered ? '#d9534f' : '#2c3531';
      ctx.lineWidth = isHovered ? 8 : 6;
      ctx.lineCap = 'round';
      ctx.beginPath();
      ctx.moveTo(wall.x1, wall.y1);
      ctx.lineTo(wall.x2, wall.y2);
      ctx.stroke();

      // Wall joint caps
      ctx.fillStyle = isHovered ? '#d9534f' : '#4a534e';
      ctx.beginPath();
      ctx.arc(wall.x1, wall.y1, 4, 0, Math.PI * 2);
      ctx.arc(wall.x2, wall.y2, 4, 0, Math.PI * 2);
      ctx.fill();
    });

    // Draw preview wall currently being drawn
    if (isDrawingWall && wallStart && wallCurrent) {
      ctx.strokeStyle = '#4a7c59';
      ctx.lineWidth = 5;
      ctx.setLineDash([8, 6]);
      ctx.beginPath();
      ctx.moveTo(wallStart.x, wallStart.y);
      ctx.lineTo(wallCurrent.x, wallCurrent.y);
      ctx.stroke();
      ctx.setLineDash([]);

      // Start & end points
      ctx.fillStyle = '#4a7c59';
      ctx.beginPath();
      ctx.arc(wallStart.x, wallStart.y, 5, 0, Math.PI * 2);
      ctx.arc(wallCurrent.x, wallCurrent.y, 5, 0, Math.PI * 2);
      ctx.fill();
    }

    // Draw Devices
    devices.forEach((dev) => {
      const isSelected = selectedDeviceId === dev.id;
      const isHovered = hoveredDeviceId === dev.id;
      const fault = faults[dev.id] || 'none';
      const isFaulty = fault !== 'none';
      const isPowerOn =
        dev.state?.power === true ||
        dev.state?.locked === true ||
        (dev.kind === 'sensor' && fault === 'none');

      // Glowing Aura for Light or Active devices
      if (dev.kind === 'light' && dev.state?.power) {
        const brightness = dev.state.brightness ?? 80;
        const glowRadius = 30 + (brightness / 100) * 35;
        const grad = ctx.createRadialGradient(dev.x, dev.y, 6, dev.x, dev.y, glowRadius);
        grad.addColorStop(0, 'rgba(255, 220, 120, 0.65)');
        grad.addColorStop(0.5, 'rgba(250, 195, 80, 0.25)');
        grad.addColorStop(1, 'rgba(250, 195, 80, 0)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(dev.x, dev.y, glowRadius, 0, Math.PI * 2);
        ctx.fill();
      }

      // Selection ring
      if (isSelected) {
        ctx.strokeStyle = '#4a7c59';
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.arc(dev.x, dev.y, 22, 0, Math.PI * 2);
        ctx.stroke();

        ctx.strokeStyle = 'rgba(74, 124, 89, 0.25)';
        ctx.lineWidth = 6;
        ctx.beginPath();
        ctx.arc(dev.x, dev.y, 26, 0, Math.PI * 2);
        ctx.stroke();
      } else if (isHovered) {
        ctx.strokeStyle = 'rgba(74, 124, 89, 0.4)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(dev.x, dev.y, 20, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Device Base Circle
      ctx.fillStyle = isFaulty
        ? '#fee2e2'
        : isPowerOn
        ? dev.kind === 'light'
          ? '#fef3c7'
          : '#eaf2ec'
        : '#f0ece4';
      ctx.strokeStyle = isFaulty
        ? '#ef4444'
        : isPowerOn
        ? dev.kind === 'light'
          ? '#f59e0b'
          : '#4a7c59'
        : '#cec7ba';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(dev.x, dev.y, 16, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Device Icon placeholder/symbol
      ctx.fillStyle = isFaulty
        ? '#dc2626'
        : isPowerOn
        ? dev.kind === 'light'
          ? '#b45309'
          : '#2d603d'
        : '#707772';
      ctx.font = '12px "Nunito Sans", sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';

      let symbol = '●';
      if (dev.kind === 'light') symbol = '💡';
      else if (dev.kind === 'aircon') symbol = '❄️';
      else if (dev.kind === 'blind') symbol = '🪟';
      else if (dev.kind === 'speaker') symbol = '🔊';
      else if (dev.kind === 'lock') symbol = dev.state?.locked ? '🔒' : '🔓';
      else if (dev.kind === 'sensor') {
        if (dev.state?.temperature !== undefined) symbol = '🌡️';
        else if (dev.state?.gas_detected !== undefined) symbol = '🔥';
        else if (dev.state?.motion !== undefined) symbol = '🚶';
        else if (dev.state?.open !== undefined) symbol = '🚪';
        else symbol = '📡';
      }

      ctx.fillText(symbol, dev.x, dev.y);

      // Device Label Pill
      const labelText = dev.name;
      ctx.font = 'bold 11px "Nunito Sans", sans-serif';
      const textMetrics = ctx.measureText(labelText);
      const textWidth = textMetrics.width;
      const pillW = textWidth + 14;
      const pillH = 18;
      const pillX = dev.x - pillW / 2;
      const pillY = dev.y + 20;

      // Pill background
      ctx.fillStyle = isSelected ? '#4a7c59' : 'rgba(255, 255, 255, 0.92)';
      ctx.strokeStyle = isSelected ? '#3b6548' : '#e0dad0';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect(pillX, pillY, pillW, pillH, 9);
      ctx.fill();
      ctx.stroke();

      // Pill text
      ctx.fillStyle = isSelected ? '#ffffff' : '#2c3531';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(labelText, dev.x, pillY + pillH / 2);

      // Fault indicator badge
      if (isFaulty) {
        ctx.fillStyle = '#dc2626';
        ctx.beginPath();
        ctx.arc(dev.x + 12, dev.y - 12, 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 8px sans-serif';
        ctx.fillText('!', dev.x + 12, dev.y - 12);
      }
    });

    ctx.restore();
  }, [
    walls,
    devices,
    faults,
    selectedDeviceId,
    hoveredDeviceId,
    hoveredWallIndex,
    toolMode,
    zoom,
    pan,
    isDrawingWall,
    wallStart,
    wallCurrent,
    detectedRooms,
  ]);

  // ResizeObserver to adapt dynamically and set canvas buffer resolution
  useEffect(() => {
    const wrapper = wrapperRef.current;
    const canvas = canvasRef.current;
    if (!wrapper || !canvas) return;

    const resizeObserver = new ResizeObserver(() => {
      const rect = wrapper.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const targetWidth = Math.round(rect.width * dpr);
      const targetHeight = Math.round(rect.height * dpr);

      if (targetWidth > 0 && targetHeight > 0) {
        sizeRef.current = { width: rect.width, height: rect.height, dpr };
        if (canvas.width !== targetWidth || canvas.height !== targetHeight) {
          canvas.width = targetWidth;
          canvas.height = targetHeight;
        }
        draw();
      }
    });

    resizeObserver.observe(wrapper);

    return () => {
      resizeObserver.disconnect();
    };
  }, [draw]);

  // Call draw on demand whenever state/props change
  useEffect(() => {
    draw();
  }, [draw]);

  // Mouse Handlers
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;
    const world = toWorldCoords(clientX, clientY);

    // Middle button or Shift+click for Panning
    if (e.button === 1 || e.shiftKey) {
      setIsPanning(true);
      setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
      return;
    }

    // Check if clicking room badge to rename
    const hitBadge = getRoomBadgeAt(world.x, world.y);
    if (hitBadge && e.button === 0) {
      handleRenameRoom(hitBadge);
      return;
    }

    if (toolMode === 'wall') {
      const snappedX = snap(world.x);
      const snappedY = snap(world.y);
      setIsDrawingWall(true);
      setWallStart({ x: snappedX, y: snappedY });
      setWallCurrent({ x: snappedX, y: snappedY });
    } else if (toolMode === 'deleteWall') {
      const wallIdx = getWallAt(world.x, world.y);
      if (wallIdx !== null) {
        const nextWalls = [...walls];
        nextWalls.splice(wallIdx, 1);
        onSaveWalls(nextWalls);
        setHoveredWallIndex(null);
      }
    } else if (toolMode === 'select') {
      const hitDev = getDeviceAt(world.x, world.y);
      if (hitDev) {
        onSelectDevice(hitDev);
        setDraggingDeviceId(hitDev.id);
        setDragOffset({ x: world.x - hitDev.x, y: world.y - hitDev.y });
      } else {
        onSelectDevice(null);
        // Start pan if clicking on empty area
        setIsPanning(true);
        setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
      }
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;
    const world = toWorldCoords(clientX, clientY);

    if (isPanning) {
      setPan({
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y,
      });
      return;
    }

    if (isDrawingWall && wallStart) {
      setWallCurrent({
        x: snap(world.x),
        y: snap(world.y),
      });
      return;
    }

    if (draggingDeviceId) {
      const newX = snap(world.x - dragOffset.x);
      const newY = snap(world.y - dragOffset.y);
      const room = findContainingRoom(newX, newY);
      onUpdateDevicePosition(draggingDeviceId, newX, newY, room?.name);
      return;
    }

    // Hover checks
    if (toolMode === 'deleteWall') {
      setHoveredWallIndex(getWallAt(world.x, world.y));
    } else {
      const dev = getDeviceAt(world.x, world.y);
      setHoveredDeviceId(dev ? dev.id : null);
    }
  };

  const handleMouseUp = () => {
    if (isPanning) {
      setIsPanning(false);
    }

    if (isDrawingWall && wallStart && wallCurrent) {
      if (Math.hypot(wallCurrent.x - wallStart.x, wallCurrent.y - wallStart.y) > 15) {
        const newWall: Wall = {
          x1: wallStart.x,
          y1: wallStart.y,
          x2: wallCurrent.x,
          y2: wallCurrent.y,
        };
        onSaveWalls([...walls, newWall]);
      }
      setIsDrawingWall(false);
      setWallStart(null);
      setWallCurrent(null);
    }

    if (draggingDeviceId) {
      setDraggingDeviceId(null);
    }
  };

  // Touch Handlers for mobile & tablet support
  const handleTouchStart = (e: React.TouchEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();

    if (e.touches.length === 1) {
      const touch = e.touches[0];
      const clientX = touch.clientX - rect.left;
      const clientY = touch.clientY - rect.top;
      const world = toWorldCoords(clientX, clientY);

      touchStateRef.current.type = 'single';

      // 1. Check room badge tap
      const hitBadge = getRoomBadgeAt(world.x, world.y);
      if (hitBadge) {
        handleRenameRoom(hitBadge);
        return;
      }

      // 2. Tool Mode Actions
      if (toolMode === 'wall') {
        const sx = snap(world.x);
        const sy = snap(world.y);
        setIsDrawingWall(true);
        setWallStart({ x: sx, y: sy });
        setWallCurrent({ x: sx, y: sy });
      } else if (toolMode === 'deleteWall') {
        const wallIdx = getWallAt(world.x, world.y);
        if (wallIdx !== null) {
          const nextWalls = [...walls];
          nextWalls.splice(wallIdx, 1);
          onSaveWalls(nextWalls);
        }
      } else if (toolMode === 'select') {
        const dev = getDeviceAt(world.x, world.y);
        if (dev) {
          onSelectDevice(dev);
          setDraggingDeviceId(dev.id);
          setDragOffset({ x: world.x - dev.x, y: world.y - dev.y });
        } else {
          onSelectDevice(null);
          setIsPanning(true);
          setPanStart({ x: touch.clientX - pan.x, y: touch.clientY - pan.y });
        }
      }
    } else if (e.touches.length === 2) {
      // Multi-touch: 2-finger pinch zoom & pan
      const t0 = e.touches[0];
      const t1 = e.touches[1];
      const dist = Math.hypot(t1.clientX - t0.clientX, t1.clientY - t0.clientY);
      const centerX = (t0.clientX + t1.clientX) / 2 - rect.left;
      const centerY = (t0.clientY + t1.clientY) / 2 - rect.top;

      touchStateRef.current = {
        type: 'pinch',
        startDist: dist,
        startZoom: zoom,
        startPan: { ...pan },
        startCenter: { x: centerX, y: centerY },
      };

      setIsDrawingWall(false);
      setWallStart(null);
      setWallCurrent(null);
      setDraggingDeviceId(null);
      setIsPanning(false);
    }
  };

  const handleTouchMove = (e: React.TouchEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();

    if (e.touches.length === 1 && touchStateRef.current.type === 'single') {
      const touch = e.touches[0];
      const clientX = touch.clientX - rect.left;
      const clientY = touch.clientY - rect.top;
      const world = toWorldCoords(clientX, clientY);

      if (isPanning) {
        setPan({
          x: touch.clientX - panStart.x,
          y: touch.clientY - panStart.y,
        });
        return;
      }

      if (isDrawingWall && wallStart) {
        setWallCurrent({
          x: snap(world.x),
          y: snap(world.y),
        });
        return;
      }

      if (draggingDeviceId) {
        const newX = snap(world.x - dragOffset.x);
        const newY = snap(world.y - dragOffset.y);
        const room = findContainingRoom(newX, newY);
        onUpdateDevicePosition(draggingDeviceId, newX, newY, room?.name);
        return;
      }
    } else if (e.touches.length === 2 && touchStateRef.current.type === 'pinch') {
      const t0 = e.touches[0];
      const t1 = e.touches[1];
      const currentDist = Math.hypot(t1.clientX - t0.clientX, t1.clientY - t0.clientY);
      const centerX = (t0.clientX + t1.clientX) / 2 - rect.left;
      const centerY = (t0.clientY + t1.clientY) / 2 - rect.top;

      const { startDist, startZoom, startPan, startCenter } = touchStateRef.current;
      if (startDist <= 0) return;

      const scale = currentDist / startDist;
      const newZoom = Math.min(2.5, Math.max(0.4, startZoom * scale));

      const worldCenterX = (startCenter.x - startPan.x) / startZoom;
      const worldCenterY = (startCenter.y - startPan.y) / startZoom;

      const newPanX = centerX - worldCenterX * newZoom;
      const newPanY = centerY - worldCenterY * newZoom;

      setZoom(newZoom);
      setPan({ x: newPanX, y: newPanY });
    }
  };

  const handleTouchEnd = (e: React.TouchEvent<HTMLCanvasElement>) => {
    if (e.touches.length === 0) {
      if (isPanning) {
        setIsPanning(false);
      }

      if (isDrawingWall && wallStart && wallCurrent) {
        if (Math.hypot(wallCurrent.x - wallStart.x, wallCurrent.y - wallStart.y) > 15) {
          const newWall: Wall = {
            x1: wallStart.x,
            y1: wallStart.y,
            x2: wallCurrent.x,
            y2: wallCurrent.y,
          };
          onSaveWalls([...walls, newWall]);
        }
        setIsDrawingWall(false);
        setWallStart(null);
        setWallCurrent(null);
      }

      if (draggingDeviceId) {
        setDraggingDeviceId(null);
      }

      touchStateRef.current.type = 'none';
    } else if (e.touches.length === 1) {
      touchStateRef.current.type = 'single';
      setIsPanning(false);
    }
  };

  // Wheel Zoom
  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    const newZoom = Math.min(2.5, Math.max(0.4, zoom * zoomFactor));

    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;

    setPan({
      x: clientX - (clientX - pan.x) * (newZoom / zoom),
      y: clientY - (clientY - pan.y) * (newZoom / zoom),
    });
    setZoom(newZoom);
  };

  // Drag & Drop new devices from Library
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const rawData = e.dataTransfer.getData('application/json');
    if (!rawData || !onDropNewDevice) return;
    try {
      const item = JSON.parse(rawData);
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const world = toWorldCoords(e.clientX - rect.left, e.clientY - rect.top);
      const dropX = snap(world.x);
      const dropY = snap(world.y);
      const room = findContainingRoom(dropX, dropY);
      const roomName = room ? room.name : item.room || 'Phòng khách';

      onDropNewDevice(
        item.kind || 'light',
        item.name || 'Thiết bị mới',
        roomName,
        dropX,
        dropY
      );
    } catch (err) {
      console.error('Failed to drop device:', err);
    }
  };

  return (
    <div className="relative w-full h-full flex flex-col bg-background rounded-xl overflow-hidden shadow-soft border border-outline-variant select-none min-h-0 min-w-0 flex-1">
      {/* Top Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-2.5 sm:px-4 py-2 bg-surface border-b border-outline-variant z-10">
        <div className="flex items-center space-x-1 sm:space-x-1.5 bg-surface-container p-1 rounded-xl flex-wrap gap-1">
          <button
            onClick={() => setToolMode('select')}
            title="Chế độ chọn & di chuyển thiết bị"
            className={`flex items-center space-x-1 sm:space-x-1.5 px-2.5 sm:px-3 py-1.5 min-h-[38px] md:min-h-[40px] text-xs font-semibold rounded-lg transition-all ${
              toolMode === 'select'
                ? 'bg-primary text-white shadow-sm'
                : 'text-earth-dark hover:bg-surface-variant'
            }`}
          >
            <Move size={14} />
            <span>Chọn / Di chuyển</span>
          </button>

          <button
            onClick={() => setToolMode('wall')}
            title="Vẽ tường mới (Kéo thả trên canvas)"
            className={`flex items-center space-x-1 sm:space-x-1.5 px-2.5 sm:px-3 py-1.5 min-h-[38px] md:min-h-[40px] text-xs font-semibold rounded-lg transition-all ${
              toolMode === 'wall'
                ? 'bg-primary text-white shadow-sm'
                : 'text-earth-dark hover:bg-surface-variant'
            }`}
          >
            <PenTool size={14} />
            <span>Vẽ tường</span>
          </button>

          <button
            onClick={() => setToolMode('deleteWall')}
            title="Click vào tường để xoá"
            className={`flex items-center space-x-1 sm:space-x-1.5 px-2.5 sm:px-3 py-1.5 min-h-[38px] md:min-h-[40px] text-xs font-semibold rounded-lg transition-all ${
              toolMode === 'deleteWall'
                ? 'bg-red-600 text-white shadow-sm'
                : 'text-earth-dark hover:bg-red-50 hover:text-red-600'
            }`}
          >
            <Trash2 size={14} />
            <span>Xoá tường</span>
          </button>
        </div>

        {/* Zoom & View Presets */}
        <div className="flex items-center space-x-1.5 sm:space-x-2">
          <div className="flex items-center bg-surface-container rounded-lg p-0.5 text-xs">
            <button
              onClick={() => setZoom((z) => Math.max(0.4, z - 0.15))}
              title="Thu nhỏ"
              className="p-2 min-w-[34px] min-h-[34px] flex items-center justify-center hover:bg-surface-variant rounded text-earth-dark"
            >
              <ZoomOut size={14} />
            </button>
            <span className="px-1.5 sm:px-2 font-mono text-earth-muted text-[11px] sm:text-xs">
              {Math.round(zoom * 100)}%
            </span>
            <button
              onClick={() => setZoom((z) => Math.min(2.5, z + 0.15))}
              title="Phóng to"
              className="p-2 min-w-[34px] min-h-[34px] flex items-center justify-center hover:bg-surface-variant rounded text-earth-dark"
            >
              <ZoomIn size={14} />
            </button>
            <button
              onClick={() => {
                setZoom(1.0);
                setPan({ x: 40, y: 30 });
              }}
              title="Đặt lại góc nhìn"
              className="p-2 min-w-[34px] min-h-[34px] flex items-center justify-center hover:bg-surface-variant rounded text-earth-dark ml-0.5"
            >
              <RotateCcw size={14} />
            </button>
          </div>

          <div className="text-xs text-earth-muted hidden lg:flex items-center space-x-1 pl-1">
            <Layers size={13} />
            <span>
              {walls.length} tường · {detectedRooms.length} phòng · {devices.length} thiết bị
            </span>
          </div>
        </div>
      </div>

      {/* Canvas Viewport */}
      <div
        ref={wrapperRef}
        className="relative flex-1 w-full h-full overflow-hidden cursor-crosshair min-h-0 min-w-0 touch-none"
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        <canvas
          ref={canvasRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
          onTouchEnd={handleTouchEnd}
          onTouchCancel={handleTouchEnd}
          onWheel={handleWheel}
          className="w-full h-full block touch-none"
          style={{ touchAction: 'none' }}
        />

        {/* Tip floating badge */}
        <div className="absolute bottom-3 left-4 bg-surface/90 backdrop-blur px-3 py-1.5 rounded-lg border border-outline-variant text-[11px] text-earth-muted shadow-sm pointer-events-none flex items-center space-x-1.5">
          <Sparkles size={12} className="text-primary" />
          <span>
            {toolMode === 'wall'
              ? 'Kéo trên canvas để dựng tường. Tự động nhận diện 4 bức tường thành phòng.'
              : toolMode === 'deleteWall'
              ? 'Nhấp/chạm vào bức tường bất kỳ để xoá bỏ.'
              : 'Chọn/kéo thiết bị vào phòng để tự động gán vị trí. Chạm tên phòng để đổi tên.'}
          </span>
        </div>
      </div>
    </div>
  );
};
