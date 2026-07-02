"""Neural (AUNN) evaluation: feature extraction, network, and provider.

Two renderings of the reference solution's small network share one architecture:

- :class:`~chessbot.evaluation.neural.network.AunnNetwork` - a float, trainable
  form used as the engine's neural evaluator (phase-2 training target).
- :class:`~chessbot.evaluation.neural.quantized.QuantizedAunn` - the integer
  (deployment) form, a bit-exact port of the reference's ``QuantizedAUNN``
  validated against its own test vectors in ``tests/test_reference_fidelity.py``.

See ``reference/kaggle_solution`` (notebook 065d) for the originals.
"""

from __future__ import annotations

from chessbot.evaluation.neural.network import AunnNetwork
from chessbot.evaluation.neural.quantized import QuantizedAunn, parse_params_header

__all__ = ["AunnNetwork", "QuantizedAunn", "parse_params_header"]
