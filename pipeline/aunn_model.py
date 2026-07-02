"""AUNN model + config extracted verbatim from reference notebook 065d (faithful)."""
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

########################################
########################################
class AUNN(nn.Module):
    def __init__(
        self,
        white_cols: list[str],
        black_cols: list[str],
        common_cols: list[str],
        side_to_move_col: str,
        feature_means: torch.Tensor,
        feature_stds: torch.Tensor,
        feature_maxs: torch.Tensor,
        feature_to_index: dict[str, int],
        fixed_weight: torch.Tensor,
        fixed_bias: torch.Tensor,  # 0
        adder_features: list[str],
        feature_names,
        replacement,
    ):
        """Constructor; see reference notebook 065d for full field descriptions."""
        super().__init__()

        embedding_dim = 16
        l2out_dim = 32

        self.feature_names = feature_names
        self.replacement = replacement

        self.white_idx = [feature_to_index[c] for c in white_cols]
        self.black_idx = [feature_to_index[c] for c in black_cols]
        self.common_idx = [feature_to_index[c] for c in common_cols]
        self.side_to_move_idx = feature_to_index[side_to_move_col]

        adder_features = set(adder_features)
        self.white_add_idx = [feature_to_index[c] for c in white_cols if c[:-2] in adder_features]
        self.white_mul_idx = [feature_to_index[c] for c in white_cols if c[:-2] not in adder_features]
        self.black_add_idx = [feature_to_index[c] for c in black_cols if c[:-2] in adder_features]
        self.black_mul_idx = [feature_to_index[c] for c in black_cols if c[:-2] not in adder_features]
        self.common_add_idx = [feature_to_index[c] for c in common_cols if c in adder_features]
        self.common_mul_idx = [feature_to_index[c] for c in common_cols if c not in adder_features]
        self.register_buffer("is_add_in_color",  torch.tensor([(idx in self.white_add_idx)  for idx in self.white_idx]))
        self.register_buffer("is_add_in_common", torch.tensor([(idx in self.common_add_idx) for idx in self.common_idx]))

        self.register_buffer("color_feature_means", feature_means[self.white_idx].contiguous())
        self.register_buffer("color_feature_stds", feature_stds[self.white_idx].contiguous())
        self.register_buffer("color_feature_maxs", feature_maxs[self.white_idx].contiguous())
        self.register_buffer("common_feature_means", feature_means[self.common_idx].contiguous())
        self.register_buffer("common_feature_stds", feature_stds[self.common_idx].contiguous())
        self.register_buffer("common_feature_maxs", feature_maxs[self.common_idx].contiguous())

        num_color_features = len(white_cols)

        self.register_buffer("fixed_weight", fixed_weight[self.white_idx] / 2 ** 12)

        self.linear_color = nn.Linear(num_color_features, embedding_dim - 2)
        self.linear_common = nn.Linear(len(common_cols), embedding_dim - 2, bias=False)
        self.linear2 = nn.Linear(embedding_dim * 2, l2out_dim)
        self.linear3 = nn.Linear(l2out_dim, 1)

    def _round_quant(self, x):
        return x + (x.detach().round() - x.detach())

    def _ceil_quant(self, x):
        return x + (x.detach().ceil() - x.detach())

    def _floor_quant(self, x):
        return x + (x.detach().floor() - x.detach())

    def quantize_weights(self):
        """Return each layer's quantized weights (fixed part and normalization merged), rounded at a fixed scale to match QuantizedAUNN; kept in fp32 and differentiable."""
        trainable_color_weight = self.linear_color.weight.transpose(0,1).contiguous()
        trainable_color_weight = trainable_color_weight / self.color_feature_stds[:, None]
        trainable_color_bias = self.linear_color.bias.clone()
        trainable_color_bias = trainable_color_bias - ((self.color_feature_means / self.color_feature_stds) @ self.linear_color.weight.transpose(0,1))
        
        common_weight = self.linear_common.weight.transpose(0,1).contiguous()
        common_weight = common_weight / self.common_feature_stds[:, None]
        trainable_color_bias = trainable_color_bias - ((self.common_feature_means / self.common_feature_stds) @ self.linear_common.weight.transpose(0,1))
        
        fixed_bias = torch.zeros((2,), device=self.fixed_weight.device)
        combined_weight = torch.cat([self.fixed_weight, trainable_color_weight], dim=1)  # (n_color, 16)
        combined_bias   = torch.cat([fixed_bias, trainable_color_bias], dim=0)           # (16,)
        
        scale1 = 32 * 128       # 4096
        scale2 = (1 << 15)      # 32768
        weight_scale = scale1 * scale2  # 134217728
        
        quant_linear_color_weight = combined_weight * weight_scale
        #quant_linear_color_weight = self._round_quant(quant_linear_color_weight)
        quant_linear_bias = self._round_quant(combined_bias * scale1) + (1 << 4)
        
        # n_color = quant_linear_color_weight.shape[0]
        # multipliers = []
        # for i in range(n_color):
        #     feature_index = self.white_idx[i]
        #     if feature_index in self.white_add_idx:
        #         multipliers.append(1 << 15)  # 32768
        #     else:
        #         max_val = quant_linear_color_weight[i].abs().max()
        #         mult = self._ceil_quant(max_val / 32767.0)
        #         mult = torch.clamp(mult, min=1.0)
        #         multipliers.append(mult)
        # color_multiplyer = torch.tensor(multipliers, dtype=torch.float32, device=quant_linear_color_weight.device)
        # quant_linear_color_weight = self._round_quant(quant_linear_color_weight / color_multiplyer[:, None])
        
        # n_common = common_weight.shape[0]
        # zeros_fixed = torch.zeros((n_common, 2), device=common_weight.device, dtype=common_weight.dtype)
        # quant_linear_common_weight = torch.cat([zeros_fixed, common_weight], dim=1)  # (n_common, 16)
        # quant_linear_common_weight = quant_linear_common_weight * weight_scale
        # #quant_linear_common_weight = self._round_quant(quant_linear_common_weight)
        # multipliers_common = []
        # for i in range(n_common):
        #     feature_index = self.common_idx[i]
        #     if feature_index in self.common_add_idx:
        #         multipliers_common.append(1 << 15)
        #     else:
        #         max_val = quant_linear_common_weight[i].abs().max()
        #         mult = self._ceil_quant(max_val / 32767.0)
        #         mult = torch.clamp(mult, min=1.0)
        #         multipliers_common.append(mult)
        # common_multiplyer = torch.tensor(multipliers_common, dtype=torch.float32, device=quant_linear_common_weight.device)
        # quant_linear_common_weight = self._round_quant(quant_linear_common_weight / common_multiplyer[:, None])

        abs_max_color = quant_linear_color_weight.abs().amax(dim=1)  # shape: (n_color,)
        mult_calc = self._ceil_quant(abs_max_color / 32767.0)
        mult_calc = torch.clamp(mult_calc, min=1.0)
        color_multiplyer = torch.where(self.is_add_in_color.bool(),
                                       torch.tensor(1 << 15, dtype=mult_calc.dtype, device=mult_calc.device),
                                       mult_calc)
        quant_linear_color_weight = self._round_quant(quant_linear_color_weight / color_multiplyer[:, None])
        
        
        n_common = common_weight.shape[0]
        zeros_fixed = torch.zeros((n_common, 2), device=common_weight.device, dtype=common_weight.dtype)
        quant_linear_common_weight = torch.cat([zeros_fixed, common_weight], dim=1)  # (n_common, 16)
        quant_linear_common_weight = quant_linear_common_weight * weight_scale
        
        abs_max_common = quant_linear_common_weight.abs().amax(dim=1)  # shape: (n_common,)
        mult_calc_common = self._ceil_quant(abs_max_common / 32767.0)
        mult_calc_common = torch.clamp(mult_calc_common, min=1.0)
        common_multiplyer = torch.where(self.is_add_in_common.bool(),
                                        torch.tensor(1 << 15, dtype=mult_calc_common.dtype, device=mult_calc_common.device),
                                        mult_calc_common)
        quant_linear_common_weight = self._round_quant(quant_linear_common_weight / common_multiplyer[:, None])

        if not hasattr(self, 'replacement_color_mask_for_forward'):
            replacement_color = [self.replacement.get(self.feature_names[idx][:-2]) for idx in self.white_idx]
            self.replacement_color_mask_for_forward = torch.tensor([r is None for r in replacement_color], device=quant_linear_color_weight.device)
        if not hasattr(self, 'replacement_common_mask_for_forward'):
            replacement_common = [self.replacement.get(self.feature_names[idx]) for idx in self.common_idx]
            self.replacement_common_mask_for_forward = torch.tensor([r is None for r in replacement_common], device=quant_linear_common_weight.device)
        quant_linear_color_weight[:, :2] *= self.replacement_color_mask_for_forward.to(quant_linear_color_weight.dtype).unsqueeze(1)
        quant_linear_common_weight[:, :2] *= self.replacement_common_mask_for_forward.to(quant_linear_common_weight.dtype).unsqueeze(1)
        
        quant_linear2_weight = self._round_quant(self.linear2.weight * 64)
        quant_linear2_bias   = self._round_quant(self.linear2.bias * (64 * 128)) + (1 << 5)
        quant_linear3_weight = self._round_quant(self.linear3.weight.squeeze(0) * 64)
        quant_linear3_bias   = self._round_quant(self.linear3.bias * (64 * 128)) + (1 << 4)
        
        return {
            'linear_color_weight': quant_linear_color_weight,  # (n_color, 16)
            'color_multiplyer': color_multiplyer,                # (n_color,)
            'linear_bias': quant_linear_bias,                    # (16,)
            'linear_common_weight': quant_linear_common_weight,  # (n_common, 16)
            'common_multiplyer': common_multiplyer,              # (n_common,)
            'linear2_weight': quant_linear2_weight,              # (l2out_dim, 32)
            'linear2_bias': quant_linear2_bias,                  # (l2out_dim,)
            'linear3_weight': quant_linear3_weight,              # (l2out_dim,)
            'linear3_bias': quant_linear3_bias                   # scalar
        }

    def forward(self, x):
        """Quantization-aware forward: x is treated as integer-rounded, then each layer rounds at a fixed scale so the result matches QuantizedAUNN's integer arithmetic."""
        x_q = self._round_quant(x)
        x_int = torch.round(x_q)

        white = x_int[:, self.white_idx].to(torch.float32)  # (B, n_color)
        black = x_int[:, self.black_idx].to(torch.float32)  # (B, n_color)
        common = x_int[:, self.common_idx].to(torch.float32)  # (B, n_common)
        
        q = self.quantize_weights()
        
        common_scaled = common * q['common_multiplyer']  # (B, n_common)
        common_out = torch.sum(self._round_quant(common_scaled.unsqueeze(2) * q['linear_common_weight'].unsqueeze(0) / (1<<15)), dim=1)  # (B, 16)
        
        white_scaled = white * q['color_multiplyer']  # (B, n_color)
        white_out = torch.sum(self._round_quant(white_scaled.unsqueeze(2) * q['linear_color_weight'].unsqueeze(0) / (1<<15)), dim=1)  # (B, 16)
        black_scaled = black * q['color_multiplyer']
        black_out = torch.sum(self._round_quant(black_scaled.unsqueeze(2) * q['linear_color_weight'].unsqueeze(0) / (1<<15)), dim=1)  # (B, 16)

        white_result = white_out + common_out + q['linear_bias']  # (B, 16)
        black_result = black_out + common_out + q['linear_bias']  # (B, 16)
        white_result = self._floor_quant(white_result / 32.0)
        white_result = torch.clamp(white_result, 0, 127)
        black_result = self._floor_quant(black_result / 32.0)
        black_result = torch.clamp(black_result, 0, 127)

        
        is_white_to_move = (x[:, self.side_to_move_idx] == 0).unsqueeze(1)  # (B,1)
        first_part = torch.where(is_white_to_move, white_result, black_result)
        second_part = torch.where(is_white_to_move, black_result, white_result)
        combined = torch.cat([first_part, second_part], dim=1)  # (B, 32)
        #print("o combined:", combined.int())
        
        out2 = torch.sum(q['linear2_weight'].unsqueeze(0) * combined.unsqueeze(1), dim=2) + q['linear2_bias']
        #print("o out2", out2.int())
        out2 = self._floor_quant(out2 / 64.0)
        out2 = torch.clamp(out2, 0, 127)

        
        out3 = torch.sum(q['linear3_weight'] * out2, dim=1) + q['linear3_bias']
        #print("o out:", out3.int())
        out3 = self._floor_quant(out3 / 32.0)
        return out3  # (B,)

    def clip(self):
        with torch.no_grad():
            # 32767 / (1<<14) * std
            limit_color_add  = 32767 / (1<<14) * self.color_feature_stds.unsqueeze(0)
            limit_color_mul  = 8 * (self.color_feature_stds  / self.color_feature_maxs ).unsqueeze(0) / 2.0
            limit_color  = torch.where(self.is_add_in_color,  limit_color_add,  limit_color_mul)
            self.linear_color.weight.data.clamp_(-limit_color, limit_color)
            limit_common_add = 32767 / (1<<14) * self.common_feature_stds.unsqueeze(0)
            limit_common_mul = 8 * (self.common_feature_stds / self.common_feature_maxs).unsqueeze(0) / 2.0  # (1, n_common)
            limit_common = torch.where(self.is_add_in_common, limit_common_add, limit_common_mul)
            self.linear_common.weight.data.clamp_(-limit_common, limit_common)
            clip_range = 2 * 127 / 128
            self.linear2.weight.data.clamp_(-clip_range, clip_range)
            self.linear2.bias.data.clamp_(-clip_range, clip_range)
            self.linear3.weight.data.clamp_(-clip_range, clip_range)
            self.linear3.bias.data.clamp_(-clip_range, clip_range)


