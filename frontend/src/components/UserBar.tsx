import { useEffect, useState } from "react";
import { api } from "../api";

export type Me = {
  id: number;
  username: string;
  display_name?: string | null;
  avatar_url?: string | null;
  bio?: string | null;
};

type Props = { onLogout: () => void };

export default function UserBar({ onLogout }: Props) {
  const [me, setMe] = useState<Me | null>(null);
  const [imgOk, setImgOk] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api<Me>("/auth/me")
      .then((u) => {
        if (!cancelled) setMe(u);
      })
      .catch(() => {
        if (!cancelled) setMe(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setImgOk(true);
  }, [me?.avatar_url]);

  const displayName = me?.display_name || me?.username || "?";
  const initial = displayName.slice(0, 1).toUpperCase();

  return (
    <div className="header-user" title={me ? me.username : ""}>
      {me ? (
        <>
          <div className="user-avatar-wrap">
            {imgOk && me.avatar_url ? (
              <img
                className="user-avatar"
                src={me.avatar_url}
                alt=""
                referrerPolicy="no-referrer"
                onError={() => setImgOk(false)}
              />
            ) : (
              <span className="user-avatar user-avatar-fallback" aria-hidden>
                {initial}
              </span>
            )}
          </div>
          <div className="user-meta">
            <span className="user-name">{displayName}</span>
          </div>
        </>
      ) : (
        <span className="muted" style={{ fontSize: "0.85rem" }}>
          …
        </span>
      )}
      <button type="button" className="user-logout" onClick={onLogout}>
        退出
      </button>
    </div>
  );
}
