from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import ShareToken, utc_now
from app.security.recorder import token_digest

Scope = Literal["calendar", "view"]
CALENDAR_SCOPE: Scope = "calendar"
VIEW_SCOPE: Scope = "view"


def valid_share(db: Session, token: str, scope: Scope) -> bool:
    if len(token) != 43:
        return False
    return db.scalar(select(ShareToken.id).where(
        ShareToken.token_hash == token_digest(token),
        ShareToken.scope == scope,
        ShareToken.revoked_at.is_(None),
        or_(ShareToken.expires_at.is_(None), ShareToken.expires_at > utc_now()),
    )) is not None
