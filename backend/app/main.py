from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.calendar_feed import router as calendar_router
from app.api.checkups import router as checkups_router
from app.api.daily import router as daily_router
from app.api.health import router as health_router
from app.api.milestones import router as milestones_router
from app.api.notes_questions import router as notes_questions_router
from app.api.pregnancy import router as pregnancy_router
from app.api.share_tokens import router as subscriptions_router
from app.api.supplements import router as supplements_router
from app.api.trends import router as trends_router
from app.api.viewer import PRIVATE_HEADERS, router as viewer_router
from app.config import Settings
from app.db.connection import create_sqlite_engine
from app.db.session import Database
from app.security.recorder import LoginLimiter
from app.security.sharing import VIEW_SCOPE, ShareRevocations, valid_share


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    dist = settings.frontend_dist

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_sqlite_engine(settings.database_path)
        app.state.engine = engine
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="孕期陪伴", version="0.5.1", lifespan=lifespan)
    app.state.settings = settings
    app.state.login_limiter = LoginLimiter()
    app.state.share_revocations = ShareRevocations()
    for router in (
        health_router, auth_router, pregnancy_router, checkups_router, milestones_router,
        subscriptions_router, daily_router, supplements_router, notes_questions_router, trends_router, viewer_router,
    ):
        app.include_router(router, prefix="/api")
    app.include_router(calendar_router)

    @app.middleware("http")
    async def protect_api(request: Request, call_next):
        is_api = request.url.path.startswith("/api/")
        if is_api and request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("X-Preg-Request") != "1":
                return JSONResponse(
                    {"detail": "请求来源无效。"}, status_code=403,
                    headers={"Cache-Control": "no-store"},
                )
        response = await call_next(request)
        if is_api:
            response.headers["Cache-Control"] = "no-store"
        if request.url.path.startswith("/api/view/"):
            response.headers.update(PRIVATE_HEADERS)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": error["loc"], "msg": error["msg"].removeprefix("Value error, ")}
            for error in exc.errors()
        ]
        return JSONResponse({"detail": errors}, status_code=422)

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/", include_in_schema=False)
    def recorder() -> FileResponse:
        page = dist / "index.html"
        if not page.is_file():
            raise HTTPException(404, "Frontend build not found")
        return FileResponse(page, headers={"Cache-Control": "no-store"})

    @app.api_route("/view/{token}", methods=["GET", "HEAD"], include_in_schema=False)
    def viewer(token: str, db: Database) -> FileResponse:
        page = dist / "viewer.html"
        if not page.is_file():
            raise HTTPException(404, "Frontend build not found")
        return FileResponse(
            page,
            status_code=200 if valid_share(db, token, VIEW_SCOPE) else 404,
            headers=PRIVATE_HEADERS,
        )

    return app


app = create_app()
