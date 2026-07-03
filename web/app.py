from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from web.api.routes import router
from web.config import WebConfig
from web.services.engine import EngineService
from web.services.game import GameService

STATIC_DIR = Path(__file__).parent / "static"


def create_app(config: WebConfig | None = None) -> FastAPI:
    config = config or WebConfig()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = EngineService(config)
        engine.open()
        app.state.config = config
        app.state.engine = engine
        app.state.game = GameService()
        try:
            yield
        finally:
            engine.close()

    app = FastAPI(title="chessbot", lifespan=lifespan)
    app.include_router(router, prefix="/api")
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
