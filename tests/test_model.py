import pandas as pd
import pytest
import torch
from pitchlab.model import NUMBERS, Model, PitchNet, baseline_type_average, encode, new_seed, predict, split_validation

# A plain mean of the two FF rows would be 2.5; weighting by pitches pulls it toward the 300-pitch row
def test_baseline_is_the_pitch_weighted_average_per_type():
    train = pd.DataFrame({
        "pitch_type": pd.Categorical(["FF", "FF", "SL"]),
        "run_value_per100": [1.0, 4.0, 2.0],
        "pitches": [300, 100, 50],
    })
    rows = pd.DataFrame({"pitch_type": pd.Categorical(["SL", "FF"])})
    assert baseline_type_average(train, rows).tolist() == pytest.approx([2.0, 1.75])


def test_pitchnet_returns_one_value_per_row():
    net = PitchNet(n_types=11)
    out = net(torch.tensor([0, 3, 10]), torch.tensor([0, 1, 1]), torch.randn(3, 4))
    assert out.shape == (3,)


def _rows(types, hands):
    n = len(types)
    return pd.DataFrame({
        "pitch_type": types,
        "p_throws": hands,
        "velo_mph": [90.0] * n,
        "spin_rpm": [2200.0] * n,
        "ivb_in": [10.0] * n,
        "hb_arm_in": [-8.0] * n,
    })


# The means and stds passed in are used as given, never recomputed from the rows being encoded
def test_encode_standardizes_with_the_given_means_and_stds():
    means = pd.Series([88.0, 2000.0, 12.0, -6.0], index=NUMBERS)
    stds = pd.Series([2.0, 100.0, 4.0, 2.0], index=NUMBERS)
    type_idx, hand_idx, numbers = encode(_rows(["SL", "FF"], ["L", "R"]), {"FF": 0, "SL": 1}, {"R": 0, "L": 1}, means, stds)
    assert type_idx.tolist() == [1, 0]
    assert hand_idx.tolist() == [1, 0]
    assert numbers[0].tolist() == pytest.approx([1.0, 2.0, -0.5, -1.0])


def test_encode_rejects_a_pitch_type_not_seen_in_training():
    means = pd.Series([0.0] * 4, index=NUMBERS)
    stds = pd.Series([1.0] * 4, index=NUMBERS)
    with pytest.raises(ValueError, match="not seen in training"):
        encode(_rows(["FF", "SV"], ["R", "R"]), {"FF": 0}, {"R": 0}, means, stds)


def test_predict_returns_one_value_per_row_with_the_rows_index():
    torch.manual_seed(0)
    model = Model(
        net=PitchNet(n_types=2),
        type_map={"FF": 0, "SL": 1},
        hand_map={"R": 0, "L": 1},
        means=pd.Series([90.0, 2200.0, 10.0, -8.0], index=NUMBERS),
        stds=pd.Series([2.0, 100.0, 4.0, 2.0], index=NUMBERS),
        seed=0,
    )
    rows = _rows(["FF", "SL"], ["R", "L"])
    rows.index = [5, 7]
    out = predict(model, rows)
    assert out.index.tolist() == [5, 7]
    assert out.notna().all()


def test_split_validation_partitions_the_rows_and_repeats_with_the_same_seed():
    train = pd.DataFrame({"x": range(1000)})
    fit_rows, val_rows = split_validation(train, seed=3)
    assert len(fit_rows) + len(val_rows) == 1000
    assert set(fit_rows.index).isdisjoint(val_rows.index)
    assert 50 < len(val_rows) < 150
    _, val_again = split_validation(train, seed=3)
    assert val_again.index.tolist() == val_rows.index.tolist()


def test_new_seed_fits_in_32_bits():
    assert 0 <= new_seed() < 2**32
