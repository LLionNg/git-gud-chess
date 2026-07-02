"""Perft sanity: confirms the move-generation foundation the engine relies on."""

from __future__ import annotations

import chess
import pytest


def perft(board: chess.Board, depth: int) -> int:
    if depth == 0:
        return 1
    total = 0
    for move in board.legal_moves:
        board.push(move)
        total += perft(board, depth - 1)
        board.pop()
    return total


@pytest.mark.parametrize("depth,expected", [(1, 20), (2, 400), (3, 8902)])
def test_perft_startpos(depth: int, expected: int) -> None:
    assert perft(chess.Board(), depth) == expected


def test_perft_kiwipete() -> None:
    # Kiwipete is the standard tricky position (castling, en passant, pins).
    board = chess.Board("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
    assert perft(board, 2) == 2039
