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

```bash
pip install -r requirements.txt
python -m chessbot                # standard UCI, pure Python (~8k nodes/sec)
```

Point a GUI at `python -m chessbot`, or type UCI commands directly:

```
uci
position startpos moves e2e4 e7e5
go movetime 2000
```

## Reproduce the training

The full loop - build -> self-play -> extract features -> train -> quantize ->
recompile - is scripted and documented in
[pipeline/README.md](pipeline/README.md).

## Tests

```bash
python -m pytest      # perft, evaluation, mates, tactics, UCI, and the native bridge
```

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
