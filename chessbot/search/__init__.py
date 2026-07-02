"""Alpha-beta search: the searcher, its limits and result types."""

from __future__ import annotations

from chessbot.search.limits import SearchLimits, SearchResult
from chessbot.search.searcher import Searcher

__all__ = ["Searcher", "SearchLimits", "SearchResult"]
