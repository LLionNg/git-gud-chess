"""NumPy port of the reference AUNN network architecture.

Faithful to the structure in ``reference/kaggle_solution`` (notebook 065d): each
side's features pass through a *shared* linear layer to a small embedding; the
two embeddings are concatenated side-to-move first, then reduced through one
clamped hidden layer to a single score. The reference then integer-quantizes the
weights to fit a tiny C binary; here we keep float weights for clarity and
training. Weights are learned in phase 2 — an untrained network is not useful.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from chessbot.evaluation.neural import features

EMBEDDING_DIM = 16
HIDDEN_DIM = 32
# Activation clamp mirrors the reference's [0, 127] quantized range.
CLAMP = 127.0


@dataclass
class AunnNetwork:
    """The AUNN weights and forward pass over a single feature vector."""

    color_weight: np.ndarray   # (num_paired, EMBEDDING_DIM), shared by both sides
    common_weight: np.ndarray  # (num_common, EMBEDDING_DIM)
    embed_bias: np.ndarray     # (EMBEDDING_DIM,)
    hidden_weight: np.ndarray  # (2*EMBEDDING_DIM, HIDDEN_DIM)
    hidden_bias: np.ndarray    # (HIDDEN_DIM,)
    output_weight: np.ndarray  # (HIDDEN_DIM,)
    output_bias: float

    @classmethod
    def zeros(cls) -> "AunnNetwork":
        """A deterministic, untrained network (returns a constant score)."""
        n_paired = len(features.PAIRED_FEATURES)
        n_common = len(features.COMMON_FEATURES)
        return cls(
            color_weight=np.zeros((n_paired, EMBEDDING_DIM), np.float32),
            common_weight=np.zeros((n_common, EMBEDDING_DIM), np.float32),
            embed_bias=np.zeros(EMBEDDING_DIM, np.float32),
            hidden_weight=np.zeros((2 * EMBEDDING_DIM, HIDDEN_DIM), np.float32),
            hidden_bias=np.zeros(HIDDEN_DIM, np.float32),
            output_weight=np.zeros(HIDDEN_DIM, np.float32),
            output_bias=0.0,
        )

    def forward(self, x: np.ndarray) -> float:
        """Return a centipawn score from the side-to-move's perspective."""
        white = x[features.WHITE_IDX]
        black = x[features.BLACK_IDX]
        common = x[features.COMMON_IDX]
        common_embed = common @ self.common_weight + self.embed_bias
        # Shared color weights: the same transform scores each side's features.
        white_embed = np.clip(white @ self.color_weight + common_embed, 0.0, CLAMP)
        black_embed = np.clip(black @ self.color_weight + common_embed, 0.0, CLAMP)

        white_to_move = x[features.STM_IDX] == 0.0
        first, second = (white_embed, black_embed) if white_to_move else (black_embed, white_embed)
        hidden_in = np.concatenate([first, second])
        hidden = np.clip(hidden_in @ self.hidden_weight + self.hidden_bias, 0.0, CLAMP)
        return float(hidden @ self.output_weight + self.output_bias)

    def save(self, path: str) -> None:
        np.savez(
            path,
            color_weight=self.color_weight, common_weight=self.common_weight,
            embed_bias=self.embed_bias, hidden_weight=self.hidden_weight,
            hidden_bias=self.hidden_bias, output_weight=self.output_weight,
            output_bias=np.float32(self.output_bias),
        )

    @classmethod
    def load(cls, path: str) -> "AunnNetwork":
        data = np.load(path)
        return cls(
            color_weight=data["color_weight"], common_weight=data["common_weight"],
            embed_bias=data["embed_bias"], hidden_weight=data["hidden_weight"],
            hidden_bias=data["hidden_bias"], output_weight=data["output_weight"],
            output_bias=float(data["output_bias"]),
        )
