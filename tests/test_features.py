import pandas as pd
import pytest
from pitchlab.features import add_arm_side_break

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
