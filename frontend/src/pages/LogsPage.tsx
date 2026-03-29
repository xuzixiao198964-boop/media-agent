import { useEffect, useState } from "react";
import { api } from "../api";

type Row = {
  id: number;
  ref_type: string;
  ref_id: number | null;
  step: string;
  message: string;
  level: string;
  created_at: string;
};

export default function LogsPage() {
  const [rows, setRows] = useState<Row[]>([]);

  useEffect(() => {
    const load = () => api<Row[]>("/logs/flow?limit=200").then(setRows);
    load();
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, []);

  return (
    <div>
      <h2>流程日志</h2>
      <p className="muted">抓取、生成、发布等环节的关键日志（后端 FlowLog）。</p>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>对象</th>
              <th>步骤</th>
              <th>消息</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td className="muted">{String(r.created_at)}</td>
                <td>
                  {r.ref_type}
                  {r.ref_id != null ? `#${r.ref_id}` : ""}
                </td>
                <td>{r.step}</td>
                <td>{r.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
