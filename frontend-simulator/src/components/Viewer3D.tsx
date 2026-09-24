import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { Device, Wall, FaultMode } from '../types';
import { detectEnclosedRooms, isPointInPolygon } from '../utils/roomDetection';
import { 
  Box, 
  RotateCcw, 
  Compass, 
  Layers, 
  Sun, 
  Moon, 
  Thermometer, 
  Activity,
  Armchair,
  Sparkles
} from 'lucide-react';

interface Viewer3DProps {
  walls: Wall[];
  devices: Device[];
  faults: Record<string, FaultMode>;
  selectedDeviceId: string | null;
  onSelectDevice: (device: Device | null) => void;
}

interface AnimatedObject {
  id: string;
  update: (time: number, delta: number) => void;
}

// Utility to create high-DPI room climate label canvas texture
function createRoomBadgeTexture(
  roomName: string, 
  climateText: string, 
  iconType: 'temp' | 'eco' | 'warn',
  isNight: boolean
): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 140;
  const ctx = canvas.getContext('2d');
  if (ctx) {
    // Rounded Card Background adhering to Terra Organic Design
    ctx.fillStyle = isNight ? 'rgba(39, 48, 44, 0.94)' : 'rgba(250, 246, 240, 0.94)';
    ctx.shadowColor = isNight ? 'rgba(0, 0, 0, 0.45)' : 'rgba(46, 50, 48, 0.12)';
    ctx.shadowBlur = 16;
    ctx.shadowOffsetY = 4;
    ctx.beginPath();
    ctx.roundRect(14, 14, 484, 112, 22);
    ctx.fill();

    // Border stroke
    ctx.shadowColor = 'transparent';
    ctx.strokeStyle = iconType === 'warn' 
      ? '#c2410c' 
      : isNight 
      ? 'rgba(122, 168, 135, 0.55)' 
      : 'rgba(74, 124, 89, 0.45)';
    ctx.lineWidth = 3;
    ctx.stroke();

    // Room Name
    ctx.fillStyle = isNight ? '#f5f2eb' : '#242826';
    ctx.font = 'bold 34px "Nunito Sans", sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(roomName, 256, 48);

    // Climate subtitle
    ctx.fillStyle = iconType === 'warn' 
      ? '#f97316' 
      : isNight 
      ? '#a8c5b0' 
      : '#705c30';
    ctx.font = '600 23px "Nunito Sans", sans-serif';
    ctx.fillText(climateText, 256, 92);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.generateMipmaps = true;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  return texture;
}

// Procedural Parquet Wood / Stone Texture Generator for Room Floor Plates
function createFloorTileTexture(type: 'wood' | 'tile' | 'slate', isNight: boolean): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 256;
  const ctx = canvas.getContext('2d');
  if (ctx) {
    if (type === 'wood') {
      ctx.fillStyle = isNight ? '#8e8272' : '#e2d9cc';
      ctx.fillRect(0, 0, 256, 256);

      // Parquet plank lines
      ctx.strokeStyle = isNight ? '#6e6456' : '#cdc2b2';
      ctx.lineWidth = 2;
      const plankH = 32;
      for (let y = 0; y < 256; y += plankH) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(256, y);
        ctx.stroke();

        // Staggered vertical seams
        const offset = (y / plankH) % 2 === 0 ? 0 : 64;
        for (let x = offset; x < 256; x += 128) {
          ctx.beginPath();
          ctx.moveTo(x, y);
          ctx.lineTo(x, y + plankH);
          ctx.stroke();
        }
      }
    } else {
      ctx.fillStyle = isNight ? '#8a948e' : '#dbd6cc';
      ctx.fillRect(0, 0, 256, 256);

      // Tile grid lines
      ctx.strokeStyle = isNight ? '#68746e' : '#c8c2b7';
      ctx.lineWidth = 2;
      for (let i = 0; i <= 256; i += 64) {
        ctx.beginPath();
        ctx.moveTo(i, 0);
        ctx.lineTo(i, 256);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(0, i);
        ctx.lineTo(256, i);
        ctx.stroke();
      }
    }
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  return texture;
}

// Texture caches for high-performance rendering without constant reallocation
const floorTextureCache = new Map<string, THREE.CanvasTexture>();
function getFloorTileTexture(type: 'wood' | 'tile' | 'slate', isNight: boolean): THREE.CanvasTexture {
  const key = `${type}_${isNight ? 'night' : 'day'}`;
  if (!floorTextureCache.has(key)) {
    floorTextureCache.set(key, createFloorTileTexture(type, isNight));
  }
  return floorTextureCache.get(key)!;
}

const roomBadgeTextureCache = new Map<string, THREE.CanvasTexture>();
function getRoomBadgeTexture(
  roomName: string, 
  climateText: string, 
  iconType: 'temp' | 'eco' | 'warn',
  isNight: boolean
): THREE.CanvasTexture {
  const key = `${roomName}_${climateText}_${iconType}_${isNight ? 'night' : 'day'}`;
  if (!roomBadgeTextureCache.has(key)) {
    roomBadgeTextureCache.set(key, createRoomBadgeTexture(roomName, climateText, iconType, isNight));
  }
  return roomBadgeTextureCache.get(key)!;
}

// Shared Material Cache for high-performance 3D rendering without constant reallocation
const sharedMaterialCache = new Map<string, THREE.Material>();
function getSharedMaterial<T extends THREE.Material>(key: string, factory: () => T): T {
  if (!sharedMaterialCache.has(key)) {
    sharedMaterialCache.set(key, factory());
  }
  return sharedMaterialCache.get(key) as T;
}

