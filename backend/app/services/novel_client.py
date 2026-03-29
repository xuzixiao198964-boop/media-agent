"""ai-novel-agent HTTP 客户端，拉取小说内容。"""
import httpx

from app.config import get_settings


def _base() -> str:
    return get_settings().novel_agent_base_url.rstrip("/")


def list_novels(page: int = 1, per_page: int = 20) -> dict:
    url = f"{_base()}/novel-api/novels"
    with httpx.Client(timeout=30) as c:
        r = c.get(url, params={"page": page, "per_page": per_page})
        r.raise_for_status()
        return r.json()


def get_novel_detail(slug: str) -> dict:
    url = f"{_base()}/novel-api/novels/by-slug/{slug}"
    with httpx.Client(timeout=30) as c:
        r = c.get(url)
        r.raise_for_status()
        return r.json()


def get_chapter_text(slug: str, chapter_no: int) -> dict:
    url = f"{_base()}/novel-api/novels/by-slug/{slug}/chapter/{chapter_no}"
    with httpx.Client(timeout=30) as c:
        r = c.get(url)
        r.raise_for_status()
        return r.json()


def search_novels(q: str) -> dict:
    url = f"{_base()}/novel-api/search"
    with httpx.Client(timeout=30) as c:
        r = c.get(url, params={"q": q})
        r.raise_for_status()
        return r.json()