class QuantizedAUNN:
    def __init__(self, aunn):
        self.feature_names = aunn.feature_names
        self.replacement = aunn.replacement
        self.white_idx = aunn.white_idx
        self.black_idx = aunn.black_idx
        self.common_idx = aunn.common_idx
        self.side_to_move_idx = aunn.side_to_move_idx
        self.white_add_idx = aunn.white_add_idx
        self.white_mul_idx = aunn.white_mul_idx
        self.common_add_idx = aunn.common_add_idx
        self.common_mul_idx = aunn.common_mul_idx

        replacement_color = [self.replacement.get(self.feature_names[idx][:-2]) for idx in aunn.white_idx]
        self.replacement_color_mask_for_forward = torch.tensor([r is None for r in replacement_color])
        replacement_common = [self.replacement.get(self.feature_names[idx]) for idx in aunn.common_idx]
        self.replacement_common_mask_for_forward = torch.tensor([r is None for r in replacement_common])

        trainable_color_weight = aunn.linear_color.weight.data.clone().transpose(0, 1).contiguous()  # (n_color,14)
        trainable_color_weight /= aunn.color_feature_stds[:, None]
        trainable_color_bias   = aunn.linear_color.bias.data.clone()  # (14,)
        trainable_color_bias   -= (aunn.color_feature_means / aunn.color_feature_stds) @ aunn.linear_color.weight.data.transpose(0, 1)

        common_weight        = aunn.linear_common.weight.data.clone().transpose(0, 1).contiguous()  # (n_common,14)
        common_weight        /= aunn.common_feature_stds[:, None]
        trainable_color_bias -= (aunn.common_feature_means / aunn.common_feature_stds) @ aunn.linear_common.weight.data.transpose(0, 1)

        self.linear_common_weight = torch.cat(
            [torch.zeros((common_weight.size(0), 2), device=common_weight.device), common_weight], dim=1
        )  # (n_common,16)
        self.linear_common_weight = self.linear_common_weight * (32 * 128 << 15)
        self.common_multiplyer = torch.where(
            torch.tensor([(idx in aunn.common_add_idx) for idx in aunn.common_idx]),
            torch.tensor(1 << 15),
            torch.ceil(self.linear_common_weight.abs().max(1).values / 32767).to(torch.int64),
        )
        self.linear_common_weight = torch.round(self.linear_common_weight / self.common_multiplyer[:, None]).to(torch.int64)

        fixed_weight = aunn.fixed_weight
        fixed_bias   = torch.zeros((2,))
        combined_weight = torch.cat([fixed_weight, trainable_color_weight], dim=1)  # (n_color,16)
        combined_bias   = torch.cat([fixed_bias,   trainable_color_bias],   dim=0)    # (16,)
        self.linear_bias         = torch.round(combined_bias * (32 * 128)).to(torch.int64) + (1 << 4)
        self.linear_color_weight = combined_weight * (32 * 128 << 15)

        self.color_multiplyer = torch.where(
            torch.tensor([(idx in aunn.white_add_idx) for idx in aunn.white_idx]),
            torch.tensor(1 << 15),
            torch.ceil(torch.tensor(
                [(v if r is None else max(v, *[abs(ri)*(1<<15) for ri in r]))
                 for v, r
                 in zip(self.linear_color_weight.abs().max(1).values.tolist(), replacement_color)]
            ) / 32767).to(torch.int64)
        )
        self.linear_color_weight = torch.round(self.linear_color_weight / self.color_multiplyer[:, None]).to(torch.int64)

        self.linear2_weight = torch.round(aunn.linear2.weight.data * 64).to(torch.int16)
        self.linear2_bias   = torch.round(aunn.linear2.bias.data * (64 * 128)).to(torch.int16) + (1 << 5)

        self.linear3_weight = torch.round(aunn.linear3.weight.data.squeeze(0) * 64).to(torch.int16)
        self.linear3_bias   = torch.round(aunn.linear3.bias.data * (64 * 128)).to(torch.int16) + (1 << 4)

    def forward(self, x):
        # x: tensor((B, num_features), int16)
        #print("quantized mult:", self.color_multiplyer)
        #print("quantized lin:", self.linear_color_weight)
        is_white_to_move = x[:, self.side_to_move_idx] == 0  # (B,)
        white = x[:, self.white_idx].to(torch.int32)  # (B, n_color)
        black = x[:, self.black_idx].to(torch.int32)  # (B, n_color)
        linear_common_weight = self.linear_common_weight.clone()
        linear_common_weight[:, :2] *= self.replacement_common_mask_for_forward[:, None]
        common = x[:, self.common_idx].to(torch.int32)  # (B, n_common)
        common = common * self.common_multiplyer
        common = (common[:, :, None] * linear_common_weight[None, :, :] + (1<<14) >> 15).sum(1)
        linear_color_weight = self.linear_color_weight.clone()
        linear_color_weight[:, :2] *= self.replacement_color_mask_for_forward[:, None]
        white = white * self.color_multiplyer
        white = (white[:, :, None] * linear_color_weight[None, :, :] + (1<<14) >> 15).sum(1)
        white = white + common + self.linear_bias
        white = (white >> 5).clamp(min=0, max=127)
        black = black * self.color_multiplyer
        black = (black[:, :, None] * linear_color_weight[None, :, :] + (1<<14) >> 15).sum(1)
        black = black + common + self.linear_bias  # (B, 16)
        black = (black >> 5).clamp(min=0, max=127)

        first_part = torch.where(is_white_to_move.unsqueeze(1), white, black)
        second_part = torch.where(is_white_to_move.unsqueeze(1), black, white)
        combined = torch.cat([first_part, second_part], dim=1)

        # print("q is_white_to_move", is_white_to_move)
        # print("q combined:", combined.int())

        out = (self.linear2_weight[None, :, :] * combined[:, None, :]).sum(2) + self.linear2_bias
        #print("o out2", out.int())
        out = (out >> 6).clamp(min=0, max=127)
        out = (self.linear3_weight * out).sum(1) + self.linear3_bias
        #print("q out:", out.int())
        return out >> 5

    def print(self):
        MAX_LENGTH = 32
        print("#define PARAMS_BIAS1 " + ",".join([f"{v:4d}" for v in self.linear_bias][::-1]))
        for idx, feature_name in enumerate(self.feature_names):
            if idx in self.white_add_idx:
                idx_in_color = self.white_idx.index(idx)
                coef = self.linear_color_weight[idx_in_color]
                if feature_name[:-2] in self.replacement:
                    coef[0] = self.replacement[feature_name[:-2]][0]
                    coef[1] = self.replacement[feature_name[:-2]][1]
                print(f"#define PARAMS_{feature_name[:-2].upper():{MAX_LENGTH}} {','.join([f'{v:6d}' for v in coef][::-1])}")
            elif idx in self.white_mul_idx:
                idx_in_color = self.white_idx.index(idx)
                mult = self.color_multiplyer[idx_in_color]
                coef = self.linear_color_weight[idx_in_color].clone()
                if feature_name[:-2] in replacement:
                    coef[0] = ((self.replacement[feature_name[:-2]][0] * (1 << 15)) / mult).round().int()
                    coef[1] = ((self.replacement[feature_name[:-2]][1] * (1 << 15)) / mult).round().int()
                print(f"#define PARAMS_{feature_name[:-2].upper()}_MULT {mult}")
                print(f"#define PARAMS_{feature_name[:-2].upper():{MAX_LENGTH}} {','.join([f'{v:6d}' for v in coef][::-1])}")
            elif idx in self.common_add_idx:
                idx_in_common = self.common_idx.index(idx)
                coef = self.linear_common_weight[idx_in_common]
                if feature_name in self.replacement:
                    coef[0] = self.replacement[feature_name][0]
                    coef[1] = self.replacement[feature_name][1]
                print(f"#define PARAMS_{feature_name.upper():{MAX_LENGTH}} {','.join([f'{v:6d}' for v in coef][::-1])}")
            elif idx in self.common_mul_idx:
                idx_in_common = self.common_idx.index(idx)
                mult = self.common_multiplyer[idx_in_common]
                coef = self.linear_common_weight[idx_in_common]
                if feature_name in self.replacement:
                    coef[0] = ((self.replacement[feature_name][0] * (1 << 15)) / mult).round().int()
                    coef[1] = ((self.replacement[feature_name][1] * (1 << 15)) / mult).round().int()
                print(f"#define PARAMS_{feature_name.upper()}_MULT {mult}")
                print(f"#define PARAMS_{feature_name.upper():{MAX_LENGTH}} {','.join([f'{v:6d}' for v in coef][::-1])}")
        print("#define PARAMS_WEIGHT2 { \\")
        for wi in self.linear2_weight:
            print("  {" + ",".join(f"{v:4d}" for v in wi) +"}, \\")
        print("}")
        print("#define PARAMS_BIAS2   " + ",".join([f"{v:6d}" for v in self.linear2_bias]))
        print("#define PARAMS_WEIGHT3 " + ",".join([f"{v:4d}" for v in self.linear3_weight]))
        print("#define PARAMS_BIAS3   " + str(self.linear3_bias.item()))


