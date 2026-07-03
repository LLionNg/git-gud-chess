"""Neural (AUNN) evaluation: feature extraction, network, and provider.

:class:`~chessbot.evaluation.neural.network.AunnNetwork` is a small, float,
trainable network used as the engine's optional neural evaluator.
"""

from __future__ import annotations

from chessbot.evaluation.neural.network import AunnNetwork

__all__ = ["AunnNetwork"]
