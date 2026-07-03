"""Train the neural evaluator by knowledge distillation.

Play out positions, label each with a teacher evaluation, then fit the small AUNN
so it reproduces the teacher from cheap hand-crafted features. The trained float
weights are saved as ``.npz`` and loaded directly by :class:`NeuralEvaluator` --
a self-contained train -> play loop.

Usage:
    uv run python training/train.py --positions 8000 --epochs 120 --out weights.npz
    # distil a strong standard-UCI engine instead of the classical eval:
    uv run python training/train.py --teacher-engine /path/to/stockfish
"""

from __future__ import annotations

import argparse
import os
import random
import sys

import chess
import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from chessbot.config import EvaluationConfig  # noqa: E402
from chessbot.evaluation.classical import ClassicalEvaluator  # noqa: E402
from chessbot.evaluation.neural import features as F  # noqa: E402
from chessbot.evaluation.neural.network import CLAMP, EMBEDDING_DIM, HIDDEN_DIM, AunnNetwork  # noqa: E402

N_PAIRED = len(F.PAIRED_FEATURES)
N_COMMON = len(F.COMMON_FEATURES)


class TorchAunn(nn.Module):
    """Trainable mirror of :class:`AunnNetwork`'s forward pass.

    Trains on *normalized* features for stable gradients; the normalization is
    later folded into the exported raw-feature weights so the numpy network needs
    no runtime normalization.
    """

    def __init__(self) -> None:
        super().__init__()
        self.color = nn.Linear(N_PAIRED, EMBEDDING_DIM, bias=False)
        self.common = nn.Linear(N_COMMON, EMBEDDING_DIM, bias=True)  # bias plays the embed bias
        self.hidden = nn.Linear(2 * EMBEDDING_DIM, HIDDEN_DIM)
        self.out = nn.Linear(HIDDEN_DIM, 1)
        # Positive embed bias keeps clipped-ReLU units alive at the start of training.
        nn.init.constant_(self.common.bias, 40.0)

    def forward(self, white: torch.Tensor, black: torch.Tensor,
                common: torch.Tensor, stm: torch.Tensor) -> torch.Tensor:
        common_embed = self.common(common)
        white_embed = torch.clamp(self.color(white) + common_embed, 0.0, CLAMP)
        black_embed = torch.clamp(self.color(black) + common_embed, 0.0, CLAMP)
        # The side to move fills the first half of the hidden input.
        white_to_move = (stm == 0).unsqueeze(1)
        first = torch.where(white_to_move, white_embed, black_embed)
        second = torch.where(white_to_move, black_embed, white_embed)
        hidden = torch.clamp(self.hidden(torch.cat([first, second], dim=1)), 0.0, CLAMP)
        return self.out(hidden).squeeze(1)


def _random_game_positions(rng: random.Random, out: list[str]) -> None:
    """Play one capture-biased random game, sampling positions into ``out``.

    Random play with a capture bias produces the material imbalances the net must
    learn to score; the teacher supplies the ground-truth value for each.
    """
    board = chess.Board()
    length = rng.randint(6, 60)
    for ply in range(length):
        if board.is_game_over():
            break
        legal = list(board.legal_moves)
        captures = [m for m in legal if board.is_capture(m)]
        move = rng.choice(captures) if captures and rng.random() < 0.5 else rng.choice(legal)
        board.push(move)
        if ply >= 4 and rng.random() < 0.25:
            out.append(board.fen())


