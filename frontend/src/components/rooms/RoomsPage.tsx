import { useState } from "react";
import type { ApiDeviceCommand } from "../../api/types";
import type {
  Approval,
  CreateDevicePayload,
  Device,
  DiscoveredDevice,
  HomePreset,
  IconName,
  Role,
  Room,
  UpdateDevicePayload,
} from "../../types";
import { AddDeviceModal } from "./AddDeviceModal";
import { AddRoomModal } from "./AddRoomModal";
import { RoomDeviceModal } from "./RoomDeviceModal";
import { HomeDashboard } from "./HomeDashboard";

export function RoomsPage({
  role,
  rooms,
  approvals,
  discoveredDevices = [],
  roomPage,
  selectedRoom,
  listening,
  onRoomPage,
  onOpenRoom,
  onCloseRoom,
  onOpenVoice,
  onDeviceCommand,
  onRequestPinUnlock,
  onAddDevice,
  onDeleteDevice,
  onUpdateDevice,
  onRenameRoom,
  onDeleteRoom,
  onAddRoom,
  onScanDevices,
  onPairDiscovered,
  onDismissDiscovered,
  onNavigateApprovals,
  presets,
  onPresetsChange,
}: {
  role: Role;
  rooms: Room[];
  approvals: Approval[];
  discoveredDevices?: DiscoveredDevice[];
  roomPage: number;
  selectedRoom: Room | null;
  listening: boolean;
  onRoomPage: (page: number) => void;
  onOpenRoom: (room: Room) => void;
  onCloseRoom: () => void;
  onOpenVoice: () => void;
  onDeviceCommand: (device: Device, command: ApiDeviceCommand) => Promise<void>;
  onRequestPinUnlock: (device: Device) => void;
  onAddDevice?: (payload: CreateDevicePayload) => Promise<void>;
  onDeleteDevice?: (deviceId: string) => Promise<void>;
  onUpdateDevice?: (deviceId: string, payload: UpdateDevicePayload) => Promise<void>;
  onRenameRoom?: (oldName: string, newName: string) => Promise<void>;
  onDeleteRoom?: (roomName: string) => Promise<void>;
  onAddRoom?: (name: string, icon: IconName, deviceIds: string[]) => Promise<void>;
  onScanDevices?: () => Promise<void>;
  onPairDiscovered?: (deviceId: string, name?: string, room?: string) => Promise<void>;
  onDismissDiscovered?: (deviceId: string) => Promise<void>;
  onNavigateApprovals?: () => void;
  presets: HomePreset[];
  onPresetsChange: (next: HomePreset[]) => void;
}) {
  const [addDeviceModalOpen, setAddDeviceModalOpen] = useState(false);
  const [addRoomModalOpen, setAddRoomModalOpen] = useState(false);

  const allDevices = rooms.flatMap((r) => r.devices);

  return (
    <section className="hm-rooms-page" aria-label="Trạng thái các phòng">
      <HomeDashboard
        rooms={rooms}
        approvals={approvals}
        discoveredDevices={discoveredDevices}
        onOpenRoom={onOpenRoom}
        onOpenVoice={onOpenVoice}
        listening={listening}
        onAddRoom={onAddRoom ? () => setAddRoomModalOpen(true) : undefined}
        onAddDevice={onAddDevice ? () => setAddDeviceModalOpen(true) : undefined}
        onNavigateApprovals={onNavigateApprovals}
        role={role}
        presets={presets}
        onPresetsChange={onPresetsChange}
        onDeviceCommand={onDeviceCommand}
      />

      <RoomDeviceModal
        room={selectedRoom}
        role={role}
        allRooms={rooms}
        onClose={onCloseRoom}
        onDeviceCommand={onDeviceCommand}
        onRequestPinUnlock={onRequestPinUnlock}
        onDeleteDevice={onDeleteDevice}
        onUpdateDevice={onUpdateDevice}
        onRenameRoom={onRenameRoom}
        onDeleteRoom={onDeleteRoom}
      />

      {onAddDevice && onPairDiscovered && onDismissDiscovered && (
        <AddDeviceModal
          open={addDeviceModalOpen}
          rooms={rooms}
          discoveredDevices={discoveredDevices}
          onClose={() => setAddDeviceModalOpen(false)}
          onAddDevice={onAddDevice}
          onScanDevices={onScanDevices}
          onPairDiscovered={onPairDiscovered}
          onDismissDiscovered={onDismissDiscovered}
        />
      )}

      {onAddRoom && (
        <AddRoomModal
          open={addRoomModalOpen}
          allDevices={allDevices}
          onClose={() => setAddRoomModalOpen(false)}
          onAddRoom={onAddRoom}
        />
      )}
    </section>
  );
}
