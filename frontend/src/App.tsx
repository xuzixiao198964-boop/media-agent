import type { ReactNode } from "react";
import { NavLink, Route, Routes, Navigate, useNavigate } from "react-router-dom";
import ActivitySync from "./ActivitySync";
import UserBar from "./components/UserBar";
import { isIdleExpired, LS_ACTIVITY, touchActivity } from "./session";
import DashboardPage from "./pages/DashboardPage";
import ArticlesPage from "./pages/ArticlesPage";
import UploadPage from "./pages/UploadPage";
import JobsPage from "./pages/JobsPage";
import OutputsPage from "./pages/OutputsPage";
import PublishPage from "./pages/PublishPage";
import LogsPage from "./pages/LogsPage";
import SettingsPage from "./pages/SettingsPage";
import NovelProjectsPage from "./pages/NovelProjectsPage";
import NovelProjectDetailPage from "./pages/NovelProjectDetailPage";
import NovelChapterPage from "./pages/NovelChapterPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";

function Layout({ children }: { children: ReactNode }) {
  const nav = useNavigate();
  function logout() {
    fetch("/api/v1/auth/logout", {
      method: "POST",
      headers: { Authorization: `Bearer ${localStorage.getItem("token") || ""}` },
    }).catch(() => {});
    localStorage.removeItem("token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem(LS_ACTIVITY);
    nav("/login", { replace: true });
  }
  return (
    <div className="layout">
      <header className="app-header">
        <div className="header-brand">
          <h1>Media Agent · 资讯 → 短视频 → 发布</h1>
        </div>
        <nav className="header-nav">
          <NavLink end className={({ isActive }) => (isActive ? "active" : "")} to="/">
            总览
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? "active" : "")} to="/articles">
            资讯
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? "active" : "")} to="/upload">
            上传
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? "active" : "")} to="/jobs">
            生成
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? "active" : "")} to="/publish">
            发布
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? "active" : "")} to="/outputs">
            成片
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? "active" : "")} to="/logs">
            日志
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? "active" : "")} to="/novel">
            小说视频
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? "active" : "")} to="/settings">
            API
          </NavLink>
        </nav>
        <UserBar onLogout={logout} />
      </header>
      <ActivitySync />
      <main>{children}</main>
    </div>
  );
}

function Private({ children }: { children: ReactNode }) {
  const token = typeof localStorage !== "undefined" ? localStorage.getItem("token") : null;
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  // 仅有 token 而无活动时间（如旧数据、或验证码登录时序）：补写，避免被误判 idle 立即踢回登录页
  if (typeof localStorage !== "undefined" && !localStorage.getItem(LS_ACTIVITY)) {
    touchActivity();
  }
  if (isIdleExpired()) {
    localStorage.removeItem("token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem(LS_ACTIVITY);
    return <Navigate to="/login" replace />;
  }
  return <Layout>{children}</Layout>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route
        path="/"
        element={
          <Private>
            <DashboardPage />
          </Private>
        }
      />
      <Route
        path="/articles"
        element={
          <Private>
            <ArticlesPage />
          </Private>
        }
      />
      <Route
        path="/upload"
        element={
          <Private>
            <UploadPage />
          </Private>
        }
      />
      <Route
        path="/jobs"
        element={
          <Private>
            <JobsPage />
          </Private>
        }
      />
      <Route
        path="/outputs"
        element={
          <Private>
            <OutputsPage />
          </Private>
        }
      />
      <Route
        path="/publish"
        element={
          <Private>
            <PublishPage />
          </Private>
        }
      />
      <Route
        path="/logs"
        element={
          <Private>
            <LogsPage />
          </Private>
        }
      />
      <Route
        path="/settings"
        element={
          <Private>
            <SettingsPage />
          </Private>
        }
      />
      <Route
        path="/novel"
        element={
          <Private>
            <NovelProjectsPage />
          </Private>
        }
      />
      <Route
        path="/novel/:projectId"
        element={
          <Private>
            <NovelProjectDetailPage />
          </Private>
        }
      />
      <Route
        path="/novel/:projectId/chapter/:chapterId"
        element={
          <Private>
            <NovelChapterPage />
          </Private>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
