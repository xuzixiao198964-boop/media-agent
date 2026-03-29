import { LS_ACTIVITY, touchActivity } from "./session";

export const API_PREFIX = "/api/v1";
const prefix = API_PREFIX;

function authHeader(): HeadersInit {
  const t = localStorage.getItem("token");
  return t ? { Authorization: `Bearer ${t}` } : {};
}

let _refreshing: Promise<boolean> | null = null;

async function tryRefreshToken(): Promise<boolean> {
  const rt = localStorage.getItem("refresh_token");
  if (!rt) return false;
  try {
    const res = await fetch(`${prefix}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (!res.ok) {
      localStorage.removeItem("token");
      localStorage.removeItem("refresh_token");
      return false;
    }
    const data = await res.json();
    if (data.access_token) {
      localStorage.setItem("token", data.access_token);
      if (data.refresh_token) {
        localStorage.setItem("refresh_token", data.refresh_token);
      }
      return true;
    }
  } catch {
    /* ignore */
  }
  localStorage.removeItem("token");
  localStorage.removeItem("refresh_token");
  return false;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${prefix}${path}`, {
    ...init,
    headers: {
      ...(init?.headers || {}),
      ...authHeader(),
    },
  });

  if (res.status === 401 && !path.startsWith("/auth/")) {
    if (!_refreshing) {
      _refreshing = tryRefreshToken().finally(() => { _refreshing = null; });
    }
    const refreshed = await _refreshing;
    if (refreshed) {
      const retry = await fetch(`${prefix}${path}`, {
        ...init,
        headers: {
          ...(init?.headers || {}),
          ...authHeader(),
        },
      });
      if (retry.ok) {
        if (retry.status === 204) {
          touchActivity();
          return undefined as T;
        }
        const data = (await retry.json()) as T;
        touchActivity();
        return data;
      }
    }
    localStorage.removeItem("token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem(LS_ACTIVITY);
    if (
      typeof window !== "undefined" &&
      !/^\/(login|register|forgot-password)(\/|$)/.test(window.location.pathname)
    ) {
      window.location.href = "/login";
    }
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail ?? JSON.stringify(j);
    } catch { /* ignore */ }
    throw new Error(`${res.status} ${detail}`);
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail ?? JSON.stringify(j);
    } catch {
      /* ignore */
    }
    throw new Error(`${res.status} ${detail}`);
  }
  if (res.status === 204) {
    touchActivity();
    return undefined as T;
  }
  const data = (await res.json()) as T;
  touchActivity();
  return data;
}
