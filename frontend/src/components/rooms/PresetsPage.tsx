import type { ApiDeviceCommand } from "../../api/types";
import type { Device, HomePreset, Role } from "../../types";
import { PresetPanel } from "./PresetPanel";

/** Full-page counterpart to the compact Dashboard preset widget. */
export function PresetsPage({
  role,
  devices,
  presets,
  onPresetsChange,
  onDeviceCommand,
}: {
  role: Role;
  devices: Device[];
  presets: HomePreset[];
  onPresetsChange: (next: HomePreset[]) => void;
  onDeviceCommand: (device: Device, command: ApiDeviceCommand) => Promise<void>;
}) {
  return (
    <PresetPanel
      variant="page"
      devices={devices}
      presets={presets}
      canEdit={role === "homeadmin"}
      onPresetsChange={onPresetsChange}
      onDeviceCommand={onDeviceCommand}
    />
  );
}
