from asyncio import Event
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import ShareToken, utc_now
from app.security.recorder import token_digest

Scope = Literal["calendar", "view"]
CALENDAR_SCOPE: Scope = "calendar"
VIEW_SCOPE: Scope = "view"


def active_share(db: Session, token: str, scope: Scope) -> ShareToken | None:
    if len(token) != 43:
        return None
    return db.scalar(select(ShareToken).where(
        ShareToken.token_hash == token_digest(token),
        ShareToken.scope == scope,
        ShareToken.revoked_at.is_(None),
        or_(ShareToken.expires_at.is_(None), ShareToken.expires_at > utc_now()),
    ))


def valid_share(db: Session, token: str, scope: Scope) -> bool:
    return active_share(db, token, scope) is not None


class ShareRevocations:
    """Notify open viewer connections on this application's event loop."""

    def __init__(self) -> None:
        self._listeners: dict[int, set[Event]] = {}

    @contextmanager
    def listen(self, share_id: int) -> Iterator[Event]:
        signal = Event()
        listeners = self._listeners.setdefault(share_id, set())
        listeners.add(signal)
        try:
            yield signal
        finally:
            listeners.remove(signal)
            if not listeners:
                del self._listeners[share_id]

    def notify(self, share_id: int) -> None:
        for signal in self._listeners.get(share_id, ()):
            signal.set()
