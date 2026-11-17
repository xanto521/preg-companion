from asyncio import wait_for
from datetime import UTC, date, datetime, time
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Checkup, DailyLog, MealEntry, Note, SymptomEntry, utc_now
from app.db.session import Database
from app.domain.gestation import gestational_days
from app.domain.pregnancy import current_pregnancy
from app.domain.trends import TrendMetric, TrendSeries, trend_metrics, trend_series
from app.domain.visibility import visible_checkup, visible_daily_log, visible_note
from app.security.sharing import VIEW_SCOPE, active_share, valid_share

router = APIRouter(prefix="/view", tags=["family view"], include_in_schema=False)
PRIVATE_HEADERS = {
    "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
}
RECENT_LIMIT = 20
ACCESS_HEARTBEAT = 15
ACCESS_ENDED = "event: unavailable\ndata: {}\n\n"


class SharedPregnancy(BaseModel):
    due_date: date
    ga_days: int
    days_until_due: int


class SharedAppointment(BaseModel):
    day: date
    time: time | None


class SharedEntry(BaseModel):
    kind: Literal["checkup", "daily", "note"]
    day: date
    title: str | None = None
    text: str | None = None
    ga_days: int | None = None
    mood: str | None = None
    tags: list[str] = Field(default_factory=list)
    meals: dict[str, str] = Field(default_factory=dict)


class SharedSummary(BaseModel):
    pregnancy: SharedPregnancy | None
    next_appointment: SharedAppointment | None
    last_checkup: SharedEntry | None
    metrics: list[TrendMetric]
    entries: list[SharedEntry]


def authorize(db: Database, token: str) -> None:
    # Keep permission checks and visible records in the same SQLite snapshot.
    db.connection().exec_driver_sql("BEGIN")
    if not valid_share(db, token, VIEW_SCOPE):
        raise HTTPException(404, "分享链接已失效或不存在。", headers=PRIVATE_HEADERS)


@router.get("/{token}/access")
async def watch_access(token: str, request: Request) -> StreamingResponse:
    def read_access() -> tuple[int, datetime | None] | None:
        # Each check releases its own database session before the stream waits.
        with Session(request.app.state.engine) as db:
            share = active_share(db, token, VIEW_SCOPE)
            return (share.id, share.expires_at) if share else None

    access = await run_in_threadpool(read_access)
    if access is None:
        raise HTTPException(404, "分享链接已失效或不存在。", headers=PRIVATE_HEADERS)
    share_id, expires_at = access

    async def messages():
        with request.app.state.share_revocations.listen(share_id) as revoked:
            # Recheck after registering so a simultaneous revocation cannot be missed.
            if await run_in_threadpool(read_access) is None or revoked.is_set():
                yield ACCESS_ENDED
                return
            yield "event: ready\ndata: {}\n\n"
            while True:
                timeout = ACCESS_HEARTBEAT
                if expires_at is not None:
                    timeout = min(timeout, max(0, (expires_at - utc_now()).total_seconds()))
                try:
                    await wait_for(revoked.wait(), timeout=timeout)
                except TimeoutError:
                    if await run_in_threadpool(read_access) is not None and not revoked.is_set():
                        yield ": keepalive\n\n"
                        continue
                yield ACCESS_ENDED
                return

    return StreamingResponse(messages(), media_type="text/event-stream", headers=PRIVATE_HEADERS)


@router.get("/{token}/summary")
def summary(token: str, request: Request, db: Database) -> SharedSummary:
    authorize(db, token)
    zone = ZoneInfo(request.app.state.settings.timezone)
    today = datetime.now(zone).date()
    pregnancy = current_pregnancy(db)
    shared_pregnancy = None
    next_appointment = None
    checkups = []
    if pregnancy:
        shared_pregnancy = SharedPregnancy(
            due_date=pregnancy.edd_date,
            ga_days=gestational_days(pregnancy.edd_date, today),
            days_until_due=(pregnancy.edd_date - today).days,
        )
        visible = select(Checkup).where(Checkup.pregnancy_id == pregnancy.id, visible_checkup())
        checkups = [
            SharedEntry(kind="checkup", day=entry.visit_date, text=entry.viewer_note, ga_days=entry.ga_days)
            for entry in db.scalars(visible.order_by(
                Checkup.visit_date.desc(), Checkup.visit_time.desc(), Checkup.id.desc(),
            ).limit(RECENT_LIMIT))
        ]
        appointment = db.scalar(visible.where(Checkup.next_visit_date >= today).order_by(
            Checkup.next_visit_date, Checkup.next_visit_time, Checkup.id,
        ).limit(1))
        if appointment and appointment.next_visit_date is not None:
            next_appointment = SharedAppointment(day=appointment.next_visit_date, time=appointment.next_visit_time)

    daily_entries = db.scalars(select(DailyLog).where(visible_daily_log()).order_by(
        DailyLog.log_date.desc(),
    ).limit(RECENT_LIMIT))
    entries = list(checkups)
    for entry in daily_entries:
        tags = db.scalars(select(SymptomEntry.tag).where(SymptomEntry.daily_log_id == entry.id).order_by(SymptomEntry.id))
        meals = db.execute(select(MealEntry.meal_type, MealEntry.description).where(
            MealEntry.daily_log_id == entry.id, MealEntry.description.is_not(None),
        ).order_by(MealEntry.id))
        entries.append(SharedEntry(
            kind="daily", day=entry.log_date, text=entry.note, mood=entry.mood,
            tags=list(dict.fromkeys(tags)), meals={kind: text for kind, text in meals if text},
        ))

    notes = db.scalars(select(Note).where(visible_note()).order_by(Note.occurred_at.desc(), Note.id.desc()).limit(RECENT_LIMIT))
    for note in notes:
        day = note.occurred_at.replace(tzinfo=UTC).astimezone(zone).date()
        entries.append(SharedEntry(kind="note", day=day, title=note.title, text=note.body, tags=note.tags or []))
    entries.sort(key=lambda item: item.day, reverse=True)
    return SharedSummary(
        pregnancy=shared_pregnancy, next_appointment=next_appointment,
        last_checkup=checkups[0] if checkups else None,
        metrics=trend_metrics(db, viewer=True), entries=entries[:RECENT_LIMIT],
    )


@router.get("/{token}/metrics/{code}/series")
def series(token: str, code: str, request: Request, db: Database) -> TrendSeries:
    authorize(db, token)
    result = trend_series(db, code, ZoneInfo(request.app.state.settings.timezone), viewer=True)
    if result is None:
        raise HTTPException(404, "找不到可查看的指标。")
    return result
