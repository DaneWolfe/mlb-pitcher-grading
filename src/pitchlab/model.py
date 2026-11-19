"""Pitch model: a small PyTorch network and the type-average baseline it must beat."""

import pandas as pd
import numpy as np
import torch
import copy
import logging
from torch import nn
from dataclasses import dataclass

logger = logging.getLogger(__name__)

LABEL = "run_value_per100"
WEIGHT = "pitches"

BATCH_SIZE = 256
MAX_EPOCHS = 300
PATIENCE = 20
LEARNING_RATE = 1e-3

@dataclass(frozen = True)
class Columns:
    """Which columns a model reads: category columns, number columns, the label, and an optional weight."""

    categories: list[str]
    numbers: list[str]
    label: str
    weight: str | None

PITCH = Columns(
    categories = ["pitch_type", "p_throws", "stand", "count"],
    numbers = ["velo_mph", "spin_rpm", "ivb_in", "hb_arm_in", "plate_x_away_in", "zone_height"],
    label = "run_value",
    weight = None
)

SEASON_AVG = Columns(
    categories = ["pitch_type", "p_throws"],
    numbers = ["velo_mph", "spin_rpm", "ivb_in", "hb_arm_in"],
    label = "run_value_per100",
    weight = "pitches"
)

class PitchNet(nn.Module):
    """Small neural network: a learned vector per category column, plus the numbers, through two hidden layers."""

    def __init__(self, n_values: list[int], n_numbers: int, hidden: int = 32) -> None:
        super().__init__()
        # One lookup table of trainable numbers per category column, min(4, values) wide. It has to be a
        # ModuleList: tables in a plain list would never be trained
        self.embeddings = nn.ModuleList([nn.Embedding(n, min(4, n)) for n in n_values])
        width = sum(min(4, n) for n in n_values) + n_numbers
        self.layers = nn.Sequential(
            # First layer's input size must equal the width of the glued row: every embedding plus the numbers
            nn.Linear(width, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, 1)
        )

    def forward(self, category_idx: list[torch.Tensor], numbers: torch.Tensor) -> torch.Tensor:
        """Predict a value for each row of a batch."""

        vectors = [embedding(idx) for embedding, idx in zip(self.embeddings, category_idx)]
        x = torch.cat(vectors + [numbers], dim = 1)
        # The last layer gives shape (batch, 1); squeeze(1) flattens it to (batch,) to match the labels
        return self.layers(x).squeeze(1)

@dataclass
class Model:
    """A trained network plus the columns, maps, means, stds, and seed that predict() needs."""

    net: PitchNet
    columns: Columns
    category_maps: dict[str, dict[str, int]]
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

def encode(rows: pd.DataFrame, columns: Columns, category_maps: dict[str, dict[str, int]], means: pd.Series, stds: pd.Series) -> tuple[list[torch.Tensor], torch.Tensor]:
    """Turn rows into (one code tensor per category column, standardized numbers). means/stds must come from the training rows."""

    category_idx = [_category_codes(rows[c], category_maps[c]) for c in columns.categories]
    numbers = torch.tensor(((rows[columns.numbers] - means) / stds).to_numpy(), dtype = torch.float32)

    return category_idx, numbers

def baseline_type_average(train: pd.DataFrame, rows: pd.DataFrame) -> pd.Series:
    """Predict each row's pitch type's pitch-weighted average run value per 100 in `train`."""

    types = train["pitch_type"].astype(str)

    weighted_sum = (train[LABEL] * train[WEIGHT]).groupby(types).sum()
    total_weight = train[WEIGHT].groupby(types).sum()

    averages = weighted_sum / total_weight

    return rows["pitch_type"].astype(str).map(averages)

def predict(model: Model, rows: pd.DataFrame) -> pd.Series:
    """Return the model's predicted value for `rows` (in the units of its label), as a Series with the same index."""

    inputs = encode(rows, model.columns, model.category_maps, model.means, model.stds)
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

def _weighted_mse(pred: torch.Tensor, target: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:

    return (weight * (pred - target) ** 2).sum() / weight.sum()

def _weights(rows: pd.DataFrame, columns: Columns) -> torch.Tensor:
    """Each row's weight: the weight column if there is one, otherwise 1 for every row."""

    if columns.weight is None:
        return torch.ones(len(rows))

    return torch.tensor(rows[columns.weight].to_numpy(), dtype = torch.float32)

def fit(train: pd.DataFrame, columns: Columns = PITCH, kind: str = "mlp", seed: int | None = None) -> Model:

    if kind != "mlp":
        raise NotImplementedError("Only choice available is mlp")

    if seed is None:
        seed = new_seed()
    logger.info("Training with seed %d", seed)

    torch.manual_seed(seed)

    category_maps = {
        c: {v: i for i, v in enumerate(sorted(train[c].astype(str).unique()))}
        for c in columns.categories
    }

    means = train[columns.numbers].mean()
    stds = train[columns.numbers].std()

    fit_rows, val_rows = split_validation(train, seed)

    fit_in = encode(fit_rows, columns, category_maps, means, stds)
    val_in = encode(val_rows, columns, category_maps, means, stds)

    fit_y = torch.tensor(fit_rows[columns.label].to_numpy(), dtype = torch.float32)
    fit_w = _weights(fit_rows, columns)

    val_y = torch.tensor(val_rows[columns.label].to_numpy(), dtype = torch.float32)
    val_w = _weights(val_rows, columns)

    net = PitchNet([len(category_maps[c]) for c in columns.categories], len(columns.numbers))
    optimizer = torch.optim.Adam(net.parameters(), lr = LEARNING_RATE)
    shuffler = torch.Generator().manual_seed(seed)

    best_loss = float("inf")
    best_state = copy.deepcopy(net.state_dict())
    stale_epochs = 0

    for epoch in range(MAX_EPOCHS):
        net.train()
        order = torch.randperm(len(fit_rows), generator = shuffler)

        for start in range(0, len(order), BATCH_SIZE):
            idx = order[start:start + BATCH_SIZE]
            pred = net([c[idx] for c in fit_in[0]], fit_in[1][idx])
            loss = _weighted_mse(pred, fit_y[idx], fit_w[idx])

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        net.eval()
        with torch.no_grad():
            val_loss = _weighted_mse(net(*val_in), val_y, val_w).item()

        if val_loss < best_loss:
            best_loss = val_loss
            best_state = copy.deepcopy(net.state_dict())
            stale_epochs = 0
        else:
            stale_epochs += 1
            if stale_epochs >= PATIENCE:
                break

    net.load_state_dict(best_state)
    logger.info("Stopped after %d epochs, best validation loss: %.4f", epoch + 1, best_loss)

    return Model(net, columns, category_maps, means, stds, seed)