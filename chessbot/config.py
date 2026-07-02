"""Typed engine configuration via Pydantic models.

A single ``EngineConfig`` is threaded through the evaluator, search and UCI
layers so options set over the UCI protocol validate and propagate cleanly.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EvaluatorType(str, Enum):
    """Selects which evaluation provider the engine uses."""

    CLASSICAL = "classical"
    NEURAL = "neural"


class EvaluationConfig(BaseModel):
    """Options controlling how a position is scored."""

    provider: EvaluatorType = EvaluatorType.CLASSICAL
    # Small bonus for having the move; stabilises evaluation symmetry.
    tempo: int = Field(default=18, ge=0, le=100)
    # Path to quantized weights for the neural provider (phase-2 training output).
    weights_path: str | None = None


class SearchConfig(BaseModel):
    """Options controlling the alpha-beta search."""

    max_depth: int = Field(default=64, ge=1, le=246)
    tt_size_mb: int = Field(default=64, ge=1, le=1024)
    use_null_move: bool = True
    use_lmr: bool = True
    use_aspiration: bool = True
    # Extra milliseconds subtracted from the clock to cover process overhead.
    move_overhead_ms: int = Field(default=30, ge=0, le=1000)


class EngineConfig(BaseModel):
    """Top-level engine configuration surfaced through UCI ``setoption``."""

    name: str = "chessbot"
    author: str = "chessbot"
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
