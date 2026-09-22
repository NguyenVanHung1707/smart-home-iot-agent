import type {
  ApiApproval,
  ApiDevice,
  ApiDeviceCommand,
  ApiSimulatorEvent,
  VoiceProcessResponse,
  VoiceStatus,
  VoiceTranscription,
} from "./types";
import { getAccessToken, refreshAccessToken } from "./tokenStore";

export const apiBaseUrl = (import.meta.env.VITE_API_URL || "/api/v1").replace(/\/$/, "");

function withAuthHeaders(init?: RequestInit): RequestInit | undefined {
  const token = getAccessToken();
  const dataMode = (typeof window !== "undefined" ? localStorage.getItem("homemind-data-mode") : null) || "simulator";
  const headers = new Headers(init?.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  headers.set("X-Data-Mode", dataMode);
  return { ...init, headers };
}

export function apiErrorMessage(status: number, detail: string) {
  const messages: Record<string, string> = {
    device_offline: "Thiết bị hiện không sẵn sàng (mất kết nối hoặc bị ngắt).",
    unsupported_action: "Thiết bị không hỗ trợ thao tác này.",
    invalid_set_value: "Giá trị điều khiển không hợp lệ.",
    voice_disabled: "Giọng nói chưa được bật trong cấu hình Hub.",
    no_speech_detected: "Không nghe rõ lời nói. Hãy nói gần microphone rồi thử lại.",
    stt_unavailable: "Zipformer STT chưa sẵn sàng. Hãy kiểm tra model STT.",
    audio_too_long: "Đoạn thu âm quá dài. Hãy thử lại với câu ngắn hơn.",
    piper_timeout: "Piper tạo giọng nói quá lâu.",
    piper_unavailable: "Piper chưa sẵn sàng; phản hồi văn bản vẫn hoạt động.",
    empty_piper_response: "Piper không tạo được âm thanh; phản hồi văn bản vẫn dùng được.",
    invalid_credentials: "Email hoặc mật khẩu không đúng.",
    account_locked: "Tài khoản đã bị khóa. Hãy liên hệ chủ nhà để mở lại.",
    too_many_login_attempts: "Bạn đã thử đăng nhập quá nhiều lần. Vui lòng chờ ít phút rồi thử lại.",
    invalid_token: "Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại.",
    email_exists: "Email này đã được sử dụng.",
    forbidden: "Bạn không có quyền thực hiện thao tác này.",
  };
  if (messages[detail]) return messages[detail];
  if (status === 401) return "Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại.";
  if (status === 403) return "Bạn không có quyền thực hiện thao tác này.";
  if (status === 409) return "Thiết bị hiện không sẵn sàng hoặc đang cần xử lý trước.";
  if (status === 422) return detail || "Yêu cầu không hợp lệ.";
  if (status === 504) return "Hub chờ thiết bị phản hồi quá lâu (MQTT timeout).";
  if (status >= 500) return "Backend Hub gặp lỗi khi xử lý yêu cầu.";
  return detail || `Yêu cầu thất bại (HTTP ${status}).`;
}

export async function apiFetch<T>(path: string, init?: RequestInit, options?: { skipAuthRetry?: boolean }): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, withAuthHeaders(init));
  } catch {
    throw new Error("Không kết nối được Hub API. Vui lòng kiểm tra backend hoặc chuyển chế độ Mock Data.");
  }

  if (response.status === 401 && !options?.skipAuthRetry) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiFetch<T>(path, init, { skipAuthRetry: true });
    }
  }

  const contentType = response.headers.get("content-type") ?? "";
  const body = await response.text();
  let data: unknown = body;
  if (body.trim() && contentType.includes("application/json")) {
    try {
      data = JSON.parse(body);
    } catch {
      if (response.ok) throw new Error("Hub trả về JSON không hợp lệ.");
    }
  }

  if (!response.ok) {
    const detail = typeof data === "object" && data !== null && "detail" in data
      ? String(data.detail)
      : typeof data === "string" ? data.trim() : "";
    throw new Error(apiErrorMessage(response.status, detail));
  }

  return (body.trim() ? data : undefined) as T;
}

