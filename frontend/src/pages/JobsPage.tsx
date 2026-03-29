import { useEffect, useMemo, useState } from "react";
import { api } from "../api";

type Article = { id: number; title: string; category_id: number; hot_score: number };
type UV = { id: number; original_name: string };
type Category = { id: number; name: string; slug: string };
type Job = {
  id: number;
  article_id: number | null;
  user_video_id: number;
  status: string;
  output_path: string | null;
  narration_text: string | null;
  output_description: string | null;
  error: string | null;
  meta: Record<string, unknown> | null;
  queue_position?: number | null;
  queue_pending_total?: number | null;
};
type VoicePrint = {
  id: number;
  status: string;
  source_type: string;
  source_video_id: number | null;
  original_name: string;
  voice_gender: number;
  tts_language: string;
  error?: string | null;
  voice_source_label_zh?: string;
  voice_type_label_zh?: string;
  demo_audio_path?: string | null;
};

export default function JobsPage() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [videos, setVideos] = useState<UV[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [voiceprints, setVoiceprints] = useState<VoicePrint[]>([]);
  const [genMode, setGenMode] = useState<"article" | "text">("article");
  const [aid, setAid] = useState<number | "">("");
  const [vid, setVid] = useState<number | "">("");
  const [lang, setLang] = useState("zh-CN");
  const [categoryId, setCategoryId] = useState<number | "">("");
  const [voiceprintId, setVoiceprintId] = useState<number | "">("");
  const [userPrompt, setUserPrompt] = useState("");
  const [directScript, setDirectScript] = useState("");
  const [scriptSource, setScriptSource] = useState<"deepseek" | "direct">("deepseek");
  const [displayTitle, setDisplayTitle] = useState("");
  const [audioMode, setAudioMode] = useState<"tts" | "tts_bgm" | "bgm_only">("tts");
  const [bgmVolume, setBgmVolume] = useState(0.22);
  const [lipSync, setLipSync] = useState(true);
  const [outputDesc, setOutputDesc] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function refresh() {
    const [a, c, v, j, vp] = await Promise.all([
      api<Article[]>("/articles?sort=hot&limit=100"),
      api<Category[]>("/categories"),
      api<UV[]>("/videos"),
      api<Job[]>("/pipeline/jobs?limit=80"),
      api<VoicePrint[]>("/voiceprints"),
    ]);
    setArticles(a);
    setCategories(c);
    setVideos(v);
    setJobs(j);
    setVoiceprints(vp);
    if (categoryId === "") {
      const ai = c.find((x) => /ai|人工智能/i.test(x.slug + x.name));
      if (ai) setCategoryId(ai.id);
    }
  }

  useEffect(() => {
    refresh().catch((e) => setErr(String(e)));
    const t = setInterval(() => refresh().catch(() => {}), 8000);
    return () => clearInterval(t);
  }, []);

  async function createJob() {
    setErr(null);
    if (vid === "") {
      setErr("请选择真人视频");
      return;
    }
    if (genMode === "article") {
      if (aid === "") {
        setErr("请选择资讯文章");
        return;
      }
    } else {
      if (scriptSource === "deepseek" && !userPrompt.trim()) {
        setErr("请填写文字需求，或切换到「直接粘贴口播」");
        return;
      }
      if (scriptSource === "direct" && !directScript.trim()) {
        setErr("请粘贴口播正文");
        return;
      }
    }
    const body: Record<string, unknown> = {
      generation_mode: genMode,
      user_video_id: vid,
      tts_language: lang,
      voice_profile_id: voiceprintId === "" ? undefined : Number(voiceprintId),
      script_source: genMode === "article" ? "article" : scriptSource,
      audio_mode: audioMode,
      bgm_volume: bgmVolume,
      lip_sync: lipSync,
      output_description: outputDesc.trim() || undefined,
    };
    if (genMode === "article") {
      body.article_id = aid;
    } else {
      body.user_prompt = userPrompt.trim() || undefined;
      body.direct_script = directScript.trim() || undefined;
      body.display_title = displayTitle.trim() || undefined;
    }
    try {
      await api<Job>("/pipeline/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      await refresh();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "失败");
    }
  }

  async function retry(id: number) {
    setErr(null);
    try {
      await api<Job>(`/pipeline/jobs/${id}/retry`, { method: "POST" });
      await refresh();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "失败");
    }
  }

  function pillFor(s: string) {
    if (s === "done") return "pill ok";
    if (s === "failed") return "pill err";
    return "pill warn";
  }

  const filteredArticles = useMemo(() => {
    const base = categoryId === "" ? articles : articles.filter((x) => x.category_id === categoryId);
    return [...base].sort((a, b) => b.hot_score - a.hot_score);
  }, [articles, categoryId]);

  return (
    <div className="page-jobs">
      <h2>AI 生成任务</h2>
      {err && <p className="pill err">{err}</p>}

      <div className="card">
        <div className="muted" style={{ marginBottom: 8 }}>
          生成模式
        </div>
        <div className="row">
          <label className="row-inline">
            <input type="radio" checked={genMode === "article"} onChange={() => setGenMode("article")} />
            资讯成片（抓取栏目 + DeepSeek 口播）
          </label>
          <label className="row-inline">
            <input type="radio" checked={genMode === "text"} onChange={() => setGenMode("text")} />
            文案成片（文字需求 → DeepSeek 写稿 或 直接粘贴口播）
          </label>
        </div>

        {genMode === "text" && (
          <>
            <div style={{ height: 10 }} />
            <label className="muted">成片标题（横幅展示，可空）</label>
            <input value={displayTitle} onChange={(e) => setDisplayTitle(e.target.value)} placeholder="如：今日科技快讯" />
            <div style={{ height: 10 }} />
            <label className="muted">文案来源</label>
            <div className="row">
              <label className="row-inline">
                <input
                  type="radio"
                  checked={scriptSource === "deepseek"}
                  onChange={() => setScriptSource("deepseek")}
                />
                用文字需求让 DeepSeek 生成口播
              </label>
              <label className="row-inline">
                <input type="radio" checked={scriptSource === "direct"} onChange={() => setScriptSource("direct")} />
                直接粘贴口播正文
              </label>
            </div>
            {scriptSource === "deepseek" ? (
              <>
                <div style={{ height: 10 }} />
                <label className="muted">文字需求（会调用 DeepSeek API）</label>
                <textarea rows={4} value={userPrompt} onChange={(e) => setUserPrompt(e.target.value)} placeholder="描述你想要的短视频风格、要点、受众等" />
              </>
            ) : (
              <>
                <div style={{ height: 10 }} />
                <label className="muted">口播正文</label>
                <textarea rows={6} value={directScript} onChange={(e) => setDirectScript(e.target.value)} placeholder="粘贴完整口播稿" />
              </>
            )}
          </>
        )}

        <div style={{ height: 12 }} />
        <div className="muted">画面与声音</div>
        <div className="row cols-mobile">
          {genMode === "article" && (
            <>
              <select value={categoryId} onChange={(e) => setCategoryId(e.target.value ? Number(e.target.value) : "")}>
                <option value="">全部栏目（按热度）</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              <select value={aid} onChange={(e) => setAid(e.target.value ? Number(e.target.value) : "")}>
                <option value="">选择资讯（热度高在前）</option>
                {filteredArticles.map((a) => (
                  <option key={a.id} value={a.id}>
                    #{a.id} [热度 {a.hot_score}] {a.title.slice(0, 40)}
                  </option>
                ))}
              </select>
            </>
          )}
          <select value={vid} onChange={(e) => setVid(e.target.value ? Number(e.target.value) : "")}>
            <option value="">选择真人视频</option>
            {videos.map((v) => (
              <option key={v.id} value={v.id}>
                #{v.id} {v.original_name}
              </option>
            ))}
          </select>
          <select value={lang} onChange={(e) => setLang(e.target.value)}>
            <option value="zh-CN">简体中文（默认）</option>
            <option value="en-US">English</option>
            <option value="ja-JP">日本語</option>
          </select>

          <select value={audioMode} onChange={(e) => setAudioMode(e.target.value as typeof audioMode)}>
            <option value="tts">口播配音（TTS）</option>
            <option value="tts_bgm">口播 + 背景音乐（需服务器配置 BGM 文件）</option>
            <option value="bgm_only">仅字幕 + 背景音乐（无口播人声）</option>
          </select>

          <label className="row-inline">
            <input type="checkbox" checked={lipSync} onChange={(e) => setLipSync(e.target.checked)} />
            口型与配音一致（需 DashScope VideoRetalk；关闭则本地合成）
          </label>
        </div>

        {audioMode !== "tts" && (
          <p className="muted" style={{ marginTop: 8 }}>
            口播+BGM / 纯BGM 模式需在服务器环境变量配置 <code>DEFAULT_BGM_PATH</code> 指向有效 mp3/wav 文件。
          </p>
        )}

        {audioMode === "tts_bgm" && (
          <div className="row" style={{ marginTop: 8 }}>
            <label className="muted" style={{ flex: "1 1 200px" }}>
              背景音乐相对音量 {Math.round(bgmVolume * 100)}%
              <input
                type="range"
                min={0.05}
                max={0.55}
                step={0.01}
                value={bgmVolume}
                onChange={(e) => setBgmVolume(Number(e.target.value))}
              />
            </label>
          </div>
        )}

        <div style={{ height: 10 }} />
        <label className="muted">成片说明（写入成片库，可空）</label>
        <textarea rows={2} value={outputDesc} onChange={(e) => setOutputDesc(e.target.value)} placeholder="一句话说明这条成片主题，便于在「成片」页展示" />

        <div style={{ height: 10 }} />
        <label className="muted">合成声纹（可选；不选且视频有原声时会自动尝试原生声纹）</label>
        <select value={voiceprintId} onChange={(e) => setVoiceprintId(e.target.value ? Number(e.target.value) : "")}>
          <option value="">默认 / 自动原生声纹</option>
          {voiceprints.map((vp) => (
            <option
              key={vp.id}
              value={vp.id}
              disabled={vp.status !== "ready"}
              title={vp.voice_type_label_zh || vp.voice_source_label_zh || ""}
            >
              #{vp.id} {vp.status !== "ready" ? `[${vp.status}] ` : ""}
              {vp.voice_source_label_zh ? `${vp.voice_source_label_zh.slice(0, 12)}…` : vp.original_name.slice(0, 18)}
            </option>
          ))}
        </select>

        <div style={{ height: 12 }} />
        <button className="primary" type="button" onClick={createJob}>
          创建生成任务
        </button>

        <div className="row" style={{ marginTop: 12, justifyContent: "space-between" }}>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={async () => {
                setErr(null);
                if (vid === "") {
                  setErr("请先选择真人视频（用于提取视频声纹）");
                  return;
                }
                if (lang !== "zh-CN") {
                  setErr("当前声纹（VRS）仅实现中文，请切换到简体中文再提取。");
                  return;
                }
                try {
                  await api<VoicePrint>("/voiceprints/from-video", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ user_video_id: vid, voice_gender: 1, tts_language: lang }),
                  });
                  await refresh();
                } catch (e: unknown) {
                  setErr(e instanceof Error ? e.message : "提取失败");
                }
              }}
            >
              提取所选视频声纹
            </button>
            <label className="muted" style={{ display: "flex", gap: 8, alignItems: "center" }}>
              导入声音
              <input
                type="file"
                accept="audio/*,video/*"
                onChange={async (e) => {
                  const f = e.target.files?.[0] ?? null;
                  if (!f) return;
                  setErr(null);
                  if (lang !== "zh-CN") {
                    setErr("当前声纹（VRS）仅实现中文，请切换到简体中文再导入。");
                    return;
                  }
                  try {
                    const fd = new FormData();
                    fd.append("file", f);
                    fd.append("voice_gender", "1");
                    fd.append("tts_language", lang);
                    const token = localStorage.getItem("token");
                    await fetch("/api/v1/voiceprints/import-audio", {
                      method: "POST",
                      headers: { Authorization: token ? `Bearer ${token}` : "" },
                      body: fd,
                    }).then(async (r) => {
                      if (!r.ok) throw new Error(await r.text());
                    });
                    await refresh();
                  } catch (e: unknown) {
                    setErr(e instanceof Error ? e.message : "导入失败");
                  }
                }}
              />
            </label>
          </div>
        </div>
      </div>

      <h3>任务列表（含生成中）</h3>
      <div className="job-list">
        {jobs.map((j) => (
          <div key={j.id} className="card">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <span className={pillFor(j.status)}>{j.status}</span>{" "}
                <span className="muted">
                  job #{j.id} · {(j.meta as { generation_mode?: string } | null)?.generation_mode || "article"} · 文章{" "}
                  {j.article_id ?? "—"} · 视频 {j.user_video_id}
                  {j.queue_position != null && j.queue_pending_total != null && (
                    <> · 队列第 {j.queue_position}/{j.queue_pending_total} 位</>
                  )}
                </span>
              </div>
              <button type="button" onClick={() => retry(j.id)}>
                重新生成
              </button>
            </div>
            {j.output_description && (
              <div style={{ marginTop: 8 }} className="muted">
                说明：{j.output_description}
              </div>
            )}
            {j.narration_text && (
              <div style={{ marginTop: 10 }}>
                <div className="muted">口播稿</div>
                <div className="body-text">{j.narration_text}</div>
              </div>
            )}
            {j.error && (
              <div style={{ marginTop: 10, color: "var(--danger)" }}>
                {j.error}
              </div>
            )}
            {j.status === "done" && j.output_path && (
              <div style={{ marginTop: 10 }}>
                <video src={`/media/job_${j.id}.mp4`} controls playsInline />
              </div>
            )}
          </div>
        ))}
        {!jobs.length && <div className="card muted">暂无任务</div>}
      </div>
    </div>
  );
}
