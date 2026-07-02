"""Standard-UCI bridge to the native C++ engine (the replicated Lgeu fork).

The fork speaks a shortened UCI dialect (``po`` instead of ``position``,
``wtm``/``btm`` instead of ``wtime``/``btime``, ``pd`` instead of ``ponder``), so
it will not work in a normal chess GUI directly. This adapter presents a standard
UCI interface on stdin/stdout and translates each line to the fork's dialect -
the same subprocess-wrapper idea as the reference's ``main.py``, but GUI-ready.

By default it selects the trained AUNN evaluation (``Use NNUE=false``), which is
the actual competition solution; set ``CHESSBOT_NATIVE_NNUE=1`` to use NNUE.

Run:  python -m chessbot.native            (auto-locates kaggle-stockfish/stockfish_play.exe)
      CHESSBOT_ENGINE=/path/to/engine python -m chessbot.native
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

# Standard-UCI token -> fork token. Only command words are mapped; numeric values
# never collide with these keys, so a flat per-token rewrite is safe.
_TOKEN_MAP = {"wtime": "wtm", "btime": "btm", "ponder": "pd"}


def _default_engine_path() -> Optional[Path]:
    env = os.environ.get("CHESSBOT_ENGINE")
    if env:
        return Path(env)
    root = Path(__file__).resolve().parents[2]  # repo root
    for name in ("stockfish_play.exe", "stockfish_play", "stockfish.exe"):
        candidate = root / "kaggle-stockfish" / name
        if candidate.exists():
            return candidate
    return None


def translate(line: str) -> str:
    """Rewrite one standard-UCI line into the fork's shortened dialect."""
    parts = line.split()
    if not parts:
        return line
    if parts[0] == "position":
        return "po " + " ".join(parts[1:])
    if parts[0] == "go":
        return "go " + " ".join(_TOKEN_MAP.get(tok, tok) for tok in parts[1:])
    return line


class UciBridge:
    """Drives the native engine, translating standard UCI to/from its dialect."""

    def __init__(self, engine_path: Path, use_nnue: bool = False) -> None:
        self._engine = subprocess.Popen(
            [str(engine_path)], cwd=str(engine_path.parent),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
        )
        # Select the AUNN (classical) evaluation - the trained competition solution.
        self._send(f"setoption name Use NNUE value {'true' if use_nnue else 'false'}")

    def _send(self, command: str) -> None:
        assert self._engine.stdin is not None
        self._engine.stdin.write(command + "\n")
        self._engine.stdin.flush()

    def _pump_engine_output(self) -> None:
        """Forward engine output to our stdout, relabelling only the id name."""
        assert self._engine.stdout is not None
        for line in self._engine.stdout:
            line = line.rstrip("\n")
            if line.startswith("id name "):
                line = "id name chessbot-native (Lgeu Stockfish fork)"
            sys.stdout.write(line + "\n")
            sys.stdout.flush()

    def run(self, stream=sys.stdin) -> None:
        reader = threading.Thread(target=self._pump_engine_output, daemon=True)
        reader.start()
        for raw in stream:
            command = raw.strip()
            if not command:
                continue
            self._send(translate(command))
            if command == "quit":
                break
        self._engine.wait()


def main() -> None:
    engine_path = _default_engine_path()
    if engine_path is None or not engine_path.exists():
        sys.stderr.write(
            "native engine not found. Build it first:\n"
            "  export PATH=\"/c/mingw64/bin:$PATH\"; bash pipeline/setup_engine.sh\n"
            "or set CHESSBOT_ENGINE=/path/to/engine\n")
        raise SystemExit(1)
    use_nnue = os.environ.get("CHESSBOT_NATIVE_NNUE", "0") == "1"
    UciBridge(engine_path, use_nnue=use_nnue).run()


if __name__ == "__main__":
    main()
