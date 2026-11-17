from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request

from app.api.auth import require_recorder
from app.db.session import Database
from app.domain.journal_calendar import JournalEvent, journal_month

router = APIRouter(prefix="/journal-calendar", tags=["journal calendar"], dependencies=[Depends(require_recorder)])


@router.get("")
def read_month(
    year: Annotated[int, Query(ge=2, le=9998)],
    month: Annotated[int, Query(ge=1, le=12)],
    request: Request,
    db: Database,
) -> list[JournalEvent]:
    zone = ZoneInfo(request.app.state.settings.timezone)
    db.connection().exec_driver_sql("BEGIN")
    return journal_month(db, year, month, zone, datetime.now(zone).date())
