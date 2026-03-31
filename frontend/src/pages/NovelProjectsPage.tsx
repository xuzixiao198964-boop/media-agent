import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

type SourceNovel = { slug: string; title: string; author?: string; category?: string; total_chapters?: number };
type Project = {
  id: number;
  novel_slug: string;
  novel_title: string;
  novel_author: string | null;
  novel_intro: string | null;
  narrator_voice_id: string | null;
  visual_style: string | null;
  status: string;
  chapter_count: number;
  character_count: number;
  created_at: string;
};

export default function NovelProjectsPage() {
  const nav = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [novels, setNovels] = useState<SourceNovel[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [selectedSlug, setSelectedSlug] = useState("");
  const [visualStyle, setVisualStyle] = useState("电影质感，暖色调");
  const [orientation, setOrientation] = useState("portrait");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function refresh() {
    const p = await api<Project[]>("/novel/projects");
    setProjects(p);
  }

  async function loadNovels() {
    try {
      const data = await api<any>("/novel/source/novels");
      const items = data?.novels || data?.items || (Array.isArray(data) ? data : []);
      setNovels(items);
    } catch (e: any) {
      setErr("无法连接 ai-novel-agent: " + e.message);
    }
  }

  useEffect(() => {
    refresh().catch((e) => setErr(e.message));
  }, []);

  async function create() {
    if (!selectedSlug) { setErr("请选择一部小说"); return; }
    setLoading(true);
    setErr(null);
    try {
      const p = await api<Project>("/novel/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ novel_slug: selectedSlug, visual_style: visualStyle, video_orientation: orientation }),
      });
      await refresh();
      setShowCreate(false);
      nav(`/novel/${p.id}`);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>小说视频项目</h2>
        <button className="primary" onClick={() => { setShowCreate(true); loadNovels(); }}>
          新建项目
        </button>
      </div>

      {err && <div className="card" style={{ borderColor: "var(--danger)", color: "var(--danger)" }}>{err}</div>}

      {showCreate && (
        <div className="card" style={{ borderColor: "var(--accent)" }}>
          <h3 style={{ margin: "0 0 12px" }}>从 ai-novel-agent 选择小说</h3>
          {novels.length === 0 ? (
            <p className="muted">正在加载小说列表...</p>
          ) : (
            <select value={selectedSlug} onChange={(e) => setSelectedSlug(e.target.value)} style={{ marginBottom: 10 }}>
              <option value="">-- 选择小说 --</option>
              {novels.map((n) => (
                <option key={n.slug} value={n.slug}>
                  {n.title} {n.author ? `(${n.author})` : ""} {n.total_chapters ? `[${n.total_chapters}章]` : ""}
                </option>
              ))}
            </select>
          )}
          <div className="row" style={{ marginBottom: 10 }}>
            <div style={{ flex: 1 }}>
              <label className="muted">视觉风格</label>
              <input value={visualStyle} onChange={(e) => setVisualStyle(e.target.value)} placeholder="电影质感，暖色调" />
            </div>
            <div style={{ flex: "0 0 160px" }}>
              <label className="muted">画面方向</label>
              <select value={orientation} onChange={(e) => setOrientation(e.target.value)}>
                <option value="portrait">竖屏 (1080x1920)</option>
                <option value="landscape">横屏 (1920x1080)</option>
              </select>
            </div>
          </div>
          <div className="row" style={{ gap: 8 }}>
            <button className="primary" onClick={create} disabled={loading}>
              {loading ? "创建中..." : "创建项目"}
            </button>
            <button onClick={() => setShowCreate(false)}>取消</button>
          </div>
        </div>
      )}

      <div>
        {projects.map((p) => (
          <div key={p.id} className="card" style={{ cursor: "pointer" }} onClick={() => nav(`/novel/${p.id}`)}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <strong style={{ fontSize: "1.1rem" }}>{p.novel_title}</strong>
                <span className="muted" style={{ marginLeft: 8 }}>{p.novel_author}</span>
              </div>
              <span className={`pill ${p.status === "active" ? "ok" : ""}`}>{p.status}</span>
            </div>
            <div className="muted" style={{ marginTop: 6 }}>
              {p.chapter_count} 章 · {p.character_count} 个角色 · {p.visual_style || "默认风格"}
            </div>
            {p.novel_intro && (
              <div className="muted" style={{ marginTop: 4, fontSize: "0.85rem" }}>
                {p.novel_intro.slice(0, 120)}...
              </div>
            )}
          </div>
        ))}
        {projects.length === 0 && !showCreate && (
          <div className="card muted" style={{ textAlign: "center", padding: 40 }}>
            还没有小说项目，点击「新建项目」开始
          </div>
        )}
      </div>
    </div>
  );
}
