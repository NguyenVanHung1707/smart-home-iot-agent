import { useCallback, useEffect, useRef, useState } from "react";
import type { UserPublic } from "../api/auth";
import { getCurrentUser, login as loginRequest, logout as logoutRequest, refreshSession, roleFromBackend } from "../api/auth";
import { clearTokens, getRefreshToken, setRefreshHandler } from "../api/tokenStore";
import type { Role } from "../types";

export type AuthStatus = "loading" | "anonymous" | "authenticated";

export function useAuth() {
  const [status, setStatus] = useState<AuthStatus>(() => (getRefreshToken() ? "loading" : "anonymous"));
  const [user, setUser] = useState<UserPublic | null>(null);
  const userRef = useRef<UserPublic | null>(null);

  const applyUser = useCallback((next: UserPublic | null) => {
    userRef.current = next;
    setUser(next);
    setStatus(next ? "authenticated" : "anonymous");
  }, []);

  // Cho apiFetch tự làm mới access token khi gặp 401.
  useEffect(() => {
    setRefreshHandler(async () => {
      const refreshed = await refreshSession();
      if (!refreshed) {
        applyUser(null);
        return false;
      }
      applyUser(refreshed);
      return true;
    });
    return () => setRefreshHandler(null);
  }, [applyUser]);

  // Phục hồi phiên khi tải lại trang.
  useEffect(() => {
    let cancelled = false;
    if (!getRefreshToken()) {
      setStatus("anonymous");
      return;
    }
    void (async () => {
      const restored = await refreshSession();
      if (cancelled) return;
      if (!restored) {
        applyUser(null);
        return;
      }
      try {
        const fresh = await getCurrentUser();
        if (!cancelled) applyUser(fresh);
      } catch {
        if (!cancelled) applyUser(restored);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applyUser]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const signedIn = await loginRequest(email, password);
      applyUser(signedIn);
      return signedIn;
    },
    [applyUser],
  );

  const signOut = useCallback(async () => {
    await logoutRequest();
    clearTokens();
    applyUser(null);
  }, [applyUser]);

  const role: Role | null = user ? roleFromBackend(user.role) : null;

  return { status, user, role, signIn, signOut };
}
