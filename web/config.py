import sys

from pydantic import BaseModel


class WebConfig(BaseModel):
    engine_command: list[str] = [sys.executable, "-m", "chessbot"]
    weights: str | None = None
    movetime_ms: int = 800
    host: str = "127.0.0.1"
    port: int = 13501
