"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from chessbot.config import EngineConfig
from chessbot.evaluation import build_evaluator
from chessbot.search import Searcher


@pytest.fixture
def evaluator():
    return build_evaluator(EngineConfig().evaluation)


@pytest.fixture
def searcher(evaluator):
    return Searcher(EngineConfig(), evaluator)
