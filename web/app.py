from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from web.api.routes import router
from web.config import WebConfig
from web.services.engine import EngineService

STATIC_DIR = Path(__file__).parent / "static"

# Code assets must revalidate on every load (cheap 304s); without this,
# browsers heuristically cache them and serve stale JS for days after a
# deploy. Images and sounds keep the default caching.
REVALIDATE_SUFFIXES = (".html", ".js", ".css")


def create_app(config: WebConfig | None = None) -> FastAPI:
    config = config or WebConfig()
    app = FastAPI(title="chessbot")
    # Built eagerly (not in a lifespan hook) so the app also works on
    # serverless hosts that may not run ASGI startup events.
    app.state.config = config
    app.state.engine = EngineService(config)
    app.include_router(router, prefix="/api")
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    @app.middleware("http")
    async def revalidate_code_assets(request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.endswith("/") or path.endswith(REVALIDATE_SUFFIXES):
            response.headers.setdefault("Cache-Control", "no-cache")
        return response

    return app


app = create_app()
