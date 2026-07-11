"""Stateless game rules: every request carries the position, nothing is stored.

claim_draw=True applies threefold repetition and the 50-move rule
automatically, like chess.com.
"""

import chess


def board_from(fen: str | None) -> chess.Board:
    try:
        return chess.Board(fen) if fen else chess.Board()
    except ValueError as error:
        raise ValueError(f"invalid FEN: {error}")


def is_over(board: chess.Board) -> bool:
    return board.outcome(claim_draw=True) is not None


def engine_to_move(board: chess.Board, human_color: chess.Color) -> bool:
    return not is_over(board) and board.turn != human_color


def push_uci(board: chess.Board, uci: str) -> None:
    if is_over(board):
        raise ValueError("game is over")
    try:
        move = chess.Move.from_uci(uci)
    except ValueError:
        raise ValueError(f"invalid move: {uci}")
    if move not in board.legal_moves:
        raise ValueError(f"illegal move: {uci}")
    board.push(move)
