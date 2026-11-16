from datetime import UTC, date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from app.api.auth import require_recorder
from app.db.connection import start_write
from app.db.models import EddHistory, Pregnancy
from app.db.session import Database
from app.domain.gestation import gestational_days
from app.domain.pregnancy import current_pregnancy

router = APIRouter(prefix="/pregnancy", tags=["pregnancy"], dependencies=[Depends(require_recorder)])
Source = Literal["lmp", "ultrasound", "manual"]


class PregnancyInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    edd_date: date
    edd_source: Source
    lmp_date: date | None = None
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_dates(self) -> "PregnancyInput":
        if self.lmp_date and self.lmp_date >= self.edd_date:
            raise ValueError("末次月经日期须早于预产期。")
        return self


class PregnancyDetails(BaseModel):
    id: int
    edd_date: date
    edd_source: str
    lmp_date: date | None
    ga_days: int
    days_until_due: int


class HistoryItem(BaseModel):
    edd_date: date
    source: str
    note: str | None
    changed_at: datetime


class PregnancySummary(BaseModel):
    today: date
    pregnancy: PregnancyDetails | None
    history: list[HistoryItem]


def summarize(request: Request, db: Database, pregnancy: Pregnancy | None) -> PregnancySummary:
    today = datetime.now(ZoneInfo(request.app.state.settings.timezone)).date()
    if pregnancy is None:
        return PregnancySummary(today=today, pregnancy=None, history=[])

    history = db.scalars(
        select(EddHistory)
        .where(EddHistory.pregnancy_id == pregnancy.id)
        .order_by(EddHistory.changed_at.desc(), EddHistory.id.desc())
    )
    return PregnancySummary(
        today=today,
        pregnancy=PregnancyDetails(
            id=pregnancy.id,
            edd_date=pregnancy.edd_date,
            edd_source=pregnancy.edd_source,
            lmp_date=pregnancy.lmp_date,
            ga_days=gestational_days(pregnancy.edd_date, today),
            days_until_due=(pregnancy.edd_date - today).days,
        ),
        history=[
            HistoryItem(
                edd_date=entry.edd_date, source=entry.source, note=entry.note,
                changed_at=entry.changed_at.replace(tzinfo=UTC),
            )
            for entry in history
        ],
    )


@router.get("")
def read_pregnancy(request: Request, db: Database) -> PregnancySummary:
    return summarize(request, db, current_pregnancy(db))


@router.put("")
def set_pregnancy(payload: PregnancyInput, request: Request, db: Database) -> PregnancySummary:
    start_write(db)
    pregnancy = current_pregnancy(db)
    values = payload.model_dump(exclude={"note"})
    if pregnancy is None:
        pregnancy = Pregnancy(**values)
        db.add(pregnancy)
    else:
        changed = any(getattr(pregnancy, key) != value for key, value in values.items())
        if not changed:
            return summarize(request, db, pregnancy)
        for key, value in values.items():
            setattr(pregnancy, key, value)
        pregnancy.version += 1
    db.flush()
    db.add(EddHistory(
        pregnancy_id=pregnancy.id, edd_date=payload.edd_date,
        source=payload.edd_source, note=payload.note or None,
    ))
    db.commit()
    return summarize(request, db, pregnancy)
