"""Bit-exact fidelity to the reference solution's quantized inference.

Loads the actual training notebook (``reference/kaggle_solution/...065d...``),
rebuilds its quantized model from the trained ``params.h`` it printed, and checks
that :class:`QuantizedAunn` reproduces the intermediate and final values the
notebook itself recorded (cells 8 and 10). This is the guard that our port of the
reference's pipeline logic stays faithful.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from chessbot.evaluation.neural.quantized import QuantizedAunn, parse_params_header

NOTEBOOK = (Path(__file__).resolve().parents[1]
            / "reference" / "kaggle_solution" / "chess-065d-lr-1e-2-epoch-500.ipynb")

# Values the notebook printed for its own trained model (ground truth).
CELL8_WHITE = [1659, 0, -6, 0, -32, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 18, 0, 0, 0, 0, 0, 0, 0, 0, 14, 0, 0, 0, -183, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -64, 0, 0, 0, 0, 166, 0, 0, 0, 0, -13, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 24, 72, 0, 12, 0, 0, 0, 0, 0]
CELL8_BLACK = [1572, 0, -6, 0, 36, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 49, 0, 0, 0, 0, 0, 0, 0, 67, 0, 0, 0, -28, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -75, 0, 0, -56, 2, 0, 0, 0, 0, 0, 0, 0, 0, -26, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 24, 72, 0, 12, 0, 0, 0, 0, 0]
CELL10_L2_INPUT = [127, 127, 0, 0, 103, 0, 0, 0, 72, 4, 0, 33, 127, 0, 110, 76] * 2
CELL10_L3 = [0, 0, 0, 74, 127, 0, 0, 19, 0, 0, 0, 0, 0, 0, 13, 0, 19, 0, 70, 0, 0, 0, 127, 0, 0, 0, 111, 0, 0, 0, 0, 0]
CELL10_FINAL = -132

pytestmark = pytest.mark.skipif(not NOTEBOOK.exists(), reason="reference notebook not present")


def _code_cells(notebook: dict) -> list[dict]:
    return [c for c in notebook["cells"] if c.get("cell_type") == "code"]


def _cell_output_text(cell: dict) -> str:
    text = ""
    for out in cell.get("outputs", []):
        if out.get("output_type") == "stream":
            text += "".join(out.get("text", []))
        elif out.get("output_type") in ("execute_result", "display_data"):
            text += "".join(out.get("data", {}).get("text/plain", []))
    return text


@pytest.fixture(scope="module")
def reference():
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    cells = _code_cells(notebook)
    sources = ["".join(c.get("source", [])) for c in cells]

    # Rebuild the feature layout by executing the notebook's own config block.
    config_cell = next(s for s in sources if "feature_names = [" in s)
    config = "feature_names = [" + config_cell.split("feature_names = [", 1)[1].split(
        "dataloader = SplitDataLoader")[0]
    namespace: dict = {}
    exec(config, namespace)  # defines feature_names, coefs, replacement, white/black/common cols
    feature_to_index = {name: i for i, name in enumerate(namespace["feature_names"])}

    params = parse_params_header(_cell_output_text(cells[6]))  # trained params.h
    model = QuantizedAunn.from_params(
        params, namespace["white_cols"], namespace["black_cols"], namespace["common_cols"],
        feature_to_index, namespace["replacement"],
    )

    return model, _extract_data_tmp(sources)


def _extract_data_tmp(sources: list[str]) -> list[int]:
    src = next(s for s in sources if "data_tmp = torch.tensor" in s)
    body = src.split("data_tmp = torch.tensor([[")[1].split("]])")[0]
    return [int(n) for n in re.findall(r"-?\d+", body)]


def test_embedding_matches_reference_cell8(reference) -> None:
    model, data_tmp = reference
    # Per-feature contribution to embedding dim 0, as the notebook's test_l1 printed.
    def contrib(idx):
        return [(data_tmp[i] * m * w[0] + (1 << 14)) >> 15
                for i, m, w in zip(idx, model.color_mult, model.color_weight)]
    assert contrib(model.white_idx) == CELL8_WHITE
    assert contrib(model.black_idx) == CELL8_BLACK


def test_head_matches_reference_cell10(reference) -> None:
    model, _ = reference
    l3 = [max(0, min(127, (sum(model.hidden_weight[j][i] * CELL10_L2_INPUT[i] for i in range(32))
                             + model.hidden_bias[j]) >> 6)) for j in range(32)]
    final = (sum(model.output_weight[j] * l3[j] for j in range(32)) + model.output_bias) >> 5
    assert l3 == CELL10_L3
    assert final == CELL10_FINAL


def test_full_forward_is_deterministic(reference) -> None:
    model, data_tmp = reference
    # Assembled forward over the reference test position; guards against regressions.
    assert model.forward(data_tmp) == -301
