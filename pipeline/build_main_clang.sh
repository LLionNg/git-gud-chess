#!/usr/bin/env bash
#
# Build the 16-wide `main` engine with clang-19 on Linux - Lgeu's exact toolchain.
#
# This reproduces "Path 2". It demonstrates that the public 16-wide branch is a
# broken dev snapshot: built with the author's own compiler (clang 19) and target
# (x86_64-linux-gnu), loaded with his own 065d submission weights, the engine still
# hangs a free queen and opens a2a3. Run it from a WSL Ubuntu shell.
#
# Usage:  bash pipeline/build_main_clang.sh [BRANCH]     # BRANCH defaults to main
set -euo pipefail

BRANCH="${1:-main}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
FORK="$REPO/kaggle-stockfish"
NOTEBOOK="$(ls "$REPO"/reference/kaggle_solution/*065d* 2>/dev/null | head -1 || true)"
CLANG="$HOME/clang19"
BUILD="$HOME/sf-$BRANCH"

# 1. clang-19 (no sudo needed): download the official LLVM release once into ~/clang19.
if [ ! -x "$CLANG/bin/clang++" ]; then
  echo ">> installing clang-19 into $CLANG (one-time, ~1.2GB) ..."
  url=https://github.com/llvm/llvm-project/releases/download/llvmorg-19.1.7/LLVM-19.1.7-Linux-X64.tar.xz
  curl -fL --retry 3 -o /tmp/llvm19.tar.xz "$url"
  mkdir -p "$CLANG"
  tar -xf /tmp/llvm19.tar.xz -C "$CLANG" --strip-components=1
  rm -f /tmp/llvm19.tar.xz
fi
export PATH="$CLANG/bin:/usr/bin:/bin"
echo ">> $(clang++ --version | head -1)"

# 2. Export the branch's source tree (leaves your working checkout untouched).
git -C "$FORK" fetch --quiet origin "$BRANCH:$BRANCH" 2>/dev/null || true
rm -rf "$BUILD" && mkdir -p "$BUILD"
git -C "$FORK" archive "$BRANCH" | tar -x -C "$BUILD"

# 3. Write Lgeu's real 065d submission params (16-wide) straight from the notebook.
if [ -z "$NOTEBOOK" ]; then echo "!! 065d notebook not found under reference/"; exit 2; fi
python3 - "$NOTEBOOK" > "$BUILD/src/params.h" <<'PY'
import json, sys
nb = json.load(open(sys.argv[1], encoding="utf-8"))
text = ""
for cell in nb.get("cells", []):
    for out in cell.get("outputs", []):
        chunk = out.get("text") or (out.get("data", {}) or {}).get("text/plain") or ""
        if isinstance(chunk, list):
            chunk = "".join(chunk)
        if "PARAMS_BIAS1" in chunk:
            text = chunk
lines = text.splitlines()
start = next(i for i, l in enumerate(lines) if "#define PARAMS_BIAS1" in l)
end = next(i for i, l in enumerate(lines) if "#define PARAMS_BIAS3" in l)
print("\n".join(lines[start:end + 1]))
PY
echo ">> params.h: $(grep -c 'define PARAMS_' "$BUILD/src/params.h") macros (16-wide)"

# 4. Build. LTO needs a linker that understands LLVM bitcode; the release tarball
#    ships no gold plugin, so link with lld instead of GNU ld.
cd "$BUILD/src"
make -j"$(nproc)" build ARCH=x86-64-bmi2 COMP=clang EXTRALDFLAGS='-fuse-ld=lld'

echo
echo ">> built $BUILD/src/stockfish"
echo ">> play it (standard UCI; AUNN eval via 'Use NNUE value false'):"
echo "     cd $BUILD/src && ./stockfish"
echo "     uci"
echo "     setoption name Use NNUE value false"
echo "     position startpos"
echo "     go depth 12"
