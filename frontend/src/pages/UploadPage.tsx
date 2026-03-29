import { useEffect, useState } from "react";
import { api } from "../api";

type Category = { id: number; name: string };
type UV = {
  id: number;
  original_name: string;
  stored_path: string;
  duration_sec: number | null;
  category_id: number | null;
};

export default function UploadPage() {
  const [cats, setCats] = useState<Category[]>([]);
  const [cat, setCat] = useState<number | "">("");
  const [list, setList] = useState<UV[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api<Category[]>("/categories")
      .then(setCats)
      .catch((e) => setErr(String(e)));
    api<UV[]>("/videos")
      .then(setList)
      .catch((e) => setErr(String(e)));
  }, []);

  async function onFile(f: File | null) {
    if (!f) return;
    setErr(null);
    const fd = new FormData();
    fd.append("file", f);
    if (cat !== "") fd.append("category_id", String(cat));
    try {
      await fetch("/api/v1/videos/upload", {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
        body: fd,
      }).then(async (r) => {
        if (!r.ok) throw new Error(await r.text());
      });
      const rows = await api<UV[]>("/videos");
      setList(rows);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "上传失败");
    }
  }

  async function onDelete(videoId: number) {
    const ok = window.confirm(`确定删除该上传视频（ID: ${videoId}）？该操作会删除关联的生成产物。`);
    if (!ok) return;
    setErr(null);
    try {
      await api(`/videos/${videoId}`, { method: "DELETE" });
      const rows = await api<UV[]>("/videos");
      setList(rows);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "删除失败");
    }
  }

  return (
    <div>
      <h2>上传真人视频</h2>
      <p className="muted">支持 mp4 / mov / webm 等；服务器单文件上限 500MB。建议竖屏 1080×1920 或 720×1280，时长 15–60 秒便于成片节奏。</p>
      {err && <p className="pill err">{err}</p>}
      <div className="card">
        <div className="row">
          <select value={cat} onChange={(e) => setCat(e.target.value ? Number(e.target.value) : "")}>
            <option value="">不指定栏目（可选）</option>
            {cats.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <input type="file" accept="video/*" onChange={(e) => onFile(e.target.files?.[0] ?? null)} />
        </div>
      </div>
      <h3>已上传</h3>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>文件</th>
              <th>时长</th>
              <th>预览</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {list.map((v) => (
              <tr key={v.id}>
                <td>{v.id}</td>
                <td>{v.original_name}</td>
                <td>{v.duration_sec != null ? `${v.duration_sec.toFixed(1)}s` : "-"}</td>
                <td>
                  <video src={`/uploads/${v.stored_path}`} controls muted playsInline style={{ maxWidth: 220 }} />
                </td>
                <td>
                  <button className="btn" type="button" onClick={() => onDelete(v.id)}>
                    删除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
