"""Integer forward matching the reference solution's ``QuantizedAUNN``.

This reproduces the engine-side (deployment) inference of notebook 065d exactly:
per-side feature embeddings with per-feature multipliers, a fixed-point shift with
rounding, clamping to ``[0, 127]``, side-to-move ordering, then two integer linear
layers. It is validated bit-for-bit against the reference's own test vectors in
``tests/test_reference_fidelity.py``. Weights are the quantized ``params.h`` values.

Pure Python ints are used so the arithmetic (right shifts, rounding) matches the
reference's ``int64`` operations exactly, without overflow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Fixed-point constants from the reference: embeddings accumulate at a 1<<15 scale
# with round-to-nearest, then shift down by 5/6 between layers.
_ROUND = 1 << 14
_EMB_SHIFT = 15
_L1_SHIFT = 5
_L2_SHIFT = 6
_L3_SHIFT = 5
_CLAMP_MAX = 127


@dataclass
class QuantizedAunn:
    """Quantized AUNN inference over an integer feature vector."""

    color_weight: list[list[int]]   # (num_paired, 16), shared by both sides
    color_mult: list[int]           # (num_paired,)
    common_weight: list[list[int]]  # (num_common, 16)
    common_mult: list[int]          # (num_common,)
    embed_bias: list[int]           # (16,)
    hidden_weight: list[list[int]]  # (32, 32) as [out][in]
    hidden_bias: list[int]          # (32,)
    output_weight: list[int]        # (32,)
    output_bias: int
    white_idx: list[int]
    black_idx: list[int]
    common_idx: list[int]
    stm_idx: int

    def _embed(self, feats: list[int], weight: list[list[int]], mult: list[int]) -> list[int]:
        """Accumulate one side's 16-dim embedding at the 1<<15 fixed-point scale."""
        out = [0] * 16
        for value, wc, m in zip(feats, weight, mult):
            scaled = value * m
            for d in range(16):
                out[d] += (scaled * wc[d] + _ROUND) >> _EMB_SHIFT
        return out

    def forward(self, x: list[int]) -> int:
        """Return the integer evaluation (256x scale) from White's frame layout."""
        common = self._embed([x[i] for i in self.common_idx], self.common_weight, self.common_mult)
        white_raw = self._embed([x[i] for i in self.white_idx], self.color_weight, self.color_mult)
        black_raw = self._embed([x[i] for i in self.black_idx], self.color_weight, self.color_mult)
        white = [_clamp((white_raw[d] + common[d] + self.embed_bias[d]) >> _L1_SHIFT) for d in range(16)]
        black = [_clamp((black_raw[d] + common[d] + self.embed_bias[d]) >> _L1_SHIFT) for d in range(16)]

        # The side to move occupies the first half of the hidden input.
        first, second = (white, black) if x[self.stm_idx] == 0 else (black, white)
        combined = first + second
        hidden = [
            _clamp((sum(self.hidden_weight[j][i] * combined[i] for i in range(32)) + self.hidden_bias[j]) >> _L2_SHIFT)
            for j in range(32)
        ]
        out = sum(self.output_weight[j] * hidden[j] for j in range(32)) + self.output_bias
        return out >> _L3_SHIFT

    @classmethod
    def from_params(cls, params: dict, white_cols: list[str], black_cols: list[str],
                    common_cols: list[str], feature_to_index: dict[str, int],
                    replacement: dict[str, tuple]) -> "QuantizedAunn":
        """Rebuild the model from a parsed ``params.h`` and the feature layout.

        ``params.h`` prints each feature's 16 coefficients reversed and stores a
        separate ``_MULT`` (adder features default to ``1<<15``). Replacement
        (king-danger) features have their first two dims zeroed in this linear
        forward, matching the reference's ``replacement_*_mask``.
        """
        def build(cols: list[str], strip: bool):
            weights, mults = [], []
            for name in cols:
                base = name[:-2] if strip else name  # color names carry a "_0"/"_1" suffix
                coefs = list(reversed(params[base.upper()]))
                if base in replacement:
                    coefs[0] = coefs[1] = 0
                weights.append(coefs)
                mults.append(params.get(base.upper() + "_MULT", 1 << 15))
            return weights, mults

        color_weight, color_mult = build(white_cols, strip=True)
        common_weight, common_mult = build(common_cols, strip=False)
        return cls(
            color_weight=color_weight, color_mult=color_mult,
            common_weight=common_weight, common_mult=common_mult,
            embed_bias=list(reversed(params["BIAS1"])),
            hidden_weight=params["WEIGHT2"], hidden_bias=params["BIAS2"],
            output_weight=params["WEIGHT3"], output_bias=params["BIAS3"],
            white_idx=[feature_to_index[c] for c in white_cols],
            black_idx=[feature_to_index[c] for c in black_cols],
            common_idx=[feature_to_index[c] for c in common_cols],
            stm_idx=feature_to_index["side_to_move"],
        )


def _clamp(value: int) -> int:
    return 0 if value < 0 else (_CLAMP_MAX if value > _CLAMP_MAX else value)


def parse_params_header(text: str) -> dict:
    """Parse a ``params.h`` (``QuantizedAUNN.print()`` output) into a dict.

    Scalar ``_MULT``/``BIAS3`` become ints, ``WEIGHT2`` a 32x32 list, and every
    other ``PARAMS_<NAME>`` a flat int list.
    """
    params: dict = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        match = re.match(r"#define\s+PARAMS_(\S+)\s+(.*)", lines[i])
        if not match:
            i += 1
            continue
        name, rest = match.group(1), match.group(2)
        if name == "WEIGHT2":
            rows = []
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("}"):
                nums = re.findall(r"-?\d+", lines[j])
                if nums:
                    rows.append([int(n) for n in nums])
                j += 1
            params["WEIGHT2"] = rows
            i = j + 1
            continue
        nums = [int(n) for n in re.findall(r"-?\d+", rest)]
        params[name] = nums[0] if len(nums) == 1 else nums
        i += 1
    return params
