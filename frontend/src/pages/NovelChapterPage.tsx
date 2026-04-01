import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../api";

type Scene = {
  scene_id: number; type: string; speaker: string; text: string;
  visual_prompt: string; mood: string; duration_hint: number;
};
type Script = { summary: string; estimated_duration_sec: number; scenes: Scene[] };
type ReviewItem = { scene_id?: number; field?: string; comment: string };
type Review = {
  id: number; review_stage: string; review_round: number; status: string;
  notes: string | null; items: ReviewItem[] | null; created_at: string;
};
type ChapterDetail = {
  id: number; project_id: number; chapter_no: number; title: string;
  raw_text: string | null; script: Script | null;
  script_status: string; script_review_notes: string | null;
  prompt_status: string; prompt_review_notes: string | null;
  image_status: string; image_review_notes: string | null;
  video_status: string; video_review_notes: string | null;
  output_path: string | null; audio_assets: Record<string, any> | null;
  visual_assets: Record<string, any> | null;
  image_prompts: Record<string, any> | null;
  bgm_id: number | null; bgm_volume: number;
  estimated_duration: number | null; actual_duration: number | null;
  prompt_review_round: number; image_review_round: number;
  error: string | null;
};

const MOOD_COLORS: Record<string, string> = {
  neutral: "#9aa3b2", happy: "#3ddc97", sad: "#6ea8fe", tense: "#ff6b6b",
  romantic: "#f7a8b8", mysterious: "#c49cde", angry: "#ff6b6b", peaceful: "#74c0fc",
};

