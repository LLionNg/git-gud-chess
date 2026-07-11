"""Game-end rules exposed by the web API: claimable draws and resignation."""

import chess
import pytest

from web.api.schemas import GameState
from web.services import game as rules


def _shuffle_knights(board: chess.Board, times: int) -> None:
    for _ in range(times):
        for uci in ("g1f3", "g8f6", "f3g1", "f6g8"):
            board.push(chess.Move.from_uci(uci))


def test_threefold_repetition_ends_game():
    board = chess.Board()
    _shuffle_knights(board, 2)  # start position occurs a third time
    state = GameState.from_board(board, chess.WHITE)
    assert state.is_over
    assert state.result == "1/2-1/2"
    assert state.termination == "threefold_repetition"
    assert state.legal == []


def test_stalemate_and_insufficient_material():
    stalemate = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    state = GameState.from_board(stalemate, chess.WHITE)
    assert state.is_over and state.termination == "stalemate"

    bare_kings = chess.Board("8/8/4k3/8/8/4K3/8/8 w - - 0 1")
    state = GameState.from_board(bare_kings, chess.WHITE)
    assert state.is_over and state.termination == "insufficient_material"


def test_fifty_move_rule_ends_game():
    board = chess.Board("8/8/4k3/8/8/4K3/6R1/8 w - - 100 80")
    state = GameState.from_board(board, chess.WHITE)
    assert state.is_over
    assert state.termination == "fifty_moves"


def test_resignation_scores_for_the_engine():
    board = chess.Board()
    state = GameState.from_board(board, chess.WHITE, resigned=True)
    assert state.is_over
    assert state.result == "0-1"
    assert state.termination == "resignation"

    state = GameState.from_board(board, chess.BLACK, resigned=True)
    assert state.result == "1-0"


def test_no_moves_on_a_finished_position():
    board = chess.Board()
    _shuffle_knights(board, 2)
    with pytest.raises(ValueError):
        rules.push_uci(board, "e2e4")
    assert not rules.engine_to_move(board, chess.BLACK)


def test_illegal_and_invalid_input_rejected():
    board = chess.Board()
    with pytest.raises(ValueError):
        rules.push_uci(board, "e2e5")
    with pytest.raises(ValueError):
        rules.push_uci(board, "not-a-move")
    with pytest.raises(ValueError):
        rules.board_from("not a fen")
