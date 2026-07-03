import chess
from fastapi import APIRouter, HTTPException, Request

from web.api.schemas import GameState, MoveRequest, NewGameRequest

router = APIRouter()


def _color(name: str) -> chess.Color:
    return chess.BLACK if name == "black" else chess.WHITE


def _maybe_engine_move(game, engine) -> str | None:
    if not game.engine_to_move():
        return None
    move = engine.best_move(game.board)
    game.board.push(move)
    return move.uci()


@router.post("/new", response_model=GameState)
def new_game(payload: NewGameRequest, request: Request) -> GameState:
    game = request.app.state.game
    engine = request.app.state.engine
    try:
        game.reset(_color(payload.human_color), payload.fen)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    engine_move = _maybe_engine_move(game, engine)
    return GameState.from_board(game.board, game.human_color, engine_move)


@router.get("/state", response_model=GameState)
def get_state(request: Request) -> GameState:
    game = request.app.state.game
    return GameState.from_board(game.board, game.human_color)


@router.post("/move", response_model=GameState)
def make_move(payload: MoveRequest, request: Request) -> GameState:
    game = request.app.state.game
    engine = request.app.state.engine
    try:
        game.push(payload.uci)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    engine_move = _maybe_engine_move(game, engine)
    return GameState.from_board(game.board, game.human_color, engine_move)
