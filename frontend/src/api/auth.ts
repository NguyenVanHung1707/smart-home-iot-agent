import type { Role } from "../types";
import { apiFetch, postJson } from "./client";
import { clearTokens, getRefreshToken, setTokens } from "./tokenStore";

export type BackendRole = "ADMIN" | "MEMBER";

export interface UserPublic {
  id: string;
  email: string;
  display_name: string;
  role: BackendRole;
  locked: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserPublic;
}

export function roleFromBackend(role: BackendRole): Role {
  return role === "ADMIN" ? "homeadmin" : "member";
}

export async function login(email: string, password: string): Promise<UserPublic> {
  const data = await postJson<TokenResponse>("/auth/login", {
    email: email.trim().toLowerCase(),
    password,
  });
  setTokens(data.access_token, data.refresh_token);
  return data.user;
}

/** Đổi refresh token trong localStorage thành access token mới. */
export async function refreshSession(): Promise<UserPublic | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;
  try {
    const data = await apiFetch<TokenResponse>(
      "/auth/refresh",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      },
      { skipAuthRetry: true },
    );
    setTokens(data.access_token, data.refresh_token);
    return data.user;
  } catch {
    clearTokens();
    return null;
  }
}

export function getCurrentUser() {
  return apiFetch<UserPublic>("/auth/me");
}

export async function logout(): Promise<void> {
  try {
    await postJson("/auth/logout");
  } catch {
    // Kể cả khi Hub không phản hồi, phiên phía client vẫn phải bị xóa.
  } finally {
    clearTokens();
  }
}
