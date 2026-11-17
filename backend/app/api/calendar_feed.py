from hashlib import sha256
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request, Response

from app.calendar.events import collect_events
from app.calendar.ics import render_calendar
from app.db.session import Database
from app.security.sharing import CALENDAR_SCOPE, valid_share

router = APIRouter()


def not_found() -> HTTPException:
    return HTTPException(404, "日历订阅不存在或已失效。", headers={"Cache-Control": "no-store"})


@router.api_route("/cal/{token}.ics", methods=["GET", "HEAD"], include_in_schema=False)
def calendar_feed(token: str, request: Request, db: Database) -> Response:
    # Read authorization and event sources from the same SQLite snapshot.
    db.connection().exec_driver_sql("BEGIN")
    if not valid_share(db, token, CALENDAR_SCOPE):
        raise not_found()

    settings = request.app.state.settings
    zone = ZoneInfo(settings.timezone)
    events = collect_events(db, zone)
    db.rollback()
    content = render_calendar(events, settings.public_domain, zone)
    etag = '"' + sha256(content).hexdigest() + '"'
    headers = {"ETag": etag, "Cache-Control": "private, no-cache, must-revalidate", "Referrer-Policy": "no-referrer"}
    offered = {tag.strip().removeprefix("W/") for tag in request.headers.get("If-None-Match", "").split(",")}
    if "*" in offered or etag in offered:
        return Response(status_code=304, headers=headers)
    headers["Content-Length"] = str(len(content))
    headers["Content-Disposition"] = 'inline; filename="preg-companion.ics"'
    return Response(content if request.method == "GET" else b"", media_type="text/calendar", headers=headers)
