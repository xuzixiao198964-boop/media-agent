import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../api";

type Project = {
  id: number; novel_slug: string; novel_title: string; novel_author: string | null;
  novel_intro: string | null; visual_style: string | null; narrator_voice_id: string | null;
  default_bgm_id: number | null; video_orientation: string; status: string;
  chapter_count: number; character_count: number;
};
type Chapter = {
  id: number; chapter_no: number; title: string;
  script_status: string; prompt_status: string; image_status: string; video_status: string;
  estimated_duration: number | null; actual_duration: number | null; error: string | null;
  output_path: string | null; prompt_review_round: number; image_review_round: number;
};
type Character = {
  id: number; name: string; gender: string; voice_id: string | null;
  personality: string | null; appearance: string | null;
};

const SCRIPT_STATUS_LABEL: Record<string, { text: string; cls: string }> = {
  pending: { text: "待生成", cls: "" },
  generating: { text: "生成中", cls: "warn" },
  draft: { text: "待审核", cls: "warn" },
  approved: { text: "已通过", cls: "ok" },
  rejected: { text: "已驳回", cls: "err" },
};
const PROMPT_STATUS_LABEL: Record<string, { text: string; cls: string }> = {
  pending: { text: "待评审", cls: "" },
  reviewing: { text: "评审中", cls: "warn" },
  approved: { text: "已通过", cls: "ok" },
  rejected: { text: "已驳回", cls: "err" },
};
const IMAGE_STATUS_LABEL: Record<string, { text: string; cls: string }> = {
  pending: { text: "待生成", cls: "" },
  generating: { text: "生成中", cls: "warn" },
  reviewing: { text: "待审核", cls: "warn" },
  approved: { text: "已通过", cls: "ok" },
  rejected: { text: "已驳回", cls: "err" },
};
const VIDEO_STATUS_LABEL: Record<string, { text: string; cls: string }> = {
  pending: { text: "待生成", cls: "" },
  generating: { text: "素材生成中", cls: "warn" },
  compositing: { text: "合成中", cls: "warn" },
  reviewing: { text: "待审核", cls: "warn" },
  approved: { text: "已通过", cls: "ok" },
  rejected: { text: "已驳回", cls: "err" },
  published: { text: "已发布", cls: "ok" },
};

function StatusPill({ status, map }: { status: string; map: Record<string, { text: string; cls: string }> }) {
  const info = map[status] || { text: status, cls: "" };
  return <span className={`pill ${info.cls}`}>{info.text}</span>;
}

