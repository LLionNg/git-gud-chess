"""Train the AUNN on generated features and emit params.h - the reference loop.

Faithful to notebook 065d: loads the ``*.features`` files the datagen engine
wrote, targets ``nnue_raw_value - winnable`` (the NNUE teacher minus the winnable
term), trains the extracted ``AUNN``, quantizes it, and prints ``params.h``.
Recompiling the engine with that header closes the self-play -> train -> quantize
-> rebuild loop.

Demo scale only: a few thousand rows and few epochs yield weak weights. The
reference used tens of millions of positions; run at scale for real strength.

Usage:
    python pipeline/train.py --features kaggle-stockfish/src/features \\
        --epochs 30 --out kaggle-stockfish/src/params.h
"""

from __future__ import annotations

import argparse
import contextlib
import glob
import os
import sys

import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(__file__))
from aunn_model import (  # noqa: E402  (extracted verbatim from notebook 065d)
    AUNN,
    QuantizedAUNN,
    adder_features,
    black_cols,
    coefs,
    common_cols,
    feature_names,
    replacement,
    white_cols,
)


def load_features(feature_dir: str) -> np.ndarray:
    n = len(feature_names)
    rows = []
    for path in sorted(glob.glob(os.path.join(feature_dir, "*.features"))):
        data = np.fromfile(path, dtype=np.int16)
        rows.append(data[: data.size // n * n].reshape(-1, n))
    if not rows:
        raise SystemExit(f"no .features files in {feature_dir}")
    return np.concatenate(rows, axis=0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", default="kaggle-stockfish/src/features")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--lr", type=float, default=1e-2)
    parser.add_argument("--out", default="kaggle-stockfish/src/params.h")
    args = parser.parse_args()

    feature_to_index = {name: i for i, name in enumerate(feature_names)}
    data_np = load_features(args.features)
    print(f"loaded {data_np.shape[0]} feature rows x {data_np.shape[1]}")

    data = torch.from_numpy(data_np)
    # Target: NNUE teacher value minus the winnable term, in pawns/256 (as in 065d).
    nnue_idx, winnable_idx = feature_to_index["nnue_raw_value"], feature_to_index["winnable"]
    target = (data[:, nnue_idx].to(torch.int32) - data[:, winnable_idx].to(torch.int32))
    target = (target.to(torch.float32) / 256.0)

    stats = data[::5].float()
    feature_means, feature_stds = stats.mean(0), stats.std(0).clamp(min=1e-6)
    feature_maxs = stats.abs().max(0).values.clamp(min=1.0)

    # Fixed (Stockfish-coefficient) part of the model, exactly as the notebook builds it.
    fixed_weight = torch.full((len(feature_names), 2), -10000.0)
    for col, values in coefs.items():
        v = torch.tensor(values, dtype=torch.float32)
        if col in feature_to_index:
            fixed_weight[feature_to_index[col]] = v
        else:
            fixed_weight[feature_to_index[col + "_0"]] = v
            fixed_weight[feature_to_index[col + "_1"]] = v

    model = AUNN(white_cols, black_cols, common_cols, "side_to_move",
                 feature_means, feature_stds, feature_maxs, feature_to_index,
                 fixed_weight, torch.zeros(2), adder_features, feature_names, replacement)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    criterion = nn.MSELoss()
    n = data.shape[0]
    for epoch in range(args.epochs):
        perm = torch.randperm(n)
        total = 0.0
        model.train()
        for i in range(0, n - args.batch_size + 1, args.batch_size):
            idx = perm[i : i + args.batch_size]
            optimizer.zero_grad()
            out = model(data[idx])
            loss = criterion(out / 256.0, target[idx])
            loss.backward()
            optimizer.step()
            model.clip()
            total += loss.item()
        scheduler.step()
        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"  epoch {epoch + 1}/{args.epochs}  loss {total / max(1, n // args.batch_size):.4f}")

    # Quantize and write params.h (QuantizedAUNN.print() emits the C macros).
    model.eval()
    model.replacement_color_mask_for_forward = model.replacement_color_mask_for_forward.cpu()
    model.replacement_common_mask_for_forward = model.replacement_common_mask_for_forward.cpu()
    qmodel = QuantizedAUNN(model.cpu())
    with open(args.out, "w", encoding="utf-8") as fh, contextlib.redirect_stdout(fh):
        qmodel.print()
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
