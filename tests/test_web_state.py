"""Game-end rules exposed by the web API: claimable draws and resignation."""

import chess
import pytest

from web.api.schemas import GameState
from web.services.game import GameService


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
    game = GameService()
    game.reset(chess.WHITE)
    game.resign()
    state = GameState.from_board(game.board, game.human_color, resigned=game.resigned)
    assert state.is_over
    assert state.result == "0-1"
    assert state.termination == "resignation"

    game.reset(chess.BLACK)
    game.resign()
    state = GameState.from_board(game.board, game.human_color, resigned=game.resigned)
    assert state.result == "1-0"


def test_no_moves_after_resigning():
    game = GameService()
    game.reset(chess.WHITE)
    game.resign()
    with pytest.raises(ValueError):
        game.push("e2e4")
    with pytest.raises(ValueError):
        game.resign()
    assert not game.engine_to_move()
