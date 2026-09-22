export type FaultMode = 'none' | 'offline' | 'timeout' | 'error';

export interface DeviceState {
  power?: boolean;
  brightness?: number;
  target_temperature?: number;
  mode?: string;
  temperature?: number;
  humidity?: number;
  ppm?: number;
  gas_detected?: boolean;
  motion?: boolean;
  open?: boolean;
  locked?: boolean;
  position?: number;
  volume?: number;
  playing?: boolean;
  battery?: number;
  [key: string]: any;
}

export interface Device {
  id: string;
  name: string;
  kind: 'light' | 'aircon' | 'blind' | 'speaker' | 'lock' | 'sensor' | string;
  room: string;
  x: number;
  y: number;
  state: DeviceState;
  auto_simulate?: boolean;
}

export interface Wall {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface SimulatorState {
  walls: Wall[];
  devices: Device[];
  faults: Record<string, FaultMode>;
}

export interface MqttLogMessage {
  id: string;
  timestamp: string;
  topic: string;
  payload: any;
  direction: 'in' | 'out';
  type: 'state' | 'command' | 'discovery' | 'fault' | 'ack' | 'info';
}
