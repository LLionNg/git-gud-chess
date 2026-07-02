# Reference: Lgeu's Kaggle solution (review)

`kaggle_solution/` holds the 34 notebooks downloaded as a top-3 solution to the
FIDE & Google Efficient Chess AI Challenge. This note records what they contain,
because it determines what could and could not be reproduced.

## The notebooks are a training pipeline, not the engine

Every notebook orchestrates a **private** C++ Stockfish fork that is never
included:

```python
!git clone https://Lgeu:{TOKEN}@github.com/Lgeu/kaggle-stockfish.git
!git checkout nn
```

| Notebooks | Role |
|---|---|
| `chess-042` | Build the engine from the private repo; package `main.py` + a stripped, gzipped `stockfish_s` binary |
| `chess-043*` (14), `chess-053*` (7), `chess-059*` (2) | Self-play with `-DGENERATE_TRAINING_DATA` to dump ~224 evaluation features per position |
| `chess-058b/058c` | Rebuild the engine embedding a trained `params.h` (the quantized weights) |
| `chess-064*` (8) | Shard the feature files by `row % 8` |
| `chess-065d` | Train the small **AUNN** network (features -> NNUE value), quantize, and print `params.h` |

## What is present vs. missing

**Present in the notebooks:** the AUNN model, its quantization and training loop
(`065d`); the exact ~224-feature taxonomy and Stockfish base coefficients; two
full trained `params.h` weight sets (`058b/c`); the `main.py` UCI subprocess
driver; and the compile/packaging flags.

**Missing and unobtainable:** the entire C++ engine - move generation, search,
and the `evaluate.cpp` that both computes the 224 features and runs the quantized
network. Also missing: the multi-GB self-play datasets, the teacher NNUE file,
and the Kaggle-only dependencies (`kaggle_environments`, `kaggle_secrets`, the
private token). The trained `params.h` is unusable without the identical C++
feature extractor that produces its exact input vector.

## Conclusion

Exact replication of the competition binary is impossible from these files. The
*method*, however, is fully legible and is what `chessbot` reconstructs in clean
Python: classical evaluation features -> a small (optionally learned) network ->
alpha-beta search -> UCI. The reconstruction shares none of the private source.

## Fidelity check

Where the notebooks *do* contain runnable logic - the `QuantizedAUNN` integer
inference - the reconstruction is verified against it. `chessbot`'s `QuantizedAunn`
is rebuilt from the trained `params.h` printed in notebook 065d (cell 6) and
reproduces that notebook's own recorded outputs bit-for-bit: the per-feature
embedding contributions (cell 8) and the two-layer head result (cell 10, `-132`).
See `tests/test_reference_fidelity.py`.
