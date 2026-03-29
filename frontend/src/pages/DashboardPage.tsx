import { useEffect, useState } from "react";
import { api } from "../api";

type Summary = {
  articles_active: number;
  my_videos: number;
  generation: { pending: number; processing: number; done: number; failed: number };
  publish: { success: number; failed: number };
};

export default function DashboardPage() {
  const [s, setS] = useState<Summary | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const data = await api<Summary>("/status/summary");
        if (alive) setS(data);
      } catch (e: unknown) {
        if (alive) setErr(e instanceof Error ? e.message : "加载失败");
      }
    }
    load();
    const t = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  return (
    <div>
      <h2>总览</h2>
      <p className="muted">状态约每 15 秒刷新；全流程异步由 Celery Worker 执行。</p>
      {err && <p className="pill err">{err}</p>}
      {s && (
        <div className="grid">
          <div className="stat">
            <div className="k">可用资讯</div>
            <div className="v">{s.articles_active}</div>
          </div>
          <div className="stat">
            <div className="k">我的真人视频</div>
            <div className="v">{s.my_videos}</div>
          </div>
          <div className="stat">
            <div className="k">生成中</div>
            <div className="v">{s.generation.processing + s.generation.pending}</div>
          </div>
          <div className="stat">
            <div className="k">已生成</div>
            <div className="v">{s.generation.done}</div>
          </div>
          <div className="stat">
            <div className="k">生成失败</div>
            <div className="v">{s.generation.failed}</div>
          </div>
          <div className="stat">
            <div className="k">发布成功 / 失败</div>
            <div className="v">
              {s.publish.success} / {s.publish.failed}
            </div>
          </div>
        </div>
      )}
      <div className="card" style={{ marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>推荐操作顺序</h3>
        <ol className="muted">
          <li>「资讯」页触发栏目抓取或等待定时任务。</li>
          <li>「上传」页上传真人短视频（建议竖屏，便于 9:16 输出）。</li>
          <li>「生成」页选择文章与视频，创建任务；完成后在页面预览成片。</li>
          <li>「发布」页使用 mock 平台验证发布状态回写（真实平台需开放平台资质）。</li>
        </ol>
      </div>
    </div>
  );
}
