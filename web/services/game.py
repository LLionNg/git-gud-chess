import chess


class GameService:
    def __init__(self) -> None:
        self._board = chess.Board()
        self._human_color = chess.WHITE
        self._resigned = False

    def reset(self, human_color: chess.Color, fen: str | None = None) -> None:
        self._board = chess.Board(fen) if fen else chess.Board()
        self._human_color = human_color
        self._resigned = False

    @property
    def board(self) -> chess.Board:
        return self._board

    @property
    def human_color(self) -> chess.Color:
        return self._human_color

    @property
    def resigned(self) -> bool:
        return self._resigned

    def is_over(self) -> bool:
        return self._resigned or self._board.outcome(claim_draw=True) is not None

    def engine_to_move(self) -> bool:
        return not self.is_over() and self._board.turn != self._human_color

    def push(self, uci: str) -> None:
        if self.is_over():
            raise ValueError("game is over")
        move = chess.Move.from_uci(uci)
        if move not in self._board.legal_moves:
            raise ValueError(f"illegal move: {uci}")
        self._board.push(move)

    def resign(self) -> None:
        if self.is_over():
            raise ValueError("game is already over")
        self._resigned = True
