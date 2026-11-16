from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.auth import require_recorder
from app.db.connection import start_write
from app.db.models import ShareToken, utc_now
from app.db.session import Database
from app.security.recorder import new_token, token_digest
from app.security.sharing import CALENDAR_SCOPE, Scope

router = APIRouter(prefix="/share-tokens", tags=["share links"], dependencies=[Depends(require_recorder)])


class SubscriptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    scope: Scope = CALENDAR_SCOPE
    label: str | None = Field(default=None, max_length=80)
    expires_in_days: int | None = Field(default=None, ge=1, le=366)


class Subscription(BaseModel):
    id: int
    label: str | None
    created_at: datetime
    expires_at: datetime | None
    state: Literal["active", "expired", "revoked"]


class SubscriptionCreated(Subscription):
    path: str
    public_origin: str | None


def describe(token: ShareToken) -> Subscription:
    if token.revoked_at:
        state = "revoked"
    elif token.expires_at and token.expires_at <= utc_now():
        state = "expired"
    else:
        state = "active"
    return Subscription(
        id=token.id, label=token.label, state=state,
        created_at=token.created_at.replace(tzinfo=UTC),
        expires_at=token.expires_at.replace(tzinfo=UTC) if token.expires_at else None,
    )


@router.get("")
def list_subscriptions(db: Database, scope: Scope = CALENDAR_SCOPE) -> list[Subscription]:
    tokens = db.scalars(select(ShareToken).where(ShareToken.scope == scope).order_by(ShareToken.id.desc()))
    return [describe(token) for token in tokens]


@router.post("", status_code=201)
def issue_subscription(payload: SubscriptionInput, request: Request, db: Database) -> SubscriptionCreated:
    settings = request.app.state.settings
    raw = new_token()
    now = utc_now()
    token = ShareToken(
        scope=payload.scope, label=payload.label or None, token_hash=token_digest(raw), created_at=now,
        expires_at=now + timedelta(days=payload.expires_in_days or settings.share_token_ttl_days),
    )
    db.add(token)
    db.commit()
    return SubscriptionCreated(
        **describe(token).model_dump(),
        path=f"/cal/{raw}.ics" if payload.scope == CALENDAR_SCOPE else f"/view/{raw}",
        public_origin=None if settings.public_domain == "localhost" else f"https://{settings.public_domain}",
    )


@router.delete("/{token_id}", status_code=204)
def revoke_subscription(token_id: int, db: Database, scope: Scope = CALENDAR_SCOPE) -> None:
    start_write(db)
    token = db.get(ShareToken, token_id)
    if token is None or token.scope != scope:
        raise HTTPException(404, "这条链接不存在。")
    if token.revoked_at is None:
        token.revoked_at = utc_now()
        db.commit()
