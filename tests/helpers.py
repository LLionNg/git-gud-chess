"""Test-only helpers, independent of the engine under test."""

from __future__ import annotations

import chess


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
