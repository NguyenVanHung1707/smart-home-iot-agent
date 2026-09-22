import { Device, FaultMode, SimulatorState, Wall } from '../types';

const API_BASE = '/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const errorBody = await res.text();
    let errorDetail = errorBody;
    try {
      const parsed = JSON.parse(errorBody);
      errorDetail = parsed.detail || errorBody;
    } catch {
      // ignore
    }
    throw new Error(`API Error (${res.status}): ${errorDetail}`);
  }

  return res.json();
}

export const api = {
  async getState(): Promise<SimulatorState> {
    return request<SimulatorState>(`${API_BASE}/state`);
  },

  async saveWalls(walls: Wall[]): Promise<Wall[]> {
    return request<Wall[]>(`${API_BASE}/walls`, {
      method: 'POST',
      body: JSON.stringify(walls),
    });
  },

  async addDevice(device: Partial<Device>): Promise<Device> {
    return request<Device>(`${API_BASE}/devices`, {
      method: 'POST',
      body: JSON.stringify(device),
    });
  },

  async updateDevice(deviceId: string, updates: Partial<Device>): Promise<Device> {
    return request<Device>(`${API_BASE}/devices/${deviceId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  },

  async deleteDevice(deviceId: string): Promise<{ success: boolean }> {
    return request<{ success: boolean }>(`${API_BASE}/devices/${deviceId}`, {
      method: 'DELETE',
    });
  },

  async performAction(deviceId: string, action: string, value?: any): Promise<Device> {
    return request<Device>(`${API_BASE}/devices/${deviceId}/action`, {
      method: 'POST',
      body: JSON.stringify({ action, value }),
    });
  },

  async setDeviceFault(deviceId: string, mode: FaultMode): Promise<{ device_id: string; fault: FaultMode }> {
    return request<{ device_id: string; fault: FaultMode }>(`${API_BASE}/devices/${deviceId}/fault`, {
      method: 'POST',
      body: JSON.stringify({ mode }),
    });
  },

  async triggerScan(): Promise<{ status: string; device_count: number }> {
    return request<{ status: string; device_count: number }>(`${API_BASE}/discovery/scan`, {
      method: 'POST',
    });
  },

  async resetState(): Promise<SimulatorState> {
    return request<SimulatorState>(`${API_BASE}/state/reset`, {
      method: 'POST',
    });
  },

  async getHealth(): Promise<{ status: string; mqtt_connected: boolean; broker: string; topic_prefix: string }> {
    return request<{ status: string; mqtt_connected: boolean; broker: string; topic_prefix: string }>(`/health`);
  },
};
