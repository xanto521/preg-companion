from datetime import date

from app.db.models import SupplementPlan


def is_scheduled(plan: SupplementPlan, day: date) -> bool:
    return bool(
        plan.active and plan.deleted_at is None
        and plan.start_date <= day
        and (plan.end_date is None or day <= plan.end_date)
    )
