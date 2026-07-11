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
    termination: str | None

    @classmethod
    def from_board(cls, board: chess.Board, human_color: chess.Color,
                   engine_move: str | None = None, resigned: bool = False) -> "GameState":
        if resigned:
            over = True
            result = "0-1" if human_color == chess.WHITE else "1-0"
            termination = "resignation"
        else:
            # claim_draw applies threefold repetition and the 50-move rule
            # automatically, like chess.com; without it only the forced
            # fivefold/75-move variants would end the game.
            outcome = board.outcome(claim_draw=True)
            over = outcome is not None
            result = outcome.result() if outcome else None
            termination = outcome.termination.name.lower() if outcome else None
        return cls(
            fen=board.fen(),
            turn="white" if board.turn == chess.WHITE else "black",
            human_color="white" if human_color == chess.WHITE else "black",
            legal=[] if over else [move.uci() for move in board.legal_moves],
            last_move=board.peek().uci() if board.move_stack else None,
            engine_move=engine_move,
            check_square=chess.square_name(board.king(board.turn)) if board.is_check() else None,
            is_over=over,
            result=result,
            termination=termination,
        )
