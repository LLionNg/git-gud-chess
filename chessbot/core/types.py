"""Score constants and mate-aware helpers shared across search and evaluation."""

from __future__ import annotations

import chess

# Evaluation is expressed in centipawns from the side-to-move's perspective.
INFINITY: int = 32_000

# A checkmate is scored just below INFINITY; the ply distance is subtracted so
# that shorter mates outrank longer ones.
MATE_SCORE: int = 31_000

# Any score at least this large must involve a forced mate rather than material.
MATE_THRESHOLD: int = MATE_SCORE - 1_000

DRAW_SCORE: int = 0

# Longest mate the engine will represent; also bounds the mate-score window.
MAX_PLY: int = 246


def is_mate_score(score: int) -> bool:
    """True when the score encodes a forced mate for or against the side to move."""
    return abs(score) >= MATE_THRESHOLD


def mate_in_moves(score: int) -> int:
    """Convert a mate score into full moves (positive = we mate, negative = we are mated)."""
    plies = MATE_SCORE - abs(score)
    moves = (plies + 1) // 2
    return moves if score > 0 else -moves


# python-chess piece values are not used for search; these mirror the phase
# weights of Stockfish's material so the tapered evaluation matches its blend.
GAME_PHASE_INC: dict[int, int] = {
    chess.PAWN: 0,
    chess.KNIGHT: 1,
    chess.BISHOP: 1,
    chess.ROOK: 2,
    chess.QUEEN: 4,
    chess.KING: 0,
}

# Sum of GAME_PHASE_INC over the full starting position (used to interpolate).
PHASE_MAX: int = 24
