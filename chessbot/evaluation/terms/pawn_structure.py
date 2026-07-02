"""Pawn structure: passed, isolated and doubled pawns via precomputed masks."""

from __future__ import annotations

import chess

# Passed-pawn bonus indexed by the pawn's rank relative to its own side
# (0 = home rank, 6 = one step from promotion). Endgame values are larger
# because passers decide pawn endings.
_PASSED_MG = (0, 5, 10, 20, 35, 60, 100, 0)
_PASSED_EG = (0, 15, 25, 40, 65, 100, 160, 0)

_ISOLATED_MG, _ISOLATED_EG = -12, -8
_DOUBLED_MG, _DOUBLED_EG = -10, -16

# Bitboard of the two files adjacent to each file, used for isolated/passed tests.
_ADJACENT_FILES: list[int] = []
for _f in range(8):
    mask = 0
    if _f > 0:
        mask |= chess.BB_FILES[_f - 1]
    if _f < 7:
        mask |= chess.BB_FILES[_f + 1]
    _ADJACENT_FILES.append(mask)

# For each colour and square: squares ahead on the same file (front span) and the
# span across own+adjacent files that must be pawn-free for a passer.
_FRONT_SPAN: dict[chess.Color, list[int]] = {chess.WHITE: [], chess.BLACK: []}
_PASSED_MASK: dict[chess.Color, list[int]] = {chess.WHITE: [], chess.BLACK: []}
for _sq in range(64):
    _f = chess.square_file(_sq)
    _r = chess.square_rank(_sq)
    _white_front = 0
    _black_front = 0
    for _rr in range(_r + 1, 8):
        _white_front |= chess.BB_RANKS[_rr]
    for _rr in range(0, _r):
        _black_front |= chess.BB_RANKS[_rr]
    _FRONT_SPAN[chess.WHITE].append(_white_front & chess.BB_FILES[_f])
    _FRONT_SPAN[chess.BLACK].append(_black_front & chess.BB_FILES[_f])
    _files = chess.BB_FILES[_f] | _ADJACENT_FILES[_f]
    _PASSED_MASK[chess.WHITE].append(_white_front & _files)
    _PASSED_MASK[chess.BLACK].append(_black_front & _files)


def pawn_structure(board: chess.Board) -> tuple[int, int]:
    """Return ``(mg, eg)`` pawn-structure score from White's perspective."""
    mg = 0
    eg = 0
    for color in (chess.WHITE, chess.BLACK):
        own_pawns = board.pawns & board.occupied_co[color]
        enemy_pawns = board.pawns & board.occupied_co[not color]
        sign = 1 if color == chess.WHITE else -1
        for square in chess.scan_forward(own_pawns):
            file = chess.square_file(square)
            if not own_pawns & _ADJACENT_FILES[file]:
                mg += sign * _ISOLATED_MG
                eg += sign * _ISOLATED_EG
            # A pawn with a friendly pawn ahead on its file is doubled.
            if own_pawns & _FRONT_SPAN[color][square]:
                mg += sign * _DOUBLED_MG
                eg += sign * _DOUBLED_EG
            if not enemy_pawns & _PASSED_MASK[color][square]:
                rank = chess.square_rank(square)
                relative = rank if color == chess.WHITE else 7 - rank
                mg += sign * _PASSED_MG[relative]
                eg += sign * _PASSED_EG[relative]
    return mg, eg
