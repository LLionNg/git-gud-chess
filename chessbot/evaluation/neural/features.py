"""Feature extraction for the neural evaluator.

The reference solution fed its network ~224 Stockfish-internal evaluation terms
that we cannot reproduce without its private C++. This module keeps the *same
feature layout* it used — colour-paired features, then shared "common" features,
then a side-to-move flag — over a compact, self-contained feature set. Weights
trained (phase 2) on these features drive :class:`AunnNetwork`.
"""

from __future__ import annotations

import chess
import numpy as np

from chessbot.evaluation.terms.material import _EG_WHITE, _MG_WHITE  # reuse merged tables
from chessbot.evaluation.terms.mobility import pawn_attacks
from chessbot.evaluation.terms.pawn_structure import _ADJACENT_FILES, _FRONT_SPAN, _PASSED_MASK

# One value per side; the extractor emits white then black for each (interleaved).
PAIRED_FEATURES = (
    "pawns", "knights", "bishops", "rooks", "queens",
    "psqt_mg", "psqt_eg", "mobility", "king_shield", "king_attackers",
    "passed", "isolated", "doubled", "bishop_pair", "rook_open",
)
COMMON_FEATURES = ("phase", "pawn_total")

FEATURE_NAMES: list[str] = []
for _name in PAIRED_FEATURES:
    FEATURE_NAMES.append(f"{_name}_0")  # white
    FEATURE_NAMES.append(f"{_name}_1")  # black
FEATURE_NAMES.extend(COMMON_FEATURES)
FEATURE_NAMES.append("side_to_move")

NUM_FEATURES = len(FEATURE_NAMES)
WHITE_IDX = [FEATURE_NAMES.index(f"{n}_0") for n in PAIRED_FEATURES]
BLACK_IDX = [FEATURE_NAMES.index(f"{n}_1") for n in PAIRED_FEATURES]
COMMON_IDX = [FEATURE_NAMES.index(n) for n in COMMON_FEATURES]
STM_IDX = FEATURE_NAMES.index("side_to_move")

_ATTACK_WEIGHT = {chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 5}


def _side_features(board: chess.Board, color: chess.Color) -> list[float]:
    """Compute the paired feature block for one colour."""
    occ = board.occupied_co[color]
    pawns = board.pawns & occ
    enemy_pawns = board.pawns & board.occupied_co[not color]

    counts = [
        chess.popcount(pawns),
        chess.popcount(board.knights & occ),
        chess.popcount(board.bishops & occ),
        chess.popcount(board.rooks & occ),
        chess.popcount(board.queens & occ),
    ]

    mg_table, eg_table = _MG_WHITE, _EG_WHITE
    psqt_mg = psqt_eg = 0
    for pt in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING):
        for sq in chess.scan_forward(board.pieces_mask(pt, color)):
            # Read every piece from White's frame so both colours share a scale.
            index = sq if color == chess.WHITE else sq ^ 56
            psqt_mg += mg_table[pt][index]
            psqt_eg += eg_table[pt][index]

    area = ~occ & ~pawn_attacks(enemy_pawns, not color)
    mob = sum((board.attacks_mask(sq) & area).bit_count()
              for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
              for sq in board.pieces(pt, color))

    king_sq = board.king(color)
    shield = attackers = 0
    if king_sq is not None:
        file = chess.square_file(king_sq)
        files = chess.BB_FILES[file] | _ADJACENT_FILES[file]
        shield = chess.popcount(pawns & files & board.attacks_mask(king_sq))
        ring = board.attacks_mask(king_sq)
        for pt, _w in _ATTACK_WEIGHT.items():
            for sq in board.pieces(pt, not color):
                if board.attacks_mask(sq) & ring:
                    attackers += 1

    passed = isolated = doubled = 0
    for sq in chess.scan_forward(pawns):
        f = chess.square_file(sq)
        if not pawns & _ADJACENT_FILES[f]:
            isolated += 1
        if pawns & _FRONT_SPAN[color][sq]:
            doubled += 1
        if not enemy_pawns & _PASSED_MASK[color][sq]:
            passed += 1

    bishop_pair = 1.0 if counts[2] >= 2 else 0.0
    rook_open = sum(1 for sq in board.pieces(chess.ROOK, color)
                    if not board.pawns & chess.BB_FILES[chess.square_file(sq)])
    return [*counts, psqt_mg / 100.0, psqt_eg / 100.0, float(mob), float(shield),
            float(attackers), float(passed), float(isolated), float(doubled),
            bishop_pair, float(rook_open)]


def extract_features(board: chess.Board) -> np.ndarray:
    """Return the feature vector for ``board`` in :data:`FEATURE_NAMES` order."""
    vector = np.empty(NUM_FEATURES, dtype=np.float32)
    white = _side_features(board, chess.WHITE)
    black = _side_features(board, chess.BLACK)
    for i, (w, b) in enumerate(zip(white, black)):
        vector[2 * i] = w
        vector[2 * i + 1] = b
    phase = (chess.popcount(board.knights) + chess.popcount(board.bishops)
             + 2 * chess.popcount(board.rooks) + 4 * chess.popcount(board.queens))
    vector[COMMON_IDX[0]] = phase
    vector[COMMON_IDX[1]] = chess.popcount(board.pawns)
    vector[STM_IDX] = 0.0 if board.turn == chess.WHITE else 1.0
    return vector
