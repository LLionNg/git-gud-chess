"""Hand-crafted tapered evaluation, the default scoring provider.

This mirrors the feature families of the reference solution (material/placement,
mobility, king safety, pawn structure, piece bonuses) as an interpretable
hand-crafted evaluation rather than the neural blend it eventually learned.
"""

from __future__ import annotations

import chess

from chessbot.config import EvaluationConfig
from chessbot.core.types import PHASE_MAX
from chessbot.evaluation.base import Evaluator
from chessbot.evaluation.terms.king_safety import king_safety
from chessbot.evaluation.terms.material import material_psqt_phase
from chessbot.evaluation.terms.mobility import mobility
from chessbot.evaluation.terms.pawn_structure import pawn_structure
from chessbot.evaluation.terms.pieces import pieces


class ClassicalEvaluator(Evaluator):
    """Sums weighted terms and blends middlegame/endgame scores by material phase."""

    name = "classical"

    def __init__(self, config: EvaluationConfig | None = None) -> None:
        self._tempo = (config or EvaluationConfig()).tempo

    def evaluate(self, board: chess.Board) -> int:
        mg, eg, phase = material_psqt_phase(board)

        # Each minor/major piece's attack set is computed once here and shared by
        # the mobility and king-safety terms, halving the slider-attack work.
        piece_attacks = {
            sq: board.attacks_mask(sq)
            for sq in chess.scan_forward(board.knights | board.bishops | board.rooks | board.queens)
        }
        mob_mg, mob_eg = mobility(board, piece_attacks)
        ks_mg, ks_eg = king_safety(board, piece_attacks)
        pawn_mg, pawn_eg = pawn_structure(board)
        pc_mg, pc_eg = pieces(board)
        mg += mob_mg + ks_mg + pawn_mg + pc_mg
        eg += mob_eg + ks_eg + pawn_eg + pc_eg

        # Tapered eval: interpolate between middlegame and endgame by how much
        # non-pawn material remains, then flip to the side-to-move's perspective.
        phase = min(phase, PHASE_MAX)
        score = (mg * phase + eg * (PHASE_MAX - phase)) // PHASE_MAX
        score = score if board.turn == chess.WHITE else -score
        return score + self._tempo