export const Viewer3D: React.FC<Viewer3DProps> = ({
  walls,
  devices,
  faults,
  selectedDeviceId,
  onSelectDevice,
}) => {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const animFrameIdRef = useRef<number | null>(null);

  // Group references
  const floorPlatesGroupRef = useRef<THREE.Group>(new THREE.Group());
  const wallsGroupRef = useRef<THREE.Group>(new THREE.Group());
  const devicesGroupRef = useRef<THREE.Group>(new THREE.Group());
  const lightsGroupRef = useRef<THREE.Group>(new THREE.Group());
  const climateOverlayGroupRef = useRef<THREE.Group>(new THREE.Group());
  const architecturalDecorGroupRef = useRef<THREE.Group>(new THREE.Group());
  
  // Animation registry
  const animatedObjectsRef = useRef<AnimatedObject[]>([]);
  const deviceMeshesMap = useRef<Map<string, THREE.Object3D>>(new Map());

  // Lighting & Environment States (Default to 'day' per Terra Organic Design)
  const [lightingMode, setLightingMode] = useState<'night' | 'day'>('day');

  // Layer Visibility States
  const [showClimateOverlay, setShowClimateOverlay] = useState<boolean>(true);
  const [showDynamicLights, setShowDynamicLights] = useState<boolean>(true);
  const [showFloorGrid, setShowFloorGrid] = useState<boolean>(true);
  const [showDecor, setShowDecor] = useState<boolean>(true);

  // Tooltip & hover (ref-based mouse pos to avoid React re-renders on pointermove)
  const [hoveredDev, setHoveredDev] = useState<Device | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const mousePosRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const raycastPendingRef = useRef<boolean>(false);
  const raycasterRef = useRef<THREE.Raycaster>(new THREE.Raycaster());
  const mouseVecRef = useRef<THREE.Vector2>(new THREE.Vector2());
  const needsRenderRef = useRef<boolean>(true);

  // Mesh & Light refs for dynamic day/night switching
  const gridMeshRef = useRef<THREE.GridHelper | null>(null);
  const ambientLightRef = useRef<THREE.AmbientLight | null>(null);
  const sunLightRef = useRef<THREE.DirectionalLight | null>(null);
  const fillLightRef = useRef<THREE.DirectionalLight | null>(null);
  const baseFloorMeshRef = useRef<THREE.Mesh | null>(null);

  // Check if a device is a Door / Lock / Entry Contact sensor
  const isDoorDevice = useCallback((d: Device) => {
    const k = d.kind?.toLowerCase() || '';
    const n = d.name?.toLowerCase() || '';
    return (
      k === 'lock' || 
      k === 'door' || 
      d.state?.open !== undefined || 
      d.state?.locked !== undefined ||
      n.includes('cửa') || 
      n.includes('khóa') || 
      n.includes('door') || 
      n.includes('lock')
    );
  }, []);

  // 1. Automatic 4-Wall Atomic Room Detection with intelligent room naming
  const detectedRooms = useMemo(() => {
    return detectEnclosedRooms(walls, devices);
  }, [walls, devices]);

  // Fallback room Aggregation from devices (when no 4-wall rooms are detected)
  const roomAggregates = useMemo(() => {
    const map = new Map<string, {
      devices: Device[];
      avgTemp?: number;
      avgHumidity?: number;
      hasGasWarning?: boolean;
      hasMotion?: boolean;
      centerX: number;
      centerY: number;
      minX: number;
      maxX: number;
      minY: number;
      maxY: number;
      width: number;
      depth: number;
      radius: number;
      corners?: { x: number; y: number }[];
    }>();

    devices.forEach((dev) => {
      const room = dev.room || 'Phòng Chung';
      if (!map.has(room)) {
        map.set(room, {
          devices: [],
          centerX: 0,
          centerY: 0,
          minX: dev.x,
          maxX: dev.x,
          minY: dev.y,
          maxY: dev.y,
          width: 90,
          depth: 90,
          radius: 45,
        });
      }
      const item = map.get(room)!;
      item.devices.push(dev);
      item.minX = Math.min(item.minX, dev.x);
      item.maxX = Math.max(item.maxX, dev.x);
      item.minY = Math.min(item.minY, dev.y);
      item.maxY = Math.max(item.maxY, dev.y);
    });

    map.forEach((data) => {
      let sumX = 0;
      let sumY = 0;
      let sumTemp = 0;
      let tempCount = 0;
      let sumHum = 0;
      let humCount = 0;
      let gasWarn = false;
      let motionActive = false;

      data.devices.forEach((d) => {
        sumX += d.x;
        sumY += d.y;
        if (d.state?.temperature !== undefined) {
          sumTemp += d.state.temperature;
          tempCount++;
        } else if (d.kind === 'aircon' && d.state?.target_temperature !== undefined) {
          sumTemp += d.state.target_temperature;
          tempCount++;
        }

        if (d.state?.humidity !== undefined) {
          sumHum += d.state.humidity;
          humCount++;
        }
        if (d.state?.gas_detected || (d.state?.ppm && d.state.ppm > 400)) {
          gasWarn = true;
        }
        if (d.state?.motion) {
          motionActive = true;
        }
      });

      const count = data.devices.length;
      data.centerX = sumX / count;
      data.centerY = sumY / count;

      if (tempCount > 0) data.avgTemp = Number((sumTemp / tempCount).toFixed(1));
      if (humCount > 0) data.avgHumidity = Number((sumHum / humCount).toFixed(0));
      data.hasGasWarning = gasWarn;
      data.hasMotion = motionActive;

      // Floor plate bounding dimensions
      const pad = 36;
      data.width = Math.max(96, (data.maxX - data.minX) + pad * 2);
      data.depth = Math.max(96, (data.maxY - data.minY) + pad * 2);

      // Bounding radius
      let maxDist = 45;
      data.devices.forEach((d) => {
        const dist = Math.hypot(d.x - data.centerX, d.y - data.centerY);
        if (dist > maxDist) maxDist = dist;
      });
      data.radius = Math.min(190, Math.max(50, maxDist + 28));
    });

    return Array.from(map.entries()).map(([room, stats]) => ({ room, ...stats }));
  }, [devices]);

  // Combined Room Telemetry & Geometric Layout Mapping
  const roomTelemetry = useMemo(() => {
    if (detectedRooms.length === 0) {
      return roomAggregates;
    }

    return detectedRooms.map((room) => {
      const roomDevs = devices.filter(
        (d) => isPointInPolygon({ x: d.x, y: d.y }, room.corners) || d.room === room.name
      );

      let sumTemp = 0;
      let tempCount = 0;
      let sumHum = 0;
      let humCount = 0;
      let gasWarn = false;
      let motionActive = false;

      roomDevs.forEach((d) => {
        if (d.state?.temperature !== undefined) {
          sumTemp += d.state.temperature;
          tempCount++;
        } else if (d.kind === 'aircon' && d.state?.target_temperature !== undefined) {
          sumTemp += d.state.target_temperature;
          tempCount++;
        }

        if (d.state?.humidity !== undefined) {
          sumHum += d.state.humidity;
          humCount++;
        }
        if (d.state?.gas_detected || (d.state?.ppm && d.state.ppm > 400)) {
          gasWarn = true;
        }
        if (d.state?.motion) {
          motionActive = true;
        }
      });

      const avgTemp = tempCount > 0 ? Number((sumTemp / tempCount).toFixed(1)) : undefined;
      const avgHumidity = humCount > 0 ? Number((sumHum / humCount).toFixed(0)) : undefined;

      const xs = room.corners.map((c) => c.x);
      const ys = room.corners.map((c) => c.y);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);
      const width = Math.max(96, maxX - minX);
      const depth = Math.max(96, maxY - minY);

      return {
        id: room.id,
        room: room.name,
        corners: room.corners,
        centroid: room.centroid,
        area: room.area,
        devices: roomDevs,
        avgTemp,
        avgHumidity,
        hasGasWarning: gasWarn,
        hasMotion: motionActive,
        centerX: room.centroid.x,
        centerY: room.centroid.y,
        minX,
        maxX,
        minY,
        maxY,
        width,
        depth,
        radius: Math.max(width, depth) / 2,
      };
    });
  }, [detectedRooms, devices, roomAggregates]);

  // Intelligent Doorway Detection & Wall Splitting Map
  // Calculates door placements along walls and aligns door rotations
  const doorAlignments = useMemo(() => {
    const alignments = new Map<string, { x: number; z: number; rotationY: number; wallAngle: number }>();
    const doorDevs = devices.filter(isDoorDevice);

    doorDevs.forEach((dDev) => {
      let bestDist = 32; // Search radius for nearest wall
      let bestProj: { x: number; z: number; rotationY: number; wallAngle: number } | null = null;

      walls.forEach((wall) => {
        const dx = wall.x2 - wall.x1;
        const dz = wall.y2 - wall.y1;
        const length = Math.hypot(dx, dz);
        if (length < 2) return;

        const ux = dx / length;
        const uz = dz / length;

        // Project door onto wall line
        const vx = dDev.x - wall.x1;
        const vz = dDev.y - wall.y1;
        const s = vx * ux + vz * uz;
        const t = s / length;

        if (t >= 0.04 && t <= 0.96) {
          const px = wall.x1 + s * ux;
          const pz = wall.y1 + s * uz;
          const dist = Math.hypot(dDev.x - px, dDev.y - pz);

          if (dist < bestDist) {
            bestDist = dist;
            const wallAngle = Math.atan2(dz, dx);
            bestProj = {
              x: px,
              z: pz,
              rotationY: -wallAngle,
              wallAngle,
            };
          }
        }
      });

      if (bestProj) {
        alignments.set(dDev.id, bestProj);
      }
    });

    return alignments;
  }, [devices, walls, isDoorDevice]);

  // Camera presets
  const setCameraPreset = useCallback((preset: 'iso' | 'top' | 'front') => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;

    if (preset === 'iso') {
      camera.position.set(300, 380, 460);
      controls.target.set(300, 0, 200);
    } else if (preset === 'top') {
      camera.position.set(300, 580, 200);
      controls.target.set(300, 0, 200);
    } else if (preset === 'front') {
      camera.position.set(300, 160, 580);
      controls.target.set(300, 15, 200);
    }
    controls.update();
  }, []);

  // Initialize Three.js Scene
  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const width = mount.clientWidth;
    const height = mount.clientHeight;

    // 1. Scene with Dynamic Environmental Background & Fog
    const scene = new THREE.Scene();
    const isNight = lightingMode === 'night';
    const initBgColor = isNight ? 0x27302c : 0xfaf6f0;
    scene.background = new THREE.Color(initBgColor);
    scene.fog = new THREE.FogExp2(initBgColor, isNight ? 0.00035 : 0.0006);
    sceneRef.current = scene;

    // 2. Perspective Camera
    const camera = new THREE.PerspectiveCamera(45, width / height, 1, 3000);
    camera.position.set(300, 380, 460);
    cameraRef.current = camera;

    // 3. WebGL Renderer with PCF Shadow Mapping & Performance Optimization
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.25));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.25;
    mount.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // 4. OrbitControls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.maxPolarAngle = Math.PI / 2 - 0.03; // Don't clip under floor
    controls.minDistance = 60;
    controls.maxDistance = 1400;
    controls.target.set(300, 0, 200);
    controls.addEventListener('change', () => {
      needsRenderRef.current = true;
    });
    controls.update();
    controlsRef.current = controls;

    // 5. Environmental Lighting (Night / Day adaptive)
    const ambientLight = new THREE.AmbientLight(
      isNight ? 0x6e8077 : 0xfcf9f2, 
      isNight ? 0.85 : 0.95
    );
    scene.add(ambientLight);
    ambientLightRef.current = ambientLight;

    // Directional Light (Moonlight / Sunlight) casting soft shadows
    const sunLight = new THREE.DirectionalLight(
      isNight ? 0xc0d0e0 : 0xfff7ea, 
      isNight ? 0.9 : 1.35
    );
    sunLight.position.set(320, 520, 320);
    sunLight.castShadow = true;
    sunLight.shadow.mapSize.width = 1024;
    sunLight.shadow.mapSize.height = 1024;
    sunLight.shadow.camera.near = 10;
    sunLight.shadow.camera.far = 1300;
    const shadowD = 450;
    sunLight.shadow.camera.left = -shadowD;
    sunLight.shadow.camera.right = shadowD;
    sunLight.shadow.camera.top = shadowD;
    sunLight.shadow.camera.bottom = -shadowD;
    sunLight.shadow.bias = -0.0006;
    sunLight.shadow.radius = 2.0;
    scene.add(sunLight);
    sunLightRef.current = sunLight;

    // Secondary fill light
    const fillLight = new THREE.DirectionalLight(
      isNight ? 0x4a5952 : 0xe5ede7, 
      isNight ? 0.5 : 0.45
    );
    fillLight.position.set(-220, 220, -220);
    scene.add(fillLight);
    fillLightRef.current = fillLight;

    // 6. Base Ground Plane
    const floorGeo = new THREE.PlaneGeometry(1600, 1600);
    const floorMat = new THREE.MeshStandardMaterial({
      color: isNight ? 0x424c47 : 0xede7df,
      roughness: 0.92,
      metalness: 0.02,
    });
    const baseFloor = new THREE.Mesh(floorGeo, floorMat);
    baseFloor.rotation.x = -Math.PI / 2;
    baseFloor.position.set(300, -0.4, 200);
    baseFloor.receiveShadow = true;
    scene.add(baseFloor);
    baseFloorMeshRef.current = baseFloor;

    // Architectural Grid Helper
    const grid = new THREE.GridHelper(
      1200, 
      48, 
      isNight ? 0x6e7b74 : 0xd2c9bd, 
      isNight ? 0x525e58 : 0xe2dcce
    );
    grid.position.set(300, 0, 200);
    scene.add(grid);
    gridMeshRef.current = grid;

    // Add Object Groups
    scene.add(floorPlatesGroupRef.current);
    scene.add(climateOverlayGroupRef.current);
    scene.add(architecturalDecorGroupRef.current);
    scene.add(wallsGroupRef.current);
    scene.add(devicesGroupRef.current);
    scene.add(lightsGroupRef.current);

    // Resize Handler
    const handleResize = () => {
      if (!mountRef.current || !cameraRef.current || !rendererRef.current) return;
      const w = mountRef.current.clientWidth;
      const h = mountRef.current.clientHeight;
      if (w === 0 || h === 0) return;
      cameraRef.current.aspect = w / h;
      cameraRef.current.updateProjectionMatrix();
      rendererRef.current.setSize(w, h);
      needsRenderRef.current = true;
    };
    window.addEventListener('resize', handleResize);

    const resizeObserver = new ResizeObserver(() => {
      handleResize();
    });
    if (mountRef.current) {
      resizeObserver.observe(mountRef.current);
    }

    // Optimized Animation Loop with Smart Dynamic Sleep
    const clock = new THREE.Clock();
    const animate = () => {
      const delta = clock.getDelta();
      const time = clock.getElapsedTime();

      const hasAnimations = animatedObjectsRef.current.length > 0;
      const controlsUpdated = controls.update();

      if (hasAnimations || controlsUpdated || needsRenderRef.current) {
        if (hasAnimations) {
          animatedObjectsRef.current.forEach((anim) => anim.update(time, delta));
        }
        renderer.render(scene, camera);
        needsRenderRef.current = false;
      }

      animFrameIdRef.current = requestAnimationFrame(animate);
    };
    animate();

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', handleResize);
      if (animFrameIdRef.current) cancelAnimationFrame(animFrameIdRef.current);
      if (rendererRef.current && rendererRef.current.domElement) {
        mount.removeChild(rendererRef.current.domElement);
        rendererRef.current.dispose();
      }
    };
  }, []);

  // Update Dynamic Day/Night Lighting Mode & Grid
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;

    const isNight = lightingMode === 'night';
    const bgColor = isNight ? 0x27302c : 0xfaf6f0;
    const fogColor = isNight ? 0x27302c : 0xfaf6f0;

    if (scene.background instanceof THREE.Color) {
      scene.background.set(bgColor);
    } else {
      scene.background = new THREE.Color(bgColor);
    }

    if (scene.fog instanceof THREE.FogExp2) {
      scene.fog.color.set(fogColor);
      scene.fog.density = isNight ? 0.00035 : 0.0006;
    }

    if (ambientLightRef.current) {
      ambientLightRef.current.color.set(isNight ? 0x6e8077 : 0xfcf9f2);
      ambientLightRef.current.intensity = isNight ? 0.85 : 0.95;
    }

    if (sunLightRef.current) {
      sunLightRef.current.color.set(isNight ? 0xc0d0e0 : 0xfff7ea);
      sunLightRef.current.intensity = isNight ? 0.9 : 1.35;
    }

    if (fillLightRef.current) {
      fillLightRef.current.color.set(isNight ? 0x4a5952 : 0xe5ede7);
      fillLightRef.current.intensity = isNight ? 0.5 : 0.45;
    }

    if (baseFloorMeshRef.current && baseFloorMeshRef.current.material instanceof THREE.MeshStandardMaterial) {
      baseFloorMeshRef.current.material.color.set(isNight ? 0x424c47 : 0xede7df);
    }

    if (gridMeshRef.current) {
      scene.remove(gridMeshRef.current);
      gridMeshRef.current.geometry.dispose();
      if (Array.isArray(gridMeshRef.current.material)) {
        gridMeshRef.current.material.forEach((m) => m.dispose());
      } else {
        gridMeshRef.current.material.dispose();
      }
      const grid = new THREE.GridHelper(
        1200,
        48,
        isNight ? 0x6e7b74 : 0xd2c9bd,
        isNight ? 0x525e58 : 0xe2dcce
      );
      grid.position.set(300, 0, 200);
      grid.visible = showFloorGrid;
      scene.add(grid);
      gridMeshRef.current = grid;
    }
  }, [lightingMode, showFloorGrid]);

  // Update Dynamic Lights Visibility
  useEffect(() => {
    lightsGroupRef.current.visible = showDynamicLights;
  }, [showDynamicLights]);

  // Update Climate Overlay Visibility
  useEffect(() => {
    climateOverlayGroupRef.current.visible = showClimateOverlay;
  }, [showClimateOverlay]);

  // Update Decor Visibility
  useEffect(() => {
    architecturalDecorGroupRef.current.visible = showDecor;
  }, [showDecor]);

  // =========================================================================
  // 1. ARCHITECTURAL CUTAWAY WALLS & SMART DOOR OPENINGS
  // =========================================================================
  useEffect(() => {
    const group = wallsGroupRef.current;
    while (group.children.length > 0) {
      const obj = group.children[0] as THREE.Mesh;
      group.remove(obj);
      if (obj.geometry) obj.geometry.dispose();
    }

    // Cutaway architectural wall specifications per brief:
    // wallHeight = 25, top trim = 1.6, baseboard = 2.0
    const wallHeight = 25;
    const wallThickness = 7.0;
    const doorwayGapWidth = 30; // Width of door opening
    const isNight = lightingMode === 'night';

    const wallMaterial = getSharedMaterial(
      `wall_${isNight ? 'night' : 'day'}`,
      () => new THREE.MeshStandardMaterial({
        color: isNight ? 0xbac4be : 0xf7f4ed,
        roughness: 0.88,
        metalness: 0.04,
      })
    );
    const capMaterial = getSharedMaterial(
      `cap_${isNight ? 'night' : 'day'}`,
      () => new THREE.MeshStandardMaterial({
        color: isNight ? 0x526059 : 0x4a554f,
        roughness: 0.55,
        metalness: 0.12,
      })
    );
    const baseboardMaterial = getSharedMaterial(
      `baseboard_${isNight ? 'night' : 'day'}`,
      () => new THREE.MeshStandardMaterial({
        color: isNight ? 0x98a39c : 0xded7cc,
        roughness: 0.72,
      })
    );

    const doorDevs = devices.filter(isDoorDevice);

    walls.forEach((wall) => {
      const dx = wall.x2 - wall.x1;
      const dz = wall.y2 - wall.y1;
      const totalLength = Math.hypot(dx, dz);
      if (totalLength < 1) return;

      const angle = Math.atan2(dz, dx);
      const ux = dx / totalLength;
      const uz = dz / totalLength;

      // Find all door devices along this wall segment within distance < 30 units
      const doorGaps: { start: number; end: number }[] = [];

      doorDevs.forEach((dDev) => {
        const vx = dDev.x - wall.x1;
        const vz = dDev.y - wall.y1;
        const s = vx * ux + vz * uz;
        const t = s / totalLength;

        if (t >= 0.04 && t <= 0.96) {
          const px = wall.x1 + s * ux;
          const pz = wall.y1 + s * uz;
          const dist = Math.hypot(dDev.x - px, dDev.y - pz);

          if (dist < 30) {
            // Cutout gap centered at s
            const halfGap = doorwayGapWidth / 2;
            const gStart = Math.max(0, s - halfGap);
            const gEnd = Math.min(totalLength, s + halfGap);
            doorGaps.push({ start: gStart, end: gEnd });
          }
        }
      });

      // Sort and merge overlapping gaps
      doorGaps.sort((a, b) => a.start - b.start);
      const mergedGaps: { start: number; end: number }[] = [];
      doorGaps.forEach((gap) => {
        if (mergedGaps.length === 0) {
          mergedGaps.push(gap);
        } else {
          const last = mergedGaps[mergedGaps.length - 1];
          if (gap.start <= last.end + 2) {
            last.end = Math.max(last.end, gap.end);
          } else {
            mergedGaps.push(gap);
          }
        }
      });

      // Build wall segments for non-gap intervals
      const segments: { start: number; end: number }[] = [];
      let currentPos = 0;
      mergedGaps.forEach((gap) => {
        if (gap.start > currentPos + 2) {
          segments.push({ start: currentPos, end: gap.start });
        }
        currentPos = gap.end;
      });
      if (currentPos < totalLength - 2) {
        segments.push({ start: currentPos, end: totalLength });
      }

      // If no door gaps exist, create single full segment
      if (segments.length === 0 && mergedGaps.length === 0) {
        segments.push({ start: 0, end: totalLength });
      }

      // Render each split wall segment
      segments.forEach((seg) => {
        const segLen = seg.end - seg.start;
        if (segLen < 2) return;

        const midS = (seg.start + seg.end) / 2;
        const midX = wall.x1 + midS * ux;
        const midZ = wall.y1 + midS * uz;

        // 1. Baseboard Trim at bottom
        const baseGeom = new THREE.BoxGeometry(segLen, 2.0, wallThickness + 0.6);
        const baseMesh = new THREE.Mesh(baseGeom, baseboardMaterial);
        baseMesh.position.set(midX, 1.0, midZ);
        baseMesh.rotation.y = -angle;
        baseMesh.receiveShadow = true;
        group.add(baseMesh);

        // 2. Cutaway Architectural Wall Block (Height = 22 units)
        const wallGeom = new THREE.BoxGeometry(segLen, wallHeight, wallThickness);
        const wallMesh = new THREE.Mesh(wallGeom, wallMaterial);
        wallMesh.position.set(midX, wallHeight / 2, midZ);
        wallMesh.rotation.y = -angle;
        wallMesh.castShadow = true;
        wallMesh.receiveShadow = true;
        group.add(wallMesh);

        // 3. Top Cap Trim (Height = 1.6 units)
        const topTrimGeom = new THREE.BoxGeometry(segLen + 0.4, 1.6, wallThickness + 0.6);
        const topTrim = new THREE.Mesh(topTrimGeom, capMaterial);
        topTrim.position.set(midX, wallHeight + 0.8, midZ);
        topTrim.rotation.y = -angle;
        topTrim.castShadow = true;
        group.add(topTrim);
      });
    });
  }, [walls, devices, isDoorDevice, lightingMode]);

  // =========================================================================
  // 2. ROOM FLOOR PLATES & THERMAL HEATMAP (HomeSmartMesh Styled)
  // =========================================================================
  useEffect(() => {
    const floorPlateGroup = floorPlatesGroupRef.current;
    const climateGroup = climateOverlayGroupRef.current;
    const isNight = lightingMode === 'night';

    // Clear old meshes and dispose geometries
    while (floorPlateGroup.children.length > 0) {
      const obj = floorPlateGroup.children[0] as THREE.Mesh;
      floorPlateGroup.remove(obj);
      if (obj.geometry) obj.geometry.dispose();
    }
    while (climateGroup.children.length > 0) {
      const obj = climateGroup.children[0] as THREE.Mesh;
      climateGroup.remove(obj);
      if (obj.geometry) obj.geometry.dispose();
    }

    roomTelemetry.forEach((roomData) => {
      const roomLower = roomData.room.toLowerCase();
      const isWetArea = 
        roomLower.includes('bếp') || 
        roomLower.includes('kitchen') || 
        roomLower.includes('tắm') || 
        roomLower.includes('bath') || 
        roomLower.includes('vệ sinh');

      const floorTex = getFloorTileTexture(isWetArea ? 'tile' : 'wood', isNight);
      floorTex.repeat.set(Math.max(1, roomData.width / 48), Math.max(1, roomData.depth / 48));

      // Dynamic Room Thermal / Climate Heatmap Floor Tint & Alert Status
      let tintColor = 0x7ca887; // Organic Sage (Comfortable 23-26.5°C)
      let iconType: 'temp' | 'eco' | 'warn' = 'eco';
      let infoText = `${roomData.avgTemp ?? 25}°C`;
      if (roomData.avgHumidity) infoText += ` · ${roomData.avgHumidity}% RH`;

      if (roomData.hasGasWarning) {
        tintColor = 0xc46955; // Terracotta alert
        iconType = 'warn';
        infoText = '⚠️ Cảnh báo khí gas';
      } else if (roomData.avgTemp !== undefined) {
        if (roomData.avgTemp < 22) {
          tintColor = 0x7e9fa3; // Cool Slate Teal
          iconType = 'temp';
        } else if (roomData.avgTemp > 29.5) {
          tintColor = 0xc46955; // Terracotta (Hot)
          iconType = 'warn';
        } else if (roomData.avgTemp > 26.5) {
          tintColor = 0xd4a366; // Warm Amber Gold
          iconType = 'temp';
        }
      }

      // Check if this room has valid 4-wall corner polygon
      if (roomData.corners && roomData.corners.length >= 3) {
        // Build THREE.Shape matching the room boundary polygon
        const shape = new THREE.Shape();
        shape.moveTo(roomData.corners[0].x, -roomData.corners[0].y);
        for (let i = 1; i < roomData.corners.length; i++) {
          shape.lineTo(roomData.corners[i].x, -roomData.corners[i].y);
        }
        shape.closePath();

        // 1. 3D Floor Plate with ShapeGeometry at Y = 0.25 units above base ground
        const plateGeo = new THREE.ShapeGeometry(shape);
        plateGeo.rotateX(-Math.PI / 2);
        plateGeo.computeVertexNormals();

        const plateMat = getSharedMaterial(
          `floor_plate_${isWetArea ? 'tile' : 'wood'}_${isNight ? 'night' : 'day'}`,
          () => new THREE.MeshStandardMaterial({
            color: isWetArea 
              ? (isNight ? 0x8e9892 : 0xdbd6cc) 
              : (isNight ? 0x948877 : 0xe2d9cc),
            map: floorTex,
            roughness: 0.75,
            metalness: 0.05,
          })
        );
        plateMat.map = floorTex;

        const plateMesh = new THREE.Mesh(plateGeo, plateMat);
        plateMesh.position.set(0, 0.25, 0);
        plateMesh.receiveShadow = true;
        floorPlateGroup.add(plateMesh);

        // 2. Bevel Trim Line
        const trimEdges = new THREE.EdgesGeometry(plateGeo);
        const trimMat = getSharedMaterial(
          `floor_trim_line_${isNight ? 'night' : 'day'}`,
          () => new THREE.LineBasicMaterial({
            color: isNight ? 0x6a756f : 0xc7beaf,
            linewidth: 2,
          })
        );
        const trimLine = new THREE.LineSegments(trimEdges, trimMat);
        trimLine.position.set(0, 0.26, 0);
        floorPlateGroup.add(trimLine);

        // 3. Dynamic Room Thermal / Climate Heatmap Floor Tint
        const heatShapeGeo = new THREE.ShapeGeometry(shape);
        heatShapeGeo.rotateX(-Math.PI / 2);
        const heatMat = new THREE.MeshBasicMaterial({
          color: tintColor,
          transparent: true,
          opacity: roomData.hasGasWarning ? 0.35 : isNight ? 0.18 : 0.14,
          depthWrite: false,
        });
        const heatMesh = new THREE.Mesh(heatShapeGeo, heatMat);
        heatMesh.position.set(0, 0.28, 0);
        climateGroup.add(heatMesh);

        // Room Badge at exact geometric center (cx, cy)
        const badgeTex = getRoomBadgeTexture(roomData.room, infoText, iconType, isNight);
        const badgeMat = new THREE.SpriteMaterial({
          map: badgeTex,
          transparent: true,
          opacity: 0.92,
          depthWrite: false,
        });
        const sprite = new THREE.Sprite(badgeMat);
        sprite.scale.set(36, 10, 1);
        sprite.position.set(roomData.centerX, 6.5, roomData.centerY);
        climateGroup.add(sprite);
      } else {
        // Fallback for non-polygon bounds
        const plateGeo = new THREE.BoxGeometry(roomData.width, 0.25, roomData.depth);
        const plateMat = getSharedMaterial(
          `floor_plate_${isWetArea ? 'tile' : 'wood'}_${isNight ? 'night' : 'day'}`,
          () => new THREE.MeshStandardMaterial({
            color: isWetArea 
              ? (isNight ? 0x8e9892 : 0xdbd6cc) 
              : (isNight ? 0x948877 : 0xe2d9cc),
            map: floorTex,
            roughness: 0.75,
            metalness: 0.05,
          })
        );
        plateMat.map = floorTex;
        const plateMesh = new THREE.Mesh(plateGeo, plateMat);
        plateMesh.position.set(roomData.centerX, 0.125, roomData.centerY);
        plateMesh.receiveShadow = true;
        floorPlateGroup.add(plateMesh);

        const trimGeo = new THREE.BoxGeometry(roomData.width + 1.2, 0.25, roomData.depth + 1.2);
        const trimMat = getSharedMaterial(
          `floor_trim_${isNight ? 'night' : 'day'}`,
          () => new THREE.MeshStandardMaterial({
            color: isNight ? 0x6a756f : 0xc7beaf,
            roughness: 0.8,
          })
        );
        const trimMesh = new THREE.Mesh(trimGeo, trimMat);
        trimMesh.position.set(roomData.centerX, 0.1, roomData.centerY);
        floorPlateGroup.add(trimMesh);

        const heatGeo = new THREE.PlaneGeometry(roomData.width - 2, roomData.depth - 2);
        const heatMat = new THREE.MeshBasicMaterial({
          color: tintColor,
          transparent: true,
          opacity: roomData.hasGasWarning ? 0.35 : isNight ? 0.18 : 0.14,
          depthWrite: false,
        });
        const heatMesh = new THREE.Mesh(heatGeo, heatMat);
        heatMesh.rotation.x = -Math.PI / 2;
        heatMesh.position.set(roomData.centerX, 0.28, roomData.centerY);
        climateGroup.add(heatMesh);

        const badgeTex = getRoomBadgeTexture(roomData.room, infoText, iconType, isNight);
        const badgeMat = new THREE.SpriteMaterial({
          map: badgeTex,
          transparent: true,
          opacity: 0.92,
          depthWrite: false,
        });
        const sprite = new THREE.Sprite(badgeMat);
        sprite.scale.set(36, 10, 1);
        sprite.position.set(roomData.centerX, 6.5, roomData.centerY - roomData.depth / 2 + 12);
        climateGroup.add(sprite);
      }
    });

    needsRenderRef.current = true;
  }, [roomTelemetry, lightingMode]);

  // =========================================================================
  // 3. MINIMALIST ARCHITECTURAL DECOR SILHOUETTES (Design.md Terra Aesthetic)
  // =========================================================================
  useEffect(() => {
    const group = architecturalDecorGroupRef.current;
    while (group.children.length > 0) {
      const obj = group.children[0] as THREE.Mesh;
      group.remove(obj);
      if (obj.geometry) obj.geometry.dispose();
    }

    const oakMat = getSharedMaterial('decor_oak', () => new THREE.MeshStandardMaterial({ color: 0xa88358, roughness: 0.7, metalness: 0.05 }));
    const darkWoodMat = getSharedMaterial('decor_darkwood', () => new THREE.MeshStandardMaterial({ color: 0x5a4836, roughness: 0.65 }));
    const sofaFabricMat = getSharedMaterial('decor_sofa_fabric', () => new THREE.MeshStandardMaterial({ color: 0xe2dcd2, roughness: 0.9 }));
    const sageMat = getSharedMaterial('decor_sage', () => new THREE.MeshStandardMaterial({ color: 0x7a9182, roughness: 0.85 }));
    const terracottaMat = getSharedMaterial('decor_terracotta', () => new THREE.MeshStandardMaterial({ color: 0xb36f56, roughness: 0.8 }));
    const rugMat = getSharedMaterial('decor_rug', () => new THREE.MeshStandardMaterial({ color: 0xede6db, roughness: 0.95 }));
    const metalDarkMat = getSharedMaterial('decor_metal_dark', () => new THREE.MeshStandardMaterial({ color: 0x242826, roughness: 0.4, metalness: 0.6 }));
    const screenMat = getSharedMaterial('decor_screen', () => new THREE.MeshStandardMaterial({ color: 0x181c1a, roughness: 0.2, metalness: 0.8 }));
    const lampShadeMat = getSharedMaterial('decor_lamp_shade', () => new THREE.MeshStandardMaterial({ color: 0xfbf8f2, roughness: 0.5 }));
    const lampStemMat = getSharedMaterial('decor_lamp_stem', () => new THREE.MeshStandardMaterial({ color: 0x8a7238, metalness: 0.8, roughness: 0.3 }));
    const countertopMat = getSharedMaterial('decor_countertop', () => new THREE.MeshStandardMaterial({ color: 0xf5f0e6, roughness: 0.4, metalness: 0.05 }));
    const cooktopMat = getSharedMaterial('decor_cooktop', () => new THREE.MeshStandardMaterial({ color: 0x222624, roughness: 0.3, metalness: 0.7 }));

    roomTelemetry.forEach((roomData) => {
      const rName = roomData.room.toLowerCase();
      const cX = roomData.centerX;
      const cZ = roomData.centerY;

      // 1. LIVING ROOM (Phòng khách)
      if (rName.includes('khách') || rName.includes('living')) {
        // Living room area rug: width ~110 - 135, depth ~80 - 95
        const rugGeo = new THREE.BoxGeometry(120, 0.2, 88);
        const rug = new THREE.Mesh(rugGeo, rugMat);
        rug.position.set(cX, 0.28, cZ + 6);
        rug.receiveShadow = true;
        group.add(rug);

        // Comfortable 3-seater sofa: width ~80 - 95, depth ~32 - 38, height ~18 - 22
        // Seat base
        const sofaBaseGeo = new THREE.BoxGeometry(86, 7.0, 32);
        const sofaBase = new THREE.Mesh(sofaBaseGeo, sofaFabricMat);
        sofaBase.position.set(cX, 4.0, cZ + 24);
        sofaBase.castShadow = true;
        group.add(sofaBase);

        // Backrest
        const sofaBackGeo = new THREE.BoxGeometry(86, 13.0, 8.0);
        const sofaBack = new THREE.Mesh(sofaBackGeo, sofaFabricMat);
        sofaBack.position.set(cX, 12.0, cZ + 36);
        sofaBack.castShadow = true;
        group.add(sofaBack);

        // Left armrest
        const armLeftGeo = new THREE.BoxGeometry(6.5, 10.0, 34);
        const armLeft = new THREE.Mesh(armLeftGeo, sofaFabricMat);
        armLeft.position.set(cX - 43, 8.0, cZ + 25);
        armLeft.castShadow = true;
        group.add(armLeft);

        // Right armrest
        const armRightGeo = new THREE.BoxGeometry(6.5, 10.0, 34);
        const armRight = new THREE.Mesh(armRightGeo, sofaFabricMat);
        armRight.position.set(cX + 43, 8.0, cZ + 25);
        armRight.castShadow = true;
        group.add(armRight);

        // Accent cushions (2 cushions: Sage and Terracotta)
        const cush1Geo = new THREE.BoxGeometry(14, 10, 5.0);
        const cush1 = new THREE.Mesh(cush1Geo, sageMat);
        cush1.position.set(cX - 24, 11.5, cZ + 31);
        group.add(cush1);

        const cush2Geo = new THREE.BoxGeometry(14, 10, 5.0);
        const cush2 = new THREE.Mesh(cush2Geo, terracottaMat);
        cush2.position.set(cX + 24, 11.5, cZ + 31);
        group.add(cush2);

        // Modern coffee table: width ~48 - 60, depth ~28 - 34, height ~9 - 11
        const tableBaseGeo = new THREE.BoxGeometry(46, 7.5, 26);
        const tableBase = new THREE.Mesh(tableBaseGeo, darkWoodMat);
        tableBase.position.set(cX, 4.0, cZ - 2);
        tableBase.castShadow = true;
        group.add(tableBase);

        const tableTopGeo = new THREE.BoxGeometry(54, 2.0, 30);
        const tableTop = new THREE.Mesh(tableTopGeo, oakMat);
        tableTop.position.set(cX, 8.8, cZ - 2);
        tableTop.castShadow = true;
        group.add(tableTop);

        // TV entertainment credenza with TV screen: credenza width ~65 - 80, flat TV screen width ~45 - 55, height ~26
        const credenzaGeo = new THREE.BoxGeometry(72, 10.0, 18);
        const credenzaMesh = new THREE.Mesh(credenzaGeo, darkWoodMat);
        credenzaMesh.position.set(cX, 5.2, cZ - 36);
        credenzaMesh.castShadow = true;
        group.add(credenzaMesh);

        // Flat TV Screen
        const tvStandGeo = new THREE.BoxGeometry(16, 2.0, 8.0);
        const tvStand = new THREE.Mesh(tvStandGeo, metalDarkMat);
        tvStand.position.set(cX, 11.2, cZ - 36);
        group.add(tvStand);

        const tvScreenGeo = new THREE.BoxGeometry(50, 26, 2.5);
        const tvScreen = new THREE.Mesh(tvScreenGeo, screenMat);
        tvScreen.position.set(cX, 24.5, cZ - 36);
        tvScreen.castShadow = true;
        group.add(tvScreen);

        // Floor plant pot: cylinder radius ~6.5, foliage sphere radius ~8.5, height ~22
        const potGeo = new THREE.CylinderGeometry(6.5, 5.0, 10, 20);
        const pot = new THREE.Mesh(potGeo, terracottaMat);
        pot.position.set(cX + 48, 5.2, cZ + 24);
        pot.castShadow = true;
        group.add(pot);

        const plantGeo = new THREE.SphereGeometry(8.5, 16, 16);
        const plant = new THREE.Mesh(plantGeo, sageMat);
        plant.position.set(cX + 48, 16.5, cZ + 24);
        plant.castShadow = true;
        group.add(plant);
      }

      // 2. BEDROOM (Phòng ngủ)
      else if (rName.includes('ngủ') || rName.includes('bed')) {
        // Bedroom rug under bed: width ~110 - 130, depth ~110 - 130
        const bedRugGeo = new THREE.BoxGeometry(120, 0.2, 120);
        const bedRug = new THREE.Mesh(bedRugGeo, rugMat);
        bedRug.position.set(cX, 0.28, cZ + 4);
        bedRug.receiveShadow = true;
        group.add(bedRug);

        // Large double bed: width ~75 - 90, length ~95 - 115, height ~18 - 22
        // Bed platform frame
        const bedFrameGeo = new THREE.BoxGeometry(84, 9.0, 106);
        const bedFrame = new THREE.Mesh(bedFrameGeo, oakMat);
        bedFrame.position.set(cX, 4.8, cZ + 4);
        bedFrame.castShadow = true;
        group.add(bedFrame);

        // Headboard: width ~80 - 95, height ~32 - 36, thickness ~4
        const headGeo = new THREE.BoxGeometry(88, 34, 4.0);
        const head = new THREE.Mesh(headGeo, oakMat);
        head.position.set(cX, 17.2, cZ - 48);
        head.castShadow = true;
        group.add(head);

        // Mattress & Duvet
        const duvetGeo = new THREE.BoxGeometry(78, 8.5, 96);
        const duvet = new THREE.Mesh(duvetGeo, sofaFabricMat);
        duvet.position.set(cX, 12.0, cZ + 7);
        duvet.castShadow = true;
        group.add(duvet);

        // Pillows (2x)
        const pillow1Geo = new THREE.BoxGeometry(26, 5.0, 16);
        const pillow1 = new THREE.Mesh(pillow1Geo, sofaFabricMat);
        pillow1.position.set(cX - 20, 17.0, cZ - 26);
        pillow1.castShadow = true;
        group.add(pillow1);

        const pillow2Geo = new THREE.BoxGeometry(26, 5.0, 16);
        const pillow2 = new THREE.Mesh(pillow2Geo, sofaFabricMat);
        pillow2.position.set(cX + 20, 17.0, cZ - 26);
        pillow2.castShadow = true;
        group.add(pillow2);

        // Folded duvet runner (Sage Green)
        const runnerGeo = new THREE.BoxGeometry(78.5, 1.0, 26);
        const runner = new THREE.Mesh(runnerGeo, sageMat);
        runner.position.set(cX, 16.5, cZ + 36);
        group.add(runner);

        // Two bedside nightstands (left & right): width ~16 - 20, depth ~16 - 20, height ~14 with bedside table lamps
        // Left nightstand
        const standLeftGeo = new THREE.BoxGeometry(18, 14, 18);
        const standLeft = new THREE.Mesh(standLeftGeo, darkWoodMat);
        standLeft.position.set(cX - 54, 7.2, cZ - 40);
        standLeft.castShadow = true;
        group.add(standLeft);

        // Left lamp
        const lampLeftBaseGeo = new THREE.CylinderGeometry(2.8, 3.2, 1.8, 16);
        const lampLeftBase = new THREE.Mesh(lampLeftBaseGeo, lampStemMat);
        lampLeftBase.position.set(cX - 54, 15.1, cZ - 40);
        group.add(lampLeftBase);

        const lampLeftShadeGeo = new THREE.ConeGeometry(4.2, 5.5, 16);
        const lampLeftShade = new THREE.Mesh(lampLeftShadeGeo, lampShadeMat);
        lampLeftShade.position.set(cX - 54, 19.5, cZ - 40);
        group.add(lampLeftShade);

        // Right nightstand
        const standRightGeo = new THREE.BoxGeometry(18, 14, 18);
        const standRight = new THREE.Mesh(standRightGeo, darkWoodMat);
        standRight.position.set(cX + 54, 7.2, cZ - 40);
        standRight.castShadow = true;
        group.add(standRight);

        // Right lamp
        const lampRightBaseGeo = new THREE.CylinderGeometry(2.8, 3.2, 1.8, 16);
        const lampRightBase = new THREE.Mesh(lampRightBaseGeo, lampStemMat);
        lampRightBase.position.set(cX + 54, 15.1, cZ - 40);
        group.add(lampRightBase);

        const lampRightShadeGeo = new THREE.ConeGeometry(4.2, 5.5, 16);
        const lampRightShade = new THREE.Mesh(lampRightShadeGeo, lampShadeMat);
        lampRightShade.position.set(cX + 54, 19.5, cZ - 40);
        group.add(lampRightShade);
      }

      // 3. KITCHEN & DINING (Phòng bếp & Phòng ăn)
      else if (rName.includes('bếp') || rName.includes('kitchen') || rName.includes('ăn') || rName.includes('dining')) {
        // Kitchen island / counter: width ~85 - 110, depth ~32 - 40, height ~18 - 20 (countertop, cooktop stove surface)
        const islandBaseGeo = new THREE.BoxGeometry(95, 17, 36);
        const islandBase = new THREE.Mesh(islandBaseGeo, darkWoodMat);
        islandBase.position.set(cX, 8.8, cZ + 26);
        islandBase.castShadow = true;
        group.add(islandBase);

        const islandTopGeo = new THREE.BoxGeometry(100, 2.4, 40);
        const islandTop = new THREE.Mesh(islandTopGeo, countertopMat);
        islandTop.position.set(cX, 18.2, cZ + 26);
        islandTop.castShadow = true;
        group.add(islandTop);

        // Cooktop stove surface
        const cooktopGeo = new THREE.BoxGeometry(34, 0.4, 22);
        const cooktop = new THREE.Mesh(cooktopGeo, cooktopMat);
        cooktop.position.set(cX - 24, 19.5, cZ + 26);
        group.add(cooktop);

        // Dining table: width ~60 - 75, depth ~35 - 45, height ~16 with dining chairs
        const tableBaseGeo = new THREE.BoxGeometry(56, 14, 30);
        const tableBase = new THREE.Mesh(tableBaseGeo, darkWoodMat);
        tableBase.position.set(cX, 7.2, cZ - 26);
        tableBase.castShadow = true;
        group.add(tableBase);

        const tableTopGeo = new THREE.BoxGeometry(68, 2.0, 42);
        const tableTop = new THREE.Mesh(tableTopGeo, oakMat);
        tableTop.position.set(cX, 15.2, cZ - 26);
        tableTop.castShadow = true;
        group.add(tableTop);

        // 4 Dining Chairs around table
        [
          { x: cX - 20, z: cZ - 8, backZ: cZ - 2 },
          { x: cX + 20, z: cZ - 8, backZ: cZ - 2 },
          { x: cX - 20, z: cZ - 44, backZ: cZ - 50 },
          { x: cX + 20, z: cZ - 44, backZ: cZ - 50 },
        ].forEach((pos) => {
          const seatGeo = new THREE.BoxGeometry(12, 8.5, 12);
          const seat = new THREE.Mesh(seatGeo, oakMat);
          seat.position.set(pos.x, 4.5, pos.z);
          seat.castShadow = true;
          group.add(seat);

          const backGeo = new THREE.BoxGeometry(12, 10, 2.5);
          const back = new THREE.Mesh(backGeo, oakMat);
          back.position.set(pos.x, 12.0, pos.backZ);
          back.castShadow = true;
          group.add(back);
        });
      }

      // 4. OTHER / ENTRY / BALCONY (Lối vào / Hành lang / Ban công)
      else {
        // Entry bench: width ~38 - 48, depth ~14 - 18, height ~9 - 11
        const benchBaseGeo = new THREE.BoxGeometry(42, 8.0, 16);
        const benchBase = new THREE.Mesh(benchBaseGeo, oakMat);
        benchBase.position.set(cX - 10, 4.2, cZ - 12);
        benchBase.castShadow = true;
        group.add(benchBase);

        const benchCushGeo = new THREE.BoxGeometry(40, 2.0, 15);
        const benchCush = new THREE.Mesh(benchCushGeo, sofaFabricMat);
        benchCush.position.set(cX - 10, 9.2, cZ - 12);
        benchCush.castShadow = true;
        group.add(benchCush);

        // Ceramic planter pot: cylinder radius ~7.5, foliage radius ~9.5
        const potGeo = new THREE.CylinderGeometry(7.5, 5.8, 14, 20);
        const pot = new THREE.Mesh(potGeo, terracottaMat);
        pot.position.set(cX + 18, 7.2, cZ + 14);
        pot.castShadow = true;
        group.add(pot);

        const plantGeo = new THREE.SphereGeometry(9.5, 16, 16);
        const plant = new THREE.Mesh(plantGeo, sageMat);
        plant.position.set(cX + 18, 19.5, cZ + 14);
        plant.castShadow = true;
        group.add(plant);
      }
    });

    needsRenderRef.current = true;
  }, [roomTelemetry]);

  // =========================================================================
  // 4. INTERACTIVE 3D DEVICES, LIGHT FIXTURES, SMART DOORS & CONTROLS
  // =========================================================================
  useEffect(() => {
    const devGroup = devicesGroupRef.current;
    const lightGroup = lightsGroupRef.current;
    const isNight = lightingMode === 'night';

    deviceMeshesMap.current.clear();
    animatedObjectsRef.current = [];

    // Clear old objects
    while (devGroup.children.length > 0) devGroup.remove(devGroup.children[0]);
    while (lightGroup.children.length > 0) lightGroup.remove(lightGroup.children[0]);

    devices.forEach((dev) => {
      const isSelected = selectedDeviceId === dev.id;
      const isHovered = hoveredDev?.id === dev.id;
      const fault = faults[dev.id] || 'none';
      const state = dev.state || {};

      const devContainer = new THREE.Group();

      // Check if this device is snapped and aligned to a wall doorway
      const wallAlignment = doorAlignments.get(dev.id);
      if (wallAlignment) {
        devContainer.position.set(wallAlignment.x, 0, wallAlignment.z);
        devContainer.rotation.y = wallAlignment.rotationY;
      } else {
        devContainer.position.set(dev.x, 0, dev.y);
      }

      devContainer.userData = { deviceId: dev.id, device: dev };

      // =========================================================================
      // A. LIGHT FIXTURE (Pendant Cords dropping from ~44 down to ~28 + Glow)
      // =========================================================================
      if (dev.kind === 'light') {
        const isPowerOn = state.power === true;
        const brightness = state.brightness ?? 80;
        const lampHeight = 28;
        const ceilingHeight = 44;
        const cordLength = ceilingHeight - lampHeight;

        // Ceiling Rose anchor
        const roseGeo = new THREE.CylinderGeometry(4.5, 4.5, 1.6, 20);
        const roseMat = new THREE.MeshStandardMaterial({ color: 0x333b37, roughness: 0.5 });
        const rose = new THREE.Mesh(roseGeo, roseMat);
        rose.position.set(0, ceilingHeight, 0);
        devContainer.add(rose);

        // Suspension cord dropping from ceiling (44) down to lampshade (28)
        const cordGeo = new THREE.CylinderGeometry(0.6, 0.6, cordLength, 8);
        const cordMat = new THREE.MeshStandardMaterial({ color: 0x2e3230, metalness: 0.8, roughness: 0.3 });
        const cord = new THREE.Mesh(cordGeo, cordMat);
        cord.position.set(0, lampHeight + cordLength / 2, 0);
        devContainer.add(cord);

        // Pendant Lampshade (Forest Green #4a7c59 per Design.md) - radius 15, height 12
        const shadeGeo = new THREE.ConeGeometry(15, 12, 28, 1, true);
        const shadeMat = new THREE.MeshStandardMaterial({
          color: 0x4a7c59,
          roughness: 0.35,
          metalness: 0.15,
          side: THREE.DoubleSide,
        });
        const shade = new THREE.Mesh(shadeGeo, shadeMat);
        shade.position.set(0, lampHeight, 0);
        shade.castShadow = true;
        devContainer.add(shade);

        // Shade Top Brass Ring (#705c30) - radius 3.0, height 2.0
        const ringGeo = new THREE.CylinderGeometry(3.0, 3.0, 2.0, 20);
        const brassMat = new THREE.MeshStandardMaterial({ color: 0x705c30, metalness: 0.85, roughness: 0.25 });
        const ring = new THREE.Mesh(ringGeo, brassMat);
        ring.position.set(0, lampHeight + 5.5, 0);
        devContainer.add(ring);

        // Glowing Frosted Bulb Mesh - radius 4.5
        const emissivePower = isPowerOn 
          ? (isNight ? (brightness / 100) * 4.0 : Math.max(0.6, (brightness / 100) * 2.5))
          : 0;

        const bulbGeo = new THREE.SphereGeometry(4.5, 24, 24);
        const bulbMat = new THREE.MeshStandardMaterial({
          color: isPowerOn ? 0xfffae6 : 0xa69f94,
          emissive: isPowerOn ? (isNight ? 0xffd878 : 0xfffae6) : 0x000000,
          emissiveIntensity: emissivePower,
          roughness: 0.15,
        });
        const bulb = new THREE.Mesh(bulbGeo, bulbMat);
        bulb.position.set(0, lampHeight - 2.0, 0);
        devContainer.add(bulb);

        // Warm flare aura in Night Mode & Day Mode - radius 8.0
        if (isPowerOn) {
          const auraGeo = new THREE.SphereGeometry(8.0, 20, 20);
          const auraMat = new THREE.MeshBasicMaterial({
            color: isNight ? 0xffd878 : 0xfffae6,
            transparent: true,
            opacity: (isNight ? 0.28 : 0.15) * (brightness / 100),
            depthWrite: false,
          });
          const aura = new THREE.Mesh(auraGeo, auraMat);
          aura.position.set(0, lampHeight - 2.0, 0);
          devContainer.add(aura);
        }

        // High-fidelity Three.js PointLight with Warm Golden Tone
        if (isPowerOn) {
          const pointLightIntensity = isNight 
            ? (brightness / 100) * 8.5 
            : (brightness / 100) * 4.5;
          const illuminationDistance = isNight ? 420 : 300;
          const pointLightColor = isNight ? 0xffd878 : 0xfffae6;

          const pointLight = new THREE.PointLight(
            pointLightColor,
            pointLightIntensity,
            illuminationDistance,
            1.5
          );
          pointLight.position.set(dev.x, lampHeight - 2, dev.y);
          pointLight.castShadow = false;
          lightGroup.add(pointLight);

          // Floor illumination soft glow disc: radius ~45 - 65
          const floorGlowRadius = isNight 
            ? 50 + (brightness / 100) * 15 
            : 45 + (brightness / 100) * 20;
          const floorGlowOpacity = isNight 
            ? 0.32 * (brightness / 100) 
            : 0.18 * (brightness / 100);

          const floorGlowGeo = new THREE.CircleGeometry(floorGlowRadius, 32);
          const floorGlowMat = new THREE.MeshBasicMaterial({
            color: isNight ? 0xffd878 : 0xfffae6,
            transparent: true,
            opacity: floorGlowOpacity,
            depthWrite: false,
          });
          const floorGlow = new THREE.Mesh(floorGlowGeo, floorGlowMat);
          floorGlow.rotation.x = -Math.PI / 2;
          floorGlow.position.set(0, 0.26, 0);
          devContainer.add(floorGlow);
        }
      }

      // =========================================================================
      // B. ARCHITECTURAL SMART DOORWAY, FRAME & SWING MECHANISM
      // =========================================================================
      else if (isDoorDevice(dev)) {
        const isDoorOpen = state.open === true || (state.locked === false && state.open !== false);
        const isLocked = state.locked === true || (state.locked === undefined && !isDoorOpen);
        const isUnlocked = !isLocked;

        // Architectural Doorway Dimensions matching cutaway walls
        const doorwayWidth = 28;
        const doorwayHeight = 25;
        const frameDepth = 12.0;
        const jambThick = 2.4;

        const frameMat = new THREE.MeshStandardMaterial({
          color: 0x333b37,
          roughness: 0.6,
          metalness: 0.15,
        });
        const thresholdMat = new THREE.MeshStandardMaterial({
          color: 0x5a4d3b,
          roughness: 0.7,
        });
        const doorLeafMat = new THREE.MeshStandardMaterial({
          color: 0xf2eee6,
          roughness: 0.65,
          metalness: 0.05,
        });
        const brassMat = new THREE.MeshStandardMaterial({
          color: 0x8a7238,
          metalness: 0.85,
          roughness: 0.25,
        });
        const lockBodyMat = new THREE.MeshStandardMaterial({
          color: 0x222624,
          metalness: 0.85,
          roughness: 0.2,
        });

        // 1. Ground Threshold Step
        const threshGeo = new THREE.BoxGeometry(doorwayWidth + 2.0, 0.8, frameDepth + 2.0);
        const threshMesh = new THREE.Mesh(threshGeo, thresholdMat);
        threshMesh.position.set(0, 0.4, 0);
        threshMesh.receiveShadow = true;
        devContainer.add(threshMesh);

        // 2. Door Frame Outer Jambs (Left, Right, Top)
        const leftJambGeo = new THREE.BoxGeometry(jambThick, doorwayHeight, frameDepth);
        const leftJamb = new THREE.Mesh(leftJambGeo, frameMat);
        leftJamb.position.set(-doorwayWidth / 2 + jambThick / 2, doorwayHeight / 2, 0);
        leftJamb.castShadow = true;
        devContainer.add(leftJamb);

        const rightJambGeo = new THREE.BoxGeometry(jambThick, doorwayHeight, frameDepth);
        const rightJamb = new THREE.Mesh(rightJambGeo, frameMat);
        rightJamb.position.set(doorwayWidth / 2 - jambThick / 2, doorwayHeight / 2, 0);
        rightJamb.castShadow = true;
        devContainer.add(rightJamb);

        const topJambGeo = new THREE.BoxGeometry(doorwayWidth, jambThick, frameDepth);
        const topJamb = new THREE.Mesh(topJambGeo, frameMat);
        topJamb.position.set(0, doorwayHeight - jambThick / 2, 0);
        topJamb.castShadow = true;
        devContainer.add(topJamb);

        // 3. Dynamic Swing Hinge Group (Pivot at inside edge of left jamb)
        const hingePivotX = -doorwayWidth / 2 + jambThick;
        const doorHingeGroup = new THREE.Group();
        doorHingeGroup.position.set(hingePivotX, 0, 0);

        const leafWidth = doorwayWidth - jambThick * 2 - 0.4;
        const leafHeight = doorwayHeight - jambThick - 0.6;
        const leafThick = 2.4;

        // Dynamic Swing: Closed = 0 rad; Open = -1.22 rad (~70 deg)
        doorHingeGroup.rotation.y = isDoorOpen ? -1.22 : 0;

        // 3D Door Leaf Slab
        const leafGeo = new THREE.BoxGeometry(leafWidth, leafHeight, leafThick);
        const leafMesh = new THREE.Mesh(leafGeo, doorLeafMat);
        leafMesh.position.set(leafWidth / 2, leafHeight / 2 + 0.4, 0);
        leafMesh.castShadow = true;
        leafMesh.receiveShadow = true;
        doorHingeGroup.add(leafMesh);

        // 4. Smart Lock Assembly mounted onto the Door Leaf
        const lockX = leafWidth - 3.2;
        const lockY = 11.5;

        [-leafThick / 2 - 0.5, leafThick / 2 + 0.5].forEach((zLock, idx) => {
          const isFront = idx === 1;

          // Escutcheon plate
          const plateGeo = new THREE.BoxGeometry(3.6, 12.0, 1.0);
          const plate = new THREE.Mesh(plateGeo, lockBodyMat);
          plate.position.set(lockX, lockY, zLock);
          plate.castShadow = true;
          doorHingeGroup.add(plate);

          // Status LED Indicator Ring (#4a7c59 unlocked / #b45309 locked)
          const statusRingGeo = new THREE.TorusGeometry(1.0, 0.25, 8, 16);
          const statusRingMat = new THREE.MeshBasicMaterial({
            color: isLocked ? 0xb45309 : 0x4a7c59,
          });
          const statusRing = new THREE.Mesh(statusRingGeo, statusRingMat);
          statusRing.position.set(lockX, lockY + 3.6, zLock + (isFront ? 0.55 : -0.55));
          doorHingeGroup.add(statusRing);

          // Lever Handle
          const handleGroup = new THREE.Group();
          handleGroup.position.set(lockX, lockY, zLock + (isFront ? 0.6 : -0.6));

          const stemGeo = new THREE.CylinderGeometry(0.7, 0.7, 1.2, 12);
          const stem = new THREE.Mesh(stemGeo, lockBodyMat);
          stem.rotation.x = Math.PI / 2;
          handleGroup.add(stem);

          const leverGeo = new THREE.BoxGeometry(6.5, 1.2, 0.9);
          const lever = new THREE.Mesh(leverGeo, lockBodyMat);
          lever.position.set(-2.6, 0, isFront ? 0.5 : -0.5);
          handleGroup.add(lever);

          if (isUnlocked) {
            handleGroup.rotation.z = -0.52;
          }
          doorHingeGroup.add(handleGroup);

          // Key Cylinder with Brass Finish
          const cylGeo = new THREE.CylinderGeometry(0.7, 0.7, 1.0, 16);
          const cyl = new THREE.Mesh(cylGeo, brassMat);
          cyl.rotation.x = Math.PI / 2;
          cyl.position.set(lockX, lockY - 3.6, zLock + (isFront ? 0.45 : -0.45));
          doorHingeGroup.add(cyl);
        });

        devContainer.add(doorHingeGroup);
      }

      // =========================================================================
      // C. AIR CONDITIONER (Unit + Louver + Animated Airflow Stream)
      // =========================================================================
      else if (dev.kind === 'aircon') {
        const isPowerOn = state.power === true;
        const mode = state.mode || 'cool';

        // AC Body mounted high on wall (Y = 20)
        const acGeo = new THREE.BoxGeometry(52, 15, 13);
        const acMat = new THREE.MeshStandardMaterial({
          color: 0xfbf9f6,
          roughness: 0.25,
          metalness: 0.08,
        });
        const acMesh = new THREE.Mesh(acGeo, acMat);
        acMesh.position.set(0, 20, 0);
        acMesh.castShadow = true;
        devContainer.add(acMesh);

        // Louver slot at bottom
        const louverGeo = new THREE.BoxGeometry(46, 2.2, 1.5);
        const louverMat = new THREE.MeshStandardMaterial({ color: 0xd2cbbf, roughness: 0.5 });
        const louver = new THREE.Mesh(louverGeo, louverMat);
        louver.position.set(0, 13.8, 6.2);
        devContainer.add(louver);

        // Front Display Screen Plate
        const dispGeo = new THREE.PlaneGeometry(9.0, 4.0);
        const dispMat = new THREE.MeshBasicMaterial({
          color: isPowerOn ? 0x242826 : 0xd8d2c8,
        });
        const dispMesh = new THREE.Mesh(dispGeo, dispMat);
        dispMesh.position.set(10.0, 20, 6.6);
        devContainer.add(dispMesh);

        // Mode-colored LED & Status Glow
        const ledColor = !isPowerOn
          ? 0x94a3b8
          : mode === 'cool'
          ? 0x38bdf8
          : mode === 'heat'
          ? 0xd97736
          : 0x4a7c59;

        const ledGeo = new THREE.SphereGeometry(1.4, 16, 16);
        const ledMat = new THREE.MeshBasicMaterial({ color: ledColor });
        const led = new THREE.Mesh(ledGeo, ledMat);
        led.position.set(18.0, 17.5, 6.7);
        devContainer.add(led);

        // Animated Airflow Stream Waves when ON
        if (isPowerOn) {
          const airflowGroup = new THREE.Group();
          const waveCount = 3;
          const waveMeshes: THREE.Mesh[] = [];

          for (let i = 0; i < waveCount; i++) {
            const waveGeo = new THREE.PlaneGeometry(32, 12, 8, 4);
            const waveMat = new THREE.MeshBasicMaterial({
              color: mode === 'heat' ? 0xd97736 : 0x7ca982,
              transparent: true,
              opacity: 0.25,
              side: THREE.DoubleSide,
              depthWrite: false,
            });
            const wave = new THREE.Mesh(waveGeo, waveMat);
            wave.rotation.x = Math.PI / 3;
            wave.position.set(0, 12 - i * 6, 10 + i * 5);
            airflowGroup.add(wave);
            waveMeshes.push(wave);
          }
          devContainer.add(airflowGroup);

          // Continuous airflow animation
          animatedObjectsRef.current.push({
            id: `ac-flow-${dev.id}`,
            update: (time) => {
              waveMeshes.forEach((mesh, idx) => {
                const phase = (time * 1.8 + idx * 0.33) % 1.0;
                mesh.position.y = 14 - phase * 12;
                mesh.position.z = 8 + phase * 16;
                (mesh.material as THREE.MeshBasicMaterial).opacity = Math.sin(phase * Math.PI) * 0.28;
              });
            },
          });
        }
      }

      // =========================================================================
      // D. ROLLER BLINDS
      // =========================================================================
      else if (dev.kind === 'blind') {
        const position = state.position ?? 0;
        const maxDrop = 22;
        const currentDrop = Math.max(3, (position / 100) * maxDrop);
        const windowWidth = 32;

        // Top Cassette Box
        const cassetteGeo = new THREE.CylinderGeometry(2.0, 2.0, windowWidth, 16);
        const cassetteMat = new THREE.MeshStandardMaterial({ color: 0x4a554f, roughness: 0.4 });
        const cassette = new THREE.Mesh(cassetteGeo, cassetteMat);
        cassette.rotation.z = Math.PI / 2;
        cassette.position.set(0, 22, 0);
        cassette.castShadow = true;
        devContainer.add(cassette);

        // Dynamic Fabric Sheet
        const fabricGeo = new THREE.PlaneGeometry(windowWidth, currentDrop);
        const fabricMat = new THREE.MeshStandardMaterial({
          color: 0xdfd9ce,
          roughness: 0.85,
          side: THREE.DoubleSide,
        });
        const fabric = new THREE.Mesh(fabricGeo, fabricMat);
        fabric.position.set(0, 22 - currentDrop / 2, 0);
        fabric.castShadow = true;
        devContainer.add(fabric);
      }

      // =========================================================================
      // E. SMART SPEAKER (Acoustic Body + Pulsing Soundwave Rings)
      // =========================================================================
      else if (dev.kind === 'speaker') {
        const isPlaying = state.playing === true;
        const volume = state.volume ?? 50;

        // Acoustic Body - radius 8.5 - 9.5, height 20
        const spkGeo = new THREE.CylinderGeometry(8.5, 9.5, 20, 28);
        const spkMat = new THREE.MeshStandardMaterial({
          color: 0x363d39,
          roughness: 0.5,
          metalness: 0.25,
        });
        const spkMesh = new THREE.Mesh(spkGeo, spkMat);
        spkMesh.position.set(0, 10, 0);
        spkMesh.castShadow = true;
        devContainer.add(spkMesh);

        // Top Light Ring
        const ringGeo = new THREE.TorusGeometry(7.5, 0.9, 12, 28);
        const ringMat = new THREE.MeshBasicMaterial({
          color: isPlaying ? 0x38bdf8 : 0x4a7c59,
        });
        const ring = new THREE.Mesh(ringGeo, ringMat);
        ring.rotation.x = Math.PI / 2;
        ring.position.set(0, 20.2, 0);
        devContainer.add(ring);

        // Pulsing Soundwaves when playing
        if (isPlaying) {
          const waveGroup = new THREE.Group();
          const waveCount = 3;
          const waveRings: THREE.Mesh[] = [];

          for (let i = 0; i < waveCount; i++) {
            const waveGeo = new THREE.TorusGeometry(9.5, 0.7, 12, 32);
            const waveMat = new THREE.MeshBasicMaterial({
              color: 0x38bdf8,
              transparent: true,
              opacity: 0.6,
              depthWrite: false,
            });
            const wave = new THREE.Mesh(waveGeo, waveMat);
            wave.rotation.x = Math.PI / 2;
            waveGroup.add(wave);
            waveRings.push(wave);
          }
          devContainer.add(waveGroup);

          // Soundwave pulse animation
          animatedObjectsRef.current.push({
            id: `spk-wave-${dev.id}`,
            update: (time) => {
              waveRings.forEach((wRing, idx) => {
                const progress = (time * 1.5 + idx * 0.33) % 1.0;
                const scale = 1.0 + progress * 2.0;
                wRing.scale.set(scale, scale, scale);
                wRing.position.y = 20.2 + progress * 12.0;
                (wRing.material as THREE.MeshBasicMaterial).opacity = (1 - progress) * 0.7 * (volume / 100);
              });
            },
          });
        }
      }

      // =========================================================================
      // F. SMART FAN (Ceiling / Stand Fan with Rotating Aerofoil Blades)
      // =========================================================================
      else if (dev.kind === 'fan') {
        const isPowerOn = state.power === true;
        const fanSpeed = state.speed || (isPowerOn ? 1 : 0);

        // Fan mounting base on floor
        const fanBaseGeo = new THREE.CylinderGeometry(8.0, 9.5, 2.0, 24);
        const fanBaseMat = new THREE.MeshStandardMaterial({
          color: 0x2e3632,
          roughness: 0.4,
          metalness: 0.3,
        });
        const fanBase = new THREE.Mesh(fanBaseGeo, fanBaseMat);
        fanBase.position.set(0, 1.0, 0);
        fanBase.castShadow = true;
        devContainer.add(fanBase);

        // Stand pole (Height = 22)
        const poleGeo = new THREE.CylinderGeometry(1.2, 1.2, 20, 16);
        const poleMat = new THREE.MeshStandardMaterial({
          color: 0x47554f,
          metalness: 0.6,
          roughness: 0.3,
        });
        const pole = new THREE.Mesh(poleGeo, poleMat);
        pole.position.set(0, 11, 0);
        pole.castShadow = true;
        devContainer.add(pole);

        // Motor housing
        const motorGeo = new THREE.CylinderGeometry(3.8, 3.8, 5.0, 20);
        const motorMat = new THREE.MeshStandardMaterial({
          color: 0x2e3632,
          roughness: 0.3,
        });
        const motor = new THREE.Mesh(motorGeo, motorMat);
        motor.rotation.x = Math.PI / 2;
        motor.position.set(0, 21, 0);
        motor.castShadow = true;
        devContainer.add(motor);

        // Outer wireframe cage ring
        const cageGeo = new THREE.TorusGeometry(12.5, 0.6, 12, 32);
        const cageMat = new THREE.MeshStandardMaterial({
          color: 0x64746b,
          metalness: 0.5,
          roughness: 0.4,
        });
        const cage = new THREE.Mesh(cageGeo, cageMat);
        cage.position.set(0, 21, 2.5);
        devContainer.add(cage);

        // Rotating Blade Rotor Assembly
        const rotorGroup = new THREE.Group();
        rotorGroup.position.set(0, 21, 2.5);

        // 3 Aerodynamic blades at 120° angles
        const bladeGeo = new THREE.BoxGeometry(2.4, 11.0, 0.4);
        const bladeMat = new THREE.MeshStandardMaterial({
          color: isPowerOn ? 0x38bdf8 : 0x7a8a82,
          roughness: 0.25,
          metalness: 0.2,
        });

        for (let b = 0; b < 3; b++) {
          const bladeMesh = new THREE.Mesh(bladeGeo, bladeMat);
          const angle = (b * Math.PI * 2) / 3;
          bladeMesh.rotation.z = angle;
          bladeMesh.position.set(
            Math.sin(angle) * 5.5,
            Math.cos(angle) * 5.5,
            0
          );
          rotorGroup.add(bladeMesh);
        }

        // Center spinner cap
        const capGeo = new THREE.SphereGeometry(2.2, 16, 16);
        const capMat = new THREE.MeshStandardMaterial({ color: 0x1e2924, metalness: 0.7 });
        const cap = new THREE.Mesh(capGeo, capMat);
        cap.position.set(0, 0, 0.6);
        rotorGroup.add(cap);

        devContainer.add(rotorGroup);

        // Rotate blades dynamically when ON
        if (isPowerOn) {
          animatedObjectsRef.current.push({
            id: `fan-spin-${dev.id}`,
            update: (_time, delta) => {
              const rotationSpeed = (fanSpeed || 1) * 16.0;
              rotorGroup.rotation.z += delta * rotationSpeed;
            },
          });
        }
      }

      // =========================================================================
      // G. MULTI-SENSOR DOME (Motion / Environmental / Gas / Contact Sensors)
      // =========================================================================
      else {
        const isMotionSensor = state.motion !== undefined;
        const isGasSensor = state.ppm !== undefined || state.gas_detected !== undefined;

        // Base Cylinder: radius 7.5, height 3.5
        const sensGeo = new THREE.CylinderGeometry(7.5, 7.5, 3.5, 24);
        const sensMat = new THREE.MeshStandardMaterial({
          color: 0xf8f6f0,
          roughness: 0.3,
        });
        const sensMesh = new THREE.Mesh(sensGeo, sensMat);
        sensMesh.position.set(0, 1.75, 0);
        sensMesh.castShadow = true;
        devContainer.add(sensMesh);

        // Fresnel Dome: radius 5.5, height 4.0
        const domeGeo = new THREE.SphereGeometry(5.5, 20, 16, 0, Math.PI * 2, 0, Math.PI / 2);
        const domeColor = (isMotionSensor && state.motion)
          ? 0x9333ea
          : (isGasSensor && state.gas_detected)
          ? 0xc2410c
          : 0x4a7c59;
        const domeMat = new THREE.MeshStandardMaterial({
          color: domeColor,
          roughness: 0.1,
          metalness: 0.1,
        });
        const dome = new THREE.Mesh(domeGeo, domeMat);
        dome.position.set(0, 3.5, 0);
        devContainer.add(dome);

        // Active Hazard / Radar Pulse Ring (inner ~9, outer ~11, pulse up to ~25)
        if (state.motion || state.gas_detected) {
          const pulseGeo = new THREE.RingGeometry(9.0, 11.0, 32);
          const pulseMat = new THREE.MeshBasicMaterial({
            color: state.gas_detected ? 0xc2410c : 0x9333ea,
            transparent: true,
            opacity: 0.7,
            side: THREE.DoubleSide,
            depthWrite: false,
          });
          const pulseRing = new THREE.Mesh(pulseGeo, pulseMat);
          pulseRing.rotation.x = -Math.PI / 2;
          pulseRing.position.set(0, 0.44, 0);
          devContainer.add(pulseRing);

          animatedObjectsRef.current.push({
            id: `sens-pulse-${dev.id}`,
            update: (time) => {
              const progress = (time * 2.0) % 1.0;
              const scale = 1.0 + progress * 2.3;
              pulseRing.scale.set(scale, scale, scale);
              (pulseRing.material as THREE.MeshBasicMaterial).opacity = (1 - progress) * 0.75;
            },
          });
        }
      }

      // =========================================================================
      // G. SELECTION & HOVER ANIMATED FOCUS RINGS
      // =========================================================================
      if (isSelected) {
        // Double Selection Ground Disc (Forest Green #4a7c59 + Amber #705c30)
        const selGroup = new THREE.Group();
        selGroup.position.set(0, 0.46, 0);

        const selInnerGeo = new THREE.RingGeometry(12.5, 14.5, 36);
        const selInnerMat = new THREE.MeshBasicMaterial({
          color: 0x4a7c59,
          side: THREE.DoubleSide,
          depthWrite: false,
        });
        const selInner = new THREE.Mesh(selInnerGeo, selInnerMat);
        selInner.rotation.x = -Math.PI / 2;
        selGroup.add(selInner);

        const selOuterGeo = new THREE.RingGeometry(16.0, 18.0, 36);
        const selOuterMat = new THREE.MeshBasicMaterial({
          color: 0x705c30,
          side: THREE.DoubleSide,
          depthWrite: false,
        });
        const selOuter = new THREE.Mesh(selOuterGeo, selOuterMat);
        selOuter.rotation.x = -Math.PI / 2;
        selGroup.add(selOuter);

        // Overhead marker cone beacon: radius ~4.5, height ~9.0, positioned at Y ~ 42
        const beaconGeo = new THREE.ConeGeometry(4.5, 9.0, 16);
        const beaconMat = new THREE.MeshBasicMaterial({ color: 0x4a7c59 });
        const beacon = new THREE.Mesh(beaconGeo, beaconMat);
        beacon.rotation.x = Math.PI;
        beacon.position.set(0, 42, 0);
        selGroup.add(beacon);

        devContainer.add(selGroup);

        // Selection animation
        animatedObjectsRef.current.push({
          id: `sel-marker-${dev.id}`,
          update: (time) => {
            selInner.rotation.z = time * 0.8;
            selOuter.rotation.z = -time * 0.5;
            beacon.position.y = 42 + Math.sin(time * 3.5) * 2.5;
          },
        });
      } else if (isHovered) {
        // Hover Highlight Ring
        const hoverGeo = new THREE.RingGeometry(13.0, 15.5, 32);
        const hoverMat = new THREE.MeshBasicMaterial({
          color: 0x705c30,
          transparent: true,
          opacity: 0.6,
          side: THREE.DoubleSide,
          depthWrite: false,
        });
        const hoverRing = new THREE.Mesh(hoverGeo, hoverMat);
        hoverRing.rotation.x = -Math.PI / 2;
        hoverRing.position.set(0, 0.45, 0);
        devContainer.add(hoverRing);
      }

      // =========================================================================
      // H. FAULT WARNING BEACON PILLAR
      // =========================================================================
      if (fault !== 'none') {
        const faultColor = fault === 'offline' ? 0xef4444 : fault === 'timeout' ? 0xf59e0b : 0xa855f7;
        const faultBeaconGeo = new THREE.ConeGeometry(5.0, 10.0, 16);
        const faultBeaconMat = new THREE.MeshBasicMaterial({ color: faultColor });
        const faultBeacon = new THREE.Mesh(faultBeaconGeo, faultBeaconMat);
        faultBeacon.rotation.x = Math.PI;
        faultBeacon.position.set(0, 40, 0);
        devContainer.add(faultBeacon);

        animatedObjectsRef.current.push({
          id: `fault-beacon-${dev.id}`,
          update: (time) => {
            faultBeacon.position.y = 40 + Math.sin(time * 4.0) * 2.5;
          },
        });
      }

      devGroup.add(devContainer);
      deviceMeshesMap.current.set(dev.id, devContainer);
    });
  }, [devices, selectedDeviceId, hoveredDev, faults, lightingMode, doorAlignments, isDoorDevice]);

  // Directly update floating tooltip position in DOM without causing React re-renders
  const updateTooltipDOM = useCallback((x: number, y: number) => {
    if (tooltipRef.current) {
      const left = Math.min(window.innerWidth - 260, x + 16);
      const top = Math.max(10, y - 65);
      tooltipRef.current.style.transform = `translate3d(${left}px, ${top}px, 0)`;
    }
  }, []);

  // Raycaster for 3D Click & Hover Interaction
  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    const mount = mountRef.current;
    const camera = cameraRef.current;
    const scene = sceneRef.current;
    if (!mount || !camera || !scene) return;

    const rect = mount.getBoundingClientRect();
    mouseVecRef.current.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    mouseVecRef.current.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    raycasterRef.current.setFromCamera(mouseVecRef.current, camera);

    const intersects = raycasterRef.current.intersectObjects(devicesGroupRef.current.children, true);
    if (intersects.length > 0) {
      let current: THREE.Object3D | null = intersects[0].object;
      while (current && current.parent && current.parent !== devicesGroupRef.current) {
        current = current.parent;
      }
      if (current && current.userData?.device) {
        onSelectDevice(current.userData.device);
      }
    }
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const mount = mountRef.current;
    if (!mount) return;

    const rect = mount.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    mousePosRef.current = { x: mouseX, y: mouseY };

    // Move tooltip directly in DOM without React re-render
    updateTooltipDOM(mouseX, mouseY);

    // Throttle raycasting with requestAnimationFrame
    if (!raycastPendingRef.current) {
      raycastPendingRef.current = true;
      requestAnimationFrame(() => {
        raycastPendingRef.current = false;
        const camera = cameraRef.current;
        const scene = sceneRef.current;
        if (!camera || !scene || !mountRef.current) return;

        mouseVecRef.current.x = (mousePosRef.current.x / rect.width) * 2 - 1;
        mouseVecRef.current.y = -(mousePosRef.current.y / rect.height) * 2 + 1;

        raycasterRef.current.setFromCamera(mouseVecRef.current, camera);

        const intersects = raycasterRef.current.intersectObjects(devicesGroupRef.current.children, true);
        if (intersects.length > 0) {
          let current: THREE.Object3D | null = intersects[0].object;
          while (current && current.parent && current.parent !== devicesGroupRef.current) {
            current = current.parent;
          }
          if (current && current.userData?.device) {
            const dev = current.userData.device as Device;
            setHoveredDev((prev) => (prev?.id === dev.id ? prev : dev));
            mountRef.current.style.cursor = 'pointer';
            return;
          }
        }
        setHoveredDev((prev) => (prev ? null : null));
        if (mountRef.current) mountRef.current.style.cursor = 'grab';
      });
    }
  };

  // Helper action text for floating 3D tooltip
  const getActionHint = (d: Device) => {
    if (d.kind === 'light') return 'Nhấp để chọn & điều khiển bật/tắt đèn';
    if (d.kind === 'lock' || isDoorDevice(d)) return 'Nhấp để chọn & đóng/mở, khóa cửa';
    if (d.kind === 'aircon') return 'Nhấp để chọn & chỉnh nhiệt độ điều hòa';
    if (d.kind === 'blind') return 'Nhấp để chọn & kéo rèm cửa';
    if (d.kind === 'speaker') return 'Nhấp để chọn & phát/dừng nhạc';
    return 'Nhấp để chọn & xem chi tiết thiết bị';
  };

  return (
    <div className="relative w-full h-full flex flex-col bg-background rounded-xl overflow-hidden shadow-soft border border-outline-variant select-none min-h-0 min-w-0 flex-1">
      {/* Top 3D Control Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5 bg-surface border-b border-outline-variant z-10">
        <div className="flex items-center flex-wrap gap-2">
          <span className="text-xs font-bold text-primary flex items-center space-x-1.5 bg-primary-light px-2.5 py-1 rounded-lg">
            <Box size={14} />
            <span>Không gian 3D tương tác</span>
          </span>

          {/* Camera Presets */}
          <div className="flex items-center space-x-1 bg-surface-container p-1 rounded-xl">
            <button
              onClick={() => setCameraPreset('iso')}
              className="px-2.5 py-1 text-xs font-semibold rounded-lg hover:bg-surface-variant text-earth-dark transition-all"
              title="Góc nhìn phối cảnh Isometric 3D"
            >
              Isometric
            </button>
            <button
              onClick={() => setCameraPreset('top')}
              className="px-2.5 py-1 text-xs font-semibold rounded-lg hover:bg-surface-variant text-earth-dark transition-all"
              title="Góc nhìn thẳng từ trên xuống Top-Down"
            >
              Top-Down
            </button>
            <button
              onClick={() => setCameraPreset('front')}
              className="px-2.5 py-1 text-xs font-semibold rounded-lg hover:bg-surface-variant text-earth-dark transition-all"
              title="Góc nhìn chính diện Front"
            >
              Chính diện
            </button>
          </div>
        </div>

        {/* Feature Layer & Environment Toggles */}
        <div className="flex items-center space-x-1.5">
          {/* Day / Night Mode Toggle */}
          <button
            onClick={() => setLightingMode((m) => (m === 'night' ? 'day' : 'night'))}
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition-all border ${
              lightingMode === 'night'
                ? 'bg-slate-800 border-slate-700 text-amber-300 shadow-sm'
                : 'bg-amber-50 border-amber-300 text-amber-800'
            }`}
            title={lightingMode === 'night' ? 'Chuyển sang Chế độ Ban ngày (Day Mode)' : 'Chuyển sang Chế độ Ban đêm (Night Mode)'}
          >
            {lightingMode === 'night' ? (
              <Moon size={13} className="text-amber-300" />
            ) : (
              <Sun size={13} className="text-amber-600" />
            )}
            <span>{lightingMode === 'night' ? 'Ban đêm' : 'Ban ngày'}</span>
          </button>

          {/* Climate Overlay Toggle */}
          <button
            onClick={() => setShowClimateOverlay((v) => !v)}
            className={`flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-semibold transition-all border ${
              showClimateOverlay
                ? 'bg-primary-light border-primary/30 text-primary'
                : 'bg-surface-container border-outline-variant text-earth-muted hover:bg-surface-variant'
            }`}
            title="Bật/Tắt Lớp phủ Khí hậu & Nhiệt độ phòng"
          >
            <Thermometer size={13} />
            <span className="hidden sm:inline">Khí hậu phòng</span>
          </button>

          {/* Architectural Decor Toggle */}
          <button
            onClick={() => setShowDecor((v) => !v)}
            className={`flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-semibold transition-all border ${
              showDecor
                ? 'bg-primary-light border-primary/30 text-primary'
                : 'bg-surface-container border-outline-variant text-earth-muted hover:bg-surface-variant'
            }`}
            title="Bật/Tắt Nội thất kiến trúc tối giản gợi ý không gian"
          >
            <Armchair size={13} />
            <span className="hidden sm:inline">Nội thất</span>
          </button>

          {/* Dynamic 3D Lights Toggle */}
          <button
            onClick={() => setShowDynamicLights((v) => !v)}
            className={`flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-semibold transition-all border ${
              showDynamicLights
                ? 'bg-amber-50 border-amber-300 text-amber-800'
                : 'bg-surface-container border-outline-variant text-earth-muted hover:bg-surface-variant'
            }`}
            title="Bật/Tắt Ánh sáng vật lý 3D động"
          >
            <Sun size={13} />
            <span className="hidden sm:inline">Ánh sáng 3D</span>
          </button>

          {/* Floor Grid Toggle */}
          <button
            onClick={() => setShowFloorGrid((v) => !v)}
            className={`flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-semibold transition-all border ${
              showFloorGrid
                ? 'bg-surface-variant border-outline text-earth-dark'
                : 'bg-surface-container border-outline-variant text-earth-muted hover:bg-surface-variant'
            }`}
            title="Bật/Tắt Lưới toạ độ sàn"
          >
            <Layers size={13} />
            <span className="hidden sm:inline">Lưới sàn</span>
          </button>

          {/* Reset Camera */}
          <button
            onClick={() => setCameraPreset('iso')}
            className="flex items-center space-x-1 px-2.5 py-1 bg-surface-container hover:bg-surface-variant text-xs text-earth-dark rounded-lg border border-outline-variant transition-all"
            title="Đặt lại góc quay mặc định"
          >
            <RotateCcw size={13} />
            <span className="hidden md:inline">Reset Camera</span>
          </button>
        </div>
      </div>

      {/* 3D WebGL Canvas Container */}
      <div
        ref={mountRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        className="relative flex-1 w-full h-full cursor-grab active:cursor-grabbing min-h-0 min-w-0 overflow-hidden"
      >
        {/* Floating 3D Hover Tooltip adhering to Terra Organic Design */}
        {hoveredDev && (
          <div
            ref={(el) => {
              tooltipRef.current = el;
              if (el) {
                const left = Math.min(window.innerWidth - 260, mousePosRef.current.x + 16);
                const top = Math.max(10, mousePosRef.current.y - 65);
                el.style.transform = `translate3d(${left}px, ${top}px, 0)`;
              }
            }}
            className="absolute top-0 left-0 pointer-events-none bg-surface/95 text-earth-dark backdrop-blur border border-outline-variant text-xs px-3.5 py-2.5 rounded-xl shadow-soft z-20 flex flex-col space-y-1.5 will-change-transform"
          >
            <div className="font-bold font-headline flex items-center space-x-1.5 text-primary">
              <Activity size={13} />
              <span>{hoveredDev.name}</span>
            </div>
            <div className="text-[11px] text-earth-muted flex items-center space-x-2">
              <span>{hoveredDev.room}</span>
              <span>·</span>
              <span className="font-semibold text-earth-dark">
                {hoveredDev.kind === 'light'
                  ? hoveredDev.state?.power ? `Bật (${hoveredDev.state.brightness ?? 80}%)` : 'Tắt'
                  : hoveredDev.kind === 'aircon'
                  ? hoveredDev.state?.power ? `Bật (${hoveredDev.state.target_temperature ?? 25}°C)` : 'Tắt'
                  : hoveredDev.kind === 'lock' || isDoorDevice(hoveredDev)
                  ? hoveredDev.state?.locked ? 'Khóa an toàn' : hoveredDev.state?.open ? 'Đang Mở' : 'Đã Đóng'
                  : hoveredDev.kind === 'blind'
                  ? `Mở ${hoveredDev.state?.position ?? 0}%`
                  : hoveredDev.kind === 'speaker'
                  ? hoveredDev.state?.playing ? `Phát (${hoveredDev.state.volume ?? 50}%)` : 'Tạm dừng'
                  : hoveredDev.state?.temperature !== undefined
                  ? `${hoveredDev.state.temperature}°C · ${hoveredDev.state.humidity ?? 60}%`
                  : 'Hoạt động'}
              </span>
            </div>
            <div className="text-[10px] text-primary/80 font-medium flex items-center space-x-1 pt-0.5 border-t border-outline-variant/50">
              <Sparkles size={10} />
              <span>{getActionHint(hoveredDev)}</span>
            </div>
          </div>
        )}

        {/* Bottom Helper Info */}
        <div className="absolute bottom-3 left-4 bg-surface/90 backdrop-blur px-3 py-1.5 rounded-lg border border-outline-variant text-[11px] text-earth-muted shadow-sm pointer-events-none flex items-center space-x-2">
          <Compass size={13} className="text-primary" />
          <span>Xoay: Chuột trái · Trượt: Chuột phải / Shift · Zoom: Cuộn chuột. Nhấp vào thiết bị để chọn & điều khiển.</span>
        </div>
      </div>
    </div>
  );
};
