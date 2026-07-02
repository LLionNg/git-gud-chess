"""Evaluation providers and a factory that selects one from configuration."""

from __future__ import annotations

import sys

from chessbot.config import EvaluationConfig, EvaluatorType
from chessbot.evaluation.base import Evaluator
from chessbot.evaluation.classical import ClassicalEvaluator


def build_evaluator(config: EvaluationConfig) -> Evaluator:
    """Instantiate the evaluator named by ``config.provider``.

    The neural provider needs trained weights; without them we fall back to the
    classical evaluator so the engine always has a working evaluation.
    """
    if config.provider is EvaluatorType.NEURAL and config.weights_path:
        # Imported lazily so the classical engine never requires numpy weights.
        from chessbot.evaluation.neural.evaluator import NeuralEvaluator

        return NeuralEvaluator(config)
    if config.provider is EvaluatorType.NEURAL:
        print("info string neural weights not set; using classical evaluator", file=sys.stderr)
    return ClassicalEvaluator(config)


__all__ = ["Evaluator", "ClassicalEvaluator", "build_evaluator"]
