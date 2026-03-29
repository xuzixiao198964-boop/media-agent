import { useEffect, useState } from "react";
import { api } from "../api";

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

export default function OutputsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [detail, setDetail] = useState<Job | null>(null);
  const [editDesc, setEditDesc] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function refresh() {
    const rows = await api<Job[]>("/pipeline/jobs?limit=100");
    setJobs(rows.filter((x) => x.status === "done" && !!x.output_path));
  }

  useEffect(() => {
    refresh().catch((e) => setErr(String(e)));
    const t = setInterval(() => refresh().catch(() => {}), 8000);
    return () => clearInterval(t);
  }, []);

  async function openDetail(jobId: number) {
    setErr(null);
    try {
      const d = await api<Job>(`/pipeline/jobs/${jobId}`);
      setActiveId(jobId);
      setDetail(d);
      setEditDesc(d.output_description || "");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "加载详情失败");
    }
  }

  async function saveDesc(jobId: number) {
    setErr(null);
    try {
      await api<Job>(`/pipeline/jobs/${jobId}/description`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ output_description: editDesc }),
      });
      await refresh();
      const d = await api<Job>(`/pipeline/jobs/${jobId}`);
      setDetail(d);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "保存失败");
    }
  }

  return (
    <div className="page-outputs">
      <h2>成片库</h2>
      <p className="muted">已完成任务会自动出现在此。每条成片可填写说明，便于回顾与发布。</p>
      {err && <p className="pill err">{err}</p>}

      <div className="output-list">
        {jobs.map((j) => {
          const mode = (j.meta as { generation_mode?: string } | null)?.generation_mode || "article";
          return (
            <div key={j.id} className="card">
              <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <div className="muted">
                    成片 #{j.id} · {mode === "text_prompt" ? "文案成片" : "资讯成片"} · 视频 {j.user_video_id}
                  </div>
                  {j.output_description && (
                    <div style={{ marginTop: 6, fontWeight: 500 }}>{j.output_description}</div>
                  )}
                </div>
                <button type="button" onClick={() => openDetail(j.id)}>
                  查看详情
                </button>
              </div>
              <div style={{ marginTop: 10 }}>
                <video src={`/media/job_${j.id}.mp4`} controls playsInline />
              </div>
              {activeId === j.id && detail && (
                <div style={{ marginTop: 12 }}>
                  <div className="muted">口播稿</div>
                  <div className="body-text">{detail.narration_text || "-"}</div>
                  <div style={{ marginTop: 10 }}>
                    <label className="muted">成片说明</label>
                    <textarea rows={2} value={editDesc} onChange={(e) => setEditDesc(e.target.value)} />
                    <button type="button" className="primary" style={{ marginTop: 8 }} onClick={() => saveDesc(j.id)}>
                      保存说明
                    </button>
                  </div>
                  {detail.error && <div style={{ marginTop: 8, color: "var(--danger)" }}>{detail.error}</div>}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {!jobs.length && <div className="card muted">暂无已完成成片</div>}
    </div>
  );
}