def test_quantized(model, test_input):
    q_model = QuantizedAUNN(model)

    with torch.no_grad():
        aunn_output = model(test_input)
        aunn_output_scaled = aunn_output
        q_output = q_model.forward(test_input)

    print("AUNN output:", aunn_output_scaled)
    print("QuantizedAUNN output:", q_output)
    print("Difference (Quantized - AUNNx256):", q_output.float() - aunn_output_scaled)

    diff = (q_output.float() - aunn_output_scaled).abs()
    print("Mean absolute error:", diff.mean().item())
    print("Max absolute error:", diff.max().item())

# model = AUNN(
#     white_cols,
#     black_cols,
#     common_cols,
#     side_to_move_col,
#     feature_means,
#     feature_stds,
#     feature_maxs,
#     feature_to_index,
#     fixed_weight,
#     fixed_bias,
#     adder_features,
#     feature_names,
#     replacement,
# )
# test_quantized(model.cpu(), data_tensor[[5 * i for i in range(8192)]])


########################################
########################################
# def train_model_tensor(
#     data_tensor: torch.Tensor,
#     target_tensor: torch.Tensor,
#     model: nn.Module,
#     num_epochs: int,
#     batch_size: int,
#     lr: float,
#     device,
# ):
#     N = data_tensor.shape[0]
#     optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
#     scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=num_epochs)
#     criterion = nn.MSELoss()

