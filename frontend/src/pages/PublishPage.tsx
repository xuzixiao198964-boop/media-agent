import { useEffect, useState } from "react";
import { api } from "../api";

type Job = { id: number; status: string; output_path: string | null };
type PJob = {
  id: number;
  generation_job_id: number;
  platform: string;
  status: string;
  error: string | null;
  meta: Record<string, unknown> | null;
};

export default function PublishPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [pj, setPj] = useState<PJob[]>([]);
  const [gid, setGid] = useState<number | "">("");
  const [platform, setPlatform] = useState("mock");
  const [err, setErr] = useState<string | null>(null);

  async function refresh() {
    const [g, p] = await Promise.all([
      api<Job[]>("/pipeline/jobs?limit=50"),
      api<PJob[]>("/publish/jobs?limit=50"),
    ]);
    setJobs(g.filter((x) => x.status === "done" && x.output_path));
    setPj(p);
  }

  useEffect(() => {
    refresh().catch((e) => setErr(String(e)));
    const t = setInterval(() => refresh().catch(() => {}), 10000);
    return () => clearInterval(t);
  }, []);

  async function pub() {
    setErr(null);
    if (gid === "") {
      setErr("请选择已完成的生成任务");
      return;
    }
    try {
      await api<PJob>("/publish/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ generation_job_id: gid, platform }),
      });
      await refresh();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "失败");
    }
  }

  return (
    <div>
      <h2>发布（默认 Mock）</h2>
      <p className="muted">真实抖音 / TikTok / 快手等需开放平台应用与审核；当前以 mock 验证状态机与日志。</p>
      {err && <p className="pill err">{err}</p>}
      <div className="card">
        <div className="row">
          <select value={gid} onChange={(e) => setGid(e.target.value ? Number(e.target.value) : "")}>
            <option value="">选择生成任务</option>
            {jobs.map((j) => (
              <option key={j.id} value={j.id}>
                #{j.id}（已完成）
              </option>
            ))}
          </select>
          <input value={platform} onChange={(e) => setPlatform(e.target.value)} placeholder="平台标识" />
          <button className="primary" type="button" onClick={pub}>
            触发发布
          </button>
        </div>
      </div>
      <h3>发布记录</h3>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>生成任务</th>
              <th>平台</th>
              <th>状态</th>
              <th>详情</th>
            </tr>
          </thead>
          <tbody>
            {pj.map((p) => (
              <tr key={p.id}>
                <td>{p.id}</td>
                <td>{p.generation_job_id}</td>
                <td>{p.platform}</td>
                <td>{p.status}</td>
                <td className="muted">
                  {p.error || (p.meta ? JSON.stringify(p.meta) : "-")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
