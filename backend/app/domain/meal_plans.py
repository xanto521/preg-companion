import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

Dishes = Annotated[list[str], Field(min_length=1)]
MEAL_KEYS = ("breakfast", "lunch", "dinner", "snack")
CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "meal_plans.json"


class MealMenu(BaseModel):
    day: int
    breakfast: Dishes
    lunch: Dishes
    dinner: Dishes
    snack: Dishes

    @field_validator(*MEAL_KEYS)
    @classmethod
    def fits_journal(cls, dishes: list[str]) -> list[str]:
        if not all(dish.strip() for dish in dishes) or len("、".join(dishes)) > 500:
            raise ValueError("每餐需填写菜名，总长度最多 500 个字符。")
        return dishes


class MealGroup(BaseModel):
    month: int
    days: Annotated[list[MealMenu], Field(min_length=1)]


@lru_cache(maxsize=1)
def meal_groups() -> list[MealGroup]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    withheld = set(catalog.get("withheld_dishes", []))
    for group in catalog["months"]:
        for menu in group["days"]:
            for meal in MEAL_KEYS:
                menu[meal] = [dish for dish in menu[meal] if dish.strip() not in withheld]
    return [MealGroup.model_validate(group) for group in catalog["months"]]


def recommended_month(ga_days: int | None) -> int | None:
    if ga_days is None or ga_days < 0:
        return None
    return min(ga_days // 28 + 1, 9)
