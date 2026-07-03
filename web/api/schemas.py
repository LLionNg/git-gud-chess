import chess
from pydantic import BaseModel


class NewGameRequest(BaseModel):
    human_color: str = "white"
    fen: str | None = None


class MoveRequest(BaseModel):
    uci: str


class GameState(BaseModel):
    fen: str
    turn: str
    human_color: str
    legal: list[str]
    last_move: str | None
    engine_move: str | None
    check_square: str | None
    is_over: bool
    result: str | None

    @classmethod
    def from_board(cls, board: chess.Board, human_color: chess.Color,
                   engine_move: str | None = None) -> "GameState":
        over = board.is_game_over()
        return cls(
            fen=board.fen(),
            turn="white" if board.turn == chess.WHITE else "black",
            human_color="white" if human_color == chess.WHITE else "black",
            legal=[move.uci() for move in board.legal_moves],
            last_move=board.peek().uci() if board.move_stack else None,
            engine_move=engine_move,
            check_square=chess.square_name(board.king(board.turn)) if board.is_check() else None,
            is_over=over,
            result=board.result() if over else None,
        )
