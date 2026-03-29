import hashlib
import re
from datetime import datetime
from html import unescape
from typing import Iterable

import feedparser
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Article, Category


def _strip_html(s: str) -> str:
    s = unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _hash_link(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def fetch_category_rss(db: Session, category: Category) -> int:
    added = 0
    urls: Iterable[str] = category.rss_urls or []
    for url in urls:
        if not url:
            continue
        parsed = feedparser.parse(url)
        for entry in parsed.entries[:50]:
            link = getattr(entry, "link", "") or ""
            if not link:
                continue
            h = _hash_link(link)
            exists = db.execute(select(Article.id).where(Article.content_hash == h)).scalar_one_or_none()
            if exists:
                continue
            title = _strip_html(getattr(entry, "title", "") or "")[:500]
            summary = ""
            if getattr(entry, "summary", None):
                summary = _strip_html(entry.summary)[:2000]
            elif getattr(entry, "description", None):
                summary = _strip_html(entry.description)[:2000]
            body = summary
            if getattr(entry, "content", None) and entry.content:
                try:
                    body = _strip_html(entry.content[0].get("value", ""))[:8000]
                except Exception:
                    pass
            if len(title) < 4:
                continue
            image_url = None
            if getattr(entry, "media_content", None):
                try:
                    image_url = entry.media_content[0].get("url")
                except Exception:
                    image_url = None
            status = "active"
            if _looks_spam(title, body or summary):
                status = "filtered"
            art = Article(
                category_id=category.id,
                title=title,
                summary=summary or None,
                body=body or None,
                image_url=image_url,
                source_url=link,
                content_hash=h,
                status=status,
                extra={"feed": url, "fetched_at": datetime.utcnow().isoformat() + "Z"},
            )
            db.add(art)
            added += 1
    db.commit()
    return added


def _looks_spam(title: str, text: str) -> bool:
    t = f"{title} {text}".lower()
    banned = ("casino", "viagra", "porn", "博彩", "赌场")
    return any(b in t for b in banned)
