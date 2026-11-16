from datetime import date, time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from app.api.auth import require_recorder
from app.db.connection import start_write
from app.db.models import SupplementCheck, SupplementPlan
from app.db.session import Database
from app.domain.supplements import is_scheduled

router = APIRouter(prefix="/supplements", tags=["supplements"], dependencies=[Depends(require_recorder)])


class PlanInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    dosage: str | None = Field(default=None, max_length=150)
    start_date: date
    end_date: date | None = None
    remind_time: time | None = None
    active: bool = True
    viewer_visible: bool = False

    @model_validator(mode="after")
    def validate_plan(self) -> "PlanInput":
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期。")
        if self.remind_time is not None and self.remind_time.tzinfo is not None:
            raise ValueError("请填写当地提醒时间。")
        if self.viewer_visible and self.remind_time is None:
            raise ValueError("同步日历前，请填写提醒时间。")
        return self


class PlanEdit(PlanInput):
    version: PositiveInt


class PlanRecord(PlanInput):
    # Read existing plans even if their reminder settings predate this interface.
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int

    @model_validator(mode="after")
    def validate_plan(self) -> "PlanRecord":
        return self


class DailyPlan(PlanRecord):
    scheduled: bool
    taken: bool


class CheckInput(BaseModel):
    day: date
    taken: bool


def find_plan(db: Database, plan_id: int) -> SupplementPlan:
    plan = db.get(SupplementPlan, plan_id)
    if plan is None or plan.deleted_at is not None:
        raise HTTPException(404, "补剂计划不存在。")
    return plan


@router.get("")
def list_plans(day: date, db: Database) -> list[DailyPlan]:
    statement = (
        select(SupplementPlan, SupplementCheck.taken)
        .outerjoin(SupplementCheck, (SupplementCheck.plan_id == SupplementPlan.id) & (SupplementCheck.check_date == day))
        .where(SupplementPlan.deleted_at.is_(None))
        .order_by(SupplementPlan.active.desc(), SupplementPlan.id)
    )
    return [
        DailyPlan(**PlanRecord.model_validate(plan).model_dump(), scheduled=is_scheduled(plan, day), taken=bool(taken))
        for plan, taken in db.execute(statement)
    ]


@router.post("", status_code=201)
def create_plan(payload: PlanInput, db: Database) -> PlanRecord:
    plan = SupplementPlan(**payload.model_dump(), rrule="FREQ=DAILY")
    plan.dosage = plan.dosage or None
    db.add(plan)
    db.commit()
    return PlanRecord.model_validate(plan)


@router.put("/{plan_id}")
def update_plan(plan_id: int, payload: PlanEdit, db: Database) -> PlanRecord:
    start_write(db)
    plan = find_plan(db, plan_id)
    if plan.version != payload.version:
        raise HTTPException(409, "计划已更新，请重新打开后再修改。")
    values = payload.model_dump(exclude={"version"})
    values.update(dosage=payload.dosage or None, rrule="FREQ=DAILY")
    if any(getattr(plan, name) != value for name, value in values.items()):
        for name, value in values.items():
            setattr(plan, name, value)
        plan.version += 1
    db.commit()
    return PlanRecord.model_validate(plan)


@router.post("/{plan_id}/check", status_code=204)
def mark_taken(plan_id: int, payload: CheckInput, db: Database) -> None:
    start_write(db)
    plan = find_plan(db, plan_id)
    previous = db.scalar(select(SupplementCheck).where(
        SupplementCheck.plan_id == plan.id, SupplementCheck.check_date == payload.day,
    ))
    if not is_scheduled(plan, payload.day) and (payload.taken or previous is None):
        raise HTTPException(409, "所选日期不在启用的计划内。")
    statement = insert(SupplementCheck).values(
        plan_id=plan.id, check_date=payload.day, taken=payload.taken,
    ).on_conflict_do_update(
        index_elements=["plan_id", "check_date"], set_={"taken": payload.taken},
    )
    db.execute(statement)
    db.commit()
