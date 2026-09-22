const refreshStorageKey = "homemind-refresh-token";

let accessToken: string | null = null;

export function getAccessToken() {
  return accessToken;
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(refreshStorageKey);
}

export function setTokens(access: string, refresh: string) {
  accessToken = access;
  if (typeof window !== "undefined") {
    window.localStorage.setItem(refreshStorageKey, refresh);
  }
}

export function clearTokens() {
  accessToken = null;
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(refreshStorageKey);
  }
}

/**
 * Đăng ký hàm làm mới token để apiFetch tự thử lại một lần khi gặp 401.
 * client.ts không import auth.ts trực tiếp nhằm tránh phụ thuộc vòng.
 */
type RefreshHandler = () => Promise<boolean>;

let refreshHandler: RefreshHandler | null = null;

export function setRefreshHandler(handler: RefreshHandler | null) {
  refreshHandler = handler;
}

let inflight: Promise<boolean> | null = null;

export function refreshAccessToken(): Promise<boolean> {
  if (!refreshHandler) return Promise.resolve(false);
  if (!inflight) {
    inflight = refreshHandler().finally(() => {
      inflight = null;
    });
  }
  return inflight;
}
