from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from zoneinfo import ZoneInfo

from icalendar import Calendar
from sqlalchemy.orm import Session

from app.calendar.events import collect_events
from app.calendar.ics import render_calendar
from app.db.connection import create_sqlite_engine
from app.db.models import Base, Checkup, MilestoneRule, Pregnancy, SupplementCheck, SupplementPlan


class CalendarTest(TestCase):
    def setUp(self):
        folder = self.enterContext(TemporaryDirectory())
        engine = create_sqlite_engine(Path(folder) / "test.db")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        self.db = self.enterContext(Session(engine))
        self.zone = ZoneInfo("Asia/Shanghai")
        self.stamp = datetime(2026, 11, 16, 8, 0)
        self.pregnancy = Pregnancy(
            edd_date=date(2027, 3, 1), edd_source="manual", updated_at=self.stamp,
        )
        self.db.add(self.pregnancy)
        self.db.flush()

    def feed(self):
        return render_calendar(collect_events(self.db, self.zone), "preg.test", self.zone)

    def test_feed_is_stable_and_filters_private_data(self):
        self.db.add_all([
            Checkup(
                pregnancy_id=self.pregnancy.id,
                visit_date=date(2026, 11, 1),
                hospital="private-original-hospital",
                next_visit_date=date(2026, 12, 1),
                next_visit_time=time(9, 30),
                next_visit_hospital="预约医院, 东院区; 二楼",
                viewer_visible=True,
                advice="private-advice",
                updated_at=self.stamp,
            ),
            Checkup(
                pregnancy_id=self.pregnancy.id,
                visit_date=date(2026, 11, 2),
                next_visit_date=date(2026, 12, 2),
                next_visit_hospital="private-appointment",
                viewer_visible=False,
            ),
            Checkup(
                pregnancy_id=self.pregnancy.id,
                visit_date=date(2026, 11, 3),
                next_visit_date=date(2026, 12, 3),
                next_visit_hospital="private-deleted-hospital",
                deleted_at=self.stamp,
            ),
            Checkup(
                pregnancy_id=self.pregnancy.id,
                visit_date=date(2026, 11, 4),
                hospital="原医院",
                next_visit_date=date(2026, 12, 4),
                viewer_visible=True,
            ),
        ])
        self.db.commit()
        content = self.feed()
        self.assertEqual(content, self.feed())
        self.assertNotIn(b"private-", content)
        parsed = Calendar.from_ical(content)
        items = {str(event["UID"]): event for event in parsed.walk("VEVENT")}
        self.assertEqual(set(items), {"edd-1@preg.test", "checkup-1@preg.test", "checkup-4@preg.test"})
        self.assertEqual(parsed.walk("VTIMEZONE")[0]["TZID"], "Asia/Shanghai")
        visit = items["checkup-1@preg.test"]
        self.assertEqual(visit["SUMMARY"], "产检")
        self.assertEqual(visit["LOCATION"], "预约医院, 东院区; 二楼")
        self.assertEqual(visit.decoded("DTSTART"), datetime(2026, 12, 1, 9, 30, tzinfo=self.zone))
        self.assertEqual(visit.decoded("DTEND") - visit.decoded("DTSTART"), timedelta(hours=1))
        self.assertEqual(
            [alarm.decoded("TRIGGER") for alarm in visit.walk("VALARM")],
            [timedelta(days=-1), timedelta(hours=-2)],
        )
        all_day = items["checkup-4@preg.test"]
        self.assertEqual(all_day["LOCATION"], "原医院")
        self.assertNotIn("LOCATION", items["edd-1@preg.test"])
        self.assertEqual(all_day.decoded("DTEND"), date(2026, 12, 5))
        self.assertEqual([a.decoded("TRIGGER") for a in all_day.walk("VALARM")], [timedelta(days=-1)])

    def test_correction_reschedules_window_with_same_uid(self):
        rule = MilestoneRule(
            code="sample", title="private-rule-title", note="private-rule-note",
            start_ga_days=259, end_ga_days=261, updated_at=self.stamp,
        )
        self.db.add(rule)
        self.db.commit()

        def window():
            parsed = Calendar.from_ical(self.feed())
            return next(event for event in parsed.walk("VEVENT") if str(event["UID"]).startswith("milestone-"))

        before = window()
        self.assertEqual(before.decoded("DTSTART"), date(2027, 2, 8))
        self.assertEqual(before.decoded("DTEND"), date(2027, 2, 11))
        self.assertEqual(before.walk("VALARM")[0].decoded("TRIGGER"), timedelta(0))

        self.pregnancy.edd_date += timedelta(days=3)
        self.pregnancy.version += 1
        self.pregnancy.updated_at = self.stamp + timedelta(days=1)
        self.db.commit()
        after = window()
        self.assertEqual(after["UID"], before["UID"])
        self.assertEqual(after["SEQUENCE"], before["SEQUENCE"] + 1)
        self.assertEqual(after.decoded("DTSTART"), date(2027, 2, 11))
        self.assertGreater(after.decoded("LAST-MODIFIED"), before.decoded("LAST-MODIFIED"))
        self.assertNotIn(b"private-rule", self.feed())

        rule.enabled = False
        self.db.commit()
        self.assertNotIn(b"milestone-", self.feed())

    def test_supplement_reminder_is_daily_private_and_independent_of_checkin(self):
        self.db.delete(self.pregnancy)
        plan = SupplementPlan(
            name="private-plan-name", dosage="private-dosage",
            start_date=date(2026, 11, 16), end_date=date(2026, 11, 19),
            remind_time=time(9, 15), rrule="FREQ=DAILY", viewer_visible=True,
            updated_at=self.stamp,
        )
        private_plan = SupplementPlan(
            name="private-untimed", start_date=plan.start_date, remind_time=time(10),
        )
        self.db.add_all([plan, private_plan])
        self.db.commit()

        content = self.feed()
        self.assertNotIn(b"private-", content)
        event, = Calendar.from_ical(content).walk("VEVENT")
        self.assertEqual(event["SUMMARY"], "补剂")
        self.assertEqual(event.decoded("DTSTART"), datetime(2026, 11, 16, 9, 15, tzinfo=self.zone))
        self.assertEqual(event["RRULE"]["FREQ"], ["DAILY"])
        self.assertEqual(event["RRULE"]["UNTIL"], [datetime(2026, 11, 19, 1, 15, tzinfo=UTC)])
        self.assertEqual(event.walk("VALARM")[0].decoded("TRIGGER"), timedelta(0))
        self.db.add(SupplementCheck(plan_id=plan.id, check_date=plan.start_date, taken=True))
        self.db.commit()
        self.assertEqual(content, self.feed())

        plan.active = False
        self.db.commit()
        self.assertFalse(Calendar.from_ical(self.feed()).walk("VEVENT"))
