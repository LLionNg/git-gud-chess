"""Transposition table caching search results keyed by position.

Keys are python-chess transposition keys (position + side to move + castling +
en passant). Mate scores are stored relative to the node so they stay correct
when the same position is reached at a different distance from the root.
"""

from __future__ import annotations

from typing import Hashable, Optional

import chess

from chessbot.core.types import MATE_THRESHOLD

EXACT = 0  # Score is exact.
LOWER = 1  # Score is a lower bound (a beta cutoff happened).
UPPER = 2  # Score is an upper bound (no move beat alpha).


class TTEntry:
    """One stored position result."""

    __slots__ = ("depth", "score", "flag", "move")

    def __init__(self, depth: int, score: int, flag: int, move: Optional[chess.Move]) -> None:
        self.depth = depth
        self.score = score
        self.flag = flag
        self.move = move


class TranspositionTable:
    """Insertion-ordered dict with a size cap and FIFO eviction when full."""

    def __init__(self, size_mb: int = 64) -> None:
        # Roughly size the table; entries are small Python objects, so this is an
        # order-of-magnitude bound rather than an exact byte count.
        self._max_entries = max(1, size_mb) * 32_768
        self._table: dict[Hashable, TTEntry] = {}

    def clear(self) -> None:
        self._table.clear()

    def probe(self, key: Hashable, ply: int) -> Optional[TTEntry]:
        """Return the stored entry with its score de-adjusted for the current ply."""
        entry = self._table.get(key)
        if entry is None:
            return None
        score = entry.score
        if score >= MATE_THRESHOLD:
            score -= ply
        elif score <= -MATE_THRESHOLD:
            score += ply
        return TTEntry(entry.depth, score, entry.flag, entry.move)

    def store(self, key: Hashable, depth: int, score: int, flag: int,
              move: Optional[chess.Move], ply: int) -> None:
        if score >= MATE_THRESHOLD:
            score += ply
        elif score <= -MATE_THRESHOLD:
            score -= ply
        existing = self._table.get(key)
        # Prefer deeper results; shallow re-stores of the same position are dropped.
        if existing is not None and existing.depth > depth:
            return
        if existing is None and len(self._table) >= self._max_entries:
            self._table.pop(next(iter(self._table)))
        self._table[key] = TTEntry(depth, score, flag, move)
