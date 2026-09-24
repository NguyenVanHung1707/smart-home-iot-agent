import { Wall, Device } from '../types';

export interface Point {
  x: number;
  y: number;
}

export interface DetectedRoom {
  id: string;
  name: string;
  corners: Point[]; // 4 corners in CCW order
  centroid: Point;
  area: number;
  badgeBounds?: { x: number; y: number; width: number; height: number };
}

export const DEFAULT_ROOM_NAMES = [
  'Phòng khách',
  'Phòng ngủ',
  'Phòng bếp',
  'Lối vào',
  'Phòng tắm',
  'Phòng làm việc',
  'Ban công',
  'Phòng sinh hoạt',
  'Phòng ăn',
];

// Helper to intelligently infer room name from devices inside the room
export function inferRoomNameFromDevices(devices: Device[]): string | null {
  if (!devices || devices.length === 0) return null;

  // 1. If majority of devices have an explicit room assigned, use that!
  const roomCounts: Record<string, number> = {};
  for (const d of devices) {
    if (d.room && d.room.trim()) {
      const r = d.room.trim();
      roomCounts[r] = (roomCounts[r] || 0) + 1;
    }
  }
  let bestRoom: string | null = null;
  let maxCount = 0;
  for (const [r, count] of Object.entries(roomCounts)) {
    if (count > maxCount) {
      maxCount = count;
      bestRoom = r;
    }
  }
  if (bestRoom) {
    return bestRoom;
  }

  const matchKeyword = (kwList: string[]) => {
    return devices.some((d) => {
      const target = `${d.name || ''} ${d.kind || ''} ${d.room || ''} ${d.id || ''}`.toLowerCase();
      return kwList.some((kw) => target.includes(kw.toLowerCase()));
    });
  };

  // 2. Entrance / Gate keywords: "lối vào", "cổng", "entry", "gate"
  if (matchKeyword(['lối vào', 'cổng', 'entry', 'gate', 'khoá cổng', 'khóa cổng', 'cửa chính', 'khóa'])) {
    return 'Lối vào';
  }
  // 3. Bedroom keywords: "ngủ", "đèn ngủ", "bed"
  if (matchKeyword(['đèn ngủ', 'ngủ', 'bed'])) {
    return 'Phòng ngủ';
  }
  // 4. Kitchen / Dining keywords: "bếp", "gas", "kitchen", "ăn", "dining"
  if (matchKeyword(['bếp', 'gas', 'kitchen', 'ăn', 'dining'])) {
    return 'Phòng bếp';
  }
  // 5. Living room keywords: "khách", "aircon", "loa", "speaker", "tivi", "living", "blind", "rèm"
  if (matchKeyword(['khách', 'aircon', 'loa', 'speaker', 'tivi', 'tv', 'living', 'blind', 'rèm', 'cửa sổ'])) {
    return 'Phòng khách';
  }
  // 6. Bathroom keywords: "tắm", "bath", "wc", "vệ sinh"
  if (matchKeyword(['tắm', 'bath', 'wc', 'vệ sinh'])) {
    return 'Phòng tắm';
  }
  // 7. Work office keywords: "làm việc", "work", "office"
  if (matchKeyword(['làm việc', 'work', 'office'])) {
    return 'Phòng làm việc';
  }
  // 8. Balcony keywords: "ban công", "balcony"
  if (matchKeyword(['ban công', 'balcony'])) {
    return 'Ban công';
  }

  return null;
}

// Line segment intersection with tolerance (0.15 segment margin)
export function findIntersection(w1: Wall, w2: Wall, margin = 0.15): Point | null {
  const dx1 = w1.x2 - w1.x1;
  const dy1 = w1.y2 - w1.y1;
  const dx2 = w2.x2 - w2.x1;
  const dy2 = w2.y2 - w2.y1;

  const cross = dx1 * dy2 - dy1 * dx2;
  if (Math.abs(cross) < 1e-4) return null; // parallel or degenerate

  const t = ((w2.x1 - w1.x1) * dy2 - (w2.y1 - w1.y1) * dx2) / cross;
  const u = ((w2.x1 - w1.x1) * dy1 - (w2.y1 - w1.y1) * dx1) / cross;

  if (t >= -margin && t <= 1 + margin && u >= -margin && u <= 1 + margin) {
    return {
      x: Math.round(w1.x1 + t * dx1),
      y: Math.round(w1.y1 + t * dy1),
    };
  }
  return null;
}

// Point in polygon test (ray-casting)
export function isPointInPolygon(point: Point, polygon: Point[]): boolean {
  const { x, y } = point;
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].x;
    const yi = polygon[i].y;
    const xj = polygon[j].x;
    const yj = polygon[j].y;
    const intersect = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

// Calculate polygon area (Shoelace formula)
export function polygonArea(points: Point[]): number {
  let area = 0;
  for (let i = 0; i < points.length; i++) {
    const j = (i + 1) % points.length;
    area += points[i].x * points[j].y;
    area -= points[j].x * points[i].y;
  }
  return Math.abs(area) / 2;
}

