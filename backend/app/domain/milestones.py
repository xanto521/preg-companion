from datetime import date, timedelta

from app.domain.gestation import DAYS_AT_DUE_DATE


def milestone_window(due_date: date, start_days: int, end_days: int) -> tuple[date, date] | None:
    """Return inclusive dates for a window measured from gestational day zero."""
    try:
        return (
            due_date + timedelta(days=start_days - DAYS_AT_DUE_DATE),
            due_date + timedelta(days=end_days - DAYS_AT_DUE_DATE),
        )
    except OverflowError:
        return None
