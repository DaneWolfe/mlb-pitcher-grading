import numpy as np
import pandas as pd
import pytest
import torch
from pitchlab.features import add_arm_side_break, add_location
from pitchlab.model import PITCH, SEASON_AVG, Columns, Model, PitchNet, _weights, baseline_type_average, encode, fit, new_seed, predict, split_by_season, split_validation, weighted_rmse

# A plain mean of the two FF rows would be 2.5; weighting by pitches pulls it toward the 300-pitch row
def test_baseline_is_the_pitch_weighted_average_per_type():
    train = pd.DataFrame({
        "pitch_type": pd.Categorical(["FF", "FF", "SL"]),
        "run_value_per100": [1.0, 4.0, 2.0],
        "pitches": [300, 100, 50],
    })
    rows = pd.DataFrame({"pitch_type": pd.Categorical(["SL", "FF"])})
    assert baseline_type_average(train, rows).tolist() == pytest.approx([2.0, 1.75])

def test_baseline_uses_the_label_and_weight_of_the_columns_it_is_given():
    train = pd.DataFrame({"pitch_type": ["FF", "FF", "SL"], "y": [1.0, 3.0, 5.0]})
    rows = pd.DataFrame({"pitch_type": ["FF", "SL"]})
    assert baseline_type_average(train, rows, TINY).tolist() == pytest.approx([2.0, 5.0])

# A type missing from train gives NaN instead of an error, which weighted_rmse then passes on as NaN
def test_baseline_gives_nan_for_a_pitch_type_not_in_train():
    train = pd.DataFrame({"pitch_type": ["FF"], "y": [1.0]})
    rows = pd.DataFrame({"pitch_type": ["FF", "SV"]})
    assert baseline_type_average(train, rows, TINY).isna().tolist() == [False, True]


TINY = Columns(categories = ["pitch_type", "stand"], numbers = ["a", "b"], label = "y", weight = None)

def make_rows(types, stands):
    n = len(types)
    return pd.DataFrame({"pitch_type": types, "stand": stands, "a": [1.0] * n, "b": [10.0] * n})

# Both models use the same column names the feature functions produce, so a rename in one place is caught
def test_pitch_columns_are_all_produced_by_the_feature_functions():
    pitches = pd.DataFrame({
        "p_throws": ["R", "L"], "stand": ["L", "R"], "hb_in": [-7.0, 8.0],
        "plate_x_in": [3.0, -3.0], "plate_z_in": [30.0, 30.0], "sz_top_in": [42.0, 42.0], "sz_bot_in": [18.0, 18.0],
        "balls": [1, 3], "strikes": [2, 2], "pitch_type": ["FF", "SL"], "velo_mph": [95.0, 85.0],
        "spin_rpm": [2300.0, 2500.0], "ivb_in": [16.0, 2.0], "run_value": [0.1, -0.1],
    })
    rows = add_location(add_arm_side_break(pitches))
    assert set(PITCH.categories + PITCH.numbers + [PITCH.label]) <= set(rows.columns)

# Embedding tables kept in a plain list would silently never train; they must show up as parameters
def test_pitchnet_registers_one_embedding_table_per_category_column():
    net = PitchNet(n_values = [11, 2, 12], n_numbers = 4)
    shapes = [tuple(p.shape) for p in net.parameters()]
    assert (11, 4) in shapes
    assert (2, 2) in shapes
    assert (12, 4) in shapes

# The means and stds passed in are used as given, never recomputed from the rows being encoded
def test_encode_standardizes_with_the_given_means_and_stds():
    means = pd.Series([0.0, 4.0], index = ["a", "b"])
    stds = pd.Series([2.0, 3.0], index = ["a", "b"])
    maps = {"pitch_type": {"FF": 0, "SL": 1}, "stand": {"R": 0, "L": 1}}
    category_idx, numbers = encode(make_rows(["SL", "FF"], ["L", "R"]), TINY, maps, means, stds)
    assert [c.tolist() for c in category_idx] == [[1, 0], [1, 0]]
    assert numbers[0].tolist() == pytest.approx([0.5, 2.0])

def test_encode_rejects_a_value_not_seen_in_training():
    means = pd.Series([0.0, 0.0], index = ["a", "b"])
    stds = pd.Series([1.0, 1.0], index = ["a", "b"])
    maps = {"pitch_type": {"FF": 0}, "stand": {"R": 0}}
    with pytest.raises(ValueError, match = "not seen in training"):
        encode(make_rows(["FF", "SV"], ["R", "R"]), TINY, maps, means, stds)

def test_weights_are_all_ones_without_a_weight_column_and_the_column_otherwise():
    rows = pd.DataFrame({"pitches": [30, 120]})
    assert _weights(rows, TINY).tolist() == [1.0, 1.0]
    weighted = Columns(categories = [], numbers = [], label = "y", weight = "pitches")
    assert _weights(rows, weighted).tolist() == [30.0, 120.0]

def test_predict_returns_one_value_per_row_with_the_rows_index():
    torch.manual_seed(0)
    model = Model(
        net = PitchNet(n_values = [2, 2], n_numbers = 2),
        columns = TINY,
        category_maps = {"pitch_type": {"FF": 0, "SL": 1}, "stand": {"R": 0, "L": 1}},
        means = pd.Series([0.0, 0.0], index = ["a", "b"]),
        stds = pd.Series([1.0, 1.0], index = ["a", "b"]),
        seed = 0,
    )
    rows = make_rows(["FF", "SL"], ["R", "L"])
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

