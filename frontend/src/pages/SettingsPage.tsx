import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";

type Status = {
  deepseek_configured: boolean;
  tencent_tts_configured: boolean;
  trtc_voice_clone_configured: boolean;
  dashscope_configured: boolean;
  tencent_tts_last_error?: string | null;
  dashscope_last_error?: string | null;
  publish_mode: string;
};

export default function SettingsPage() {
  const [st, setSt] = useState<Status | null>(null);
  const [deepseek, setDeepseek] = useState("");
  const [tencentSecretId, setTencentSecretId] = useState("");
  const [tencentSecretKey, setTencentSecretKey] = useState("");
  const [trtcSdkAppId, setTrtcSdkAppId] = useState("");
  const [trtcRegion, setTrtcRegion] = useState("ap-guangzhou");
  const [dashscopeApiKey, setDashscopeApiKey] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  async function load() {
    const s = await api<Status>("/settings/api-keys");
    setSt(s);
  }

  useEffect(() => {
    load().catch((e) => setMsg(String(e)));
  }, []);

  async function save(e: FormEvent) {
    e.preventDefault();
    setMsg(null);
    try {
      await api<Status>("/settings/api-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          deepseek: deepseek || undefined,
          tencent_tts_secret_id: tencentSecretId || undefined,
          tencent_tts_secret_key: tencentSecretKey || undefined,
          trtc_sdk_app_id: trtcSdkAppId || undefined,
          trtc_region: trtcRegion || undefined,
          dashscope_api_key: dashscopeApiKey || undefined,
        }),
      });
      setDeepseek("");
      setTencentSecretId("");
      setTencentSecretKey("");
      setTrtcSdkAppId("");
      setTrtcRegion("ap-guangzhou");
      setDashscopeApiKey("");
      await load();
      setMsg("已保存（密钥仅存服务端，前端不展示明文）");
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "失败");
    }
  }

  return (
    <div>
      <h2>API 配置状态</h2>
      <p className="muted">密钥可来自服务器环境变量，也可在此写入数据库（Fernet 加密）。详见项目 docs/API-SELECTION.md。</p>
      {msg && <p className="pill warn">{msg}</p>}
      {st && (
        <div className="grid" style={{ marginBottom: 12 }}>
          <div className="stat">
            <div className="k">DeepSeek</div>
            <div className="v">{st.deepseek_configured ? "已配置" : "未配置"}</div>
          </div>
          <div className="stat">
            <div className="k">腾讯云 TTS</div>
            <div className="v">
              {st.tencent_tts_configured ? (st.tencent_tts_last_error ? "异常" : "已配置") : "未配置"}
            </div>
            {st.tencent_tts_configured && st.tencent_tts_last_error && (
              <button
                type="button"
                style={{ marginTop: 8, width: "100%" }}
                className="btn"
                onClick={() => setMsg(String(st.tencent_tts_last_error))}
              >
                查看原因
              </button>
            )}
          </div>
          <div className="stat">
            <div className="k">TRTC VoiceClone</div>
            <div className="v">{st.trtc_voice_clone_configured ? "已配置" : "未配置"}</div>
          </div>
          <div className="stat">
            <div className="k">阿里云 VideoRetalk</div>
            <div className="v">
              {st.dashscope_configured ? (st.dashscope_last_error ? "异常" : "已配置") : "未配置"}
            </div>
            {st.dashscope_configured && st.dashscope_last_error && (
              <button
                type="button"
                style={{ marginTop: 8, width: "100%" }}
                className="btn"
                onClick={() => setMsg(String(st.dashscope_last_error))}
              >
                查看原因
              </button>
            )}
          </div>
          <div className="stat">
            <div className="k">发布模式</div>
            <div className="v">{st.publish_mode}</div>
          </div>
        </div>
      )}
      <div className="card">
        <h3 style={{ marginTop: 0 }}>更新密钥（留空则不变）</h3>
        <form onSubmit={save}>
          <label className="muted">DEEPSEEK_API_KEY</label>
          <input value={deepseek} onChange={(e) => setDeepseek(e.target.value)} type="password" autoComplete="off" />
          <div style={{ height: 10 }} />
          <label className="muted">腾讯云 TTS SecretId</label>
          <input value={tencentSecretId} onChange={(e) => setTencentSecretId(e.target.value)} type="password" autoComplete="off" />
          <div style={{ height: 10 }} />
          <label className="muted">腾讯云 TTS SecretKey</label>
          <input value={tencentSecretKey} onChange={(e) => setTencentSecretKey(e.target.value)} type="password" autoComplete="off" />
          <div style={{ height: 10 }} />

          <label className="muted">TRTC SdkAppID</label>
          <input value={trtcSdkAppId} onChange={(e) => setTrtcSdkAppId(e.target.value)} type="password" autoComplete="off" />
          <div style={{ height: 10 }} />
          <label className="muted">TRTC 地域（仅支持 ap-guangzhou 等）</label>
          <select value={trtcRegion} onChange={(e) => setTrtcRegion(e.target.value)}>
            <option value="ap-guangzhou">ap-guangzhou</option>
            <option value="ap-beijing">ap-beijing</option>
            <option value="ap-shanghai">ap-shanghai</option>
          </select>
          <div style={{ height: 10 }} />

          <label className="muted">DashScope API Key（VideoRetalk）</label>
          <input value={dashscopeApiKey} onChange={(e) => setDashscopeApiKey(e.target.value)} type="password" autoComplete="off" />
          <div style={{ height: 12 }} />
          <button className="primary" type="submit">
            保存
          </button>
        </form>
      </div>
    </div>
  );
}
