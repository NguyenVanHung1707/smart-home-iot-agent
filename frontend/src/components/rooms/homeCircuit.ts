import type { Device, DeviceKind, Room } from "../../types";

export type CircuitKey = "living" | "bedroom" | "kitchen" | "office" | "light" | "tv" | "fan" | "ac";

export const roomCircuits: CircuitKey[] = ["living", "bedroom", "kitchen", "office"];
export const deviceCircuits: CircuitKey[] = ["light", "tv", "fan", "ac"];

export function isRoomCircuit(circuit: CircuitKey) {
  return roomCircuits.includes(circuit);
}

export const circuitTraces: Array<{ key: CircuitKey; d: string }> = [
  { key: "living", d: "M133 222 V280 L233 380 H319 L369 430 V500 L466 597" },
  { key: "bedroom", d: "M378 222 V350 L428 400 V490 L453 515 H463 L488 540 V585" },
  { key: "kitchen", d: "M622 222 V350 L572 400 V490 L547 515 H537 L512 540 V585" },
  { key: "office", d: "M867 222 V280 L767 380 H681 L631 430 V500 L534 597" },
  { key: "light", d: "M133 416 V440 L183 490 H316 L366 540 H409 L466 597" },
  { key: "tv", d: "M378 416 V460 L428 510 H443 L488 555 V585" },
  { key: "fan", d: "M622 416 V460 L572 510 H557 L512 555 V585" },
  { key: "ac", d: "M867 416 V440 L817 490 H684 L634 540 H591 L534 597" },
];

export const circuitNodes: Array<{ key: CircuitKey; cx: number; cy: number }> = [
  { key: "living", cx: 133, cy: 222 },
  { key: "bedroom", cx: 378, cy: 222 },
  { key: "kitchen", cx: 622, cy: 222 },
  { key: "office", cx: 867, cy: 222 },
  { key: "light", cx: 133, cy: 416 },
  { key: "tv", cx: 378, cy: 416 },
  { key: "fan", cx: 622, cy: 416 },
  { key: "ac", cx: 867, cy: 416 },
];

export function roomCircuit(room: Room, index: number): CircuitKey {
  const name = room.name.toLowerCase();
  if (name.includes("khách")) return "living";
  if (name.includes("ngủ")) return "bedroom";
  if (name.includes("bếp")) return "kitchen";
  if (name.includes("làm việc") || name.includes("office")) return "office";
  return roomCircuits[index % roomCircuits.length];
}

export function deviceCircuit(device: Device, index: number): CircuitKey {
  void device;
  return deviceCircuits[index % deviceCircuits.length];
}

export function deviceIcon(kind?: DeviceKind) {
  const map: Record<DeviceKind, "bulb" | "fan" | "ac" | "desk" | "tv" | "lock" | "thermo"> = {
    light: "bulb",
    fan: "fan",
    aircon: "ac",
    blind: "desk",
    speaker: "tv",
    lock: "lock",
    sensor: "thermo",
    display: "tv",
  };
  return kind ? map[kind] : "bulb";
}
