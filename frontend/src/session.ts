/** 1 小时无操作视为过期（与后端 JWT 独立，前端强制下线） */
export const IDLE_MS = 60 * 60 * 1000;
export const LS_ACTIVITY = "last_activity_at";

export function touchActivity(): void {
  try {
    localStorage.setItem(LS_ACTIVITY, String(Date.now()));
  } catch {
    /* ignore */
  }
}

export function isIdleExpired(): boolean {
  const t = parseInt(localStorage.getItem(LS_ACTIVITY) || "0", 10);
  if (!t) return true;
  return Date.now() - t > IDLE_MS;
}
