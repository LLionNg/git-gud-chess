import threading

import chess
import chess.engine

from web.config import WebConfig


class EngineService:
    def __init__(self, config: WebConfig) -> None:
        self._config = config
        self._lock = threading.Lock()
        self._engine: chess.engine.SimpleEngine | None = None

    def open(self) -> None:
        command = list(self._config.engine_command)
        if self._config.weights:
            command += ["--weights", self._config.weights]
        self._engine = chess.engine.SimpleEngine.popen_uci(command)

    def best_move(self, board: chess.Board) -> chess.Move:
        limit = chess.engine.Limit(time=self._config.movetime_ms / 1000)
        with self._lock:
            return self._engine.play(board, limit).move

    def close(self) -> None:
        if self._engine is not None:
            self._engine.quit()
            self._engine = None
