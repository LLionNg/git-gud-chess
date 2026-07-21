"""Stateless game rules: every request carries the game, nothing is stored."""

import chess


def outcome(board: chess.Board) -> chess.Outcome | None:
    """Game end as chess.com adjudicates it: forced endings, plus threefold
    repetition and the fifty-move rule the moment they actually occur.
    (claim_draw=True would end the game one move early, when a repetition is
    merely reachable — even if the player intends a different move.)"""
    result = board.outcome()
    if result:
        return result
    if board.is_repetition(3):
        return chess.Outcome(chess.Termination.THREEFOLD_REPETITION, None)
    if board.is_fifty_moves():
        return chess.Outcome(chess.Termination.FIFTY_MOVES, None)
    return None


def board_from(fen: str | None) -> chess.Board:
    try:
        return chess.Board(fen) if fen else chess.Board()
    except ValueError as error:
        raise ValueError(f"invalid FEN: {error}")


def replay(start_fen: str | None, moves: list[str]) -> chess.Board:
    """Rebuild the game from its move list, keeping the history that
    outcome() needs to detect draws by repetition."""
    board = board_from(start_fen)
    for uci in moves:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            raise ValueError(f"invalid move in history: {uci}")
        if move not in board.legal_moves:
            raise ValueError(f"illegal move in history: {uci}")
        board.push(move)
    return board


def is_over(board: chess.Board) -> bool:
    return outcome(board) is not None


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