export function postJson<T>(path: string, payload?: unknown) {
  return apiFetch<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
}

export function sendDeviceCommand(deviceId: string, command: ApiDeviceCommand, pin?: string) {
  const query = pin ? `?pin=${encodeURIComponent(pin)}` : "";
  return postJson<{ id?: string; status?: string }>(`/devices/${deviceId}/command${query}`, command);
}

export function processVoice(transcript: string, sessionId?: string | null) {
  return postJson<VoiceProcessResponse>("/voice/process", {
    transcript,
    ...(sessionId ? { session_id: sessionId } : {}),
  });
}

export function transcribeAudio(wavBlob: Blob) {
  const form = new FormData();
  form.append("file", wavBlob, "command.wav");
  return apiFetch<VoiceTranscription>("/voice/transcribe", {
    method: "POST",
    body: form,
  });
}

export async function synthesizeVoice(text: string): Promise<{ audioUrl: string; latencyMs: number }> {
  const response = await fetch(`${apiBaseUrl}/voice/synthesize`, withAuthHeaders({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  }));
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    const detail = payload?.detail ?? "";
    throw new Error(apiErrorMessage(response.status, detail));
  }
  const latencyMs = Number(response.headers.get("X-TTS-Latency-Ms") || 0);
  const blob = await response.blob();
  const audioUrl = URL.createObjectURL(blob);
  return { audioUrl, latencyMs };
}

export function getVoiceStatus() {
  return apiFetch<VoiceStatus>("/voice/status");
}

export function getDevices() {
  return apiFetch<ApiDevice[]>("/devices");
}

export function getApprovals() {
  return apiFetch<ApiApproval[]>("/approvals");
}

export function getSimulatorEvents() {
  return apiFetch<ApiSimulatorEvent[]>("/simulator/events");
}

export function setSimulatorFault(deviceId: string, mode: "none" | "offline" | "timeout") {
  return postJson(`/simulator/devices/${deviceId}/fault`, { mode });
}

export function decideApproval(id: string, decision: "approve" | "reject") {
  return postJson(`/approvals/${id}/${decision}`);
}

export function createDevice(payload: { id: string; name: string; room: string; kind: string; state?: Record<string, unknown> }) {
  return postJson<ApiDevice>("/devices", payload);
}

export function updateDevice(deviceId: string, payload: { name?: string; room?: string; state?: Record<string, unknown> }) {
  return apiFetch<ApiDevice>(`/devices/${deviceId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function deleteDevice(deviceId: string) {
  return apiFetch<{ status: string; device_id: string }>(`/devices/${deviceId}`, {
    method: "DELETE",
  });
}

export function getDiscoveredDevices() {
  return apiFetch<import("../types").DiscoveredDevice[]>("/discovery/devices");
}

export function pairDiscoveredDevice(deviceId: string, payload?: { name?: string; room?: string }) {
  return postJson<ApiDevice>(`/discovery/devices/${deviceId}/pair`, payload || {});
}

export function dismissDiscoveredDevice(deviceId: string) {
  return apiFetch<{ status: string; device_id: string }>(`/discovery/devices/${deviceId}`, {
    method: "DELETE",
  });
}

export function renameRoom(oldName: string, newName: string) {
  return postJson<{ status: string; old_name: string; new_name: string; updated_devices_count: number }>("/rooms/rename", {
    old_name: oldName,
    new_name: newName,
  });
}

export function deleteRoom(roomName: string) {
  return apiFetch<{ status: string; room: string; deleted_devices_count: number; deleted_devices: string[] }>(
    `/rooms/${encodeURIComponent(roomName)}`,
    {
      method: "DELETE",
    }
  );
}

export function triggerDiscoveryScan() {
  return postJson<{ status: string; message: string }>("/discovery/scan", {});
}



