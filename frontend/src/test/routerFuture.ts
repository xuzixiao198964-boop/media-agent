/** 测试中启用 React Router v7 兼容开关，避免控制台 migration 警告 */
export const TEST_ROUTER_FUTURE = {
  v7_startTransition: true,
  v7_relativeSplatPath: true,
} as const;
