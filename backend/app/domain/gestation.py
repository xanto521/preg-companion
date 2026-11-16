from datetime import date

DAYS_AT_DUE_DATE = 280


def gestational_days(due_date: date, target_date: date) -> int:
    return DAYS_AT_DUE_DATE - (due_date - target_date).days
