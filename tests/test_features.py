import pandas as pd
import pytest
from pitchlab.config import MIN_PITCH_TYPE_PITCHES
from pitchlab.features import add_arm_side_break, build_pitch_seasons

# Values are typical 2025 averages (inches): right-handed four-seamer about -7.6, left-handed about +8.1,
# right-handed slider about +4.2, left-handed about -4.0
def make_pitches(*rows):
    return pd.DataFrame(list(rows), columns = ["p_throws", "hb_in"]).astype({"hb_in": "float32"})

def test_both_hands_get_the_same_sign_for_arm_side_pitches():
    result = add_arm_side_break(make_pitches(("R", -7.6), ("L", 8.1)))
    assert result["hb_arm_in"].tolist() == pytest.approx([-7.6, -8.1])

def test_glove_side_pitches_are_positive_for_both_hands():
    result = add_arm_side_break(make_pitches(("R", 4.2), ("L", -4.0)))
    assert result["hb_arm_in"].tolist() == pytest.approx([4.2, 4.0])

def test_right_handers_are_unchanged_and_left_handers_flipped():
    result = add_arm_side_break(make_pitches(("R", 3.0), ("L", 3.0)))
    assert result["hb_arm_in"].tolist() == [3.0, -3.0]

def test_unknown_hand_raises():
    with pytest.raises(ValueError, match = "1 rows"):
        add_arm_side_break(make_pitches(("R", 1.0), ("S", 1.0)))

def test_missing_hand_raises():
    with pytest.raises(ValueError, match = "1 rows"):
        add_arm_side_break(make_pitches(("R", 1.0), (None, 1.0)))

def test_input_is_not_modified_and_hb_in_is_kept():
    pitches = make_pitches(("L", 8.1))
    result = add_arm_side_break(pitches)
    assert "hb_arm_in" not in pitches.columns
    assert result["hb_in"].tolist() == pitches["hb_in"].tolist()

def test_result_is_float32_even_when_hand_is_a_category():
    pitches = make_pitches(("R", -7.6), ("L", 8.1))
    pitches["p_throws"] = pitches["p_throws"].astype("category")
    result = add_arm_side_break(pitches)
    assert result["hb_arm_in"].dtype == "float32"


def make_block(pitcher_id, season, pitch_type, n, velo = 90.0, spin = 2200.0, ivb = 15.0, hb_arm = -8.0,
               run_value = 0.0, hand = "R", name = "Test Pitcher"):
    return pd.DataFrame({
        "pitcher_id": [pitcher_id] * n,
        "season": [season] * n,
        "pitch_type": [pitch_type] * n,
        "player_name": [name] * n,
        "p_throws": [hand] * n,
        "velo_mph": [velo] * n,
        "spin_rpm": [spin] * n,
        "ivb_in": [ivb] * n,
        "hb_arm_in": [hb_arm] * n,
        "run_value": [run_value] * n,
    }).astype({"pitch_type": "category", "p_throws": "category", "run_value": "float32"})

def make_season_pitches(*blocks):
    return pd.concat(blocks, ignore_index = True)

def test_one_row_per_pitcher_season_and_pitch_type():
    pitches = make_season_pitches(
        make_block(1, 2024, "FF", 40),
        make_block(1, 2024, "SL", 35),
        make_block(1, 2025, "FF", 50),
        make_block(2, 2024, "FF", 60),
    )
    result = build_pitch_seasons(pitches)
    assert len(result) == 4
    assert not result.duplicated(["pitcher_id", "season", "pitch_type"]).any()

def test_means_counts_and_run_value_per100():
    first = make_block(1, 2024, "FF", 20, velo = 90.0, run_value = 0.01)
    second = make_block(1, 2024, "FF", 20, velo = 94.0, run_value = -0.03)
    result = build_pitch_seasons(make_season_pitches(first, second))
    row = result.iloc[0]
    assert row["pitches"] == 40
    assert row["velo_mph"] == pytest.approx(92.0)
    assert row["run_value_total"] == pytest.approx(20 * 0.01 + 20 * -0.03)
    assert row["run_value_per100"] == pytest.approx(-1.0)

def test_pitch_type_needs_the_minimum_number_of_pitches():
    pitches = make_season_pitches(
        make_block(1, 2024, "FF", MIN_PITCH_TYPE_PITCHES),
        make_block(1, 2024, "SL", MIN_PITCH_TYPE_PITCHES - 1),
    )
    result = build_pitch_seasons(pitches)
    assert result["pitch_type"].tolist() == ["FF"]

def test_season_pitches_counts_the_dropped_pitch_types_too():
    pitches = make_season_pitches(
        make_block(1, 2024, "FF", 60),
        make_block(1, 2024, "SL", 10),
    )
    row = build_pitch_seasons(pitches).iloc[0]
    assert row["season_pitches"] == 70
    assert row["usage"] == pytest.approx(60 / 70)

def test_season_pitches_is_per_pitcher_and_season():
    pitches = make_season_pitches(
        make_block(1, 2024, "FF", 40),
        make_block(1, 2025, "FF", 50),
        make_block(2, 2024, "FF", 60),
    )
    result = build_pitch_seasons(pitches).set_index(["pitcher_id", "season"])
    assert result.loc[(1, 2024), "season_pitches"] == 40
    assert result.loc[(1, 2025), "season_pitches"] == 50
    assert result.loc[(2, 2024), "season_pitches"] == 60

def test_identity_columns_and_hand_are_carried_over():
    pitches = make_season_pitches(make_block(7, 2024, "CH", 40, hand = "L", name = "Lefty Example"))
    row = build_pitch_seasons(pitches).iloc[0]
    assert row["player_name"] == "Lefty Example"
    assert row["p_throws"] == "L"
    assert row["pitcher_id"] == 7

def test_build_input_is_not_modified():
    pitches = make_season_pitches(make_block(1, 2024, "FF", 40))
    before = pitches.copy()
    build_pitch_seasons(pitches)
    pd.testing.assert_frame_equal(pitches, before)
