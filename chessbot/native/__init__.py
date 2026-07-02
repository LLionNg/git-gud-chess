"""Native backend: drive the replicated C++ engine through a standard-UCI bridge."""

from __future__ import annotations

from chessbot.native.bridge import UciBridge, translate

__all__ = ["UciBridge", "translate"]