def generate_positions(n: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    fens: list[str] = []
    while len(fens) < n:
        _random_game_positions(rng, fens)
    return fens[:n]


class ClassicalTeacher:
    """Pure-Python teacher: the hand-crafted evaluation, side-to-move centipawns."""

    def __init__(self) -> None:
        self._eval = ClassicalEvaluator(EvaluationConfig())

    def __call__(self, board: chess.Board) -> float:
        return float(self._eval.evaluate(board))


class UciEngineTeacher:
    """Distil a strong standard-UCI engine (e.g. Stockfish) at a fixed depth."""

    def __init__(self, path: str, depth: int) -> None:
        import chess.engine

        self._engine = chess.engine.SimpleEngine.popen_uci(path)
        self._depth = depth

    def __call__(self, board: chess.Board) -> float:
        import chess.engine

        info = self._engine.analyse(board, chess.engine.Limit(depth=self._depth))
        return float(info["score"].pov(board.turn).score(mate_score=30000))

    def close(self) -> None:
        self._engine.quit()


def label_positions(fens: list[str], teacher) -> tuple[np.ndarray, np.ndarray]:
    """Extract features and the teacher's centipawn score for every position."""
    feats = np.empty((len(fens), F.NUM_FEATURES), dtype=np.float32)
    labels = np.empty(len(fens), dtype=np.float32)
    for i, fen in enumerate(fens):
        board = chess.Board(fen)
        feats[i] = F.extract_features(board)
        labels[i] = teacher(board)
    return feats, labels


def fold_into_network(model: TorchAunn, mean_p: np.ndarray, std_p: np.ndarray,
                      mean_c: np.ndarray, std_c: np.ndarray) -> AunnNetwork:
    """Export the trained model to raw-feature weights, folding in normalization.

    The model trained on ``(x - mean) / std``; folding ``1/std`` into the weights
    and ``-mean/std`` into the bias makes the numpy network reproduce it on raw
    features -- so the numpy network needs no runtime normalization at play time.
    """
    with torch.no_grad():
        Wc = model.color.weight.t().cpu().numpy()      # (N_PAIRED, 16)
        Wcm = model.common.weight.t().cpu().numpy()     # (N_COMMON, 16)
        b = model.common.bias.cpu().numpy()             # (16,)
        color_weight = Wc / std_p[:, None]
        common_weight = Wcm / std_c[:, None]
        embed_bias = b - (mean_p / std_p) @ Wc - (mean_c / std_c) @ Wcm
        return AunnNetwork(
            color_weight=color_weight.astype(np.float32),
            common_weight=common_weight.astype(np.float32),
            embed_bias=embed_bias.astype(np.float32),
            hidden_weight=model.hidden.weight.t().cpu().numpy().astype(np.float32),
            hidden_bias=model.hidden.bias.cpu().numpy().astype(np.float32),
            output_weight=model.out.weight[0].cpu().numpy().astype(np.float32),
            output_bias=float(model.out.bias.item()),
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--positions", type=int, default=8000)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-2)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--teacher-engine", default=None,
                        help="path to a standard-UCI engine to distil (default: classical eval)")
    parser.add_argument("--teacher-depth", type=int, default=8)
    parser.add_argument("--out", default="weights.npz")
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    print(f"generating {args.positions} positions...")
    fens = generate_positions(args.positions, args.seed)

    if args.teacher_engine:
        print(f"teacher: UCI engine {args.teacher_engine} @ depth {args.teacher_depth}")
        teacher = UciEngineTeacher(args.teacher_engine, args.teacher_depth)
    else:
        print("teacher: classical hand-crafted evaluation")
        teacher = ClassicalTeacher()
    feats, labels = label_positions(fens, teacher)
    if isinstance(teacher, UciEngineTeacher):
        teacher.close()

    white = feats[:, F.WHITE_IDX]
    black = feats[:, F.BLACK_IDX]
    common = feats[:, F.COMMON_IDX]
    stm = feats[:, F.STM_IDX]

    # Shared normalization for the colour features (pool both sides), separate for common.
    pooled = np.concatenate([white, black], axis=0)
    mean_p, std_p = pooled.mean(0), pooled.std(0).clip(min=1e-6)
    mean_c, std_c = common.mean(0), common.std(0).clip(min=1e-6)

    to = lambda a: torch.from_numpy(np.ascontiguousarray(a)).float()
    white_t = to((white - mean_p) / std_p)
    black_t = to((black - mean_p) / std_p)
    common_t = to((common - mean_c) / std_c)
    stm_t = to(stm)
    label_t = to(labels)

    model = TorchAunn()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    criterion = nn.MSELoss()
    n = len(fens)
    for epoch in range(args.epochs):
        model.train()
        perm = torch.randperm(n)
        total = 0.0
        batches = 0
        for i in range(0, n - args.batch_size + 1, args.batch_size):
            idx = perm[i:i + args.batch_size]
            optimizer.zero_grad()
            pred = model(white_t[idx], black_t[idx], common_t[idx], stm_t[idx])
            # Regress in pawns (cp / 100) for a well-scaled loss.
            loss = criterion(pred / 100.0, label_t[idx] / 100.0)
            loss.backward()
            optimizer.step()
            total += loss.item()
            batches += 1
        scheduler.step()
        if epoch == 0 or (epoch + 1) % 10 == 0:
            print(f"  epoch {epoch + 1}/{args.epochs}  loss {total / max(1, batches):.4f}")

    model.eval()
    network = fold_into_network(model, mean_p, std_p, mean_c, std_c)

    # Faithfulness gate: the numpy network must reproduce the torch model on raw features.
    with torch.no_grad():
        torch_out = model(white_t, black_t, common_t, stm_t).cpu().numpy()
    numpy_out = np.array([network.forward(feats[i]) for i in range(min(n, 2000))])
    max_diff = float(np.abs(numpy_out - torch_out[:len(numpy_out)]).max())
    print(f"fold check: max |numpy - torch| = {max_diff:.4f} cp over {len(numpy_out)} positions")
    if max_diff > 1.0:
        raise SystemExit(f"folding mismatch too large ({max_diff:.4f}); export is not faithful")

    network.save(args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
