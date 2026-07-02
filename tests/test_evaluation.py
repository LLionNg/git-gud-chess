"""Evaluation correctness: symmetry, material sanity and known-position signs."""

from __future__ import annotations

import chess
import pytest

FENS = [
    chess.STARTING_FEN,
    "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1",
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    "8/8/8/4k3/8/8/2Q5/4K3 b - - 0 1",
]


@pytest.mark.parametrize("fen", FENS)
def test_evaluation_is_colour_symmetric(evaluator, fen: str) -> None:
    # Mirroring swaps colours and flips the board and side to move, so the
    # side-to-move score must be identical. This catches sign/flip bugs.
    board = chess.Board(fen)
    assert evaluator.evaluate(board) == evaluator.evaluate(board.mirror())


def test_startpos_is_balanced(evaluator) -> None:
    # A symmetric position is worth only the side-to-move (tempo) bonus.
    from chessbot.config import EvaluationConfig

    assert evaluator.evaluate(chess.Board()) == EvaluationConfig().tempo


def test_extra_piece_is_positive(evaluator) -> None:
    # White is a full knight up with the move; score should clearly favour White.
    board = chess.Board("rnbqkb1r/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert evaluator.evaluate(board) > 250


def test_side_to_move_perspective(evaluator) -> None:
    # Same position, opposite side to move: the winning side sees a positive score.
    white_up = chess.Board("rnbqkb1r/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    black_to_move = white_up.copy()
    black_to_move.turn = chess.BLACK
    assert evaluator.evaluate(white_up) > 0
    assert evaluator.evaluate(black_to_move) < 0
