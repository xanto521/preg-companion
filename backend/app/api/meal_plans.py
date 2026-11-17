from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.api.auth import require_recorder
from app.db.session import Database
from app.domain.gestation import gestational_days
from app.domain.meal_plans import MealGroup, meal_groups, recommended_month
from app.domain.pregnancy import current_pregnancy

router = APIRouter(prefix="/meal-plans", tags=["meal plans"], dependencies=[Depends(require_recorder)])


class DailyMealPlans(BaseModel):
    today: date
    recommended_month: int | None
    rotation_day: int
    groups: list[MealGroup]


@router.get("")
def read_menu(request: Request, db: Database) -> DailyMealPlans:
    today = datetime.now(ZoneInfo(request.app.state.settings.timezone)).date()
    pregnancy = current_pregnancy(db)
    ga_days = gestational_days(pregnancy.edd_date, today) if pregnancy else None
    month = recommended_month(ga_days)
    return DailyMealPlans(
        today=today, recommended_month=month,
        rotation_day=ga_days if month is not None else today.toordinal(),
        groups=meal_groups(),
    )
