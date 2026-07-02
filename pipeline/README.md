# Reproducing the original method (C++ Stockfish fork)

The reference solution's engine was a **private** C++ Stockfish fork during the
competition — which is why it could not be replicated earlier. It has since been
**made public** at [`github.com/Lgeu/kaggle-stockfish`](https://github.com/Lgeu/kaggle-stockfish),
so the exact original method is now fully reproducible. This directory contains
the scripts that do it, all verified working on Windows/MinGW.

## The full loop (all four stages verified)

```
                 setup_engine.sh                 generate_data.py
 fork (public) ───────────────► stockfish_gen ──────────────────► features/*.features
                                     ▲                                   │
                                     │ recompile (params.h)              │ train.py
                                     └───────────── params.h ◄───────────┘  (AUNN → quantize)
```

1. **Build the engine** — `bash pipeline/setup_engine.sh`
   Clones the fork, applies a small Windows portability shim (`win_compat.h`),
   downloads the NNUE net, and builds two binaries: `stockfish_play.exe` (plays
   with the trained AUNN evaluation) and `stockfish_gen.exe` (the
   `-DGENERATE_TRAINING_DATA` build that dumps features).
   *Verified:* plays legal chess at ~780k nps, bench passes, detects mate.

2. **Generate training data** — `python pipeline/generate_data.py --engine kaggle-stockfish/stockfish_gen.exe`
   Self-play whose searches dump each sampled position's **200 Stockfish features**
   (labelled by the NNUE teacher) to `features/*.features` — the exact int16×200
   format the notebooks consume.

3. **Train + quantize** — `python pipeline/train.py --features kaggle-stockfish/src/features`
   Runs the reference's own `AUNN` (extracted verbatim into `aunn_model.py` from
   notebook 065d), then `QuantizedAUNN.print()` to emit `params.h`.

4. **Recompile** — drop the new `params.h` into `kaggle-stockfish/src/` and rerun
   the build. *Verified:* the engine rebuilds and plays with the new weights.

## Do we have everything? Yes — with one version note

Everything needed is present: the fork is public, GCC/make installed, the NNUE
teacher downloads, and the training notebook (065d) is in `reference/`.

The one alignment detail: the **provided notebook (065d) is a 16-wide-embedding
iteration** whose `QuantizedAUNN.print()` emits 16 values per feature. It matches
the fork's **`main` branch**. The fork's final **`nn-last-spurt` branch is a later
32-wide iteration** (the strongest engine, and what `setup_engine.sh` builds by
default). So:

- Building `nn-last-spurt` (32-wide) and playing with its committed `params.h`:
  **works, strong** — this is the replicated original engine.
- Retraining end-to-end with 065d (16-wide) matches the `main` branch. `main`'s
  older SIMD code trips strict GCC 16 (`__m256`/`__m256i`); build it with clang or
  an older GCC, or use the 32-wide training notebook (066+, not in the provided
  set) to retrain `nn-last-spurt`.

The `train.py` demo runs at tiny scale (a few thousand positions, few epochs) and
so yields weak weights; the reference used tens of millions of positions.

## Custom UCI

This fork shortens UCI to save bytes: use `po fen <FEN>` / `po startpos moves ...`
(not `position`) and `go depth N` / `go wtm <ms> btm <ms>` (not `wtime`). Set
`setoption name Use NNUE value false` to evaluate with the trained AUNN.

For a standard-UCI frontend (any GUI), run `python -m chessbot.native`, which
translates to this dialect and drives the built engine.

## The 64 KiB "efficient" submission

The competition capped submissions at 64 KiB. Because the engine evaluates with
the AUNN (not NNUE), the 40 MB net is dropped via `CXXFLAGS=-DMINIMIZE`, giving a
tiny binary. Reproduced here it compiles to **346 KB stripped / 149 KB gzip**;
the reference reached ~58 KB with UPX (LZMA).

Platform note: the `MINIMIZE` build was only ever built/run on **Linux + clang**.
Under **Windows + MinGW GCC 16** it compiles (after two portability fixes:
`win_compat.h` outside the `MINIMIZE` guard, and an `<iostream>`→`fprintf` swap in
`misc.cpp`) but **segfaults at runtime**. A working 64 KiB submission therefore
needs the reference's Linux/clang environment (e.g. WSL) plus UPX. The full-size
playing engine (`stockfish_play.exe`) is unaffected and is the one to use.
