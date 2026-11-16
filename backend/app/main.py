from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    dist = settings.frontend_dist
    app = FastAPI(title="孕期陪伴", version="0.1.0")
    app.include_router(health_router, prefix="/api")

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/", include_in_schema=False)
    def recorder() -> FileResponse:
        page = dist / "index.html"
        if not page.is_file():
            raise HTTPException(404, "Frontend build not found")
        return FileResponse(page)

    @app.get("/view/{token}", include_in_schema=False)
    def viewer(token: str) -> FileResponse:
        # The shell contains no records. The summary API will validate tokens.
        page = dist / "viewer.html"
        if not page.is_file():
            raise HTTPException(404, "Frontend build not found")
        return FileResponse(
            page,
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )

    return app


app = create_app()
