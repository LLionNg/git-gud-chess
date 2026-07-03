# chessbot

A clean, dependency-light **UCI chess engine in Python**: a classical hand-crafted
evaluation and an alpha-beta search, plus an optional small trained neural
evaluator. It drops into any chess GUI and is easy to read and extend.

## Run it

With [uv](https://docs.astral.sh/uv/) (it creates the environment for you):

```bash
uv run python -m chessbot          # standard UCI over stdin/stdout
```

Or with pip:

```bash
pip install -r requirements.txt
python -m chessbot
```

Point a GUI (Arena, Cute Chess, ...) at `uv run python -m chessbot`, or type UCI
commands directly:

```
uci
position startpos moves e2e4 e7e5
go movetime 2000
```

## How it works - is it an "AI model"?

It is a chess **engine** = *search* + *evaluation*, and it is a **hybrid** - not a
pure deep-learning system:

| Part | What it is | Learned? |
|---|---|---|
| **Search** | Classical alpha-beta game-tree search (transposition table, PVS, null-move, LMR, quiescence) | No - hand-written |
| **Evaluation** | A hand-crafted tapered score (material, piece-square tables, mobility, king safety, pawn structure) by default, or an optional small **trained neural network** over the same kind of features | Optional |

The default evaluation is fully hand-crafted and needs no training. The optional
neural evaluator is a genuine but *small* network - a multi-layer perceptron (each
side's features -> a 16-dim embedding -> a 32-wide clamped hidden layer -> one
score, a few thousand weights). It reads hand-crafted features rather than the raw
board, so it is a compact cousin of a full NNUE, not a large deep net.

## The neural evaluator (optional)

Train a network and play with it - a self-contained loop in pure Python:

```bash
uv sync                            # once: installs training deps (torch)

# train: play positions, label them with a teacher, fit the net -> weights.npz
uv run python training/train.py --positions 8000 --epochs 120 --out weights.npz

# play it: the neural evaluator loads the weights over standard UCI
uv run python -m chessbot --weights weights.npz
```

It uses **knowledge distillation**: each sampled position is labelled with a
teacher evaluation, and the small network is trained to reproduce that score from
cheap features. The teacher defaults to the built-in classical evaluation (pure
Python); pass `--teacher-engine /path/to/stockfish` to distil a stronger standard-
UCI engine instead. Train on more positions/epochs for more strength.

At play time you can also select it over UCI:

```
setoption name Evaluator value neural
setoption name EvalFile value weights.npz
```

## Tests

```bash
uv run pytest          # or: python -m pytest
```

Covers perft, evaluation, mates, tactics, UCI, and the neural provider.

## Layout

- `chessbot/` - the engine: `core`, `evaluation` (classical + `neural`), `search`, `uci`.
- `training/` - the neural distillation trainer.
- `tests/`.

## Credits

Method inspired by **Lgeu (nagiss)'s** FIDE & Google Efficient Chess AI Challenge
solution. Built on [python-chess](https://github.com/niklasf/python-chess) and
public PeSTO piece-square tables. MIT-licensed.
