"""UCI protocol behaviour: handshake, position parsing, search and stop."""

from __future__ import annotations

import time

import chess

from chessbot.uci.protocol import UciProtocol, _parse_go


def make_protocol():
    out: list[str] = []
    return UciProtocol(write=out.append), out


def test_handshake() -> None:
    proto, out = make_protocol()
    proto.handle("uci")
    assert any(line.startswith("id name") for line in out)
    assert "uciok" in out
    out.clear()
    proto.handle("isready")
    assert out == ["readyok"]


def test_position_startpos_with_moves() -> None:
    proto, _ = make_protocol()
    proto.handle("position startpos moves e2e4 e7e5 g1f3")
    assert proto.engine.board.fen().startswith(
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b"
    )


def test_position_fen() -> None:
    proto, _ = make_protocol()
    fen = "8/8/8/4k3/8/8/2Q5/4K3 w - - 0 1"
    proto.handle(f"position fen {fen}")
    assert proto.engine.board.fen() == fen


def test_go_depth_produces_bestmove() -> None:
    proto, out = make_protocol()
    proto.handle("position startpos")
    proto.handle("go depth 4")
    proto._thread.join()
    bestmoves = [line for line in out if line.startswith("bestmove")]
    assert len(bestmoves) == 1
    move = bestmoves[0].split()[1]
    assert chess.Move.from_uci(move) in chess.Board().legal_moves


def test_stop_interrupts_infinite_search() -> None:
    proto, out = make_protocol()
    proto.handle("position startpos")
    proto.handle("go infinite")
    time.sleep(0.3)
    proto.handle("stop")  # Joins the worker as part of stopping.
    assert any(line.startswith("bestmove") for line in out)


def test_parse_go_time_controls() -> None:
    limits, ponder = _parse_go("wtime 300000 btime 300000 winc 2000 binc 2000 movestogo 40".split())
    assert limits.wtime_ms == 300000 and limits.winc_ms == 2000 and limits.movestogo == 40
    assert not ponder


def test_parse_go_ponder() -> None:
    limits, ponder = _parse_go("ponder wtime 60000 btime 60000".split())
    assert ponder and limits.infinite


def test_mate_score_reported_as_mate() -> None:
    proto, out = make_protocol()
    proto.handle("position fen 6k1/R7/6K1/8/8/8/8/8 w - - 0 1")
    proto.handle("go depth 3")
    proto._thread.join()
    assert any("score mate 1" in line for line in out)
