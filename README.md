# chessbot

A replication of **Lgeu (nagiss)'s top-3 solution** to the
[FIDE & Google Efficient Chess AI Challenge](https://www.kaggle.com/competitions/fide-google-efficiency-chess-ai-challenge),
plus a clean Python re-implementation of the same method.

## How it works - is it an "AI model"?

It is a chess **engine** = *search* + *evaluation*, and it is a **hybrid** - not a
pure deep-learning system:

| Part | What it is | Learned? |
|---|---|---|
| **Search** | Classical alpha-beta game-tree search (a trimmed Stockfish) that looks ahead through millions of positions | No - hand-written |
| **Evaluation** | ~200 hand-crafted Stockfish features (material, piece-square tables, mobility, king safety, pawn structure, threats, passed pawns, ...) fed into a **small trained neural network** that outputs the score | **Yes** |

**Does it have a real deep-learning model?** Yes - a genuine but *small* neural
network: a multi-layer perceptron (each side's features -> a 16-dim embedding ->
a 32-wide hidden layer -> one score, a few thousand weights). It is not a large
deep net, and it reads hand-crafted features rather than the raw board. It is a
compact cousin of Stockfish's NNUE.

**Does it need training?** The weights are the *result* of training, so training
happened once - but you **do not need to train it to run it**. The trained
weights are quantized to integers and compiled into the engine (`params.h`); at
play time the evaluation is pure integer arithmetic (no PyTorch). You train only
to re-derive or improve the weights.

*How the weights were trained (knowledge distillation):* self-play produces
millions of positions; each is labelled with Stockfish's strong **NNUE**
evaluation (the "teacher"); the small net is trained in PyTorch to reproduce that
score from the 200 cheap features; then it is quantized. This lets a tiny net
mimic a 40 MB NNUE while fitting the competition's 64 KiB limit.

## Run it

Two engines live here: the **original C++ solution** (fast, plays with the trained
network) and a **clean Python re-implementation** (readable, plays with a
hand-crafted evaluation).

### 1. The original engine - the actual solution

Needs a MinGW-w64 GCC on `PATH` (installed at `C:\mingw64`). Build once, then play:

```bash
export PATH="/c/mingw64/bin:$PATH"
bash pipeline/setup_engine.sh     # clone Lgeu's fork + build (~1 min)
python -m chessbot.native         # standard UCI -> the engine (~780k nodes/sec)
```

`python -m chessbot.native` lets any chess GUI (Arena, Cute Chess, ...) drive it
with standard UCI, using the trained neural evaluation.

### 2. The Python re-implementation

With [uv](https://docs.astral.sh/uv/) (creates the environment for you):

```bash
uv run python -m chessbot         # standard UCI, pure Python (~8k nodes/sec)
```

Or with pip:

```bash
pip install -r requirements.txt
python -m chessbot
```

Point a GUI at `uv run python -m chessbot` (or `python -m chessbot`), or type UCI
commands directly:

```
uci
position startpos moves e2e4 e7e5
go movetime 2000
```

## Training your own model

You do not need to train anything to play (both engines ship with trained weights).
Run `uv sync` once to install the training deps (including torch). There are two
training loops, depending on which engine you want to feed.

### A. The Python engine - a complete, self-contained loop

This distils a teacher evaluation into `chessbot`'s own small network (Lgeu's
knowledge-distillation method at small scale), then plays the result. No C++ engine
required:

```bash
# train: play positions, label them with a teacher, fit the net -> weights.npz
uv run python pipeline/train_python.py --positions 8000 --epochs 120 --out weights.npz

# play it: the neural evaluator loads the weights over standard UCI
uv run python -m chessbot --weights weights.npz
```

The teacher defaults to the built-in classical evaluation (pure Python); to distil
a stronger engine instead, pass `--teacher-engine /path/to/stockfish`. The trained
net finds tactics (wins a free queen) and tracks its teacher closely - train on
more positions/epochs for strength.

### B. The original C++ network - reference reproduction

This reproduces the published training of the reference's private ~200-feature net
and emits its `params.h`:

```bash
# 1. self-play that dumps 200-feature positions, labelled by the NNUE teacher
uv run python pipeline/generate_data.py --engine kaggle-stockfish/stockfish_gen.exe --games 500 --depth 12

# 2. train the AUNN + quantize -> your own params.h
uv run python pipeline/train.py --features kaggle-stockfish/src/features --epochs 300 --out my_params.h
```

This faithfully reproduces notebook `065d` (the final submission's trainer) and
writes a valid 16-wide `my_params.h`. **There is, however, no working engine to
deploy it into, and this was verified exhaustively.** The public 16-wide branches
(`main`, `tmp`, `cherry-pick-optimization`) are unfinished dev snapshots: built
with the author's *exact* compiler (clang 19) on Linux (his target) and loaded with
his *own* final-submission weights, they still hang a free queen and open `a2a3`.
The only strong, working engine, `nn-last-spurt` (the shipped `stockfish_play.exe`),
uses a wider 32-wide network whose training notebook was never published. So
`my_params.h` is a real trained model, but the C++ train -> play loop cannot be
closed from public materials - play with the shipped `stockfish_play.exe` (the
author's own weights) instead.

#### Reproducing the clang-19 build yourself

The 16-wide `main` engine is a Linux binary, so build and run it from WSL Ubuntu.
`pipeline/build_main_clang.sh` installs clang-19 (once), fetches `main`, bakes in
Lgeu's 065d weights, and builds `~/sf-main/src/stockfish` (~1 min):

```bash
wsl                                              # enter Ubuntu
bash /mnt/e/GitHub/chessbot/pipeline/build_main_clang.sh
```

Then play it over standard UCI:

```bash
cd ~/sf-main/src
./stockfish
```

and type:

```
uci
setoption name Use NNUE value false
position startpos
go depth 12
```

Or one-shot from Windows PowerShell, no WSL prompt needed:

```powershell
wsl bash -c "printf 'setoption name Use NNUE value false\nposition startpos\ngo depth 12\nquit\n' | ~/sf-main/src/stockfish"
```

It will answer `a2a3` and decline the free queen - that is the broken-branch
result described above, not a setup error.

The full loop and toolchain notes are in [pipeline/README.md](pipeline/README.md).

## Tests

```bash
uv run pytest         # or: python -m pytest
```

Covers perft, evaluation, mates, tactics, UCI, and the native bridge.

## Layout

- `chessbot/` - the Python engine (search, evaluation, UCI) and the `native` bridge to the C++ engine.
- `pipeline/` - scripts to build the original C++ fork and reproduce its training.
- `reference/` - the original Kaggle training notebooks and a review.
- `kaggle-stockfish/` - Lgeu's now-public fork (cloned locally by the setup script; not committed).

## Credits

Method and engine by **Lgeu (nagiss)** -
[github.com/Lgeu/kaggle-stockfish](https://github.com/Lgeu/kaggle-stockfish)
(GPL-3.0). The Python re-implementation uses
[python-chess](https://github.com/niklasf/python-chess) and public PeSTO
piece-square tables; it is MIT-licensed and contains none of the GPL fork, which
the setup script fetches separately.
