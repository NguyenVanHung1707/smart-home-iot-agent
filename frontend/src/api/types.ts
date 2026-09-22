import type { ApprovalStatus, DeviceCommandAction, DeviceKind } from "../types";

export interface ApiDevice {
  id: string;
  name: string;
  room: string;
  kind: DeviceKind;
  online: boolean;
  state: Record<string, unknown>;
}

export interface ApiDeviceCommand {
  action: DeviceCommandAction;
  value?: unknown;
}

export interface ApiApproval {
  id: string;
  device_id: string;
  command: ApiDeviceCommand;
  status: ApprovalStatus;
  requested_by?: string;
  created_at?: string;
  expires_at?: string;
}

export interface ApiSimulatorEvent {
  type?: string;
  event?: string;
  device_id?: string;
  topic?: string;
  action?: string;
  command_id?: string;
  timestamp?: string;
  status?: string;
  error?: string;
  state?: Record<string, unknown>;
  online?: boolean;
}

export interface VoiceStatus {
  enabled: boolean;
  ready: boolean;
  stt: { ready: boolean; model: string; vad: boolean };
  tts: { ready: boolean; voice: string };
  limits?: { max_audio_seconds: number };
}

export interface VoiceProcessResponse {
  transcript: string;
  response: string;
  analysis: string;
  plan?: Array<{
    device_id: string;
    action: string;
    value?: Record<string, unknown>;
  }>;
  session_id: string;
  tts?: { engine: string; voice: string; enabled: boolean };
}

export interface VoiceTranscription {
  transcript: string;
  language: string;
  audio_duration_ms: number;
  stt_latency_ms: number;
  model: string;
  vad_applied: boolean;
}
