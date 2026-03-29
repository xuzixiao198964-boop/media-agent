import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, afterEach } from "vitest";
import RegisterPage from "./RegisterPage";
import { TEST_ROUTER_FUTURE } from "../test/routerFuture";
import { installDefaultApiFetch } from "../test/fetchMocks";

describe("RegisterPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("渲染简化后的注册表单", () => {
    installDefaultApiFetch();

    render(
      <MemoryRouter future={TEST_ROUTER_FUTURE}>
        <RegisterPage />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "注册" })).toBeInTheDocument();
    expect(screen.getByLabelText("用户名")).toBeInTheDocument();
    expect(screen.getByLabelText("密码（≥10 位，含大小写、数字、特殊符号）")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "完成注册" })).toBeInTheDocument();
    
    // 验证不再有验证码相关元素
    expect(screen.queryByRole("img", { name: "验证码" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "发送邮箱/手机验证码" })).not.toBeInTheDocument();
  });
});
