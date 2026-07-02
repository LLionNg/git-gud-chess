"""Move ordering: try the moves most likely to cause a cutoff first.

Good ordering is what makes alpha-beta fast. Priority is: the hash move, then
winning captures/promotions (MVV-LVA), then the two killer moves, then quiet
moves ranked by the history heuristic.
"""

from __future__ import annotations

from typing import Optional

import chess

# Values used only for ordering captures (most-valuable-victim, least-valuable-attacker).
_VALUE: dict[int, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20_000,
}

_TT_BONUS = 30_000_000
_CAPTURE_BASE = 20_000_000
_PROMO_BASE = 10_000_000
_KILLER_1 = 9_000_000
_KILLER_2 = 8_000_000


def _victim_value(board: chess.Board, move: chess.Move) -> int:
    if board.is_en_passant(move):
        return _VALUE[chess.PAWN]
    victim = board.piece_type_at(move.to_square)
    return _VALUE[victim] if victim else 0


def score_move(
    board: chess.Board,
    move: chess.Move,
    tt_move: Optional[chess.Move],
    killers: tuple[Optional[chess.Move], Optional[chess.Move]],
    history: dict[tuple[int, int, int], int],
) -> int:
    """Return a sort key; higher is searched earlier."""
    if move == tt_move:
        return _TT_BONUS

    score = 0
    is_capture = board.is_capture(move)
    if is_capture:
        attacker = board.piece_type_at(move.from_square) or chess.PAWN
        score += _CAPTURE_BASE + 10 * _victim_value(board, move) - _VALUE[attacker]
    if move.promotion:
        score += _PROMO_BASE + _VALUE[move.promotion]
    if is_capture or move.promotion:
        return score

    if move == killers[0]:
        return _KILLER_1
    if move == killers[1]:
        return _KILLER_2
    # Quiet moves: rank by how often this piece-to-square move has caused cutoffs.
    piece = board.piece_type_at(move.from_square) or chess.PAWN
    return history.get((board.turn, piece, move.to_square), 0)


def order_moves(
    board: chess.Board,
    moves: list[chess.Move],
    tt_move: Optional[chess.Move],
    killers: tuple[Optional[chess.Move], Optional[chess.Move]],
    history: dict[tuple[int, int, int], int],
) -> list[chess.Move]:
    """Return ``moves`` sorted best-first by :func:`score_move`."""
    return sorted(moves, key=lambda m: score_move(board, m, tt_move, killers, history), reverse=True)
