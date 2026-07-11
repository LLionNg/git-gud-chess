"""Vercel serverless entrypoint: one ASGI app serving the API and the board.

Vercel routes every request here (see vercel.json); FastAPI serves the static
frontend and the stateless /api endpoints, with the engine running in-process.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from web.app import create_app  # noqa: E402
from web.config import WebConfig  # noqa: E402


def _weights() -> str | None:
    configured = os.environ.get("CHESSBOT_WEIGHTS")
    if configured:
        return configured
    demo = ROOT / "demo.npz"
    return str(demo) if demo.exists() else None


app = create_app(WebConfig(
    weights=_weights(),
    movetime_ms=int(os.environ.get("CHESSBOT_MOVETIME_MS", "800")),
))
