#!/usr/bin/env bash
# Reproducibly build Lgeu's (now-public) Kaggle Stockfish fork on Windows.
#
# Prereqs: git + curl (bundled with Git Bash) and a compiler on PATH.
#   - COMP=mingw (default): a MinGW-w64 GCC, e.g. C:\mingw64\bin
#   - COMP=clang:           an llvm-mingw clang, e.g. C:\llvm-mingw\bin
#     (needed to compile the 16-wide `main`/`tmp` branches, which GCC 16 rejects)
#
# Env:  BRANCH (default nn-last-spurt, the strong 32-wide engine),  COMP (mingw|clang)
# Run from the repo root:  bash pipeline/setup_engine.sh
set -euo pipefail

FORK_DIR="kaggle-stockfish"
BRANCH="${BRANCH:-nn-last-spurt}"
COMP="${COMP:-mingw}"
NET="nn-5af11540bbfe.nnue"

# Put both toolchains on PATH so `mingw32-make` (GCC pkg) and clang are found.
export PATH="/c/llvm-mingw/bin:/c/mingw64/bin:$PATH"

# 1. Clone/checkout the requested branch of the fork (public since the competition).
if [ ! -d "$FORK_DIR" ]; then
    git clone --depth 1 --branch "$BRANCH" --single-branch \
        https://github.com/Lgeu/kaggle-stockfish.git "$FORK_DIR"
else
    git -C "$FORK_DIR" fetch --depth 1 origin "$BRANCH"
    git -C "$FORK_DIR" checkout -B "$BRANCH" FETCH_HEAD
fi
cd "$FORK_DIR/src"

# 2. Windows portability shim (POSIX flockfile -> CRT _lock_file), used by two files.
cp "../../pipeline/win_compat.h" win_compat.h
grep -q win_compat.h bitboard.cpp || sed -i '/#include <cassert>/a #include "win_compat.h"' bitboard.cpp
grep -q win_compat.h search.cpp   || sed -i '/#include "uci.h"/a #include "win_compat.h"' search.cpp

# 3. Fetch the NNUE net (embedded via incbin at compile time; GitHub mirror is fast).
[ -f "$NET" ] || curl -skL -o "$NET" "https://github.com/official-stockfish/networks/raw/master/$NET"

# 4. Build the playing engine (uses the trained AUNN eval when "Use NNUE" is false).
mingw32-make clean >/dev/null 2>&1 || true
mingw32-make -j"$(nproc)" build ARCH=x86-64-bmi2 COMP="$COMP"
cp stockfish.exe ../stockfish_play.exe

# 5. Build the training-data generator (dumps 200 features/position while searching).
mingw32-make clean >/dev/null
CXXFLAGS="-DGENERATE_TRAINING_DATA -DSUPPRESS" mingw32-make -j"$(nproc)" build ARCH=x86-64-bmi2 COMP="$COMP"
cp stockfish.exe ../stockfish_gen.exe

echo
echo "Built ($BRANCH, COMP=$COMP): $FORK_DIR/stockfish_play.exe and stockfish_gen.exe"
echo "Note: nn-last-spurt's UCI is shortened -- 'po fen <FEN>' / 'go depth N' / 'go wtm <ms>'."
