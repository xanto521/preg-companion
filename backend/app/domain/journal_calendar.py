from calendar import monthrange
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Checkup, DailyLog, MealEntry, MilestoneRule, Note, SupplementCheck, SupplementPlan, SymptomEntry
from app.domain.milestones import milestone_window
from app.domain.pregnancy import current_pregnancy
from app.domain.supplements import is_scheduled

Kind = Literal["meal", "checkup", "supplement", "symptom", "note", "milestone"]
MEALS = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐", "snack": "加餐"}


class JournalEvent(BaseModel):
    key: str
    kind: Kind
    start: date
    end: date | None = None
    at: time | None = None
    state: Literal["recorded", "completed", "appointment", "taken", "pending", "planned", "window"]
    title: str
    detail: str | None = None
    target: Literal["daily", "symptoms", "checkup", "supplements", "notes", "milestones", "pregnancy"]
    record_id: int | None = None


def daily_events(db: Session, first: date, last: date) -> list[JournalEvent]:
    logs = list(db.scalars(select(DailyLog).where(
        DailyLog.log_date.between(first, last), DailyLog.deleted_at.is_(None),
    )))
    dates = {log.id: log.log_date for log in logs}
    events = []
    for meal in db.scalars(select(MealEntry).where(MealEntry.daily_log_id.in_(dates)).order_by(MealEntry.id)):
        if meal.attachment_id or meal.description:
            events.append(JournalEvent(
                key=f"meal-{meal.id}", kind="meal", start=dates[meal.daily_log_id], state="recorded",
                title=MEALS.get(meal.meal_type, "饮食"), detail=meal.description or "有饮食照片", target="daily",
            ))
    symptoms = defaultdict(list)
    for symptom in db.scalars(select(SymptomEntry).where(SymptomEntry.daily_log_id.in_(dates)).order_by(SymptomEntry.id)):
        symptoms[symptom.daily_log_id].append(symptom.tag)
    for log in logs:
        if tags := symptoms[log.id]:
            events.append(JournalEvent(
                key=f"symptom-{log.id}", kind="symptom", start=log.log_date, state="recorded",
                title="症状记录", detail="、".join(dict.fromkeys(tags)), target="symptoms",
            ))
        if log.note or log.mood:
            events.append(JournalEvent(
                key=f"daily-note-{log.id}", kind="note", start=log.log_date, state="recorded",
                title="当天备注" if log.note else "当天心情", detail=log.note or log.mood, target="daily",
            ))
    return events


def checkup_events(db: Session, first: date, last: date) -> list[JournalEvent]:
    records = db.scalars(select(Checkup).where(
        Checkup.deleted_at.is_(None),
        or_(Checkup.visit_date.between(first, last), Checkup.next_visit_date.between(first, last)),
    ).order_by(Checkup.id))
    events = []
    for record in records:
        if first <= record.visit_date <= last:
            events.append(JournalEvent(
                key=f"checkup-{record.id}", kind="checkup", start=record.visit_date, at=record.visit_time,
                state="completed", title="产检记录", detail=record.hospital, target="checkup", record_id=record.id,
            ))
        if record.next_visit_date and first <= record.next_visit_date <= last:
            events.append(JournalEvent(
                key=f"appointment-{record.id}", kind="checkup", start=record.next_visit_date, at=record.next_visit_time,
                state="appointment", title="下次产检", detail=record.hospital, target="checkup", record_id=record.id,
            ))
    return events


def supplement_events(db: Session, first: date, last: date, today: date) -> list[JournalEvent]:
    checks = set(db.execute(select(SupplementCheck.plan_id, SupplementCheck.check_date).where(
        SupplementCheck.check_date.between(first, last), SupplementCheck.taken.is_(True),
    )).tuples())
    plans = db.scalars(select(SupplementPlan).where(SupplementPlan.deleted_at.is_(None)).order_by(SupplementPlan.id))
    events = []
    for plan in plans:
        for offset in range((last - first).days + 1):
            day = first + timedelta(days=offset)
            taken = (plan.id, day) in checks
            if taken or is_scheduled(plan, day):
                events.append(JournalEvent(
                    key=f"supplement-{plan.id}-{day.isoformat()}", kind="supplement", start=day, at=plan.remind_time,
                    state="taken" if taken else "planned" if day > today else "pending",
                    title=plan.name, detail=plan.dosage, target="supplements", record_id=plan.id,
                ))
    return events


def note_events(db: Session, first: date, last: date, zone: ZoneInfo) -> list[JournalEvent]:
    start = datetime.combine(first, time.min, zone).astimezone(UTC).replace(tzinfo=None)
    end = datetime.combine(last + timedelta(days=1), time.min, zone).astimezone(UTC).replace(tzinfo=None)
    notes = db.scalars(select(Note).where(
        Note.deleted_at.is_(None), Note.occurred_at >= start, Note.occurred_at < end,
    ).order_by(Note.occurred_at, Note.id))
    return [
        JournalEvent(
            key=f"note-{note.id}", kind="note", start=note.occurred_at.replace(tzinfo=UTC).astimezone(zone).date(),
            state="recorded", title=note.title or "备注", detail=note.body, target="notes", record_id=note.id,
        )
        for note in notes
    ]


def milestone_events(db: Session, first: date, last: date) -> list[JournalEvent]:
    pregnancy = current_pregnancy(db)
    if pregnancy is None:
        return []
    events = []
    if first <= pregnancy.edd_date <= last:
        events.append(JournalEvent(
            key=f"edd-{pregnancy.id}", kind="milestone", start=pregnancy.edd_date, state="planned",
            title="预产期", target="pregnancy",
        ))
    rules = db.scalars(select(MilestoneRule).where(
        MilestoneRule.enabled.is_(True), MilestoneRule.deleted_at.is_(None),
    ).order_by(MilestoneRule.id))
    for rule in rules:
        window = milestone_window(pregnancy.edd_date, rule.start_ga_days, rule.end_ga_days)
        if window and window[0] <= last and window[1] >= first:
            events.append(JournalEvent(
                key=f"window-{rule.id}", kind="milestone", start=window[0], end=window[1], state="window",
                title=rule.title, detail=rule.note, target="milestones", record_id=rule.id,
            ))
    return events


def journal_month(db: Session, year: int, month: int, zone: ZoneInfo, today: date) -> list[JournalEvent]:
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    return [
        *checkup_events(db, first, last),
        *daily_events(db, first, last),
        *supplement_events(db, first, last, today),
        *note_events(db, first, last, zone),
        *milestone_events(db, first, last),
    ]
