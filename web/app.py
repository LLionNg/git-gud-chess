from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from web.api.routes import router
from web.config import WebConfig
from web.services.engine import EngineService

STATIC_DIR = Path(__file__).parent / "static"


def create_app(config: WebConfig | None = None) -> FastAPI:
    config = config or WebConfig()
    app = FastAPI(title="chessbot")
    # Built eagerly (not in a lifespan hook) so the app also works on
    # serverless hosts that may not run ASGI startup events.
    app.state.config = config
    app.state.engine = EngineService(config)
    app.include_router(router, prefix="/api")
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
