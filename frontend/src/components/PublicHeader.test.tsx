import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect } from "vitest";
import { TEST_ROUTER_FUTURE } from "../test/routerFuture";
import PublicHeader from "./PublicHeader";

describe("PublicHeader", () => {
  it("渲染品牌与导航链接", () => {
    render(
      <MemoryRouter future={TEST_ROUTER_FUTURE}>
        <PublicHeader active="login" />
      </MemoryRouter>
    );
    expect(screen.getByText("Media Agent")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "登录" })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("link", { name: "注册" })).toHaveAttribute("href", "/register");
  });
});
