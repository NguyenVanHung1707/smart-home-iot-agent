import type { ApiDeviceCommand } from "../../api/types";
import type { Approval, Device, DiscoveredDevice, HomePreset, Role, Room } from "../../types";
import { HomeCircuitPanel } from "./HomeCircuitPanel";
import { HomeRightRail } from "./HomeRightRail";

type HomeDashboardProps = {
  rooms: Room[];
  approvals?: Approval[];
  onOpenRoom: (room: Room) => void;
  onOpenVoice: () => void;
  listening: boolean;
  onAddRoom?: () => void;
  onAddDevice?: () => void;
  discoveredDevices?: DiscoveredDevice[];
  onNavigateApprovals?: () => void;
  role: Role;
  presets: HomePreset[];
  onPresetsChange: (next: HomePreset[]) => void;
  onDeviceCommand: (device: Device, command: ApiDeviceCommand) => Promise<void>;
};

export function HomeDashboard({
  rooms,
  approvals,
  onOpenRoom,
  onOpenVoice,
  listening,
  onAddRoom,
  onAddDevice,
  onNavigateApprovals,
  role,
  presets,
  onPresetsChange,
  onDeviceCommand,
}: HomeDashboardProps) {
  const devices = rooms.flatMap((room) => room.devices);

  return (
    <div className="hm-home-dashboard">
      <div className="content-grid">
        <HomeCircuitPanel
          rooms={rooms}
          devices={devices}
          approvals={approvals}
          onOpenRoom={onOpenRoom}
          onVoice={onOpenVoice}
          listening={listening}
          onAddRoom={onAddRoom}
          onAddDevice={onAddDevice}
          onNavigateApprovals={onNavigateApprovals}
        />
        <HomeRightRail
          rooms={rooms}
          devices={devices}
          role={role}
          presets={presets}
          onPresetsChange={onPresetsChange}
          onDeviceCommand={onDeviceCommand}
        />
      </div>
    </div>
  );
}
