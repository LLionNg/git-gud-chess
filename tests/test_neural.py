"""Neural provider: feature layout, network round-trip, and factory fallback."""

from __future__ import annotations

import os

import chess
import numpy as np
import pytest

from chessbot.config import EvaluationConfig, EvaluatorType
from chessbot.evaluation import build_evaluator
from chessbot.evaluation.neural.features import (
    BLACK_IDX,
    COMMON_IDX,
    NUM_FEATURES,
    STM_IDX,
    WHITE_IDX,
    extract_features,
)
from chessbot.evaluation.neural.network import AunnNetwork


def test_feature_vector_shape() -> None:
    x = extract_features(chess.Board())
    assert x.shape == (NUM_FEATURES,)
    assert x.dtype == np.float32
    # Start position: eight pawns a side, side to move is White.
    assert x[WHITE_IDX[0]] == 8 and x[BLACK_IDX[0]] == 8
    assert x[STM_IDX] == 0.0


def test_features_are_colour_symmetric() -> None:
    board = chess.Board("r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1")
    direct = extract_features(board)
    mirror = extract_features(board.mirror())
    # White features of a position equal Black features of its mirror, and vice versa.
    for w, b in zip(WHITE_IDX, BLACK_IDX):
        assert direct[w] == mirror[b]
        assert direct[b] == mirror[w]
    for c in COMMON_IDX:
        assert direct[c] == mirror[c]
    assert direct[STM_IDX] != mirror[STM_IDX]


def test_zeros_network_is_constant() -> None:
    net = AunnNetwork.zeros()
    assert net.forward(extract_features(chess.Board())) == 0.0


def test_network_save_load_roundtrip(tmp_path) -> None:
    rng = np.random.default_rng(1)
    net = AunnNetwork.zeros()
    net.color_weight = rng.standard_normal(net.color_weight.shape).astype(np.float32)
    net.output_weight = rng.standard_normal(net.output_weight.shape).astype(np.float32)
    net.output_bias = 12.0
    path = os.path.join(tmp_path, "weights.npz")
    net.save(path)
    x = extract_features(chess.Board("8/8/8/4k3/8/8/2Q5/4K3 w - - 0 1"))
    assert abs(AunnNetwork.load(path).forward(x) - net.forward(x)) < 1e-4


def test_neural_evaluator_via_factory(tmp_path) -> None:
    path = os.path.join(tmp_path, "weights.npz")
    AunnNetwork.zeros().save(path)
    cfg = EvaluationConfig(provider=EvaluatorType.NEURAL, weights_path=path)
    evaluator = build_evaluator(cfg)
    assert evaluator.name == "neural"
    assert isinstance(evaluator.evaluate(chess.Board()), int)


def test_neural_falls_back_without_weights() -> None:
    evaluator = build_evaluator(EvaluationConfig(provider=EvaluatorType.NEURAL))
    assert evaluator.name == "classical"


def test_neural_evaluator_requires_weights() -> None:
    from chessbot.evaluation.neural.evaluator import NeuralEvaluator

    with pytest.raises(ValueError):
        NeuralEvaluator(EvaluationConfig(provider=EvaluatorType.NEURAL))
