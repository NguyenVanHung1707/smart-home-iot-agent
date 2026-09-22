import type { DataMode, HomePreset } from "./types";

const storageKey = (mode: DataMode) => `homemind-${mode}-presets`;

export const defaultPresets: HomePreset[] = [
  {
    id: "welcome-home",
    name: "Về nhà",
    icon: "house",
    actions: [
      { id: "welcome-light", deviceId: "living-light", action: "on" },
      { id: "welcome-aircon", deviceId: "living-aircon", action: "set", value: { power: true, target_temperature: 24, mode: "cool" } },
      { id: "welcome-blind", deviceId: "living-blind", action: "set", value: { position: 80 } },
    ],
  },
  {
    id: "relax",
    name: "Thư giãn",
    icon: "sparkles",
    actions: [
      { id: "relax-light", deviceId: "living-light", action: "set", value: { power: true, brightness: 35 } },
      { id: "relax-speaker", deviceId: "hub-speaker", action: "set", value: { power: true, volume: 30 } },
    ],
  },
  {
    id: "good-night",
    name: "Đi ngủ",
    icon: "bed",
    actions: [
      { id: "night-living-light", deviceId: "living-light", action: "off" },
      { id: "night-bedroom-light", deviceId: "bedroom-light", action: "off" },
      { id: "night-blind", deviceId: "living-blind", action: "set", value: { position: 0 } },
      { id: "night-lock", deviceId: "entry-lock", action: "lock" },
    ],
  },
  {
    id: "leave-home",
    name: "Rời nhà",
    icon: "lock",
    actions: [
      { id: "leave-living-light", deviceId: "living-light", action: "off" },
      { id: "leave-bedroom-light", deviceId: "bedroom-light", action: "off" },
      { id: "leave-kitchen-light", deviceId: "kitchen-light", action: "off" },
      { id: "leave-aircon", deviceId: "living-aircon", action: "off" },
      { id: "leave-blind", deviceId: "living-blind", action: "set", value: { position: 0 } },
      { id: "leave-lock", deviceId: "entry-lock", action: "lock" },
    ],
  },
];

export function cloneDefaultPresets() {
  return JSON.parse(JSON.stringify(defaultPresets)) as HomePreset[];
}

export function loadPresets(mode: DataMode) {
  try {
    const saved = window.localStorage.getItem(storageKey(mode));
    const parsed: unknown = saved ? JSON.parse(saved) : null;
    if (Array.isArray(parsed) && parsed.every((item) => item && typeof item === "object" && "id" in item && "actions" in item)) {
      return parsed as HomePreset[];
    }
  } catch {
    // A corrupt browser value should never prevent dashboard rendering.
  }
  return cloneDefaultPresets();
}

export function savePresets(mode: DataMode, presets: HomePreset[]) {
  window.localStorage.setItem(storageKey(mode), JSON.stringify(presets));
}
