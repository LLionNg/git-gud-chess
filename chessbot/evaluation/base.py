"""Base provider for evaluation.

Concrete evaluators (classical hand-crafted, or the neural AUNN port) implement
``evaluate`` and are selected through configuration, so search never depends on
how a position is scored.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import chess


class Evaluator(ABC):
    """Scores a position in centipawns from the side-to-move's perspective."""

    name: str = "base"

    @abstractmethod
    def evaluate(self, board: chess.Board) -> int:
        """Return a positive score when the side to move is better off."""
        raise NotImplementedError
