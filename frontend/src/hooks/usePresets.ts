import { useEffect, useState } from "react";
import { loadPresets, savePresets } from "../presets";
import type { DataMode, HomePreset } from "../types";

/** Keeps preset configuration shared by the dashboard widget and the Presets page. */
export function usePresets(dataMode: DataMode) {
  const [presets, setPresets] = useState<HomePreset[]>(() => loadPresets(dataMode));

  useEffect(() => {
    setPresets(loadPresets(dataMode));
  }, [dataMode]);

  const updatePresets = (next: HomePreset[]) => {
    setPresets(next);
    savePresets(dataMode, next);
  };

  return { presets, updatePresets };
}
