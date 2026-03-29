import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import PublicHeader from "../components/PublicHeader";
import { api } from "../api";
import { touchActivity } from "../session";

export default function RegisterPage() {
  const nav = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function register(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      const r = await api<{ access_token: string; refresh_token?: string }>("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          password,
        }),
      });
      localStorage.setItem("token", r.access_token);
      if (r.refresh_token) {
        localStorage.setItem("refresh_token", r.refresh_token);
      }
      touchActivity();
      nav("/");
    } catch (e2: unknown) {
      setErr(e2 instanceof Error ? e2.message : "注册失败");
    }
  }

  return (
    <div className="layout public-layout">
      <PublicHeader active="register" />
      <main>
        <div className="card" style={{ maxWidth: 440, margin: "48px auto" }}>
          <h2 style={{ marginTop: 0 }}>注册</h2>
          <p className="muted">
            用户名仅字母数字下划线；密码至少 10 位且含大小写、数字、特殊符号。
          </p>
          <form onSubmit={register}>
            <label className="muted">用户名</label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              pattern="^[a-zA-Z0-9_]+$"
              minLength={3}
              maxLength={64}
              required
            />
            <div style={{ height: 10 }} />
            <label className="muted">密码（≥10 位，含大小写、数字、特殊符号）</label>
            <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" minLength={10} required />
            {err && <p style={{ color: "var(--danger)" }}>{err}</p>}
            <div style={{ height: 12 }} />
            <button className="primary" type="submit">
              完成注册
            </button>
          </form>
          <p className="muted" style={{ marginTop: 16 }}>
            已有账号？<Link to="/login">登录</Link>
          </p>
        </div>
      </main>
    </div>
  );
}
