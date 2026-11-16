from sqlalchemy import and_

from app.db.models import Checkup, DailyLog, Note


def visible_checkup():
    return and_(Checkup.viewer_visible.is_(True), Checkup.deleted_at.is_(None))


def visible_daily_log():
    return and_(DailyLog.viewer_visible.is_(True), DailyLog.deleted_at.is_(None))


def visible_note():
    return and_(Note.viewer_visible.is_(True), Note.deleted_at.is_(None))
