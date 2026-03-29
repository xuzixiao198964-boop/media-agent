import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { IDLE_MS, LS_ACTIVITY, isIdleExpired, touchActivity } from "./session";

describe("session", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("无活动记录时视为已过期", () => {
    expect(isIdleExpired()).toBe(true);
  });

  it("touchActivity 后未超时则未过期", () => {
    touchActivity();
    expect(isIdleExpired()).toBe(false);
  });

  it(`超过 ${IDLE_MS}ms 后视为过期`, () => {
    touchActivity();
    vi.advanceTimersByTime(IDLE_MS + 1);
    expect(isIdleExpired()).toBe(true);
  });

  it("last_activity_at 写入 localStorage", () => {
    touchActivity();
    const t = localStorage.getItem(LS_ACTIVITY);
    expect(t).toBeTruthy();
    expect(parseInt(t!, 10)).toBeGreaterThan(0);
  });
});
