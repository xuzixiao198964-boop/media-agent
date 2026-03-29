import { useEffect } from "react";
import { IDLE_MS, LS_ACTIVITY, touchActivity } from "./session";

/** 记录键鼠滚动操作；定时检查超过 IDLE_MS 则退出登录 */
export default function ActivitySync() {
  useEffect(() => {
    let last = 0;
    const bump = () => {
      const n = Date.now();
      if (n - last < 1000) return;
      last = n;
      touchActivity();
    };
    bump();
    const id = setInterval(() => {
      const ts = parseInt(localStorage.getItem(LS_ACTIVITY) || "0", 10);
      if (ts && Date.now() - ts > IDLE_MS) {
        localStorage.removeItem("token");
        localStorage.removeItem("refresh_token");
        localStorage.removeItem(LS_ACTIVITY);
        window.location.href = "/login";
      }
    }, 30_000);
    window.addEventListener("keydown", bump);
    window.addEventListener("mousedown", bump);
    window.addEventListener("touchstart", bump);
    window.addEventListener("scroll", bump, { passive: true });
    return () => {
      clearInterval(id);
      window.removeEventListener("keydown", bump);
      window.removeEventListener("mousedown", bump);
      window.removeEventListener("touchstart", bump);
      window.removeEventListener("scroll", bump);
    };
  }, []);
  return null;
}
