from datetime import UTC, date
from math import isfinite
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.models import Checkup, DailyLog, MetricDefinition, MetricValue
from app.domain.visibility import visible_checkup, visible_daily_log


class TrendMetric(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    unit: str | None
    ref_low: float | None
    ref_high: float | None


class TrendPoint(BaseModel):
    day: date
    ga_days: int | None
    value: float


class TrendSeries(BaseModel):
    metric: TrendMetric
    points: list[TrendPoint]


def available_values(*, viewer: bool):
    checkup = visible_checkup() if viewer else and_(Checkup.id.is_not(None), Checkup.deleted_at.is_(None))
    daily = visible_daily_log() if viewer else and_(DailyLog.id.is_not(None), DailyLog.deleted_at.is_(None))
    query = (
        select(MetricValue)
        .outerjoin(Checkup, Checkup.id == MetricValue.checkup_id)
        .outerjoin(DailyLog, DailyLog.id == MetricValue.daily_log_id)
        .where(
            MetricValue.value_num.is_not(None),
            or_(MetricValue.checkup_id.is_(None), and_(Checkup.id.is_not(None), checkup)),
            or_(MetricValue.daily_log_id.is_(None), and_(DailyLog.id.is_not(None), daily)),
        )
    )
    if viewer:
        query = query.where(or_(MetricValue.checkup_id.is_not(None), MetricValue.daily_log_id.is_not(None)))
    return query


def trend_metrics(db: Session, *, viewer: bool) -> list[TrendMetric]:
    query = select(MetricDefinition).where(MetricDefinition.value_type == "num")
    if viewer:
        query = query.where(
            MetricDefinition.code.in_(available_values(viewer=True).with_only_columns(MetricValue.code))
        )
    return [
        TrendMetric.model_validate(metric)
        for metric in db.scalars(query.order_by(MetricDefinition.code))
    ]


def trend_series(db: Session, code: str, zone: ZoneInfo, *, viewer: bool) -> TrendSeries | None:
    metric = db.get(MetricDefinition, code)
    if metric is None or metric.value_type != "num":
        return None
    readings = db.scalars(
        available_values(viewer=viewer).where(MetricValue.code == code)
        .order_by(MetricValue.measured_at, MetricValue.id)
    )
    points = []
    for reading in readings:
        if reading.value_num is None or not isfinite(reading.value_num):
            continue
        try:
            day = reading.measured_at.replace(tzinfo=UTC).astimezone(zone).date()
        except OverflowError:
            continue
        points.append(TrendPoint(day=day, ga_days=reading.ga_days, value=reading.value_num))
    if viewer and not points:
        return None
    return TrendSeries(metric=TrendMetric.model_validate(metric), points=points)
