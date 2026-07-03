import chess


class GameService:
    def __init__(self) -> None:
        self._board = chess.Board()
        self._human_color = chess.WHITE

    def reset(self, human_color: chess.Color, fen: str | None = None) -> None:
        self._board = chess.Board(fen) if fen else chess.Board()
        self._human_color = human_color

    @property
    def board(self) -> chess.Board:
        return self._board

    @property
    def human_color(self) -> chess.Color:
        return self._human_color

    def engine_to_move(self) -> bool:
        return not self._board.is_game_over() and self._board.turn != self._human_color

    def push(self, uci: str) -> None:
        move = chess.Move.from_uci(uci)
        if move not in self._board.legal_moves:
            raise ValueError(f"illegal move: {uci}")
        self._board.push(move)
