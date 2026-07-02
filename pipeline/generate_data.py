"""Self-play training-data generation, replicating the reference pipeline.

The reference generated features by self-play inside Kaggle's chess environment
using the engine compiled with ``-DGENERATE_TRAINING_DATA``; that build dumps a
sampled position's 200 Stockfish features (labelled by the NNUE teacher) to
``features/*.features`` during search. This driver reproduces that: it plays
diversified games with the datagen engine over UCI, which writes the feature
files as it thinks.

Usage:
    python pipeline/generate_data.py --engine kaggle-stockfish/stockfish_gen.exe \\
        --games 60 --depth 12 --out kaggle-stockfish/src/features
"""

from __future__ import annotations

import argparse
import random
import subprocess
from pathlib import Path

import chess


def _uci(engine: subprocess.Popen, command: str) -> None:
    engine.stdin.write(command + "\n")
    engine.stdin.flush()


def _bestmove(engine: subprocess.Popen) -> str | None:
    while True:
        line = engine.stdout.readline()
        if not line:
            return None
        if line.startswith("bestmove"):
            return line.split()[1]


def play_game(engine: subprocess.Popen, depth: int, rng: random.Random, max_plies: int) -> None:
    """Play one self-play game; the engine dumps features as it searches."""
    board = chess.Board()
    # Randomised opening plies so positions are diverse across games.
    for _ in range(rng.randint(1, 6)):
        moves = list(board.legal_moves)
        if not moves:
            return
        board.push(rng.choice(moves))
    _uci(engine, "ucinewgame")
    while not board.is_game_over(claim_draw=True) and board.fullmove_number < max_plies:
        _uci(engine, f"position fen {board.fen()}")
        _uci(engine, f"go depth {depth}")
        move = _bestmove(engine)
        if move is None or move == "(none)":
            break
        board.push(chess.Move.from_uci(move))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True, help="path to the -DGENERATE_TRAINING_DATA build")
    parser.add_argument("--games", type=int, default=40)
    parser.add_argument("--depth", type=int, default=12)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-plies", type=int, default=80)
    parser.add_argument("--out", default="kaggle-stockfish/src/features")
    args = parser.parse_args()

    Path(args.out).mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    # The datagen build writes features relative to its working directory, so run
    # the engine from the directory that contains the features/ folder.
    engine = subprocess.Popen(
        [str(Path(args.engine).resolve())],
        cwd=str(Path(args.out).resolve().parent),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
    )
    _uci(engine, "uci")
    _uci(engine, "setoption name Use NNUE value true")  # NNUE labels the data (teacher)
    for i in range(args.games):
        play_game(engine, args.depth, rng, args.max_plies)
        if (i + 1) % 10 == 0:
            print(f"  played {i + 1}/{args.games} games")
    _uci(engine, "quit")
    engine.wait()

    files = list(Path(args.out).glob("*.features"))
    rows = sum(f.stat().st_size // (200 * 2) for f in files)
    print(f"done: {len(files)} feature files, ~{rows} feature rows in {args.out}")


if __name__ == "__main__":
    main()
