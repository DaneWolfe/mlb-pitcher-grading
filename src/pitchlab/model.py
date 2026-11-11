"""Pitch model: a small PyTorch network and the type-average baseline it must beat."""

import pandas as pd
import numpy as np
import torch
from torch import nn
from dataclasses import dataclass

FEATURES = ["pitch_type", "p_throws", "velo_mph", "spin_rpm", "ivb_in", "hb_arm_in"]
LABEL = "run_value_per100"
WEIGHT = "pitches"
NUMBERS = ["velo_mph", "spin_rpm", "ivb_in", "hb_arm_in"]

class PitchNet(nn.Module):
    """Small neural network: learned vectors for pitch type and hand, plus four numbers, through two hidden layers."""

    def __init__(self, n_types: int, n_hands: int = 2, n_numbers: int = 4, hidden: int = 32) -> None:
        super().__init__()
        # Each embedding is a lookup table of trainable numbers: 4 per pitch type, 2 per hand
        self.type_embedding = nn.Embedding(n_types, 4)
        self.hand_embedding = nn.Embedding(n_hands, 2)
        self.layers = nn.Sequential(
            # First layer's input size must equal the width of the glued row: 4 + 2 + the numbers
            nn.Linear(4 + 2 + n_numbers, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1)
        )

    def forward(self, type_idx: torch.Tensor, hand_idx: torch.Tensor, numbers: torch.Tensor) -> torch.Tensor:
        """Predict a run value per 100 for each row of a batch."""

        x = torch.cat([self.type_embedding(type_idx), self.hand_embedding(hand_idx), numbers], dim = 1)
        # The last layer gives shape (batch, 1); squeeze(1) flattens it to (batch,) to match the labels
        return self.layers(x).squeeze(1)

@dataclass
class Model:
    """A trained network plus the maps, means, stds and seed that predict() needs."""

    net: PitchNet
    type_map: dict[str, int]
    hand_map: dict[str, int]
    means: pd.Series
    stds: pd.Series
    seed: int

def _category_codes(column: pd.Series, mapping: dict[str, int]) -> torch.Tensor:
    """Turn a text column into integer codes using `mapping`. Internal helper for encode."""

    codes = column.astype(str).map(mapping)
    # A value missing from the mapping becomes NaN, which would turn into a garbage integer below
    unseen = int(codes.isna().sum())

    if unseen > 0:
        raise ValueError(f"{unseen} rows in {column.name} have a value not seen in training")

    return torch.tensor(codes.to_numpy(), dtype = torch.long)

def encode(rows: pd.DataFrame, type_map: dict[str, int], hand_map: dict[str, int], means: pd.Series, stds: pd.Series) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Turn rows into (type codes, hand codes, standardized numbers). means/stds must come from the training rows."""

    type_idx = _category_codes(rows["pitch_type"], type_map)
    hand_idx = _category_codes(rows["p_throws"], hand_map)
    numbers = torch.tensor(((rows[NUMBERS] - means) / stds).to_numpy(), dtype = torch.float32)

    return type_idx, hand_idx, numbers

def baseline_type_average(train: pd.DataFrame, rows: pd.DataFrame) -> pd.Series:
    """Predict each row's pitch type's pitch-weighted average run value per 100 in `train`."""

    types = train["pitch_type"].astype(str)

    weighted_sum = (train[LABEL] * train[WEIGHT]).groupby(types).sum()
    total_weight = train[WEIGHT].groupby(types).sum()

    averages = weighted_sum / total_weight

    return rows["pitch_type"].astype(str).map(averages)

def predict(model: Model, rows: pd.DataFrame) -> pd.Series:
    """Return the model's predicted run value per 100 for `rows`, as a Series with the same index."""

    inputs = encode(rows, model.type_map, model.hand_map, model.means, model.stds)
    model.net.eval()

    # no_grad skips the bookkeeping PyTorch keeps for training; predicting doesn't need it
    with torch.no_grad():
        out = model.net(*inputs)

    return pd.Series(out.numpy(), index = rows.index)

def new_seed() -> int:
    """Draw a fresh random seed (32-bit). Log it and store it with the results so the run can be repeated."""

    # SeedSequence().entropy is 128 bits, too big for torch.manual_seed, so it is cut down to 32 bits
    return int(np.random.SeedSequence().entropy % 2 ** 32)

def split_validation(train: pd.DataFrame, seed: int, fraction: float = 0.1) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Randomly set aside about `fraction` of `train` for validation. Returns (fit_rows, validation_rows)."""

    # One random number per row; rows below `fraction` become validation. Same seed -> same split
    is_validation = np.random.default_rng(seed).random(len(train)) < fraction

    return train[~is_validation], train[is_validation]