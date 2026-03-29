import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import PublicHeader from "../components/PublicHeader";
import { api } from "../api";
import { touchActivity } from "../session";

export default function ForgotPasswordPage() {
  const nav = useNavigate();
  const [username, setUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      const r = await api<{ access_token: string; refresh_token?: string }>("/auth/password-reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          new_password: newPassword,
        }),
      });
      localStorage.setItem("token", r.access_token);
      if (r.refresh_token) {
        localStorage.setItem("refresh_token", r.refresh_token);
      }
      touchActivity();
      nav("/");
    } catch (e2: unknown) {
      setErr(e2 instanceof Error ? e2.message : "重置失败");
    }
  }

  return (
    <div className="layout public-layout">
      <PublicHeader active="forgot" />
      <main>
        <div className="card" style={{ maxWidth: 440, margin: "48px auto" }}>
          <h2 style={{ marginTop: 0 }}>重置密码</h2>
          <p className="muted">
            输入用户名与新密码。新密码至少 10 位且含大小写、数字、特殊符号，且不能与旧密码相同。
          </p>
          <form onSubmit={submit}>
            <label className="muted">用户名</label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              pattern="^[a-zA-Z0-9_]+$"
              minLength={3}
              maxLength={64}
            />
            <div style={{ height: 10 }} />
            <label className="muted">新密码</label>
            <input
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              type="password"
              minLength={10}
              required
            />
            {err && <p style={{ color: "var(--danger)" }}>{err}</p>}
            <div style={{ height: 12 }} />
            <button className="primary" type="submit">
              重置并登录
            </button>
          </form>
          <p className="muted" style={{ marginTop: 16 }}>
            <Link to="/login">返回登录</Link>
          </p>
        </div>
      </main>
    </div>
  );
}
