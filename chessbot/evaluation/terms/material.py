"""Material, piece placement and game phase in a single sweep over the pieces.

For speed the base value and placement bonus are pre-merged into one table per
colour (White's is pre-flipped), so scoring a piece is a single array lookup.
"""

from __future__ import annotations

import chess

from chessbot.evaluation import tables

_PIECE_TYPES = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING)

# Merged value+placement tables: MG/EG, White (flipped) and Black (direct).
_MG_WHITE: dict[int, tuple[int, ...]] = {}
_EG_WHITE: dict[int, tuple[int, ...]] = {}
_MG_BLACK: dict[int, tuple[int, ...]] = {}
_EG_BLACK: dict[int, tuple[int, ...]] = {}
for _pt in _PIECE_TYPES:
    _mg_v, _eg_v = tables.MG_PIECE_VALUE[_pt], tables.EG_PIECE_VALUE[_pt]
    _mg_psqt, _eg_psqt = tables.MG_PSQT[_pt], tables.EG_PSQT[_pt]
    _MG_WHITE[_pt] = tuple(_mg_v + _mg_psqt[sq ^ 56] for sq in range(64))
    _EG_WHITE[_pt] = tuple(_eg_v + _eg_psqt[sq ^ 56] for sq in range(64))
    _MG_BLACK[_pt] = tuple(_mg_v + _mg_psqt[sq] for sq in range(64))
    _EG_BLACK[_pt] = tuple(_eg_v + _eg_psqt[sq] for sq in range(64))


def material_psqt_phase(board: chess.Board) -> tuple[int, int, int]:
    """Return ``(mg, eg, phase)`` from White's perspective."""
    mg = 0
    eg = 0
    scan = chess.scan_forward
    for pt in _PIECE_TYPES:
        pieces = board.pieces_mask(pt, chess.WHITE)
        mg_w, eg_w = _MG_WHITE[pt], _EG_WHITE[pt]
        for sq in scan(pieces):
            mg += mg_w[sq]
            eg += eg_w[sq]
        black_pieces = board.pieces_mask(pt, chess.BLACK)
        mg_b, eg_b = _MG_BLACK[pt], _EG_BLACK[pt]
        for sq in scan(black_pieces):
            mg -= mg_b[sq]
            eg -= eg_b[sq]

    # Phase counts non-pawn material (N/B=1, R=2, Q=4) straight from the bitboards.
    phase = (chess.popcount(board.knights) + chess.popcount(board.bishops)
             + 2 * chess.popcount(board.rooks) + 4 * chess.popcount(board.queens))
    return mg, eg, phase
