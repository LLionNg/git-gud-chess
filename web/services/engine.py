import threading

import chess

from chessbot.config import EngineConfig, EvaluatorType
from chessbot.engine import Engine
from chessbot.search import SearchLimits

from web.config import WebConfig


class EngineService:
    """The chessbot engine run in-process.

    No subprocess and no game state, so it works both under uvicorn and inside
    a serverless function (built once per process, reused across warm requests).
    """

    def __init__(self, config: WebConfig) -> None:
        engine_config = EngineConfig()
        if config.weights:
            engine_config.evaluation.provider = EvaluatorType.NEURAL
            engine_config.evaluation.weights_path = config.weights
        self._engine = Engine(engine_config)
        self._movetime_ms = config.movetime_ms
        self._lock = threading.Lock()

    def best_move(self, board: chess.Board) -> chess.Move:
        with self._lock:
            self._engine.set_position(board.fen())
            result = self._engine.search(SearchLimits(movetime_ms=self._movetime_ms))
        if result.best_move is None:
            raise ValueError("no legal move in this position")
        return result.best_move
