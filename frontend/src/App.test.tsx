import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import App from "./App";
import { LS_ACTIVITY } from "./session";
import { installDefaultApiFetch } from "./test/fetchMocks";
import { TEST_ROUTER_FUTURE } from "./test/routerFuture";

describe("App 路由", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("未登录访问 / 时展示登录页", async () => {
    render(
      <MemoryRouter initialEntries={["/"]} future={TEST_ROUTER_FUTURE}>
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByTestId("login-card")).toBeInTheDocument();
    expect(screen.getByText(/使用用户名和密码登录/)).toBeInTheDocument();
  });

  it("未登录访问 /articles 时展示登录页", async () => {
    render(
      <MemoryRouter initialEntries={["/articles"]} future={TEST_ROUTER_FUTURE}>
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByTestId("login-card")).toBeInTheDocument();
  });

  it("已登录且活动有效时 / 显示总览", async () => {
    localStorage.setItem("token", "fake-jwt");
    localStorage.setItem(LS_ACTIVITY, String(Date.now()));
    installDefaultApiFetch();

    render(
      <MemoryRouter initialEntries={["/"]} future={TEST_ROUTER_FUTURE}>
        <App />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "总览" })).toBeInTheDocument();
    });
  });

  it("直接打开 /login 显示登录表单", async () => {
    render(
      <MemoryRouter initialEntries={["/login"]} future={TEST_ROUTER_FUTURE}>
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByTestId("login-card")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "登录" })).toBeInTheDocument();
  });

  it("直接打开 /register 显示注册页", async () => {
    render(
      <MemoryRouter initialEntries={["/register"]} future={TEST_ROUTER_FUTURE}>
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByRole("heading", { name: "注册" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "完成注册" })).toBeInTheDocument();
  });
});
