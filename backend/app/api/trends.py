from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, FiniteFloat, model_validator

from app.api.auth import require_recorder
from app.db.models import MetricDefinition
from app.db.session import Database
from app.domain.trends import TrendMetric, TrendSeries, trend_metrics, trend_series

router = APIRouter(prefix="/metrics", tags=["trends"], dependencies=[Depends(require_recorder)])


class ReferenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref_low: FiniteFloat | None
    ref_high: FiniteFloat | None

    @model_validator(mode="after")
    def validate_limits(self) -> "ReferenceInput":
        if self.ref_low is not None and self.ref_high is not None and self.ref_low > self.ref_high:
            raise ValueError("参考下限不能高于上限。")
        return self


@router.get("/trends")
def list_trends(db: Database) -> list[TrendMetric]:
    return trend_metrics(db, viewer=False)


@router.get("/{code}/series")
def read_series(code: str, request: Request, db: Database) -> TrendSeries:
    series = trend_series(db, code, ZoneInfo(request.app.state.settings.timezone), viewer=False)
    if series is None:
        raise HTTPException(404, "找不到这个指标。")
    return series


@router.put("/{code}/reference")
def set_reference(code: str, payload: ReferenceInput, db: Database) -> TrendMetric:
    metric = db.get(MetricDefinition, code)
    if metric is None or metric.value_type != "num":
        raise HTTPException(404, "找不到这个指标。")
    metric.ref_low = payload.ref_low
    metric.ref_high = payload.ref_high
    db.commit()
    return TrendMetric.model_validate(metric)