// Euclidean distance between two points
export function ptDistance(p1: Point, p2: Point): number {
  return Math.hypot(p1.x - p2.x, p1.y - p2.y);
}

/**
 * Atomic 4-Wall Room Detection Algorithm with Intelligent Room Identification
 * 1. Finds all candidate 4-wall cycles with 4 valid distinct intersection corners & area >= 400px^2.
 * 2. Crucial rule: Ensures the candidate room has NO other wall inside it (khong co tuong khac dong kin ben trong)
 *    by verifying that midpoints of all walls NOT forming the 4-wall boundary are outside the room polygon.
 * 3. Infers room name intelligently from enclosed devices or assigns unique default names.
 * 4. Returns unique atomic rooms sorted in CCW order with centroid and area.
 */
export function detectEnclosedRooms(
  walls: Wall[],
  devicesOrCustomNames?: Device[] | Record<string, string>,
  customNamesArg?: Record<string, string>
): DetectedRoom[] {
  if (walls.length < 4) return [];

  let devices: Device[] = [];
  let customNames: Record<string, string> = {};

  if (Array.isArray(devicesOrCustomNames)) {
    devices = devicesOrCustomNames;
    if (customNamesArg) customNames = customNamesArg;
  } else if (devicesOrCustomNames && typeof devicesOrCustomNames === 'object') {
    customNames = devicesOrCustomNames;
  }

  const n = walls.length;
  const intersections: (Point | null)[][] = Array.from({ length: n }, () => Array(n).fill(null));

  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const pt = findIntersection(walls[i], walls[j], 0.15);
      intersections[i][j] = pt;
      intersections[j][i] = pt;
    }
  }

  const foundRooms: DetectedRoom[] = [];
  const visitedKeys = new Set<string>();
  const usedNames = new Set<string>();

  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      for (let k = j + 1; k < n; k++) {
        for (let l = k + 1; l < n; l++) {
          const tuple = [i, j, k, l];
          const cycleCandidates = [
            [i, j, k, l],
            [i, j, l, k],
            [i, k, j, l],
          ];

          for (const [w0, w1, w2, w3] of cycleCandidates) {
            const p01 = intersections[w0][w1];
            const p12 = intersections[w1][w2];
            const p23 = intersections[w2][w3];
            const p30 = intersections[w3][w0];

            if (p01 && p12 && p23 && p30) {
              const pts = [p01, p12, p23, p30];
              let distinct = true;
              for (let a = 0; a < 4; a++) {
                for (let b = a + 1; b < 4; b++) {
                  if (ptDistance(pts[a], pts[b]) < 15) {
                    distinct = false;
                    break;
                  }
                }
                if (!distinct) break;
              }
              if (!distinct) continue;

              const centroid: Point = {
                x: Math.round((pts[0].x + pts[1].x + pts[2].x + pts[3].x) / 4),
                y: Math.round((pts[0].y + pts[1].y + pts[2].y + pts[3].y) / 4),
              };

              // Sort in CCW order around centroid
              const sorted = [...pts].sort((a, b) => {
                const angleA = Math.atan2(a.y - centroid.y, a.x - centroid.x);
                const angleB = Math.atan2(b.y - centroid.y, b.x - centroid.x);
                return angleA - angleB;
              });

              const area = polygonArea(sorted);
              if (area >= 400) {
                // Crucial atomic check: No interior walls inside this room polygon
                const wallIndicesSet = new Set([w0, w1, w2, w3]);
                let hasInteriorWall = false;
                for (let m = 0; m < n; m++) {
                  if (!wallIndicesSet.has(m)) {
                    const midX = (walls[m].x1 + walls[m].x2) / 2;
                    const midY = (walls[m].y1 + walls[m].y2) / 2;
                    if (isPointInPolygon({ x: midX, y: midY }, sorted)) {
                      hasInteriorWall = true;
                      break;
                    }
                  }
                }
                if (hasInteriorWall) continue;

                const key = tuple.join('-');
                if (!visitedKeys.has(key)) {
                  visitedKeys.add(key);
                  const roomId = `room-${key}`;

                  // Intelligent room name inference
                  let roomName = customNames[roomId];
                  if (!roomName) {
                    const roomDevices = devices.filter((d) =>
                      isPointInPolygon({ x: d.x, y: d.y }, sorted)
                    );
                    const inferred = inferRoomNameFromDevices(roomDevices);
                    if (inferred) {
                      roomName = inferred;
                    } else {
                      const available = DEFAULT_ROOM_NAMES.find((name) => !usedNames.has(name));
                      roomName = available || DEFAULT_ROOM_NAMES[foundRooms.length % DEFAULT_ROOM_NAMES.length];
                    }
                  }
                  usedNames.add(roomName);

                  foundRooms.push({
                    id: roomId,
                    name: roomName,
                    corners: sorted,
                    centroid,
                    area,
                  });
                }
              }
            }
          }
        }
      }
    }
  }

  return foundRooms;
}
