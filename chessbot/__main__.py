"""Entry point: ``python -m chessbot`` starts the UCI loop.

Optional flags preselect the evaluator so the neural net can be played without
typing UCI ``setoption`` lines::

    python -m chessbot --evaluator neural --weights weights.npz
"""

from __future__ import annotations

import argparse

from chessbot.config import EngineConfig, EvaluationConfig, EvaluatorType
from chessbot.engine import Engine
from chessbot.uci import UciProtocol


def main() -> None:
    parser = argparse.ArgumentParser(prog="chessbot")
    parser.add_argument("--evaluator", choices=[e.value for e in EvaluatorType],
                        default=EvaluatorType.CLASSICAL.value)
    parser.add_argument("--weights", default=None,
                        help="path to neural .npz weights (implies --evaluator neural)")
    args = parser.parse_args()

    provider = EvaluatorType.NEURAL if args.weights else EvaluatorType(args.evaluator)
    config = EngineConfig(evaluation=EvaluationConfig(provider=provider, weights_path=args.weights))
    UciProtocol(Engine(config)).run()


if __name__ == "__main__":
    main()
