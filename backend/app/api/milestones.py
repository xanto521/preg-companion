from datetime import date
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator
from sqlalchemy import select

from app.api.auth import require_recorder
from app.db.connection import start_write
from app.db.models import MilestoneRule
from app.db.session import Database
from app.domain.milestones import milestone_window
from app.domain.pregnancy import current_pregnancy

router = APIRouter(prefix="/milestones", tags=["milestones"], dependencies=[Depends(require_recorder)])


class RuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: PositiveInt | None = None
    version: PositiveInt | None = None
    title: str = Field(min_length=1, max_length=100)
    start_ga_days: int = Field(ge=0, le=370)
    end_ga_days: int = Field(ge=0, le=370)
    enabled: bool = True
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_rule(self) -> "RuleInput":
        if self.start_ga_days > self.end_ga_days:
            raise ValueError("结束孕周不能早于开始孕周。")
        if (self.id is None) != (self.version is None):
            raise ValueError("编辑已有规则需要记录编号和版本。")
        return self


class RuleDetails(BaseModel):
    id: int
    version: int
    title: str
    start_ga_days: int
    end_ga_days: int
    enabled: bool
    note: str | None
    starts_on: date | None
    ends_on: date | None


def describe(rule: MilestoneRule, due_date: date | None) -> RuleDetails:
    window = milestone_window(due_date, rule.start_ga_days, rule.end_ga_days) if due_date else None
    start, end = window or (None, None)
    return RuleDetails(
        id=rule.id, version=rule.version, title=rule.title, start_ga_days=rule.start_ga_days,
        end_ga_days=rule.end_ga_days, enabled=rule.enabled, note=rule.note,
        starts_on=start, ends_on=end,
    )


@router.get("")
def list_rules(db: Database) -> list[RuleDetails]:
    pregnancy = current_pregnancy(db)
    due_date = pregnancy.edd_date if pregnancy else None
    rules = db.scalars(
        select(MilestoneRule).where(MilestoneRule.deleted_at.is_(None))
        .order_by(MilestoneRule.start_ga_days, MilestoneRule.end_ga_days, MilestoneRule.id)
    )
    return [describe(rule, due_date) for rule in rules]


@router.put("")
def save_rule(payload: RuleInput, db: Database) -> RuleDetails:
    start_write(db)
    values = payload.model_dump(exclude={"id", "version"})
    values["note"] = values["note"] or None
    if payload.id is None:
        rule = MilestoneRule(code=f"milestone-{uuid4().hex}", **values)
        db.add(rule)
    else:
        rule = db.get(MilestoneRule, payload.id)
        if rule is None or rule.deleted_at is not None:
            raise HTTPException(404, "这条里程碑规则不存在。")
        if payload.version != rule.version:
            raise HTTPException(409, "规则已更新，请重新打开后再修改。")
        if any(getattr(rule, name) != value for name, value in values.items()):
            for name, value in values.items():
                setattr(rule, name, value)
            rule.version += 1
    pregnancy = current_pregnancy(db)
    db.commit()
    return describe(rule, pregnancy.edd_date if pregnancy else None)
