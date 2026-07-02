"""UCI protocol adapter: translates GUI commands into engine calls.

Search runs on a background thread so ``stop`` and ``ponderhit`` can be handled
while thinking. The engine speaks standard UCI, so it drops into any chess GUI.
"""

from __future__ import annotations

import sys
import threading
from typing import Callable, Optional

import chess

from chessbot.core.types import is_mate_score, mate_in_moves
from chessbot.engine import Engine
from chessbot.search import SearchLimits, SearchResult

WriteFn = Callable[[str], None]


def _default_write(line: str) -> None:
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


class UciProtocol:
    """Reads UCI commands and drives an :class:`Engine`."""

    def __init__(self, engine: Optional[Engine] = None, write: WriteFn = _default_write) -> None:
        self.engine = engine or Engine()
        self._write = write
        self._thread: Optional[threading.Thread] = None

    # -- main loop -----------------------------------------------------------
    def run(self, stream=sys.stdin) -> None:
        for line in stream:
            command = line.strip()
            if not command:
                continue
            if not self.handle(command):
                break

    def handle(self, command: str) -> bool:
        """Process one command; returns False only for ``quit``."""
        parts = command.split()
        name = parts[0]
        handler = getattr(self, f"_cmd_{name}", None)
        if handler is not None:
            return handler(parts[1:])
        return True  # Unknown commands are ignored, per the UCI spec.

    # -- handshake -----------------------------------------------------------
    def _cmd_uci(self, _args: list[str]) -> bool:
        self._write(f"id name {self.engine.config.name} {_version()}")
        self._write(f"id author {self.engine.config.author}")
        self._write("option name Hash type spin default 64 min 1 max 1024")
        self._write("option name Move Overhead type spin default 30 min 0 max 1000")
        self._write("option name Evaluator type combo default classical var classical var neural")
        self._write("uciok")
        return True

    def _cmd_isready(self, _args: list[str]) -> bool:
        self._write("readyok")
        return True

    def _cmd_ucinewgame(self, _args: list[str]) -> bool:
        self._stop_search()
        self.engine.new_game()
        return True

    def _cmd_setoption(self, args: list[str]) -> bool:
        # Format: setoption name <NAME with spaces> value <VALUE with spaces>
        if "name" not in args:
            return True
        name_idx = args.index("name") + 1
        if "value" in args:
            value_idx = args.index("value")
            name = " ".join(args[name_idx:value_idx])
            value = " ".join(args[value_idx + 1:])
        else:
            name, value = " ".join(args[name_idx:]), ""
        self.engine.set_option(name, value)
        return True

    # -- position and search -------------------------------------------------
    def _cmd_position(self, args: list[str]) -> bool:
        moves: list[str] = []
        if args and args[0] == "startpos":
            fen = None
            if "moves" in args:
                moves = args[args.index("moves") + 1:]
        elif args and args[0] == "fen":
            end = args.index("moves") if "moves" in args else len(args)
            fen = " ".join(args[1:end])
            if "moves" in args:
                moves = args[args.index("moves") + 1:]
        else:
            return True
        self.engine.set_position(fen, moves)
        return True

    def _cmd_go(self, args: list[str]) -> bool:
        self._stop_search()
        limits, ponder = _parse_go(args)
        self._thread = threading.Thread(target=self._run_search, args=(limits, ponder), daemon=True)
        self._thread.start()
        return True

    def _cmd_stop(self, _args: list[str]) -> bool:
        self._stop_search()
        return True

    def _cmd_ponderhit(self, _args: list[str]) -> bool:
        self.engine.searcher.notify_ponderhit()
        return True

    def _cmd_quit(self, _args: list[str]) -> bool:
        self._stop_search()
        return False

    # -- search worker -------------------------------------------------------
    def _run_search(self, limits: SearchLimits, ponder: bool) -> None:
        result = self.engine.search(limits, info=self._emit_info)
        self._write(_format_bestmove(result))

    def _emit_info(self, result: SearchResult) -> None:
        self._write(_format_info(result))

    def _stop_search(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            self.engine.stop()
            self._thread.join()
        self._thread = None


def _version() -> str:
    from chessbot import __version__

    return __version__


def _parse_go(args: list[str]) -> tuple[SearchLimits, bool]:
    limits = SearchLimits()
    ponder = False
    i = 0
    int_fields = {
        "wtime": "wtime_ms", "btime": "btime_ms", "winc": "winc_ms", "binc": "binc_ms",
        "movestogo": "movestogo", "depth": "depth", "nodes": "nodes", "movetime": "movetime_ms",
    }
    while i < len(args):
        token = args[i]
        if token in int_fields and i + 1 < len(args):
            setattr(limits, int_fields[token], int(args[i + 1]))
            i += 2
        elif token == "infinite":
            limits.infinite = True
            i += 1
        elif token == "ponder":
            ponder = True
            limits.infinite = True  # Ponder searches until ponderhit or stop.
            i += 1
        else:
            i += 1
    return limits, ponder


def _format_info(result: SearchResult) -> str:
    if is_mate_score(result.score):
        score = f"score mate {mate_in_moves(result.score)}"
    else:
        score = f"score cp {result.score}"
    nps = int(result.nodes / (result.time_ms / 1000)) if result.time_ms > 0 else 0
    pv = " ".join(move.uci() for move in result.pv)
    return (f"info depth {result.depth} {score} nodes {result.nodes} "
            f"nps {nps} time {result.time_ms} pv {pv}")


def _format_bestmove(result: SearchResult) -> str:
    if result.best_move is None:
        return "bestmove (none)"
    if result.ponder_move is not None:
        return f"bestmove {result.best_move.uci()} ponder {result.ponder_move.uci()}"
    return f"bestmove {result.best_move.uci()}"
