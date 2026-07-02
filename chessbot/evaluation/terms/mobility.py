"""Piece mobility: how many safe squares each minor/major piece can reach."""

from __future__ import annotations

import chess

# Centipawns awarded per reachable square, tuned low so mobility refines rather
# than dominates the material and placement terms.
_MG_WEIGHT: dict[int, int] = {chess.KNIGHT: 4, chess.BISHOP: 5, chess.ROOK: 3, chess.QUEEN: 2}
_EG_WEIGHT: dict[int, int] = {chess.KNIGHT: 4, chess.BISHOP: 5, chess.ROOK: 4, chess.QUEEN: 4}


def pawn_attacks(pawns: int, color: chess.Color) -> int:
    """Bitboard of every square attacked by ``color``'s pawns."""
    if color == chess.WHITE:
        return ((pawns & ~chess.BB_FILE_A) << 7) | ((pawns & ~chess.BB_FILE_H) << 9)
    return ((pawns & ~chess.BB_FILE_A) >> 9) | ((pawns & ~chess.BB_FILE_H) >> 7)


def mobility(board: chess.Board, piece_attacks: dict[int, int]) -> tuple[int, int]:
    """Return ``(mg, eg)`` mobility from White's perspective.

    ``piece_attacks`` maps each minor/major piece square to its attack bitboard,
    computed once by the caller and shared with the king-safety term.
    """
    mg = 0
    eg = 0
    for color in (chess.WHITE, chess.BLACK):
        own = board.occupied_co[color]
        # Squares controlled by an enemy pawn are unsafe and excluded from mobility.
        enemy_pawns = board.pawns & board.occupied_co[not color]
        area = ~own & ~pawn_attacks(enemy_pawns, not color)
        sign = 1 if color == chess.WHITE else -1
        for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
            for square in board.pieces(piece_type, color):
                moves = (piece_attacks[square] & area).bit_count()
                mg += sign * moves * _MG_WEIGHT[piece_type]
                eg += sign * moves * _EG_WEIGHT[piece_type]
    return mg, eg
