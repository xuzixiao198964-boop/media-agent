import { vi } from "vitest";

/** 测试中统一 mock fetch：覆盖总览、用户信息等受保护页会发起的请求 */
export function installDefaultApiFetch(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const u = typeof input === "string" ? input : input.url;
      if (u.includes("/api/v1/status/summary")) {
        return new Response(
          JSON.stringify({
            articles_active: 0,
            my_videos: 0,
            generation: { pending: 0, processing: 0, done: 0, failed: 0 },
            publish: { success: 0, failed: 0 },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      if (u.includes("/api/v1/auth/me")) {
        return new Response(
          JSON.stringify({
            id: 1,
            username: "testuser",
            display_name: null,
            avatar_url: "https://example.com/a.png",
            bio: null,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      if (u.includes("/api/v1/auth/captcha")) {
        return new Response(
          JSON.stringify({
            captcha_id: "captcha-test-id",
            image_base64:
              "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      if (u.includes("/api/v1/auth/logout")) {
        return new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("not found", { status: 404 });
    })
  );
}
