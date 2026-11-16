from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Checkup, MilestoneRule
from app.domain.milestones import milestone_window
from app.domain.pregnancy import current_pregnancy

DAY = timedelta(days=1)
HOUR = timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    key: str
    summary: str
    start: date | datetime
    end: date | datetime
    sequence: int
    modified: datetime
    alarms: tuple[timedelta, ...]


def checkup_event(checkup: Checkup, zone: ZoneInfo) -> CalendarEvent | None:
    day = checkup.next_visit_date
    if day is None:
        return None
    try:
        if checkup.next_visit_time:
            start = datetime.combine(day, checkup.next_visit_time, zone)
            end = (start.astimezone(UTC) + HOUR).astimezone(zone)
            alarms = (-DAY, -2 * HOUR)
        else:
            start, end = day, day + DAY
            alarms = (-DAY,)
    except OverflowError:
        return None
    return CalendarEvent(f"checkup-{checkup.id}", "产检", start, end, checkup.version, checkup.updated_at, alarms)


def collect_events(db: Session, zone: ZoneInfo) -> list[CalendarEvent]:
    pregnancy = current_pregnancy(db)
    if pregnancy is None:
        return []

    events = []
    if pregnancy.edd_date < date.max:
        events.append(CalendarEvent(
            f"edd-{pregnancy.id}", "预产期", pregnancy.edd_date, pregnancy.edd_date + DAY,
            pregnancy.version, pregnancy.updated_at, (-7 * DAY,),
        ))
    checkups = db.scalars(select(Checkup).where(
        Checkup.pregnancy_id == pregnancy.id,
        Checkup.deleted_at.is_(None),
        Checkup.viewer_visible.is_(True),
        Checkup.next_visit_date.is_not(None),
    ).order_by(Checkup.id))
    for checkup in checkups:
        event = checkup_event(checkup, zone)
        if event:
            events.append(event)

    rules = db.scalars(select(MilestoneRule).where(
        MilestoneRule.enabled.is_(True), MilestoneRule.deleted_at.is_(None),
    ).order_by(MilestoneRule.id))
    for rule in rules:
        window = milestone_window(pregnancy.edd_date, rule.start_ga_days, rule.end_ga_days)
        if window and window[1] < date.max:
            events.append(CalendarEvent(
                f"milestone-{pregnancy.id}-{rule.id}", "产检参考窗口", window[0], window[1] + DAY,
                rule.version + pregnancy.version - 1, max(rule.updated_at, pregnancy.updated_at), (timedelta(0),),
            ))
    return events
