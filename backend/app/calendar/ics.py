from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from icalendar import Alarm, Calendar, Event, Timezone

from app.calendar.events import CalendarEvent


def render_calendar(events: list[CalendarEvent], domain: str, zone: ZoneInfo) -> bytes:
    calendar = Calendar()
    calendar.add("prodid", "-//preg-companion//CN")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("x-wr-calname", "孕期日程")

    timed_years = [event.start.year for event in events if isinstance(event.start, datetime)]
    if timed_years and zone.key != "UTC":
        calendar.add_component(Timezone.from_tzinfo(
            zone,
            first_date=date(max(1, min(timed_years) - 1), 1, 1),
            last_date=date(min(9999, max(timed_years) + 2), 1, 1),
        ))

    for event in events:
        component = Event()
        modified = event.modified.replace(tzinfo=UTC)
        component.add("uid", f"{event.key}@{domain}")
        component.add("summary", event.summary)
        component.add("dtstart", event.start)
        component.add("dtend", event.end)
        component.add("dtstamp", modified)
        component.add("last-modified", modified)
        component.add("sequence", event.sequence)
        for trigger in event.alarms:
            alarm = Alarm()
            alarm.add("action", "DISPLAY")
            alarm.add("trigger", trigger)
            alarm.add("description", event.summary)
            component.add_component(alarm)
        calendar.add_component(component)
    return calendar.to_ical()
