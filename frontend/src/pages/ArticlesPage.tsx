import { useEffect, useState } from "react";
import { api } from "../api";

type Category = { id: number; name: string; slug: string };
type Article = {
  id: number;
  category_id: number;
  title: string;
  summary: string | null;
  source_url: string;
  status: string;
};

export default function ArticlesPage() {
  const [cats, setCats] = useState<Category[]>([]);
  const [cat, setCat] = useState<number | "">("");
  const [rows, setRows] = useState<Article[]>([]);
  const [msg, setMsg] = useState<string | null>(null);

  async function refreshCategories() {
    const c = await api<Category[]>("/categories");
    setCats(c);
  }

  async function refreshArticles() {
    const q = cat === "" ? "" : `?category_id=${cat}`;
    const a = await api<Article[]>(`/articles${q}`);
    setRows(a);
  }

  useEffect(() => {
    refreshCategories().catch((e) => setMsg(String(e)));
  }, []);

  useEffect(() => {
    refreshArticles().catch((e) => setMsg(String(e)));
  }, [cat]);

  async function fetchOne(id: number) {
    setMsg(null);
    try {
      await api(`/categories/${id}/fetch`, { method: "POST" });
      setMsg("已排队抓取，请稍后刷新列表");
      setTimeout(() => refreshArticles(), 5000);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "失败");
    }
  }

  return (
    <div>
      <h2>资讯列表</h2>
      {msg && <p className="pill warn">{msg}</p>}
      <div className="row" style={{ marginBottom: 12 }}>
        <select value={cat} onChange={(e) => setCat(e.target.value ? Number(e.target.value) : "")}>
          <option value="">全部栏目</option>
          {cats.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.slug})
            </option>
          ))}
        </select>
        <button type="button" onClick={() => refreshArticles()}>
          刷新
        </button>
      </div>
      <div className="row" style={{ marginBottom: 12 }}>
        {cats.map((c) => (
          <button key={c.id} type="button" className="primary" onClick={() => fetchOne(c.id)}>
            抓取：{c.name}
          </button>
        ))}
      </div>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>标题</th>
              <th>栏目</th>
              <th>链接</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.id}>
                <td>{a.id}</td>
                <td>
                  <div>{a.title}</div>
                  {a.summary && <div className="muted">{a.summary.slice(0, 120)}…</div>}
                </td>
                <td>{a.category_id}</td>
                <td>
                  <a href={a.source_url} target="_blank" rel="noreferrer">
                    原文
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
