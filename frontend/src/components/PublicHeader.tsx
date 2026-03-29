import { Link } from "react-router-dom";

type Active = "login" | "register" | "forgot";

type Props = { active?: Active };

export default function PublicHeader({ active }: Props) {
  return (
    <header className="public-header">
      <Link to="/" className="public-header-brand">
        <span className="public-header-title">Media Agent</span>
        <span className="public-header-sub muted">资讯 → 短视频 → 发布</span>
      </Link>
      <div className="public-header-actions">
        <Link to="/login" className={active === "login" ? "active" : ""}>
          登录
        </Link>
        <Link to="/register" className={active === "register" ? "active" : ""}>
          注册
        </Link>
        {active === "forgot" && (
          <span className="muted" style={{ fontSize: "0.85rem" }}>
            找回密码
          </span>
        )}
      </div>
    </header>
  );
}
