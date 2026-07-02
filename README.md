# chessbot

A clean, UCI-compatible chess engine that reconstructs the **method** of Lgeu's
top-3 solution to the [FIDE & Google Efficient Chess AI Challenge](https://www.kaggle.com/competitions/fide-google-efficiency-chess-ai-challenge).

It plays real chess out of the box, runs in any UCI GUI, and is structured so the
evaluation can grow from a hand-crafted function toward the small learned network
the reference solution used.

---

## What this is (and what the reference actually contained)

The `reference/kaggle_solution/` folder holds the 34 Kaggle notebooks that were
downloaded as "the solution". Reviewing them shows they are the **training and
data-generation pipeline only** — every notebook clones and compiles a *private*
C++ Stockfish fork:

```python
PERSONAL_ACCESS_TOKEN = UserSecretsClient().get_secret("PERSONAL_ACCESS_TOKEN")
!git clone https://Lgeu:{TOKEN}@github.com/Lgeu/kaggle-stockfish.git  # private, unavailable
```

So the actual engine — move generation, search, and the evaluation that reads the
trained weights — was **never included** and cannot be cloned. What the notebooks
*do* reveal is the architecture:

> Stockfish's classical (hand-crafted) evaluation terms → a small quantized neural
> network → a scalar score → alpha-beta search → a UCI interface.

`chessbot` is a faithful, self-contained reconstruction of that architecture in
clean Python. It does **not** reuse the reference's private C++ or its trained
`params.h` (those weights are meaningless without the exact C++ feature
extractor). See [`reference/README.md`](reference/README.md) for the full review.

## Architecture

Evaluation sits behind a **base provider** so search never depends on how a
position is scored:

- **`ClassicalEvaluator`** (default) — a tapered hand-crafted evaluation whose
  terms mirror the reference's feature families: material + piece-square tables,
  mobility, king safety, pawn structure, and piece bonuses.
- **`NeuralEvaluator`** — a faithful NumPy port of the reference **AUNN** network
  (per-side shared embedding → side-to-move ordering → clamped hidden layer →
  scalar). It loads trained weights; without them the factory falls back to the
  classical evaluator. Training is phase 2 (below).

The integer/deployment form of that network, `QuantizedAunn`, is a **bit-exact**
port of the reference's `QuantizedAUNN`: rebuilt from the trained `params.h` the
notebooks printed, it reproduces their own recorded test vectors exactly
(`tests/test_reference_fidelity.py`). That is the check that this project's
reconstruction of the reference *pipeline logic* stays faithful.

The search is a modern alpha-beta: iterative deepening, transposition table,
principal-variation search, null-move pruning, late-move reductions, check
extensions, quiescence, killer/history move ordering, and clock-based time
management.

```
chessbot/
├── config.py             # Pydantic engine/search/eval configuration
├── engine.py             # high-level facade (position, search, options)
├── __main__.py           # `python -m chessbot` -> UCI loop
├── core/types.py         # score constants, mate helpers, game phase
├── evaluation/
│   ├── base.py           # Evaluator ABC (base provider)
│   ├── classical.py      # tapered hand-crafted evaluator
│   ├── tables.py         # piece values + piece-square tables
│   ├── terms/            # material, mobility, king_safety, pawn_structure, pieces
│   └── neural/           # AUNN port: features, network, evaluator
├── search/
│   ├── searcher.py       # iterative-deepening alpha-beta
│   ├── ordering.py       # MVV-LVA + killers + history
│   ├── transposition.py  # transposition table
│   └── limits.py         # search limits + result
└── uci/protocol.py       # UCI protocol adapter
```

> **On "ORM":** a UCI engine has no persistent datastore, so an ORM would add
> weight without purpose. Configuration is typed and validated with **Pydantic**
> instead; persistence (opening books, game archives) can be added later if needed.

## Install

```bash
pip install -r requirements.txt      # runtime: python-chess, pydantic, numpy
# or, as a package:  pip install -e .
```

## Usage

**As a UCI engine (any GUI — Arena, Cute Chess, BanksiaGUI, en-croissant):**
point the GUI at the command `python -m chessbot`.

**From a terminal:**

```
python -m chessbot
uci
position startpos moves e2e4 e7e5
go movetime 2000
```

**From Python:**

```python
from chessbot.engine import Engine
from chessbot.search import SearchLimits

engine = Engine()
engine.set_position(moves=["e2e4", "e7e5"])
result = engine.search(SearchLimits(movetime_ms=2000))
print(result.best_move, result.score, result.pv)
```

**Native backend — the replicated original engine (much faster):**

The reference solution's C++ engine (Lgeu's now-public Stockfish fork) can be
built locally and driven through a standard-UCI bridge, so any GUI can use it:

```bash
export PATH="/c/mingw64/bin:$PATH"     # a MinGW-w64 GCC
bash pipeline/setup_engine.sh          # clone + build the fork (~1 min)
python -m chessbot.native              # standard UCI -> fast native engine (~780k nps)
```

`chessbot.native` translates standard UCI to the fork's shortened dialect and
selects its trained AUNN evaluation. See [pipeline/README.md](pipeline/README.md)
for the full reproduction of the original method (build → self-play → train →
quantize → recompile).

### UCI options

| Option | Default | Meaning |
|---|---|---|
| `Hash` | 64 | Transposition table size (MB) |
| `Move Overhead` | 30 | Milliseconds reserved for process/GUI latency |
| `Evaluator` | classical | `classical` or `neural` (neural needs trained weights) |

## Strength and limitations

The engine is correct and robust: perft-validated move generation, verified mate
finding, sound tactics, proper draw handling, and clean full games with no
illegal moves or crashes. Raw speed is bounded by Python (~8k nodes/sec), so it
reaches depth 6–8 under normal time controls — a solid club-level opponent rather
than a match for the reference's hand-optimized C++ binary. The clean separation
(especially the evaluation provider) is the intended trade: clarity and
extensibility over maximum node throughput.

## Phase 2: training the neural evaluator

The network architecture is complete and its quantized inference is validated
bit-exact against the reference (above); only trained weights are missing. The
reference approach, reproducible here, is:

1. Extract features (`chessbot/evaluation/neural/features.py`) over many positions.
2. Label them with a stronger reference (self-play results or a teacher engine).
3. Train `AunnNetwork` (a small MLP) to predict the label, then save weights.
4. Optionally quantize to `QuantizedAunn` (the reference's integer form).
5. Run with `Evaluator=neural` and `evaluation.weights_path` set.

The `[train]` extra (`pip install -e ".[train]"`) adds `torch` and `tqdm` for this.

## Testing

```bash
python -m pytest        # 40 tests: perft, evaluation symmetry, mates, tactics, UCI, neural
```

## Credits

Method and architecture inspired by **Lgeu (nagiss)**'s FIDE & Google Efficient
Chess AI Challenge solution. Move generation by
[python-chess](https://github.com/niklasf/python-chess). Piece-square tables are
the public PeSTO values. This project contains none of the reference's private
source. MIT-licensed.
