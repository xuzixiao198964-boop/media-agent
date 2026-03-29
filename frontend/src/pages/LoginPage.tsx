import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import PublicHeader from "../components/PublicHeader";
import { API_PREFIX, api } from "../api";
import { touchActivity } from "../session";

type LoginResp = { access_token?: string; refresh_token?: string; detail?: string; requires_captcha?: boolean };
type CaptchaResp = { captcha_id: string; image_base64: string };

export default function LoginPage() {
  const nav = useNavigate();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [captchaRequired, setCaptchaRequired] = useState(false);
  const [captchaId, setCaptchaId] = useState("");
  const [captchaImg, setCaptchaImg] = useState("");
  const [captchaAnswer, setCaptchaAnswer] = useState("");

  async function loadCaptcha() {
    try {
      const r = await api<CaptchaResp>("/auth/captcha");
      setCaptchaId(r.captcha_id);
      setCaptchaImg(r.image_base64);
      setCaptchaAnswer("");
    } catch {
      /* ignore */
    }
  }

  async function submitPassword(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    const body: Record<string, unknown> = {
      login: login.trim(),
      password,
    };
    if (captchaRequired && captchaId) {
      body.captcha_id = captchaId;
      body.captcha_answer = captchaAnswer;
    }
    const res = await fetch(`${API_PREFIX}/auth/login/password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = (await res.json().catch(() => ({}))) as LoginResp;
    if (!res.ok) {
      setErr(typeof data.detail === "string" ? data.detail : `登录失败 ${res.status}`);
      if (data.requires_captcha) {
        setCaptchaRequired(true);
        loadCaptcha();
      }
      return;
    }
    if (!data.access_token) {
      setErr("登录响应异常");
      return;
    }
    localStorage.setItem("token", data.access_token);
    if (data.refresh_token) {
      localStorage.setItem("refresh_token", data.refresh_token);
    }
    touchActivity();
    nav("/");
  }

  return (
    <div className="layout public-layout">
      <PublicHeader active="login" />
      <main>
        <div className="card" data-testid="login-card" style={{ maxWidth: 440, margin: "48px auto" }}>
          <h2 style={{ marginTop: 0 }}>登录</h2>
          <form onSubmit={submitPassword}>
            <p className="muted">使用用户名和密码登录</p>
            <label className="muted">用户名</label>
            <input value={login} onChange={(e) => setLogin(e.target.value)} required autoComplete="username" />
            <div style={{ height: 10 }} />
            <label className="muted">密码</label>
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              required
              autoComplete="current-password"
            />
            {captchaRequired && captchaImg && (
              <>
                <div style={{ height: 10 }} />
                <label className="muted">验证码</label>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <input
                    value={captchaAnswer}
                    onChange={(e) => setCaptchaAnswer(e.target.value)}
                    required
                    style={{ flex: 1 }}
                    placeholder="请输入验证码"
                  />
                  <img
                    src={`data:image/png;base64,${captchaImg}`}
                    alt="验证码"
                    style={{ height: 40, cursor: "pointer", borderRadius: 4 }}
                    onClick={loadCaptcha}
                    title="点击刷新"
                  />
                </div>
              </>
            )}
            {err && <p style={{ color: "var(--danger)" }}>{err}</p>}
            <div style={{ height: 12 }} />
            <button className="primary" type="submit">
              登录
            </button>
          </form>
          <p className="muted" style={{ marginTop: 16 }}>
            <Link to="/register">注册</Link>
            {" · "}
            <Link to="/forgot-password">忘记密码</Link>
          </p>
        </div>
      </main>
    </div>
  );
}
