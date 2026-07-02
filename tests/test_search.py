"""Search correctness: mates, tactics, draws, and always-legal output."""

from __future__ import annotations

import chess
import pytest

from chessbot.core.types import is_mate_score, mate_in_moves
from chessbot.search import SearchLimits
from tests.helpers import can_force_mate

MATE_PUZZLES = [
    ("6k1/R7/6K1/8/8/8/8/8 w - - 0 1", 1, 3),        # Ra8#
    ("8/8/8/8/3Q4/k7/8/1K6 w - - 0 1", 2, 6),        # Qd4 then mate
    ("7k/6R1/5K2/8/8/8/8/8 w - - 0 1", 3, 8),        # rook mate in 3
]


@pytest.mark.parametrize("fen,moves,depth", MATE_PUZZLES)
def test_finds_forced_mate(searcher, fen: str, moves: int, depth: int) -> None:
    board = chess.Board(fen)
    assert can_force_mate(board.copy(), 2 * moves - 1)  # Puzzle really is mate in N.

    result = searcher.search(board, SearchLimits(depth=depth))
    assert is_mate_score(result.score)
    assert mate_in_moves(result.score) == moves
    assert result.best_move in board.legal_moves


TACTICS = [
    # (fen, expected best move, minimum score) - a clearly winning capture.
    ("4k3/8/8/8/8/3q4/8/3RK3 w - - 0 1", "d1d3", 450),   # Rxd3 wins Q for R (up a rook)
    ("4k3/8/8/8/3n4/8/8/3QK3 w - - 0 1", "d1d4", 250),   # Qxd4 wins the knight
]


@pytest.mark.parametrize("fen,expected,min_score", TACTICS)
def test_wins_hanging_material(searcher, fen: str, expected: str, min_score: int) -> None:
    board = chess.Board(fen)
    result = searcher.search(board, SearchLimits(depth=6))
    assert result.best_move == chess.Move.from_uci(expected)
    assert result.score >= min_score


def test_stalemate_is_draw(searcher) -> None:
    # Black to move is stalemated; from White's side the position is not a mate.
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert board.is_stalemate()


def test_returns_none_when_no_moves(searcher) -> None:
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    result = searcher.search(board, SearchLimits(depth=3))
    assert result.best_move is None


def test_avoids_stalemate_when_winning(searcher) -> None:
    # Up a queen, the engine must not stalemate; any legal move keeps winning.
    board = chess.Board("7k/8/6K1/8/8/8/5Q2/8 w - - 0 1")
    result = searcher.search(board, SearchLimits(depth=5))
    board.push(result.best_move)
    assert not board.is_stalemate()


@pytest.mark.parametrize("fen", [
    chess.STARTING_FEN,
    "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R b KQkq - 0 1",
])
def test_always_returns_legal_move(searcher, fen: str) -> None:
    board = chess.Board(fen)
    result = searcher.search(board, SearchLimits(depth=5))
    assert result.best_move in board.legal_moves


def test_respects_node_limit(searcher) -> None:
    board = chess.Board()
    result = searcher.search(board, SearchLimits(nodes=5000))
    assert result.best_move in board.legal_moves
