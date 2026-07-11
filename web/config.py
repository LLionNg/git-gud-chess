from pydantic import BaseModel


class WebConfig(BaseModel):
    weights: str | None = None
    movetime_ms: int = 800
    host: str = "127.0.0.1"
    port: int = 13501
