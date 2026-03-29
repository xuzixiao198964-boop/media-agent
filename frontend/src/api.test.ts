import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { LS_ACTIVITY } from "./session";
import { api } from "./api";

describe("api()", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("200 时解析 JSON 并 touch 活动", async () => {
    localStorage.setItem(LS_ACTIVITY, "1000");
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ hello: "world" }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        )
      )
    );

    const out = await api<{ hello: string }>("/status/summary");
    expect(out.hello).toBe("world");
    const t1 = localStorage.getItem(LS_ACTIVITY);
    expect(t1).toBeTruthy();
    expect(Number(t1)).toBeGreaterThan(1000);
  });

  it("401 时清除 token（非 auth 路径）", async () => {
    localStorage.setItem("token", "bad");
    localStorage.setItem(LS_ACTIVITY, String(Date.now()));

    // pathname 为登录相关页时不改 href，避免 jsdom 对 location 赋值报错
    const loc = { pathname: "/login", href: "http://localhost/login" };
    vi.stubGlobal("window", { ...window, location: loc as Location });

    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ detail: "Unauthorized" }), {
            status: 401,
            headers: { "Content-Type": "application/json" },
          })
        )
      )
    );

    await expect(api("/categories")).rejects.toThrow();
    expect(localStorage.getItem("token")).toBeNull();
    expect(localStorage.getItem(LS_ACTIVITY)).toBeNull();
  });
});
