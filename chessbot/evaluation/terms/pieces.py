"""Minor and major piece bonuses: the bishop pair and rooks on open files."""

from __future__ import annotations

import chess

_BISHOP_PAIR_MG, _BISHOP_PAIR_EG = 22, 40
_ROOK_OPEN_MG, _ROOK_OPEN_EG = 25, 12  # No pawns of either colour on the file.
_ROOK_SEMI_MG, _ROOK_SEMI_EG = 12, 6   # No friendly pawn on the file.


def pieces(board: chess.Board) -> tuple[int, int]:
    """Return ``(mg, eg)`` piece-bonus score from White's perspective."""
    mg = 0
    eg = 0
    all_pawns = board.pawns
    for color in (chess.WHITE, chess.BLACK):
        sign = 1 if color == chess.WHITE else -1
        if (board.bishops & board.occupied_co[color]).bit_count() >= 2:
            mg += sign * _BISHOP_PAIR_MG
            eg += sign * _BISHOP_PAIR_EG
        own_pawns = all_pawns & board.occupied_co[color]
        for square in board.pieces(chess.ROOK, color):
            file_mask = chess.BB_FILES[chess.square_file(square)]
            if not all_pawns & file_mask:
                mg += sign * _ROOK_OPEN_MG
                eg += sign * _ROOK_OPEN_EG
            elif not own_pawns & file_mask:
                mg += sign * _ROOK_SEMI_MG
                eg += sign * _ROOK_SEMI_EG
    return mg, eg
