from datetime import datetime

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import PublishJob


def run_publish(db: Session, job: PublishJob) -> None:
    settings = get_settings()
    mode = (settings.publish_mode or "mock").lower()
    job.status = "publishing"
    db.commit()

    if mode == "mock":
        job.status = "success"
        job.meta = {
            "mock": True,
            "platform": job.platform,
            "posted_at": datetime.utcnow().isoformat() + "Z",
            "external_id": f"mock-{job.id}",
        }
        job.error = None
        db.commit()
        return

    job.status = "failed"
    job.error = f"发布模式 {mode} 尚未实现，请使用 mock 或扩展 publisher.run_publish"
    job.meta = {"hint": "接入抖音/TikTok 等开放平台后在此实现"}
    db.commit()
