from secrets import compare_digest
from typing import Annotated

from argon2.exceptions import VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import delete

from app.db.connection import start_write
from app.db.models import RecorderAccount, RecorderSession, utc_now
from app.db.session import Database
from app.security.recorder import (
    SESSION_COOKIE,
    SESSION_TTL,
    new_token,
    password_hasher,
    token_digest,
)

router = APIRouter(prefix="/auth", tags=["recorder"])


class Credentials(BaseModel):
    password: SecretStr = Field(min_length=1, max_length=128)


class SetupCredentials(BaseModel):
    token: SecretStr = Field(min_length=43, max_length=43)
    password: SecretStr = Field(min_length=12, max_length=128)


class RecorderState(BaseModel):
    authenticated: bool
    configured: bool


def get_recorder_session(request: Request, db: Database) -> RecorderSession | None:
    token = request.cookies.get(SESSION_COOKIE, "")
    if len(token) != 43:
        return None
    session = db.get(RecorderSession, token_digest(token))
    if session and session.expires_at > utc_now():
        return session
    return None


def require_recorder(request: Request, db: Database) -> RecorderSession:
    session = get_recorder_session(request, db)
    if session is None:
        raise HTTPException(401, "请先登录。")
    return session


Authenticated = Annotated[RecorderSession, Depends(require_recorder)]


def check_limit(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    limiter = request.app.state.login_limiter
    if not limiter.allow(client):
        raise HTTPException(429, "尝试次数过多，请稍后再试。", headers={"Retry-After": str(limiter.window)})


def issue_session(request: Request, response: Response, db: Database) -> RecorderState:
    now = utc_now()
    token = new_token()
    previous = request.cookies.get(SESSION_COOKIE, "")
    if len(previous) == 43:
        db.execute(delete(RecorderSession).where(RecorderSession.token_hash == token_digest(previous)))
    db.execute(delete(RecorderSession).where(RecorderSession.expires_at <= now))
    db.add(RecorderSession(token_hash=token_digest(token), expires_at=now + SESSION_TTL))
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/api",
    )
    return RecorderState(authenticated=True, configured=True)


@router.get("/session")
def session_state(request: Request, db: Database) -> RecorderState:
    account = db.get(RecorderAccount, 1)
    return RecorderState(
        authenticated=get_recorder_session(request, db) is not None,
        configured=bool(account and account.password_hash),
    )


@router.post("/login", dependencies=[Depends(check_limit)])
def login(payload: Credentials, request: Request, response: Response, db: Database) -> RecorderState:
    account = db.get(RecorderAccount, 1)
    if account is None or not account.password_hash:
        raise HTTPException(409, "请先完成首次设置。")

    previous_hash = account.password_hash
    try:
        password_hasher.verify(previous_hash, payload.password.get_secret_value())
    except VerificationError as exc:
        raise HTTPException(401, "口令不正确。") from exc

    start_write(db)
    db.refresh(account)
    if account.password_hash != previous_hash:
        raise HTTPException(401, "口令已更新，请重试。")
    return issue_session(request, response, db)


def verify_setup(account: RecorderAccount | None, digest: str) -> RecorderAccount:
    if (
        account is None
        or account.password_hash
        or not account.setup_hash
        or not account.setup_expires_at
        or account.setup_expires_at <= utc_now()
        or not compare_digest(account.setup_hash, digest)
    ):
        raise HTTPException(400, "设置链接无效或已过期。")
    return account


@router.post("/setup", dependencies=[Depends(check_limit)])
def setup(payload: SetupCredentials, request: Request, response: Response, db: Database) -> RecorderState:
    digest = token_digest(payload.token.get_secret_value())
    account = verify_setup(db.get(RecorderAccount, 1), digest)
    password_hash = password_hasher.hash(payload.password.get_secret_value())
    start_write(db)
    db.refresh(account)
    verify_setup(account, digest)
    account.password_hash = password_hash
    account.setup_hash = None
    account.setup_expires_at = None
    return issue_session(request, response, db)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Database) -> None:
    session = get_recorder_session(request, db)
    if session:
        db.delete(session)
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/api", httponly=True, samesite="strict")
