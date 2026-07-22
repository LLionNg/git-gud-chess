import chess
from fastapi import APIRouter, HTTPException, Request

from web.api.schemas import GameRef, GameState, MoveRequest, NewGameRequest, ResignRequest
from web.services import game as rules

router = APIRouter()


def _color(name: str) -> chess.Color:
    return chess.BLACK if name == "black" else chess.WHITE


def _board(fen: str | None) -> chess.Board:
    try:
        return rules.board_from(fen)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


def _game_board(payload: GameRef) -> chess.Board:
    # A legacy client sends only the position; without history it cannot
    # get repetition draws, but the game still plays.
    if payload.fen and not payload.moves and not payload.start_fen:
        return _board(payload.fen)
    try:
        return rules.replay(payload.start_fen, payload.moves)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


def _maybe_engine_move(board: chess.Board, human_color: chess.Color,
                       engine) -> str | None:
    if not rules.engine_to_move(board, human_color):
        return None
    move = engine.best_move(board)
    board.push(move)
    return move.uci()


@router.post("/new", response_model=GameState)
def new_game(payload: NewGameRequest, request: Request) -> GameState:
    board = _board(payload.fen)
    human_color = _color(payload.human_color)
    engine_move = _maybe_engine_move(board, human_color, request.app.state.engine)
    return GameState.from_board(board, human_color, engine_move)


@router.post("/move", response_model=GameState)
def make_move(payload: MoveRequest, request: Request) -> GameState:
    board = _game_board(payload)
    human_color = _color(payload.human_color)
    try:
        rules.push_uci(board, payload.uci)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    engine_move = _maybe_engine_move(board, human_color, request.app.state.engine)
    return GameState.from_board(board, human_color, engine_move)


@router.post("/state", response_model=GameState)
def game_state(payload: GameRef) -> GameState:
    # Rebuilds a position from its history without asking the engine to move;
    # the client uses this to land on the player's turn after an undo or redo.
    board = _game_board(payload)
    return GameState.from_board(board, _color(payload.human_color))


@router.post("/resign", response_model=GameState)
def resign(payload: ResignRequest, request: Request) -> GameState:
    board = _game_board(payload)
    if rules.is_over(board):
        raise HTTPException(status_code=400, detail="game is already over")
    return GameState.from_board(board, _color(payload.human_color), resigned=True)
