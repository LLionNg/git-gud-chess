"""King safety: pawn shelter plus pressure from enemy pieces on the king ring."""

from __future__ import annotations

import chess

# Attack weight per enemy piece type that bears on the squares around the king.
_ATTACK_WEIGHT: dict[int, int] = {chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 5}

_SHIELD_BONUS = 9  # Centipawns per friendly pawn sheltering the king (middlegame).

_ADJACENT_FILES: list[int] = []
for _f in range(8):
    mask = 0
    if _f > 0:
        mask |= chess.BB_FILES[_f - 1]
    if _f < 7:
        mask |= chess.BB_FILES[_f + 1]
    _ADJACENT_FILES.append(mask)


def _shield_zone(king_square: int, color: chess.Color) -> int:
    """Bitboard of the up-to-two ranks in front of the king across three files."""
    file = chess.square_file(king_square)
    rank = chess.square_rank(king_square)
    files = chess.BB_FILES[file] | _ADJACENT_FILES[file]
    ranks = 0
    steps = (rank + 1, rank + 2) if color == chess.WHITE else (rank - 1, rank - 2)
    for r in steps:
        if 0 <= r <= 7:
            ranks |= chess.BB_RANKS[r]
    return files & ranks


def king_safety(board: chess.Board, piece_attacks: dict[int, int]) -> tuple[int, int]:
    """Return ``(mg, eg)`` king-safety score from White's perspective.

    ``piece_attacks`` maps each minor/major piece square to its attack bitboard,
    shared with the mobility term to avoid recomputing attacks.
    """
    mg = 0
    for color in (chess.WHITE, chess.BLACK):
        king_square = board.king(color)
        if king_square is None:
            continue
        sign = 1 if color == chess.WHITE else -1
        own_pawns = board.pawns & board.occupied_co[color]
        shield = (own_pawns & _shield_zone(king_square, color)).bit_count()
        mg += sign * shield * _SHIELD_BONUS

        # King ring is the squares the king attacks; pressure grows with the number
        # of distinct attackers, so weight the unit sum by the attacker count.
        ring = board.attacks_mask(king_square)
        units = 0
        attackers = 0
        for piece_type, weight in _ATTACK_WEIGHT.items():
            for square in board.pieces(piece_type, not color):
                overlap = (piece_attacks[square] & ring).bit_count()
                if overlap:
                    attackers += 1
                    units += weight * overlap
        # Cap the penalty so a single term cannot dominate the whole evaluation.
        mg -= sign * min((units * attackers) // 2, 500)
    # King safety is a middlegame concern; the endgame contribution is left to PSQT.
    return mg, 0
