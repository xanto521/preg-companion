from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.connection import create_sqlite_engine
from app.db.models import Base, Checkup, DailyLog, MetricDefinition, MetricValue, Pregnancy
from app.domain.trends import trend_metrics, trend_series


class TrendVisibilityTest(TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        engine = create_sqlite_engine(Path(directory) / "trend.db")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        self.db = self.enterContext(Session(engine))
        self.zone = ZoneInfo("Asia/Shanghai")

    def test_shared_series_requires_all_linked_records_to_be_visible(self):
        pregnancy = Pregnancy(edd_date=date(2027, 4, 20), edd_source="manual")
        self.db.add(pregnancy)
        self.db.add_all([
            MetricDefinition(code="weight", name="体重", category="vital", value_type="num"),
            MetricDefinition(code="private", name="私有指标", category="vital", value_type="num"),
        ])
        self.db.flush()
        visible = Checkup(pregnancy_id=pregnancy.id, visit_date=date(2026, 11, 16), viewer_visible=True)
        hidden = Checkup(pregnancy_id=pregnancy.id, visit_date=visible.visit_date, viewer_visible=False)
        deleted = Checkup(
            pregnancy_id=pregnancy.id, visit_date=visible.visit_date, viewer_visible=True,
            deleted_at=datetime(2026, 11, 16),
        )
        visible_day = DailyLog(log_date=visible.visit_date, viewer_visible=True)
        hidden_day = DailyLog(log_date=date(2026, 11, 17), viewer_visible=False)
        self.db.add_all([visible, hidden, deleted, visible_day, hidden_day])
        self.db.flush()

        def reading(value, *, code="weight", checkup=None, day=None):
            return MetricValue(
                code=code, value_num=value, measured_at=datetime(2026, 11, 15, 17, 30), ga_days=125,
                checkup_id=checkup.id if checkup else None, daily_log_id=day.id if day else None,
            )

        self.db.add_all([
            reading(52, checkup=visible),
            reading(53, day=visible_day),
            reading(54, checkup=hidden),
            reading(55, checkup=deleted),
            reading(56, checkup=visible, day=hidden_day),
            reading(57),
            reading(58, code="private", checkup=hidden),
        ])
        self.db.commit()
        shared = trend_series(self.db, "weight", self.zone, viewer=True)
        self.assertEqual([p.value for p in shared.points], [52, 53])
        self.assertEqual(shared.points[0].day, visible.visit_date)
        self.assertEqual(shared.points[0].ga_days, 125)
        self.assertEqual([m.code for m in trend_metrics(self.db, viewer=True)], ["weight"])
        self.assertIsNone(trend_series(self.db, "private", self.zone, viewer=True))

        recorder = trend_series(self.db, "weight", self.zone, viewer=False)
        self.assertEqual([p.value for p in recorder.points], [52, 53, 54, 56, 57])
        pregnancy.edd_date += timedelta(days=8)
        self.db.commit()
        self.assertEqual(trend_series(self.db, "weight", self.zone, viewer=True), shared)
