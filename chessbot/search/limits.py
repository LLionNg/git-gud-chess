"""Per-search limits (from a UCI ``go``) and the result the searcher returns."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import chess


@dataclass
class SearchLimits:
    """Constraints for a single search; unset fields mean "no limit"."""

    depth: Optional[int] = None
    movetime_ms: Optional[int] = None
    nodes: Optional[int] = None
    infinite: bool = False
    # Remaining clock and increments, in milliseconds, for time management.
    wtime_ms: Optional[int] = None
    btime_ms: Optional[int] = None
    winc_ms: int = 0
    binc_ms: int = 0
    movestogo: Optional[int] = None


@dataclass
class SearchResult:
    """Best line found, plus statistics for UCI ``info`` output."""

    best_move: Optional[chess.Move]
    ponder_move: Optional[chess.Move] = None
    score: int = 0
    depth: int = 0
    nodes: int = 0
    time_ms: int = 0
    pv: list[chess.Move] = field(default_factory=list)