function formatDuration(sec: number | null) {
  if (!sec) return "--";
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function NovelProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const nav = useNavigate();
  const pid = Number(projectId);

  const [project, setProject] = useState<Project | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [importing, setImporting] = useState(false);
  const [importNos, setImportNos] = useState("");
  const [showAddChar, setShowAddChar] = useState(false);
  const [charName, setCharName] = useState("");
  const [charGender, setCharGender] = useState("female");
  const [charVoiceId, setCharVoiceId] = useState("");
  const [charAppearance, setCharAppearance] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [p, chs, chars] = await Promise.all([
      api<Project>(`/novel/projects/${pid}`),
      api<Chapter[]>(`/novel/projects/${pid}/chapters`),
      api<Character[]>(`/novel/projects/${pid}/characters`),
    ]);
    setProject(p);
    setChapters(chs);
    setCharacters(chars);
  }, [pid]);

  useEffect(() => {
    refresh().catch((e) => setErr(e.message));
    const t = setInterval(() => refresh().catch(() => {}), 6000);
    return () => clearInterval(t);
  }, [refresh]);

  async function doImport() {
    setImporting(true);
    setErr(null);
    try {
      const nos = importNos.trim()
        ? importNos.split(",").map((s) => parseInt(s.trim())).filter((n) => !isNaN(n))
        : [];
      const res = await api<{ imported: number; total_available: number }>(
        `/novel/projects/${pid}/import-chapters`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ chapter_nos: nos }) }
      );
      setErr(`导入 ${res.imported} 章（共 ${res.total_available} 章可用）`);
      await refresh();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setImporting(false);
    }
  }

  async function addCharacter() {
    if (!charName.trim()) return;
    try {
      await api<any>(`/novel/projects/${pid}/characters`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: charName, gender: charGender, voice_id: charVoiceId || null, appearance: charAppearance || null }),
      });
      setShowAddChar(false);
      setCharName("");
      await refresh();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function deleteChar(id: number) {
    if (!confirm("确认删除该角色？")) return;
    await api<any>(`/novel/characters/${id}`, { method: "DELETE" });
    await refresh();
  }

  async function batchGenerateScripts() {
    setErr(null);
    const pending = chapters.filter((c) => c.script_status === "pending");
    if (!pending.length) { setErr("没有待生成脚本的章节"); return; }
    for (const ch of pending) {
      try {
        await api<any>(`/novel/chapters/${ch.id}/generate-script`, { method: "POST" });
      } catch { /* continue */ }
    }
    setErr(`已提交 ${pending.length} 个脚本生成任务`);
    await refresh();
  }

  if (!project) return <div className="card muted">加载中...</div>;

  const scriptDone = chapters.filter((c) => c.script_status === "approved").length;
  const videoDone = chapters.filter((c) => ["approved", "published"].includes(c.video_status)).length;
  const totalEst = chapters.reduce((s, c) => s + (c.estimated_duration || 0), 0);
  const totalAct = chapters.reduce((s, c) => s + (c.actual_duration || 0), 0);

  return (
    <div>
      <button onClick={() => nav("/novel")} style={{ marginBottom: 12 }}>← 返回项目列表</button>

      {err && <div className="card" style={{ borderColor: "var(--accent)", color: "var(--accent)" }}>{err}</div>}

      {/* 项目概要 */}
      <div className="card">
        <h2 style={{ margin: "0 0 8px" }}>{project.novel_title}</h2>
        <div className="muted">{project.novel_author} · {project.visual_style}</div>
        {project.novel_intro && <div className="muted" style={{ marginTop: 4, fontSize: "0.85rem" }}>{project.novel_intro.slice(0, 200)}</div>}
        <div className="grid" style={{ marginTop: 12 }}>
          <div className="stat"><div className="k">章节</div><div className="v">{chapters.length}</div></div>
          <div className="stat"><div className="k">脚本通过</div><div className="v">{scriptDone}/{chapters.length}</div></div>
          <div className="stat"><div className="k">视频完成</div><div className="v">{videoDone}/{chapters.length}</div></div>
          <div className="stat"><div className="k">预估时长</div><div className="v">{formatDuration(totalEst)}</div></div>
          <div className="stat"><div className="k">实际时长</div><div className="v">{formatDuration(totalAct)}</div></div>
          <div className="stat"><div className="k">角色</div><div className="v">{characters.length}</div></div>
        </div>
      </div>

      {/* 导入章节 */}
      <div className="card">
        <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
          <h3 style={{ margin: 0 }}>章节管理</h3>
          <div className="row" style={{ gap: 8 }}>
            <input
              placeholder="章节号（如 1,2,3 留空=全部）"
              value={importNos}
              onChange={(e) => setImportNos(e.target.value)}
              style={{ width: 220 }}
            />
            <button className="primary" onClick={doImport} disabled={importing}>
              {importing ? "导入中..." : "从小说导入"}
            </button>
            <button onClick={batchGenerateScripts}>批量生成脚本</button>
          </div>
        </div>
      </div>

      {/* 章节列表 */}
      {chapters.length > 0 && (
        <div className="card" style={{ padding: 0, overflow: "auto" }}>
          <table>
            <thead>
              <tr>
                <th style={{ width: 50 }}>章</th>
                <th>标题</th>
                <th>脚本</th>
                <th>提示词</th>
                <th>图片</th>
                <th>视频</th>
                <th>预估</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {chapters.map((ch) => (
                <tr key={ch.id} style={{ cursor: "pointer" }} onClick={() => nav(`/novel/${pid}/chapter/${ch.id}`)}>
                  <td>{ch.chapter_no}</td>
                  <td>{ch.title}</td>
                  <td><StatusPill status={ch.script_status} map={SCRIPT_STATUS_LABEL} /></td>
                  <td><StatusPill status={ch.prompt_status || "pending"} map={PROMPT_STATUS_LABEL} /></td>
                  <td><StatusPill status={ch.image_status || "pending"} map={IMAGE_STATUS_LABEL} /></td>
                  <td><StatusPill status={ch.video_status} map={VIDEO_STATUS_LABEL} /></td>
                  <td className="muted">{formatDuration(ch.estimated_duration)}</td>
                  <td>
                    {ch.error && <span className="pill err" title={ch.error}>错误</span>}
                    {ch.output_path && <span className="pill ok">有成片</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 角色管理 */}
      <div className="card" style={{ marginTop: 12 }}>
        <div className="row" style={{ justifyContent: "space-between", marginBottom: 10 }}>
          <h3 style={{ margin: 0 }}>角色声线</h3>
          <button onClick={() => setShowAddChar(true)}>添加角色</button>
        </div>
        {showAddChar && (
          <div style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 10, marginBottom: 10 }}>
            <div className="row" style={{ marginBottom: 8 }}>
              <input placeholder="角色名" value={charName} onChange={(e) => setCharName(e.target.value)} style={{ flex: 1 }} />
              <select value={charGender} onChange={(e) => setCharGender(e.target.value)} style={{ width: 100 }}>
                <option value="male">男</option>
                <option value="female">女</option>
                <option value="neutral">中性</option>
              </select>
            </div>
            <input placeholder="Fish Audio 声线 ID（可选）" value={charVoiceId} onChange={(e) => setCharVoiceId(e.target.value)} style={{ marginBottom: 8 }} />
            <input placeholder="外貌描述（用于AI生图保持一致）" value={charAppearance} onChange={(e) => setCharAppearance(e.target.value)} style={{ marginBottom: 8 }} />
            <div className="row" style={{ gap: 8 }}>
              <button className="primary" onClick={addCharacter}>添加</button>
              <button onClick={() => setShowAddChar(false)}>取消</button>
            </div>
          </div>
        )}
        {characters.length > 0 ? (
          <table>
            <thead>
              <tr><th>角色名</th><th>性别</th><th>声线ID</th><th>外貌</th><th></th></tr>
            </thead>
            <tbody>
              {characters.map((ch) => (
                <tr key={ch.id}>
                  <td><strong>{ch.name}</strong></td>
                  <td className="muted">{ch.gender === "male" ? "男" : ch.gender === "female" ? "女" : "中性"}</td>
                  <td className="muted" style={{ fontSize: "0.82rem" }}>{ch.voice_id ? ch.voice_id.slice(0, 16) + "..." : "默认"}</td>
                  <td className="muted" style={{ fontSize: "0.82rem" }}>{ch.appearance?.slice(0, 30) || "--"}</td>
                  <td><button onClick={(e) => { e.stopPropagation(); deleteChar(ch.id); }} style={{ fontSize: "0.8rem" }}>删除</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="muted">AI 生成脚本时会自动识别角色</div>
        )}
      </div>
    </div>
  );
}
