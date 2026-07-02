"""Test-only helpers, independent of the engine under test."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import chess

_NOTEBOOK = (Path(__file__).resolve().parents[1]
             / "reference" / "kaggle_solution" / "chess-065d-lr-1e-2-epoch-500.ipynb")


def load_reference():
    """Load the reference model, coefficients and feature config from notebook 065d.

    Returns ``None`` when the (large) reference notebook is absent, so tests that
    depend on it skip cleanly.
    """
    if not _NOTEBOOK.exists():
        return None
    from chessbot.evaluation.neural.quantized import QuantizedAunn, parse_params_header

    notebook = json.loads(_NOTEBOOK.read_text(encoding="utf-8"))
    cells = [c for c in notebook["cells"] if c.get("cell_type") == "code"]
    sources = ["".join(c.get("source", [])) for c in cells]
    config_cell = next(s for s in sources if "feature_names = [" in s)
    config = "feature_names = [" + config_cell.split("feature_names = [", 1)[1].split(
        "dataloader = SplitDataLoader")[0]
    ns: dict = {}
    exec(config, ns)

    text = ""
    for out in cells[6].get("outputs", []):
        if out.get("output_type") == "stream":
            text += "".join(out.get("text", []))
    params = parse_params_header(text)
    feature_to_index = {name: i for i, name in enumerate(ns["feature_names"])}
    model = QuantizedAunn.from_params(
        params, ns["white_cols"], ns["black_cols"], ns["common_cols"],
        feature_to_index, ns["replacement"])
    return {"model": model, "coefs": ns["coefs"], "feature_names": ns["feature_names"]}


def can_force_mate(board: chess.Board, plies: int) -> bool:
    """Brute-force check that the side to move forces mate within ``plies``.

    We mate in ``plies`` if some move mates immediately, or leaves the opponent
    with no reply that avoids mate in ``plies - 2``. Independent of the engine,
    so it can validate puzzle FENs.
    """
    if plies <= 0:
        return False
    for move in board.legal_moves:
        board.push(move)
        try:
            if board.is_checkmate():
                return True
            replies = list(board.legal_moves)
            if replies and all(_reply_still_loses(board, r, plies - 2) for r in replies):
                return True
        finally:
            board.pop()
    return False


def _reply_still_loses(board: chess.Board, reply: chess.Move, plies: int) -> bool:
    board.push(reply)
    try:
        return can_force_mate(board, plies)
    finally:
        board.pop()
