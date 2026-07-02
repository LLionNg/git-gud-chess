"""Neural evaluation provider wrapping the AUNN network.

Loads phase-2 trained weights and scores positions by extracting features and
running :class:`AunnNetwork`. Without weights the provider is not useful, so the
factory falls back to the classical evaluator (see ``build_evaluator``).
"""

from __future__ import annotations

import chess

from chessbot.config import EvaluationConfig
from chessbot.evaluation.base import Evaluator
from chessbot.evaluation.neural.features import extract_features
from chessbot.evaluation.neural.network import AunnNetwork


class NeuralEvaluator(Evaluator):
    """Scores positions with the AUNN network over extracted features."""

    name = "neural"

    def __init__(self, config: EvaluationConfig) -> None:
        if not config.weights_path:
            raise ValueError("neural evaluator requires evaluation.weights_path")
        self._network = AunnNetwork.load(config.weights_path)

    def evaluate(self, board: chess.Board) -> int:
        return int(round(self._network.forward(extract_features(board))))
