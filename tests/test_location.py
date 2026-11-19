import pandas as pd
import pytest
from pitchlab.features import add_location

# Inches. A typical zone runs from about 18 (bottom) to 42 (top)
def make_pitches(*rows):
    return pd.DataFrame(list(rows), columns = ["stand", "plate_x_in", "plate_z_in", "sz_top_in", "sz_bot_in", "balls", "strikes"]).astype({
        "plate_x_in": "float32", "plate_z_in": "float32", "sz_top_in": "float32", "sz_bot_in": "float32",
        "balls": "int8", "strikes": "int8",
    })

# Savant's plate_x is positive toward first base. Right-handed batters stand on the third-base side,
# so for them positive is already away; left-handed batters are flipped
def test_away_is_positive_for_both_batter_sides():
    result = add_location(make_pitches(("R", 3.0, 30.0, 42.0, 18.0, 0, 0), ("L", -3.0, 30.0, 42.0, 18.0, 0, 0)))
    assert result["plate_x_away_in"].tolist() == [3.0, 3.0]

def test_inside_pitches_are_negative_for_both_batter_sides():
    result = add_location(make_pitches(("R", -5.0, 30.0, 42.0, 18.0, 0, 0), ("L", 5.0, 30.0, 42.0, 18.0, 0, 0)))
    assert result["plate_x_away_in"].tolist() == [-5.0, -5.0]

def test_zone_height_is_0_at_the_bottom_edge_and_1_at_the_top_edge():
    result = add_location(make_pitches(("R", 0.0, 18.0, 42.0, 18.0, 0, 0), ("R", 0.0, 42.0, 42.0, 18.0, 0, 0), ("R", 0.0, 30.0, 42.0, 18.0, 0, 0)))
    assert result["zone_height"].tolist() == pytest.approx([0.0, 1.0, 0.5])

def test_zone_height_is_outside_0_to_1_for_pitches_outside_the_zone():
    result = add_location(make_pitches(("R", 0.0, 12.0, 42.0, 18.0, 0, 0), ("R", 0.0, 48.0, 42.0, 18.0, 0, 0)))
    assert result["zone_height"].tolist() == pytest.approx([-0.25, 1.25])

# The same height is a different share of a tall batter's zone and a short batter's zone
def test_zone_height_uses_each_batters_own_zone():
    result = add_location(make_pitches(("R", 0.0, 30.0, 42.0, 18.0, 0, 0), ("R", 0.0, 30.0, 38.0, 22.0, 0, 0)))
    assert result["zone_height"].tolist() == pytest.approx([0.5, 0.5])
    result = add_location(make_pitches(("R", 0.0, 36.0, 42.0, 18.0, 0, 0), ("R", 0.0, 36.0, 38.0, 22.0, 0, 0)))
    assert result["zone_height"].tolist() == pytest.approx([0.75, 0.875])

# Balls come first, as in "3-2"
def test_count_is_balls_then_strikes():
    result = add_location(make_pitches(("R", 0.0, 30.0, 42.0, 18.0, 1, 2), ("R", 0.0, 30.0, 42.0, 18.0, 3, 0)))
    assert result["count"].tolist() == ["1-2", "3-0"]

def test_all_twelve_counts_are_distinct():
    rows = [("R", 0.0, 30.0, 42.0, 18.0, b, s) for b in range(4) for s in range(3)]
    result = add_location(make_pitches(*rows))
    assert result["count"].nunique() == 12

def test_unknown_batter_side_raises():
    with pytest.raises(ValueError, match = "1 rows"):
        add_location(make_pitches(("R", 1.0, 30.0, 42.0, 18.0, 0, 0), ("S", 1.0, 30.0, 42.0, 18.0, 0, 0)))

def test_missing_batter_side_raises():
    with pytest.raises(ValueError, match = "1 rows"):
        add_location(make_pitches(("R", 1.0, 30.0, 42.0, 18.0, 0, 0), (None, 1.0, 30.0, 42.0, 18.0, 0, 0)))

def test_input_is_not_modified_and_original_columns_are_kept():
    pitches = make_pitches(("L", 4.0, 30.0, 42.0, 18.0, 0, 1))
    result = add_location(pitches)
    assert not {"plate_x_away_in", "zone_height", "count"} & set(pitches.columns)
    assert result["plate_x_in"].tolist() == [4.0]

def test_new_number_columns_are_float32_even_when_stand_is_a_category():
    pitches = make_pitches(("R", 3.0, 30.0, 42.0, 18.0, 0, 0), ("L", -3.0, 30.0, 42.0, 18.0, 0, 0))
    pitches["stand"] = pitches["stand"].astype("category")
    result = add_location(pitches)
    assert result["plate_x_away_in"].dtype == "float32"
    assert result["zone_height"].dtype == "float32"
