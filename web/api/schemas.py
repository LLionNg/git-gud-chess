import chess
from pydantic import BaseModel

from web.services import game as rules


class NewGameRequest(BaseModel):
    human_color: str = "white"
    fen: str | None = None


class GameRef(BaseModel):
    """The game as the client holds it; the server stores nothing.

    The move list is what lets the server see draws by repetition — a bare
    FEN cannot express how often a position has occurred.
    """

    human_color: str = "white"
    start_fen: str | None = None
    moves: list[str] = []
    fen: str | None = None  # legacy clients that sent only the position


class MoveRequest(GameRef):
    uci: str


class ResignRequest(GameRef):
    pass


class GameState(BaseModel):
    fen: str
    start_fen: str
    moves: list[str]
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
            outcome = rules.outcome(board)
            over = outcome is not None
            result = outcome.result() if outcome else None
            termination = outcome.termination.name.lower() if outcome else None
        return cls(
            fen=board.fen(),
            start_fen=board.root().fen(),
            moves=[move.uci() for move in board.move_stack],
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
