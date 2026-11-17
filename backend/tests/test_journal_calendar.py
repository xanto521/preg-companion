from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.connection import create_sqlite_engine
from app.db.models import Base, Checkup, DailyLog, MealEntry, MilestoneRule, Note, Pregnancy, SupplementCheck, SupplementPlan
from app.domain.journal_calendar import journal_month


class JournalCalendarTest(TestCase):
    def setUp(self):
        folder = self.enterContext(TemporaryDirectory())
        engine = create_sqlite_engine(Path(folder) / "journal.db")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        self.db = self.enterContext(Session(engine))

    def test_cross_month_windows_and_source_dates(self):
        pregnancy = Pregnancy(edd_date=date(2027, 7, 1), edd_source="manual")
        self.db.add(pregnancy)
        self.db.flush()
        checkup = Checkup(
            pregnancy_id=pregnancy.id, visit_date=date(2026, 10, 15),
            next_visit_date=date(2026, 11, 20), viewer_visible=False,
        )
        daily = DailyLog(log_date=date(2026, 11, 1))
        old_plan = SupplementPlan(name="Paused", start_date=date(2026, 10, 1), active=False)
        self.db.add_all([checkup, daily, old_plan])
        self.db.flush()
        # This near-midnight UTC note belongs to November in the configured timezone.
        self.db.add_all([
            Note(title="late", occurred_at=datetime(2026, 10, 31, 17), body="local November"),
            MealEntry(daily_log_id=daily.id, meal_type="lunch", description="rice"),
            SupplementCheck(plan_id=old_plan.id, check_date=date(2026, 11, 2), taken=True),
            MilestoneRule(code="sample", title="Across months", start_ga_days=35, end_ga_days=40),
        ])
        self.db.commit()

        zone = ZoneInfo("Asia/Shanghai")
        today = date(2026, 11, 17)
        items = journal_month(self.db, 2026, 11, zone, today)
        self.assertEqual(len(items), 5)
        appointment, = [item for item in items if item.kind == "checkup"]
        self.assertEqual((appointment.state, appointment.record_id), ("appointment", checkup.id))
        note, = [item for item in items if item.kind == "note"]
        self.assertEqual(note.start, date(2026, 11, 1))
        supplement, = [item for item in items if item.kind == "supplement"]
        self.assertEqual(supplement.state, "taken")
        window, = [item for item in items if item.state == "window"]
        self.assertLess(window.start, date(2026, 11, 1))
        self.assertGreaterEqual(window.end, date(2026, 11, 1))
        prev = journal_month(self.db, 2026, 10, zone, today)
        self.assertIn(window, prev)
        self.assertTrue(any(item.state == "completed" and item.record_id == checkup.id for item in prev))
