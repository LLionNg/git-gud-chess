#!/usr/bin/env bash
# Reproducibly build Lgeu's (now-public) Kaggle Stockfish fork on Windows/MinGW.
#
# Prereqs: git, curl (Git Bash both bundle these) and a MinGW-w64 GCC on PATH,
# e.g. C:\mingw64\bin (install WinLibs GCC, then `export PATH="/c/mingw64/bin:$PATH"`).
# Run from the repo root:  bash pipeline/setup_engine.sh
set -euo pipefail

FORK_DIR="kaggle-stockfish"
BRANCH="nn-last-spurt"   # the final 32-wide engine; use `main` for the 16-wide (065d) net
NET="nn-5af11540bbfe.nnue"

# 1. Clone the fork (the source that was private during the competition, now public).
[ -d "$FORK_DIR" ] || git clone --depth 1 --branch "$BRANCH" --single-branch \
    https://github.com/Lgeu/kaggle-stockfish.git "$FORK_DIR"
cd "$FORK_DIR/src"

# 2. Windows portability shim (POSIX flockfile -> CRT _lock_file), used by two files.
cp "../../pipeline/win_compat.h" win_compat.h
grep -q win_compat.h bitboard.cpp || sed -i '/#include <cassert>/a #include "win_compat.h"' bitboard.cpp
grep -q win_compat.h search.cpp   || sed -i '/#include "uci.h"/a #include "win_compat.h"' search.cpp

# 3. Fetch the NNUE net (embedded via incbin at compile time; the GitHub mirror is fast).
[ -f "$NET" ] || curl -skL -o "$NET" "https://github.com/official-stockfish/networks/raw/master/$NET"

# 4. Build the playing engine (uses the trained AUNN eval when "Use NNUE" is false).
mingw32-make -j"$(nproc)" build ARCH=x86-64-bmi2 COMP=mingw
cp stockfish.exe ../stockfish_play.exe

# 5. Build the training-data generator (dumps 200 features/position while searching).
mingw32-make clean >/dev/null
CXXFLAGS="-DGENERATE_TRAINING_DATA -DSUPPRESS" mingw32-make -j"$(nproc)" build ARCH=x86-64-bmi2 COMP=mingw
cp stockfish.exe ../stockfish_gen.exe

echo
echo "Built: $FORK_DIR/stockfish_play.exe (play) and stockfish_gen.exe (datagen)"
echo "Note: this fork's UCI is shortened -- use 'po fen <FEN>' / 'po startpos moves ...'"
echo "      and 'go depth N' / 'go wtm <ms> btm <ms>' (not 'position'/'wtime')."
