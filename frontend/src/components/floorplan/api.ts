import { apiFetch, sendDeviceCommand } from '../../api/client';
import { Device, FaultMode, SimulatorState, Wall } from './types';

const SIMULATOR_API_BASE = '/simulator-api';

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

export const floorplanApi = {
  async getState(mode: 'real' | 'simulator' = 'simulator'): Promise<SimulatorState> {
    if (mode === 'real') {
      return apiFetch<SimulatorState>('/floorplan');
    }
    return request<SimulatorState>(`${SIMULATOR_API_BASE}/state`);
  },

  async saveWalls(walls: Wall[], mode: 'real' | 'simulator' = 'simulator'): Promise<Wall[]> {
    if (mode === 'real') {
      return apiFetch<Wall[]>('/floorplan/walls', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(walls),
      });
    }
    return request<Wall[]>(`${SIMULATOR_API_BASE}/walls`, {
      method: 'POST',
      body: JSON.stringify(walls),
    });
  },

  async updateDevice(
    deviceId: string,
    updates: Partial<Device>,
    mode: 'real' | 'simulator' = 'simulator'
  ): Promise<Device> {
    if (mode === 'real') {
      return apiFetch<Device>(`/floorplan/devices/${deviceId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
    }
    return request<Device>(`${SIMULATOR_API_BASE}/devices/${deviceId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  },

  async deleteDevice(deviceId: string): Promise<{ success: boolean }> {
    return request<{ success: boolean }>(`${SIMULATOR_API_BASE}/devices/${deviceId}`, {
      method: 'DELETE',
    });
  },

  async addDevice(device: Partial<Device>): Promise<Device> {
    return request<Device>(`${SIMULATOR_API_BASE}/devices`, {
      method: 'POST',
      body: JSON.stringify(device),
    });
  },

  async performAction(
    deviceId: string,
    action: string,
    value?: any,
    mode: 'real' | 'simulator' = 'simulator'
  ): Promise<any> {
    if (mode === 'real') {
      let cmdAction = action;
      let cmdValue = value;
      if (action === 'toggle') {
        cmdAction = 'toggle';
      } else if (action === 'turn_on' || action === 'on') {
        cmdAction = 'on';
      } else if (action === 'turn_off' || action === 'off') {
        cmdAction = 'off';
      } else if (action === 'lock') {
        cmdAction = 'lock';
      } else if (action === 'unlock') {
        cmdAction = 'unlock';
      } else if (action === 'set_speed') {
        cmdAction = 'set_speed';
        cmdValue = Number(value);
      } else if (action === 'set' && typeof value === 'object') {
        cmdAction = 'set';
        cmdValue = value;
      }
      return sendDeviceCommand(deviceId, { action: cmdAction, value: cmdValue });
    }
    return request<Device>(`${SIMULATOR_API_BASE}/devices/${deviceId}/action`, {
      method: 'POST',
      body: JSON.stringify({ action, value }),
    });
  },

  async setFault(deviceId: string, mode: FaultMode): Promise<{ success: boolean }> {
    return request<{ success: boolean }>(`${SIMULATOR_API_BASE}/devices/${deviceId}/fault`, {
      method: 'POST',
      body: JSON.stringify({ mode }),
    });
  },

  async resetState(mode: 'real' | 'simulator' = 'simulator'): Promise<SimulatorState> {
    if (mode === 'real') {
      return apiFetch<SimulatorState>('/floorplan/reset', { method: 'POST' });
    }
    return request<SimulatorState>(`${SIMULATOR_API_BASE}/state/reset`, {
      method: 'POST',
    });
  },

  async getHealth(): Promise<{ status: string; mqtt_connected: boolean; broker: string; topic_prefix: string }> {
    return request<{ status: string; mqtt_connected: boolean; broker: string; topic_prefix: string }>(
      `${SIMULATOR_API_BASE}/health`
    );
  },
};