def test_split_by_season_sends_the_test_seasons_to_test_and_keeps_every_row_once():
    df = pd.DataFrame({"season": [2023, 2024, 2025, 2026, 2025], "x": range(5)})
    train, test = split_by_season(df, [2025, 2026])
    assert train["season"].tolist() == [2023, 2024]
    assert test["season"].tolist() == [2025, 2026, 2025]
    assert sorted(train.index.tolist() + test.index.tolist()) == [0, 1, 2, 3, 4]

def test_split_by_season_with_no_matching_season_leaves_test_empty():
    df = pd.DataFrame({"season": [2023, 2024]})
    train, test = split_by_season(df, [2030])
    assert len(train) == 2
    assert len(test) == 0

def test_weighted_rmse_without_weights_is_the_root_of_the_mean_squared_error():
    rows = pd.DataFrame({"y": [0.0, 0.0]})
    assert weighted_rmse(pd.Series([1.0, 3.0]), rows, TINY) == pytest.approx(np.sqrt(5.0))

# Errors of 1 and 3 with weights 1 and 3: (1 * 1 + 3 * 9) / 4 = 7
def test_weighted_rmse_counts_each_row_in_proportion_to_its_weight():
    columns = Columns(categories = [], numbers = [], label = "y", weight = "pitches")
    rows = pd.DataFrame({"y": [0.0, 0.0], "pitches": [1, 3]})
    assert weighted_rmse(pd.Series([1.0, 3.0]), rows, columns) == pytest.approx(np.sqrt(7.0))

def test_weighted_rmse_is_zero_for_perfect_predictions():
    rows = pd.DataFrame({"y": [0.5, -0.2]})
    assert weighted_rmse(pd.Series([0.5, -0.2]), rows, TINY) == 0.0

# A missing prediction must show up in the score, not be skipped
def test_weighted_rmse_is_nan_when_a_prediction_is_missing():
    rows = pd.DataFrame({"y": [0.0, 0.0]})
    assert np.isnan(weighted_rmse(pd.Series([np.nan, 1.0]), rows, TINY))

def pitch_rows(n = 200):
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "pitch_type": rng.choice(["FF", "SL", "CH"], n),
        "p_throws": rng.choice(["R", "L"], n),
        "stand": rng.choice(["R", "L"], n),
        "count": rng.choice(["0-0", "1-2", "3-2"], n),
        "velo_mph": rng.normal(90, 3, n),
        "spin_rpm": rng.normal(2300, 150, n),
        "ivb_in": rng.normal(12, 4, n),
        "hb_arm_in": rng.normal(6, 4, n),
        "plate_x_away_in": rng.normal(0, 8, n),
        "zone_height": rng.normal(0.5, 0.4, n),
        "run_value": rng.normal(0, 0.2, n),
    })

def season_rows(n = 200):
    rng = np.random.default_rng(1)
    return pd.DataFrame({
        "pitch_type": rng.choice(["FF", "SL", "CH"], n),
        "p_throws": rng.choice(["R", "L"], n),
        "velo_mph": rng.normal(90, 3, n),
        "spin_rpm": rng.normal(2300, 150, n),
        "ivb_in": rng.normal(12, 4, n),
        "hb_arm_in": rng.normal(6, 4, n),
        "run_value_per100": rng.normal(0, 1, n),
        "pitches": rng.integers(30, 500, n),
    })


# Weight init, the validation split and batch order must all come from the seed, or runs can't be repeated
def test_fit_with_the_same_seed_gives_the_same_predictions():
    train = pitch_rows()
    first = fit(train, seed = 7)
    second = fit(train, seed = 7)
    assert first.seed == 7
    assert predict(first, train).tolist() == pytest.approx(predict(second, train).tolist())

def test_fit_without_a_seed_draws_one_and_stores_it():
    model = fit(pitch_rows(), seed = None)
    assert 0 <= model.seed < 2**32

def test_fit_rejects_a_kind_other_than_mlp():
    with pytest.raises(NotImplementedError):
        fit(pitch_rows(), kind = "gbm")

def test_fit_uses_the_pitch_columns_by_default_and_builds_a_map_per_category():
    model = fit(pitch_rows(), seed = 1)
    assert model.columns == PITCH
    assert set(model.category_maps) == set(PITCH.categories)
    assert sorted(model.category_maps["count"]) == ["0-0", "1-2", "3-2"]
    assert sorted(model.category_maps["pitch_type"]) == ["CH", "FF", "SL"]

def test_fit_works_with_the_weighted_season_average_columns():
    train = season_rows()
    model = fit(train, columns = SEASON_AVG, seed = 1)
    assert model.columns == SEASON_AVG
    out = predict(model, train)
    assert len(out) == len(train)
    assert out.notna().all()

def test_predict_after_fit_rejects_a_count_never_seen_in_training():
    model = fit(pitch_rows(), seed = 1)
    rows = pitch_rows(5)
    rows["count"] = "2-2"
    with pytest.raises(ValueError, match = "not seen in training"):
        predict(model, rows)

# Without this, a fit that returned an untrained network would pass every other test: they only check
# shapes, seeds and names. Here run value follows velocity, so a trained model must track it
def test_fit_learns_a_relationship_that_is_in_the_data():
    train = pitch_rows(3000)
    noise = np.random.default_rng(5).normal(0, 0.02, len(train))
    train["run_value"] = 0.1 * (train["velo_mph"] - 90) + noise
    model = fit(train, seed = 3)
    predicted = predict(model, train)
    assert np.corrcoef(predicted, train["run_value"])[0, 1] > 0.9
