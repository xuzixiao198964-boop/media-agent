import httpx
from sqlalchemy.orm import Session

from app.services.keyvault import get_provider_key_sync


def build_narration(db: Session, title: str, summary: str, body: str) -> str:
    key = get_provider_key_sync(db, "deepseek")
    base = (summary or "")[:1200] or (body or "")[:1200]
    if not key:
        return f"今日资讯：{title}。{base[:400]}"

    prompt = (
        "你是短视频口播撰稿人。根据新闻写一段中文口播，80~160字，"
        "语气自然、有节奏感，不要标题前缀，不要 Markdown。\n\n"
        f"标题：{title}\n摘要：{summary or '无'}\n正文节选：{base}\n"
    )
    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 400,
                },
            )
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"].strip()
            return text[:800]
    except Exception:
        return f"今日资讯：{title}。{base[:400]}"


def build_script_from_user_prompt(db: Session, user_requirement: str) -> str:
    """
    根据用户在生成页输入的「需求描述」，用 DeepSeek 生成口播文案。
    """
    key = get_provider_key_sync(db, "deepseek")
    req = (user_requirement or "").strip()
    if not req:
        return "请补充你的视频需求说明。"
    if not key:
        return req[:800]

    prompt = (
        "你是短视频口播撰稿人。根据用户的制作需求写一段中文口播稿，"
        "80~200字，语气自然、有节奏感，适合竖屏短视频；不要标题前缀，不要 Markdown。\n\n"
        f"用户需求：\n{req}\n"
    )
    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 500,
                },
            )
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"].strip()
            return text[:800]
    except Exception:
        return req[:800]
