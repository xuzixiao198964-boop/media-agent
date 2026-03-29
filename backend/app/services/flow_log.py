from sqlalchemy.orm import Session

from app.models import FlowLog


def log_sync(db: Session, ref_type: str, ref_id: int | None, step: str, message: str, level: str = "info"):
    db.add(
        FlowLog(
            ref_type=ref_type,
            ref_id=ref_id,
            step=step,
            message=message,
            level=level,
        )
    )
    db.commit()
