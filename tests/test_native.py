"""Standard-UCI -> fork-dialect translation for the native bridge."""

from __future__ import annotations

import pytest

from chessbot.native.bridge import translate

CASES = [
    ("position startpos moves e2e4 c7c5", "po startpos moves e2e4 c7c5"),
    ("position fen 8/8/8/4k3/8/8/2Q5/4K3 w - - 0 1 moves c2c7",
     "po fen 8/8/8/4k3/8/8/2Q5/4K3 w - - 0 1 moves c2c7"),
    ("go wtime 300000 btime 300000 winc 2000 binc 2000",
     "go wtm 300000 btm 300000 winc 2000 binc 2000"),
    ("go depth 12", "go depth 12"),
    ("go movetime 500", "go movetime 500"),
    ("go infinite ponder", "go infinite pd"),
    # Non-position/go lines pass through untouched.
    ("uci", "uci"),
    ("isready", "isready"),
    ("setoption name Hash value 16", "setoption name Hash value 16"),
    ("ucinewgame", "ucinewgame"),
    ("stop", "stop"),
    ("quit", "quit"),
]


@pytest.mark.parametrize("standard,dialect", CASES)
def test_translate(standard: str, dialect: str) -> None:
    assert translate(standard) == dialect


def test_empty_line_passthrough() -> None:
    assert translate("") == ""
