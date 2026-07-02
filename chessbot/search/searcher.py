"""Iterative-deepening alpha-beta searcher.

The search is negamax with a transposition table, principal-variation search,
null-move pruning, late-move reductions, check extensions and a quiescence
search. It runs on a private board copy and can be interrupted by a stop event,
a node budget or a time deadline.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Hashable, Optional

import chess

from chessbot.config import EngineConfig
from chessbot.core.types import (
    DRAW_SCORE,
    INFINITY,
    MAX_PLY,
    MATE_SCORE,
    is_mate_score,
)
from chessbot.evaluation.base import Evaluator
from chessbot.search.limits import SearchLimits, SearchResult
from chessbot.search.ordering import order_moves
from chessbot.search.transposition import EXACT, LOWER, UPPER, TranspositionTable

InfoCallback = Callable[[SearchResult], None]


class _Timeout(Exception):
    """Raised to unwind the search when time or the stop signal runs out."""


class Searcher:
    """Owns the transposition table and search heuristics across a game."""

    def __init__(self, config: EngineConfig, evaluator: Evaluator) -> None:
        self._config = config
        self._evaluator = evaluator
        self._tt = TranspositionTable(config.search.tt_size_mb)
        self.stop_event = threading.Event()

        self.board = chess.Board()
        self.nodes = 0
        self._deadline: Optional[float] = None
        self._soft_deadline: Optional[float] = None
        self._max_nodes: Optional[int] = None
        self._aborted = False
        self._search_start = 0.0
        self._limits = SearchLimits()

        self._killers: list[list[Optional[chess.Move]]] = []
        self._history: dict[tuple[int, int, int], int] = {}
        self._pv: list[list[Optional[chess.Move]]] = []
        self._pv_len: list[int] = []
        self._last_score = 0  # Previous iteration's score; seeds aspiration windows.

    # -- lifecycle -----------------------------------------------------------
    def new_game(self) -> None:
        """Reset all inter-search state for a fresh game."""
        self._tt.clear()
        self._history.clear()

    def stop(self) -> None:
        self.stop_event.set()

    def notify_ponderhit(self) -> None:
        """Convert an in-progress ponder search to a normally-timed one.

        The clock is anchored at the original search start, so time spent
        pondering counts as ours - conservative but never loses on time.
        """
        limits = self._limits
        was_infinite = limits.infinite
        limits.infinite = False
        self._setup_timing(limits, self._search_start)
        limits.infinite = was_infinite

    # -- public search entry -------------------------------------------------
    def search(self, board: chess.Board, limits: SearchLimits,
               info: Optional[InfoCallback] = None) -> SearchResult:
        self.board = board.copy(stack=True)
        self.nodes = 0
        self._aborted = False
        self.stop_event.clear()
        self._killers = [[None, None] for _ in range(MAX_PLY + 1)]
        self._history.clear()
        self._pv = [[None] * (MAX_PLY + 1) for _ in range(MAX_PLY + 1)]
        self._pv_len = [0] * (MAX_PLY + 1)

        legal = list(self.board.legal_moves)
        if not legal:
            return SearchResult(best_move=None)

        start = time.perf_counter()
        self._search_start = start
        self._limits = limits
        self._setup_timing(limits, start)

        result = SearchResult(best_move=legal[0])
        max_depth = min(limits.depth or self._config.search.max_depth, MAX_PLY)

        for depth in range(1, max_depth + 1):
            try:
                score = self._search_root(depth)
            except _Timeout:
                break

            pv = [self._pv[0][i] for i in range(self._pv_len[0]) if self._pv[0][i] is not None]
            best = pv[0] if pv else result.best_move
            result = SearchResult(
                best_move=best,
                ponder_move=pv[1] if len(pv) > 1 else None,
                score=score,
                depth=depth,
                nodes=self.nodes,
                time_ms=int((time.perf_counter() - start) * 1000),
                pv=pv,
            )
            if info:
                info(result)

            # Stop early on a proven mate or when the next iteration cannot finish.
            if is_mate_score(score) and depth >= abs(MATE_SCORE) - abs(score):
                break
            if self._soft_deadline is not None and time.perf_counter() >= self._soft_deadline:
                break
            if len(legal) == 1:
                break

        return result

    # -- timing --------------------------------------------------------------
    def _setup_timing(self, limits: SearchLimits, start: float) -> None:
        self._max_nodes = limits.nodes
        self._deadline = None
        self._soft_deadline = None
        if limits.infinite:
            return

        allocated_ms: Optional[float] = None
        if limits.movetime_ms is not None:
            allocated_ms = float(limits.movetime_ms)
        else:
            clock = limits.wtime_ms if self.board.turn == chess.WHITE else limits.btime_ms
            inc = limits.winc_ms if self.board.turn == chess.WHITE else limits.binc_ms
            if clock is not None:
                moves_to_go = limits.movestogo or 30
                # Spend a slice of the remaining clock plus most of the increment,
                # never risking more than 80% of what is left.
                allocated_ms = clock / moves_to_go + inc * 0.75
                allocated_ms = min(allocated_ms, clock * 0.8)

        if allocated_ms is None:
            if limits.depth is None and limits.nodes is None:
                allocated_ms = 5000.0  # Sensible default when asked to "just move".
            else:
                return

        allocated_ms = max(1.0, allocated_ms - self._config.search.move_overhead_ms)
        self._deadline = start + allocated_ms / 1000.0
        # Only begin a new iteration if a good fraction of the budget remains.
        self._soft_deadline = start + (allocated_ms * 0.5) / 1000.0

    def _check_stop(self) -> None:
        if self.nodes & 2047 == 0:
            if self.stop_event.is_set():
                self._aborted = True
            elif self._deadline is not None and time.perf_counter() >= self._deadline:
                self._aborted = True
            elif self._max_nodes is not None and self.nodes >= self._max_nodes:
                self._aborted = True
        if self._aborted:
            raise _Timeout()

    # -- helpers -------------------------------------------------------------
    def _key(self) -> Hashable:
        return self.board._transposition_key()

    def _has_non_pawn_material(self, color: chess.Color) -> bool:
        b = self.board
        return bool(b.occupied_co[color] & (b.knights | b.bishops | b.rooks | b.queens))

    def _update_pv(self, ply: int, move: chess.Move) -> None:
        self._pv[ply][ply] = move
        for i in range(ply + 1, self._pv_len[ply + 1]):
            self._pv[ply][i] = self._pv[ply + 1][i]
        self._pv_len[ply] = self._pv_len[ply + 1]

    def _record_quiet(self, move: chess.Move, depth: int, ply: int) -> None:
        """Reward a quiet move that caused a cutoff via killers and history."""
        killers = self._killers[ply]
        if move != killers[0]:
            killers[1] = killers[0]
            killers[0] = move
        piece = self.board.piece_type_at(move.from_square) or chess.PAWN
        key = (self.board.turn, piece, move.to_square)
        self._history[key] = self._history.get(key, 0) + depth * depth

    # -- root ----------------------------------------------------------------
    def _search_root(self, depth: int) -> int:
        alpha, beta = -INFINITY, INFINITY
        if self._config.search.use_aspiration and depth >= 4 and not is_mate_score(self._last_score):
            return self._aspiration(depth)
        score = self._negamax(depth, alpha, beta, 0, True)
        self._last_score = score
        return score

    def _aspiration(self, depth: int) -> int:
        window = 25
        while True:
            alpha = self._last_score - window
            beta = self._last_score + window
            score = self._negamax(depth, alpha, beta, 0, True)
            if score <= alpha or score >= beta:
                window *= 4  # Fell outside the window; widen and re-search this depth.
                if window > 2000:
                    score = self._negamax(depth, -INFINITY, INFINITY, 0, True)
                    self._last_score = score
                    return score
                continue
            self._last_score = score
            return score

    # -- negamax -------------------------------------------------------------
    def _negamax(self, depth: int, alpha: int, beta: int, ply: int, allow_null: bool) -> int:
        self._pv_len[ply] = ply
        self._check_stop()
        board = self.board
        is_pv = beta - alpha > 1

        if ply > 0 and (board.is_repetition(2) or board.halfmove_clock >= 100
                        or board.is_insufficient_material()):
            return DRAW_SCORE

        in_check = board.is_check()
        if in_check:
            depth += 1  # Check extension: never drop into quiescence while in check.

        if depth <= 0 or ply >= MAX_PLY:
            return self._quiescence(alpha, beta, ply)

        self.nodes += 1
        key = self._key()
        alpha_orig = alpha
        tt_move: Optional[chess.Move] = None
        entry = self._tt.probe(key, ply)
        if entry is not None:
            tt_move = entry.move
            if ply > 0 and entry.depth >= depth:
                if entry.flag == EXACT:
                    return entry.score
                if entry.flag == LOWER and entry.score >= beta:
                    return entry.score
                if entry.flag == UPPER and entry.score <= alpha:
                    return entry.score

        # Null-move pruning: give the opponent a free move; if we are still winning,
        # this line is too good and can be pruned. Skipped in check and in likely zugzwang.
        if (allow_null and not is_pv and not in_check and depth >= 3
                and self._has_non_pawn_material(board.turn)):
            reduction = 2 + (depth > 6)
            board.push(chess.Move.null())
            score = -self._negamax(depth - 1 - reduction, -beta, -beta + 1, ply + 1, False)
            board.pop()
            if score >= beta:
                return beta

        best_score = -INFINITY
        best_move: Optional[chess.Move] = None
        killers = (self._killers[ply][0], self._killers[ply][1])
        moves = order_moves(board, list(board.legal_moves), tt_move, killers, self._history)

        move_count = 0
        for move in moves:
            move_count += 1
            is_capture = board.is_capture(move)
            gives_check = board.gives_check(move)
            board.push(move)

            new_depth = depth - 1
            if move_count == 1:
                score = -self._negamax(new_depth, -beta, -alpha, ply + 1, True)
            else:
                reduction = 0
                if (self._config.search.use_lmr and depth >= 3 and move_count >= 4
                        and not in_check and not is_capture and not move.promotion
                        and not gives_check):
                    reduction = 1 if move_count < 8 or depth < 6 else 2
                # Null-window probe (optionally reduced); re-search if it beats alpha.
                score = -self._negamax(new_depth - reduction, -alpha - 1, -alpha, ply + 1, True)
                if score > alpha and reduction:
                    score = -self._negamax(new_depth, -alpha - 1, -alpha, ply + 1, True)
                if alpha < score < beta:
                    score = -self._negamax(new_depth, -beta, -alpha, ply + 1, True)
            board.pop()

            if score > best_score:
                best_score = score
                best_move = move
            if score > alpha:
                alpha = score
                self._update_pv(ply, move)
                if alpha >= beta:
                    if not is_capture and not move.promotion:
                        self._record_quiet(move, depth, ply)
                    break

        if move_count == 0:
            # No legal moves: checkmate (scaled by ply so faster mates win) or stalemate.
            return -MATE_SCORE + ply if in_check else DRAW_SCORE

        flag = UPPER if best_score <= alpha_orig else (LOWER if best_score >= beta else EXACT)
        self._tt.store(key, depth, best_score, flag, best_move, ply)
        return best_score

    # -- quiescence ----------------------------------------------------------
    def _quiescence(self, alpha: int, beta: int, ply: int) -> int:
        self._check_stop()
        self.nodes += 1
        board = self.board

        if ply >= MAX_PLY:
            return self._evaluator.evaluate(board)

        in_check = board.is_check()
        if in_check:
            # Resolve checks fully so tactics and mates are not missed on the horizon.
            moves = list(board.legal_moves)
            if not moves:
                return -MATE_SCORE + ply
            best_score = -INFINITY
        else:
            stand_pat = self._evaluator.evaluate(board)
            if stand_pat >= beta:
                return stand_pat
            if stand_pat > alpha:
                alpha = stand_pat
            best_score = stand_pat
            moves = self._tactical_moves(board)

        killers = (None, None)
        for move in order_moves(board, moves, None, killers, self._history):
            board.push(move)
            score = -self._quiescence(-beta, -alpha, ply + 1)
            board.pop()
            if score > best_score:
                best_score = score
            if score > alpha:
                alpha = score
                if alpha >= beta:
                    break
        return best_score

    @staticmethod
    def _tactical_moves(board: chess.Board) -> list[chess.Move]:
        """Captures plus queen promotions - the moves quiescence considers."""
        moves = list(board.generate_legal_captures())
        seventh = chess.BB_RANK_7 if board.turn == chess.WHITE else chess.BB_RANK_2
        if board.pawns & board.occupied_co[board.turn] & seventh:
            for move in board.generate_legal_moves(board.pawns & seventh):
                if move.promotion == chess.QUEEN and not board.is_capture(move):
                    moves.append(move)
        return moves