#     model.to(device)
#     for epoch in range(num_epochs):
#         permutation = torch.randperm(N)
#         epoch_loss = 0.0
#         model.train()
#         for i in tqdm(range(0, N, batch_size)):
#             batch_idx = permutation[i : i + batch_size]
#             batch_data = data_tensor[batch_idx].to(device)
#             batch_target = target_tensor[batch_idx].to(device)

#             optimizer.zero_grad()
#             outputs = model(batch_data)
#             loss = criterion(outputs / 256.0, batch_target)
#             loss.backward()
#             optimizer.step()

#             model.clip()

#             epoch_loss += loss.item() * batch_data.size(0)
#         avg_loss = epoch_loss / N
#         print(f"Epoch {epoch+1}/{num_epochs}, Loss: {avg_loss:.6f}")
#         scheduler.step()
#         torch.save(model.state_dict(), f"model_epoch_{epoch+1}.pth")

import threading
from tqdm.auto import tqdm
import torch
import torch.nn as nn

def train_model_tensor(
    dataloader,
    model: nn.Module,
    num_epochs: int,
    batch_size: int,
    lr: float,
    device,
):
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=num_epochs)
    criterion = nn.MSELoss()

    model.to(device)
    
    # -------------------------------
    def prefetch_next(result_container):
        data, target = dataloader.load_next()
        result_container["data"] = data
        result_container["target"] = target
    # -------------------------------
    
    current_data, current_target = dataloader.load_next()
    
    next_result = {}
    prefetch_thread = threading.Thread(target=prefetch_next, args=(next_result,))
    prefetch_thread.start()

    for epoch in range(num_epochs):
        prefetch_thread.join()
        next_data = next_result["data"]
        next_target = next_result["target"]

        next_result = {}
        prefetch_thread = threading.Thread(target=prefetch_next, args=(next_result,))
        prefetch_thread.start()
        
        N = current_data.shape[0]
        permutation = torch.randperm(N)
        epoch_loss = 0.0
        model.train()
        for i in tqdm(range(0, N // batch_size * batch_size, batch_size)):
            batch_idx = permutation[i : i + batch_size]
            batch_data = current_data[batch_idx].to(device)
            batch_target = current_target[batch_idx].to(device)

            optimizer.zero_grad()
            outputs = model(batch_data)
            loss = criterion(outputs / 256, batch_target)
            loss.backward()
            optimizer.step()

            model.clip()

            epoch_loss += loss.item() * batch_data.size(0)
        avg_loss = epoch_loss / (N // batch_size * batch_size)
        print(f"Epoch {epoch+1}/{num_epochs}, Loss: {avg_loss:.6f}")
        scheduler.step()
        torch.save(model.state_dict(), f"model_epoch_{epoch+1}.pth")
        del current_data, current_target, batch_data, batch_target

        current_data, current_target = next_data, next_target

    prefetch_thread.join()

# ==== configuration (feature layout, coefs, fixed weights) ====
feature_names = [
    # general (6)
    "psqMG_0",
    "psqMG_1",
    "psqEG_0",
    "psqEG_1",
    "imbalanceMG_0",
    "imbalanceMG_1",
    "imbalanceEG_0",
    "imbalanceEG_1",
    "pawnMG_0",
    "pawnMG_1",
    "pawnEG_0",
    "pawnEG_1",
    # pieces<*, KNIGHT> (5)
    "knightUncontestedOutpost_0",
    "knightUncontestedOutpost_1",
    "knightOutpost_0",
    "knightOutpost_1",
    "knightReachableOutpost_0",
    "knightReachableOutpost_1",
    "knightMinorBehindPawn_0",
    "knightMinorBehindPawn_1",
    "knightKingProtector_0",
    "knightKingProtector_1",
    # pieces<*, BISHOP> (10)
    "bishopOnKingRing_0",
    "bishopOnKingRing_1",
    "bishopOutpost_0",
    "bishopOutpost_1",
    "bishopMinorBehindPawn_0",
    "bishopMinorBehindPawn_1",
    "bishopKingProtector_0",
    "bishopKingProtector_1",
    "bishopPawns_0_0",
    "bishopPawns_0_1",
    "bishopPawns_1_0",
    "bishopPawns_1_1",
    "bishopPawns_2_0",
    "bishopPawns_2_1",
    "bishopPawns_3_0",
    "bishopPawns_3_1",
    "bishopXRayPawns_0",
    "bishopXRayPawns_1",
    "bishopLongDiagonal_0",
    "bishopLongDiagonal_1",
    # pieces<*, ROOK> (5)
    "rookOnKingRing_0",
    "rookOnKingRing_1",
    "rookOnOpenFile_0_0",
    "rookOnOpenFile_0_1",
    "rookOnOpenFile_1_0",
    "rookOnOpenFile_1_1",
    "rookOnClosedFile_0",
    "rookOnClosedFile_1",
    "rookTrappedRook_0",
    "rookTrappedRook_1",
    # pieces<*, QUEEN> (1)
    "queenWeakQueen_0",
    "queenWeakQueen_1",
    # mobility (8)
    "mobility_0_0_0",
    "mobility_0_0_1",
    "mobility_0_1_0",
    "mobility_0_1_1",
    "mobility_1_0_0",
    "mobility_1_0_1",
    "mobility_1_1_0",
    "mobility_1_1_1",
    "mobility_2_0_0",
    "mobility_2_0_1",
    "mobility_2_1_0",
    "mobility_2_1_1",
    "mobility_3_0_0",
    "mobility_3_0_1",
    "mobility_3_1_0",
    "mobility_3_1_1",
    # king (25)
    "kingPEKingSafetyMG_0",
    "kingPEKingSafetyMG_1",
    "kingPEKingSafetyEG_0",
    "kingPEKingSafetyEG_1",
    "kingSafeCheckRook_0_0",
    "kingSafeCheckRook_0_1",
    "kingSafeCheckRook_1_0",
    "kingSafeCheckRook_1_1",
    "kingSafeCheckQueen_0_0",
    "kingSafeCheckQueen_0_1",
    "kingSafeCheckQueen_1_0",
    "kingSafeCheckQueen_1_1",
    "kingSafeCheckBishop_0_0",
    "kingSafeCheckBishop_0_1",
    "kingSafeCheckBishop_1_0",
    "kingSafeCheckBishop_1_1",
    "kingSafeCheckKnight_0_0",
    "kingSafeCheckKnight_0_1",
    "kingSafeCheckKnight_1_0",
    "kingSafeCheckKnight_1_1",
    "kingAttackers_0",
    "kingAttackers_1",
    "kingRingWeak_0",
    "kingRingWeak_1",
    "kingUnsafeChecks_0",
    "kingUnsafeChecks_1",
    "kingBlockersForKing_0",
    "kingBlockersForKing_1",
    "kingAttacksCount_0",
    "kingAttacksCount_1",
    "kingSqFlankAttack_0",
    "kingSqFlankAttack_1",
    "kingMobility_0",
    "kingMobility_1",
    "kingQueenCount_0",
    "kingQueenCount_1",
    "kingAttackedBy_0",
    "kingAttackedBy_1",
    "kingScore_0",
    "kingScore_1",
    "kingFlankDefense_0",
    "kingFlankDefense_1",
    "kingDangerMG_0",
    "kingDangerMG_1",
    "kingDangerEG_0",
    "kingDangerEG_1",
    "kingPawnlessFlank_0",
    "kingPawnlessFlank_1",
    "kingFlankAttack_0",
    "kingFlankAttack_1",
    # passed (10)
    "passedRank_0_0",
    "passedRank_0_1",
    "passedRank_1_0",
    "passedRank_1_1",
    "passedRank_2_0",
    "passedRank_2_1",
    "passedRank_3_0",
    "passedRank_3_1",
    "passedRank_4_0",
    "passedRank_4_1",
    "passedRank_5_0",
    "passedRank_5_1",
    "passedKingProximity_0",
    "passedKingProximity_1",
    "passedKingProximitySecond_0",
    "passedKingProximitySecond_1",
    "passedFreeToAdvance_0",
    "passedFreeToAdvance_1",
    "passedFile_0",
    "passedFile_1",
    # threats (18)
    "threatByMinor_0_0",
    "threatByMinor_0_1",
    "threatByMinor_1_0",
    "threatByMinor_1_1",
    "threatByMinor_2_0",
    "threatByMinor_2_1",
    "threatByMinor_3_0",
    "threatByMinor_3_1",
    "threatByMinor_4_0",
    "threatByMinor_4_1",
    "threatByRook_0_0",
    "threatByRook_0_1",
    "threatByRook_1_0",
    "threatByRook_1_1",
    "threatByRook_2_0",
    "threatByRook_2_1",
    "threatByRook_3_0",
    "threatByRook_3_1",
    "threatByRook_4_0",
    "threatByRook_4_1",
    "threatByKing_0",
    "threatByKing_1",
    "threatHanging_0",
    "threatHanging_1",
    "threatWeakQueenProtection_0",
    "threatWeakQueenProtection_1",
    "threatRestrictedPiece_0",
    "threatRestrictedPiece_1",
    "threatBySafePawn_0",
    "threatBySafePawn_1",
    "threatByPawnPush_0",
    "threatByPawnPush_1",
    "threatKnightOnQueen_0",
    "threatKnightOnQueen_1",
    "threatSliderOnQueen_0",
    "threatSliderOnQueen_1",
    # space (1)
    "space_0",
    "space_1",
    # winnable (10)
    "winnablePassedCount",
    "winnablePawnCount",
    "winnableOutflanking",
    "winnablePawnsOnBothFlanks",
    "winnableInfiltration",
    "winnableNonPawnMaterialZero",
    "winnableAlmostUnwinnable",
    "winnableScaleFactor",
    "winnableNonPawnMaterial",
    "winnable",  # -target
    # target
    "intermediate1MG_0",
    "intermediate1MG_1",
    "intermediate1EG_0",
    "intermediate1EG_1",
    "intermediate2MG_0",
    "intermediate2MG_1",
    "intermediate2EG_0",
    "intermediate2EG_1",
    "complexity",
    "nnue_raw_value",  # +target
    "nnue_blend_value",
    "side_to_move",
]

coefs = {
    "psqMG": (1, 0),
    "psqEG": (0, 1),
    "imbalanceMG": (1, 0),
    "imbalanceEG": (0, 1),
    "knightUncontestedOutpost": (0, 10),
    "knightOutpost": (54, 34),
    "knightReachableOutpost": (33, 19),
    "knightMinorBehindPawn": (18, 3),
    "knightKingProtector": (-9, -9),
    "bishopOnKingRing": (24, 0),
    "bishopOutpost": (31, 25),
    "bishopMinorBehindPawn": (18, 3),
    "bishopKingProtector": (-7, -9),
    "bishopPawns_0": (-3, -8),
    "bishopPawns_1": (-3, -9),
    "bishopPawns_2": (-2, -7),
    "bishopPawns_3": (-3, -7),
    "bishopXRayPawns": (-4, -5),
    "bishopLongDiagonal": (45, 0),
    "rookOnKingRing": (16, 0),
    "rookOnOpenFile_0": (18, 8),
    "rookOnOpenFile_1": (49, 26),
    "rookOnClosedFile": (-10, -5),
    "rookTrappedRook": (-55, -13),
    "queenWeakQueen": (-57, -19),
    "mobility_0_0": (1, 0),
    "mobility_0_1": (0, 1),
    "mobility_1_0": (1, 0),
    "mobility_1_1": (0, 1),
    "mobility_2_0": (1, 0),
    "mobility_2_1": (0, 1),
    "mobility_3_0": (1, 0),
    "mobility_3_1": (0, 1),
    "kingPEKingSafetyMG": (1, 0),
    "kingPEKingSafetyEG": (0, 1),
    "kingSafeCheckRook_0": (1071, 0),
    "kingSafeCheckRook_1": (1886, 0),
    "kingSafeCheckQueen_0": (730, 0),
    "kingSafeCheckQueen_1": (1128, 0),
    "kingSafeCheckBishop_0": (650, 0),
    "kingSafeCheckBishop_1": (984, 0),
    "kingSafeCheckKnight_0": (805, 0),
    "kingSafeCheckKnight_1": (1292, 0),
    "kingAttackers": (1, 0),
    "kingRingWeak": (183, 0),
    "kingUnsafeChecks": (148, 0),
    "kingBlockersForKing": (98, 0),
    "kingAttacksCount": (69, 0),
    "kingSqFlankAttack": (3 / 2**3, 0 / 2**3),
    "kingMobility": (1, 0),
    "kingQueenCount": (-873, 0),
    "kingAttackedBy": (-100, 0),
    "kingScore": (-6 / 2**3, 0 / 2**3),
    "kingFlankDefense": (-4, 0),
    "kingDangerMG": (-1, 0),
    "kingDangerEG": (0, -1),
    "kingPawnlessFlank": (-19, -97),
    "kingFlankAttack": (-8, 0),
    "threatByMinor_0": (6, 37),
    "threatByMinor_1": (64, 50),
    "threatByMinor_2": (82, 57),
    "threatByMinor_3": (103, 130),
    "threatByMinor_4": (81, 163),
    "threatByRook_0": (3, 44),
    "threatByRook_1": (36, 71),
    "threatByRook_2": (44, 59),
    "threatByRook_3": (0, 39),
    "threatByRook_4": (60, 39),
    "threatByKing": (24, 87),
    "threatHanging": (72, 40),
    "threatWeakQueenProtection": (14, 0),
    "threatRestrictedPiece": (6, 7),
    "threatBySafePawn": (167, 99),
    "threatByPawnPush": (48, 39),
    "threatKnightOnQueen": (16, 11),
    "threatSliderOnQueen": (62, 21),
    "passedRank_0": (2, 38),
    "passedRank_1": (15, 36),
    "passedRank_2": (22, 50),
    "passedRank_3": (64, 81),
    "passedRank_4": (166, 184),
    "passedRank_5": (284, 269),
    "passedKingProximity": (0, 1),
    "passedKingProximitySecond": (0, -1),
    "passedFreeToAdvance": (1, 1),
    "passedFile": (-13, -8),
    "space": (1 / 2**4, 0 / 2**4),
    "winnablePassedCount": (9, 0),
    "winnablePawnCount": (12, 0),
    "winnableOutflanking": (9, 0),
    "winnablePawnsOnBothFlanks": (21, 0),
    "winnableInfiltration": (24, 0),
    "winnableNonPawnMaterialZero": (51, 0),
    "winnableAlmostUnwinnable": (-43, 0),
    "winnableScaleFactor": (0, 0),
    "winnableNonPawnMaterial": (0, 0),
    "pawnMG": (1, 0),
    "pawnEG": (0, 1),
    "winnable": (0, 0),
    "intermediate1MG": (0, 0),
    "intermediate1EG": (0, 0),
    "intermediate2MG": (0, 0),
    "intermediate2EG": (0, 0),
    "complexity": (0, 0),
    "nnue_raw_value": (0, 0),
    "nnue_blend_value": (0, 0),
    "side_to_move": (0, 0),
}

replacement_features = [
    "kingSafeCheckRook_0",
    "kingSafeCheckRook_1",
    "kingSafeCheckQueen_0",
    "kingSafeCheckQueen_1",
    "kingSafeCheckBishop_0",
    "kingSafeCheckBishop_1",
    "kingSafeCheckKnight_0",
    "kingSafeCheckKnight_1",
    "kingAttackers",
    "kingRingWeak",
    "kingUnsafeChecks",
    "kingBlockersForKing",
    "kingAttacksCount",
    "kingSqFlankAttack",
    "kingMobility",
    "kingQueenCount",
    "kingAttackedBy",
    "kingScore",
    "kingFlankDefense",
    "winnablePassedCount",
    "winnablePawnCount",
    "winnableOutflanking",
    "winnablePawnsOnBothFlanks",
    "winnableInfiltration",
    "winnableNonPawnMaterialZero",
    "winnableAlmostUnwinnable",
]
replacement = {}
for feature_name in replacement_features:
    replacement[feature_name] = coefs[feature_name]
    coefs[feature_name] = (0, 0)
    # for color in range(2):
    #     coefs[f"{feature_name}_{color}"] = (0, 0)

print(f"{len(feature_names)=}")

adder_features = [
    "rookOnKingRing", "bishopOnKingRing", "knightOutpost", "bishopOutpost", "knightReachableOutpost",
    "knightMinorBehindPawn", "bishopMinorBehindPawn", "bishopLongDiagonal", "rookOnOpenFile_0", "rookOnOpenFile_1", "rookOnClosedFile",
    "queenWeakQueen", "kingSafeCheckRook_0", "kingSafeCheckRook_1", "kingSafeCheckQueen_0", "kingSafeCheckQueen_1",
    "kingSafeCheckBishop_0", "kingSafeCheckBishop_1", "kingSafeCheckKnight_0", "kingSafeCheckKnight_1",
    "kingPawnlessFlank", "threatByMinor_0", "threatByMinor_1", "threatByMinor_2", "threatByMinor_3", "threatByMinor_4",
    "threatByRook_0", "threatByRook_1", "threatByRook_2", "threatByRook_3", "threatByRook_4", "threatByKing",
    "passedRank_0", "passedRank_1", "passedRank_2", "passedRank_3", "passedRank_4", "passedRank_5",
    "winnablePawnsOnBothFlanks", "winnableInfiltration", "winnableNonPawnMaterialZero", "winnableAlmostUnwinnable",
]

white_cols = feature_names[:feature_names.index("winnablePassedCount"):2]
black_cols = feature_names[1:feature_names.index("winnablePassedCount"):2]
common_cols = feature_names[feature_names.index("winnablePassedCount"):feature_names.index("intermediate1MG_0")]
side_to_move_col = "side_to_move"
