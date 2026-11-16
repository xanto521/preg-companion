from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Pregnancy


def current_pregnancy(db: Session) -> Pregnancy | None:
    return db.scalar(select(Pregnancy).order_by(Pregnancy.id.desc()).limit(1))