function formatSec(sec: number | null) {
  if (!sec) return "--";
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function NovelChapterPage() {
  const { projectId, chapterId } = useParams<{ projectId: string; chapterId: string }>();
  const nav = useNavigate();
  const pid = Number(projectId);
  const cid = Number(chapterId);

  const [ch, setCh] = useState<ChapterDetail | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [tab, setTab] = useState<"script" | "images" | "video" | "reviews">("script");

  const [reviewNotes, setReviewNotes] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState("");

  const [regenSceneId, setRegenSceneId] = useState<number | "">("");
  const [regenTarget, setRegenTarget] = useState<"audio" | "visual" | "both">("both");

  const refresh = useCallback(async () => {
    const [detail, revs] = await Promise.all([
      api<ChapterDetail>(`/novel/chapters/${cid}`),
      api<Review[]>(`/novel/chapters/${cid}/reviews`),
    ]);
    setCh(detail);
    setReviews(revs);
  }, [cid]);

  useEffect(() => {
    refresh().catch((e) => setErr(e.message));
    const t = setInterval(() => refresh().catch(() => {}), 5000);
    return () => clearInterval(t);
  }, [refresh]);

  async function doAction(action: string, url: string, body?: any) {
    setBusy(action);
    setErr(null);
    try {
      await api<any>(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : undefined,
      });
      await refresh();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy("");
    }
  }

  if (!ch) return <div className="card muted">加载中...</div>;

  const script = ch.script as Script | null;

  return (
    <div>
      <button onClick={() => nav(`/novel/${pid}`)} style={{ marginBottom: 12 }}>← 返回章节列表</button>

      {err && <div className="card" style={{ borderColor: "var(--danger)", color: "var(--danger)" }}>{err}</div>}

      {/* 章节概要 */}
      <div className="card">
        <h2 style={{ margin: 0 }}>第{ch.chapter_no}章 · {ch.title}</h2>
        <div className="grid" style={{ marginTop: 12 }}>
          <div className="stat">
            <div className="k">脚本</div>
            <div className="v"><StatusLabel status={ch.script_status} type="script" /></div>
          </div>
          <div className="stat">
            <div className="k">提示词</div>
            <div className="v"><StatusLabel status={ch.prompt_status} type="prompt" /></div>
          </div>
          <div className="stat">
            <div className="k">图片</div>
            <div className="v"><StatusLabel status={ch.image_status} type="image" /></div>
          </div>
          <div className="stat">
            <div className="k">视频</div>
            <div className="v"><StatusLabel status={ch.video_status} type="video" /></div>
          </div>
          <div className="stat">
            <div className="k">预估时长</div>
            <div className="v">{formatSec(ch.estimated_duration)}</div>
          </div>
          <div className="stat">
            <div className="k">场景数</div>
            <div className="v">{script?.scenes?.length ?? 0}</div>
          </div>
        </div>
        {ch.error && <div style={{ marginTop: 10, color: "var(--danger)", fontSize: "0.85rem" }}>错误: {ch.error}</div>}
      </div>

      {/* 操作按钮 — 流水线步骤 */}
      <div className="card">
        <div style={{ fontSize: "0.8rem", color: "var(--muted)", marginBottom: 8 }}>
          流程: 脚本生成 → 提示词评审 → 图片生成 → 图片评审 → 视频生成
        </div>
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>

          {/* ① 脚本 */}
          {ch.script_status === "pending" && (
            <button className="primary" disabled={!!busy} onClick={() => doAction("gen-script", `/novel/chapters/${cid}/generate-script`)}>
              {busy === "gen-script" ? "提交中..." : "① 生成脚本"}
            </button>
          )}
          {ch.script_status === "draft" && (
            <>
              <button className="primary" disabled={!!busy} onClick={() => doAction("approve-script", `/novel/chapters/${cid}/script-review`, { action: "approve", notes: reviewNotes || undefined })}>
                通过脚本
              </button>
              <button style={{ borderColor: "var(--danger)", color: "var(--danger)" }} disabled={!!busy}
                onClick={() => {
                  if (!reviewNotes.trim()) { setErr("请填写驳回意见"); return; }
                  doAction("reject-script", `/novel/chapters/${cid}/script-review`, { action: "reject", notes: reviewNotes });
                }}>
                驳回脚本
              </button>
            </>
          )}
          {ch.script_status === "rejected" && (
            <button className="primary" disabled={!!busy} onClick={() => doAction("regen-script", `/novel/chapters/${cid}/generate-script`)}>
              重新生成脚本
            </button>
          )}

          {/* ② 提示词评审 */}
          {ch.script_status === "approved" && ch.prompt_status === "pending" && (
            <button className="primary" disabled={!!busy} onClick={() => doAction("review-prompts", `/novel/chapters/${cid}/review-prompts`)}>
              {busy === "review-prompts" ? "提交中..." : "② AI评审提示词"}
            </button>
          )}
          {ch.prompt_status === "reviewing" && (
            <>
              <button className="primary" disabled={!!busy} onClick={() => doAction("approve-prompts", `/novel/chapters/${cid}/approve-prompts`, { action: "approve", notes: reviewNotes || undefined })}>
                通过提示词
              </button>
              <button style={{ borderColor: "var(--danger)", color: "var(--danger)" }} disabled={!!busy}
                onClick={() => {
                  if (!reviewNotes.trim()) { setErr("请填写驳回意见"); return; }
                  doAction("reject-prompts", `/novel/chapters/${cid}/approve-prompts`, { action: "reject", notes: reviewNotes });
                }}>
                驳回提示词
              </button>
            </>
          )}
          {ch.prompt_status === "rejected" && (
            <button className="primary" disabled={!!busy} onClick={() => doAction("review-prompts", `/novel/chapters/${cid}/review-prompts`)}>
              重新评审提示词
            </button>
          )}

          {/* ③ 生成图片 */}
          {ch.prompt_status === "approved" && ch.image_status === "pending" && (
            <button className="primary" disabled={!!busy} onClick={() => doAction("gen-images", `/novel/chapters/${cid}/generate-images`)}>
              {busy === "gen-images" ? "提交中..." : "③ 生成图片"}
            </button>
          )}

          {/* ④ 图片评审 */}
          {ch.image_status === "reviewing" && (
            <>
              <button className="primary" disabled={!!busy} onClick={() => doAction("approve-images", `/novel/chapters/${cid}/approve-images`, { action: "approve", notes: reviewNotes || undefined })}>
                通过图片
              </button>
              <button style={{ borderColor: "var(--danger)", color: "var(--danger)" }} disabled={!!busy}
                onClick={() => {
                  if (!reviewNotes.trim()) { setErr("请填写驳回意见"); return; }
                  doAction("reject-images", `/novel/chapters/${cid}/approve-images`, { action: "reject", notes: reviewNotes });
                }}>
                驳回图片
              </button>
            </>
          )}
          {ch.image_status === "rejected" && (
            <button className="primary" disabled={!!busy} onClick={() => doAction("gen-images", `/novel/chapters/${cid}/generate-images`)}>
              重新生成图片
            </button>
          )}

          {/* ⑤ 生成视频（需要图片评审通过） */}
          {ch.image_status === "approved" && ch.video_status === "pending" && (
            <button className="primary" disabled={!!busy} onClick={() => doAction("gen-video", `/novel/chapters/${cid}/generate-video`, {})}>
              {busy === "gen-video" ? "提交中..." : "⑤ 生成视频"}
            </button>
          )}
          {ch.video_status === "reviewing" && (
            <>
              <button className="primary" disabled={!!busy} onClick={() => doAction("approve-video", `/novel/chapters/${cid}/video-review`, { action: "approve", notes: reviewNotes || undefined })}>
                通过视频
              </button>
              <button style={{ borderColor: "var(--danger)", color: "var(--danger)" }} disabled={!!busy}
                onClick={() => {
                  if (!reviewNotes.trim()) { setErr("请填写驳回意见"); return; }
                  doAction("reject-video", `/novel/chapters/${cid}/video-review`, { action: "reject", notes: reviewNotes });
                }}>
                驳回视频
              </button>
            </>
          )}
          {ch.video_status === "rejected" && (
            <button className="primary" disabled={!!busy} onClick={() => doAction("regen-video", `/novel/chapters/${cid}/generate-video`, {})}>
              重新生成视频
            </button>
          )}
        </div>

        {/* 进度中的提示 */}
        {ch.script_status === "generating" && <div className="muted" style={{ marginTop: 8 }}>⏳ AI 正在生成脚本...</div>}
        {ch.prompt_status === "reviewing" && <div className="muted" style={{ marginTop: 8 }}>⏳ AI 正在评审提示词（第{ch.prompt_review_round}轮）...</div>}
        {ch.image_status === "generating" && <div className="muted" style={{ marginTop: 8 }}>⏳ 正在生成场景图片...</div>}
        {ch.video_status === "generating" && <div className="muted" style={{ marginTop: 8 }}>⏳ 正在生成视频素材...</div>}
        {ch.video_status === "compositing" && <div className="muted" style={{ marginTop: 8 }}>⏳ 正在合成最终视频...</div>}

        {/* 评审意见 */}
        {ch.prompt_review_notes && <div style={{ marginTop: 8, fontSize: "0.85rem", color: "var(--muted)" }}>提示词评审: {ch.prompt_review_notes}</div>}
        {ch.image_review_notes && <div style={{ marginTop: 4, fontSize: "0.85rem", color: "var(--muted)" }}>图片评审: {ch.image_review_notes}</div>}

        {(ch.script_status === "draft" || ch.prompt_status === "reviewing" || ch.image_status === "reviewing" || ch.video_status === "reviewing") && (
          <textarea
            value={reviewNotes}
            onChange={(e) => setReviewNotes(e.target.value)}
            placeholder="审核意见（驳回时必填）"
            rows={2}
            style={{ marginTop: 10 }}
          />
        )}
      </div>

      {/* Tab 切换 */}
      <div className="row" style={{ gap: 0, marginBottom: 0 }}>
        {(["script", "images", "video", "reviews"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              borderRadius: "8px 8px 0 0",
              borderBottom: tab === t ? "2px solid var(--accent)" : "1px solid var(--border)",
              color: tab === t ? "var(--accent)" : "var(--muted)",
              fontWeight: tab === t ? 600 : 400,
            }}
          >
            {{ script: "脚本分镜", images: "场景图片", video: "视频预览", reviews: "审核记录" }[t]}
          </button>
        ))}
      </div>

      {/* 脚本分镜 */}
      {tab === "script" && (
        <div className="card" style={{ borderRadius: "0 12px 12px 12px" }}>
          {script ? (
            <>
              <div className="muted" style={{ marginBottom: 10 }}>
                概要: {script.summary} · 预估 {formatSec(script.estimated_duration_sec)}
              </div>
              {script.scenes.map((s, i) => (
                <div key={i} style={{
                  border: "1px solid var(--border)", borderRadius: 8, padding: 10, marginBottom: 8,
                  borderLeft: `3px solid ${MOOD_COLORS[s.mood] || "#555"}`,
                }}>
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <div>
                      <span className="pill" style={{ fontSize: "0.75rem" }}>#{s.scene_id}</span>
                      <span className="pill" style={{ marginLeft: 4, fontSize: "0.75rem" }}>{s.type}</span>
                      <strong style={{ marginLeft: 8 }}>{s.speaker}</strong>
                    </div>
                    <span className="muted" style={{ fontSize: "0.8rem" }}>
                      {s.mood} · ~{s.duration_hint}s
                    </span>
                  </div>
                  <div style={{ marginTop: 6, lineHeight: 1.5 }}>{s.text}</div>
                  <div className="muted" style={{ marginTop: 4, fontSize: "0.82rem" }}>
                    画面: {s.visual_prompt}
                  </div>
                </div>
              ))}
            </>
          ) : (
            <div className="muted" style={{ textAlign: "center", padding: 20 }}>
              {ch.script_status === "generating" ? "AI 正在生成脚本..." : "暂无脚本"}
            </div>
          )}
        </div>
      )}

      {/* 场景图片 */}
      {tab === "images" && (
        <div className="card" style={{ borderRadius: "0 12px 12px 12px" }}>
          {ch.visual_assets && Object.keys(ch.visual_assets).length > 0 ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12 }}>
              {Object.entries(ch.visual_assets)
                .sort(([a], [b]) => {
                  const na = parseInt(a.replace(/\D/g, "")) || 0;
                  const nb = parseInt(b.replace(/\D/g, "")) || 0;
                  return na - nb;
                })
                .map(([key, val]) => {
                  const url = typeof val === "string" ? val : (val as any)?.url || (val as any)?.path || "";
                  const filename = url.split("/").pop() || key;
                  const sceneNum = key.replace(/\D/g, "") || key;
                  const promptKey = `scene_${sceneNum.padStart(3, "0")}`;
                  const promptText = ch.image_prompts?.[promptKey] || ch.image_prompts?.[key] || "";
                  return (
                    <div key={key} style={{ border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden" }}>
                      <img
                        src={`/media/novel_assets/${url.includes("project_") ? url.split("novel_assets/").pop() : url}`}
                        alt={`Scene ${sceneNum}`}
                        style={{ width: "100%", height: 160, objectFit: "cover", display: "block" }}
                        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                      />
                      <div style={{ padding: 8 }}>
                        <div style={{ fontWeight: 600, fontSize: "0.85rem" }}>场景 #{sceneNum}</div>
                        {promptText && (
                          <div className="muted" style={{ fontSize: "0.78rem", marginTop: 4, lineHeight: 1.3 }}>
                            {typeof promptText === "string" ? promptText.slice(0, 80) : JSON.stringify(promptText).slice(0, 80)}
                            {typeof promptText === "string" && promptText.length > 80 ? "..." : ""}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
            </div>
          ) : (
            <div className="muted" style={{ textAlign: "center", padding: 20 }}>
              {ch.image_status === "generating" ? "正在生成场景图片..." :
               ch.prompt_status !== "approved" ? "需要先通过提示词评审" :
               "暂无图片，请点击「生成图片」"}
            </div>
          )}
          {ch.image_review_notes && (
            <div style={{ marginTop: 12, padding: 10, background: "var(--bg)", borderRadius: 8, fontSize: "0.85rem" }}>
              <strong>图片评审意见:</strong> {ch.image_review_notes}
            </div>
          )}
        </div>
      )}

      {/* 视频预览 */}
      {tab === "video" && (
        <div className="card" style={{ borderRadius: "0 12px 12px 12px" }}>
          {ch.output_path ? (
            <div>
              <video
                src={`/media/${ch.output_path.split("/").pop()}`}
                controls
                playsInline
                style={{ width: "100%", maxHeight: 500 }}
              />
              <div className="muted" style={{ marginTop: 8 }}>
                时长: {formatSec(ch.actual_duration)} · 文件: {ch.output_path.split("/").pop()}
              </div>
            </div>
          ) : (
            <div className="muted" style={{ textAlign: "center", padding: 20 }}>
              {["generating", "compositing"].includes(ch.video_status) ? "视频正在生成中..." : "暂无视频"}
            </div>
          )}

          {/* 增量重做 */}
          {script && script.scenes.length > 0 && ["reviewing", "rejected"].includes(ch.video_status) && (
            <div style={{ marginTop: 16, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
              <h4 style={{ margin: "0 0 8px" }}>增量重做场景</h4>
              <div className="row" style={{ gap: 8 }}>
                <select value={regenSceneId} onChange={(e) => setRegenSceneId(e.target.value ? Number(e.target.value) : "")}>
                  <option value="">选择场景</option>
                  {script.scenes.map((s) => (
                    <option key={s.scene_id} value={s.scene_id}>#{s.scene_id} {s.speaker}: {s.text.slice(0, 20)}...</option>
                  ))}
                </select>
                <select value={regenTarget} onChange={(e) => setRegenTarget(e.target.value as any)}>
                  <option value="both">音频+画面</option>
                  <option value="audio">仅音频</option>
                  <option value="visual">仅画面</option>
                </select>
                <button className="primary" disabled={regenSceneId === "" || !!busy}
                  onClick={() => doAction("regen-scene", `/novel/chapters/${cid}/regenerate-scenes`, {
                    scene_ids: [regenSceneId], target: regenTarget,
                  })}>
                  {busy === "regen-scene" ? "提交中..." : "重做"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 审核记录 */}
      {tab === "reviews" && (
        <div className="card" style={{ borderRadius: "0 12px 12px 12px" }}>
          {reviews.length > 0 ? (
            reviews.map((r) => (
              <div key={r.id} style={{ borderBottom: "1px solid var(--border)", paddingBottom: 10, marginBottom: 10 }}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <div>
                    <span className="pill">{{ script: "脚本", prompt: "提示词", image: "图片", video: "视频" }[r.review_stage] || r.review_stage}</span>
                    <span className={`pill ${r.status === "approved" ? "ok" : r.status === "rejected" ? "err" : ""}`} style={{ marginLeft: 4 }}>
                      {r.status === "approved" ? "通过" : r.status === "rejected" ? "驳回" : "待审"}
                    </span>
                    <span className="muted" style={{ marginLeft: 8 }}>第{r.review_round}轮</span>
                  </div>
                  <span className="muted" style={{ fontSize: "0.8rem" }}>{new Date(r.created_at).toLocaleString()}</span>
                </div>
                {r.notes && <div style={{ marginTop: 6 }}>{r.notes}</div>}
                {r.items && r.items.length > 0 && (
                  <ul style={{ marginTop: 6, paddingLeft: 20, fontSize: "0.85rem", color: "var(--muted)" }}>
                    {r.items.map((it, idx) => (
                      <li key={idx}>{it.scene_id != null && `场景#${it.scene_id} `}{it.field && `[${it.field}] `}{it.comment}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))
          ) : (
            <div className="muted" style={{ textAlign: "center", padding: 20 }}>暂无审核记录</div>
          )}
        </div>
      )}
    </div>
  );
}

function StatusLabel({ status, type }: { status: string; type: "script" | "prompt" | "image" | "video" }) {
  const MAP: Record<string, Record<string, { t: string; c: string }>> = {
    script: {
      pending: { t: "待生成", c: "var(--muted)" }, generating: { t: "生成中", c: "#ffd166" },
      draft: { t: "待审核", c: "#ffd166" }, approved: { t: "已通过", c: "var(--ok)" },
      rejected: { t: "已驳回", c: "var(--danger)" },
    },
    prompt: {
      pending: { t: "待评审", c: "var(--muted)" }, reviewing: { t: "评审中", c: "#ffd166" },
      approved: { t: "已通过", c: "var(--ok)" }, rejected: { t: "已驳回", c: "var(--danger)" },
    },
    image: {
      pending: { t: "待生成", c: "var(--muted)" }, generating: { t: "生成中", c: "#ffd166" },
      reviewing: { t: "待审核", c: "#ffd166" }, approved: { t: "已通过", c: "var(--ok)" },
      rejected: { t: "已驳回", c: "var(--danger)" },
    },
    video: {
      pending: { t: "待生成", c: "var(--muted)" }, generating: { t: "素材中", c: "#ffd166" },
      compositing: { t: "合成中", c: "#ffd166" }, reviewing: { t: "待审核", c: "#ffd166" },
      approved: { t: "已通过", c: "var(--ok)" }, rejected: { t: "已驳回", c: "var(--danger)" },
      published: { t: "已发布", c: "var(--ok)" },
    },
  };
  const info = MAP[type]?.[status] || { t: status, c: "var(--muted)" };
  return <span style={{ color: info.c, fontWeight: 600, fontSize: "1rem" }}>{info.t}</span>;
}
