"""High-level engine facade tying configuration, evaluation and search together.

This is the clean programmatic API; the UCI layer is a thin adapter over it.
"""

from __future__ import annotations

from typing import Iterable, Optional

import chess

from chessbot.config import EngineConfig, EvaluatorType
from chessbot.evaluation import build_evaluator
from chessbot.search import SearchLimits, SearchResult, Searcher
from chessbot.search.searcher import InfoCallback


class Engine:
    """Owns the current board and drives searches over it."""

    def __init__(self, config: Optional[EngineConfig] = None) -> None:
        self.config = config or EngineConfig()
        self._evaluator = build_evaluator(self.config.evaluation)
        self.searcher = Searcher(self.config, self._evaluator)
        self.board = chess.Board()

    def new_game(self) -> None:
        self.board.reset()
        self.searcher.new_game()

    def set_position(self, fen: Optional[str] = None,
                     moves: Optional[Iterable[str]] = None) -> None:
        """Set the root position from a FEN (or the start) plus a list of UCI moves."""
        self.board = chess.Board() if fen is None else chess.Board(fen)
        for uci in moves or []:
            self.board.push(chess.Move.from_uci(uci))

    def search(self, limits: SearchLimits, info: Optional[InfoCallback] = None) -> SearchResult:
        return self.searcher.search(self.board, limits, info)

    def stop(self) -> None:
        self.searcher.stop()

    def set_option(self, name: str, value: str) -> None:
        """Apply a UCI ``setoption``; rebuilds the affected component if needed."""
        key = name.strip().lower()
        if key == "hash":
            self.config.search.tt_size_mb = int(value)
            self.searcher = Searcher(self.config, self._evaluator)
        elif key == "evaluator":
            self.config.evaluation.provider = EvaluatorType(value.strip().lower())
            self._evaluator = build_evaluator(self.config.evaluation)
            self.searcher = Searcher(self.config, self._evaluator)
        elif key == "move overhead":
            self.config.search.move_overhead_ms = int(value)
