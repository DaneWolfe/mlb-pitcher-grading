import logging
import pandas as pd
import pytest
from pitchlab.clean import clean_pitches
from pitchlab.config import KEEP_COLUMNS, PITCH_TYPES

# One valid regular-season pitch as a dict. Each test overrides only the field it is about,
# and gives each row its own pitch_number so rows are not mistaken for duplicates
def make_pitch(**overrides):
    pitch = {
        "game_date": "2026-09-01",
        "game_pk": 100,
        "at_bat_number": 1,
        "pitch_number": 1,
        "game_type": "R",
        "pitcher": 123456,
        "player_name": "Doe, John",
        "p_throws": "R",
        "pitch_type": "FF",
        "release_speed": 95.0,
        "release_spin_rate": 2300.0,
        "pfx_x": -0.5,
        "pfx_z": 1.0,
        "delta_pitcher_run_exp": 0.1,
    }
    pitch.update(overrides)
    return pitch

def make_raw(*pitches):
    return pd.DataFrame(list(pitches))

# Tests clean_pitches: a row from any game type other than the regular season is dropped
def test_clean_pitches_keeps_only_regular_season():
    raw = make_raw(make_pitch(), make_pitch(pitch_number = 2, game_type = "S"))
    out = clean_pitches(raw)
    assert list(out["pitch_number"]) == [1]

# Tests clean_pitches: a slow curve (CS) is kept and relabeled CU, which only works if the rename happens before the filter
def test_clean_pitches_relabels_slow_curve_before_filtering():
    raw = make_raw(make_pitch(pitch_type = "CS"))
    out = clean_pitches(raw)
    assert len(out) == 1
    assert list(out["pitch_type"]) == ["CU"]

# Tests clean_pitches: a pitch type outside PITCH_TYPES (knuckleball, eephus) is dropped
def test_clean_pitches_drops_unwanted_pitch_types():
    raw = make_raw(make_pitch(), make_pitch(pitch_number = 2, pitch_type = "KN"), make_pitch(pitch_number = 3, pitch_type = "EP"))
    out = clean_pitches(raw)
    assert list(out["pitch_type"]) == ["FF"]

# Tests clean_pitches: every pitch type in PITCH_TYPES survives, so none is lost by a typo in the filter
def test_clean_pitches_keeps_every_wanted_pitch_type():
    raw = make_raw(*[make_pitch(pitch_number = i, pitch_type = t) for i, t in enumerate(sorted(PITCH_TYPES))])
    out = clean_pitches(raw)
    assert set(out["pitch_type"]) == PITCH_TYPES

# Tests clean_pitches: a row missing any one of the four measurements or the run value is dropped
@pytest.mark.parametrize("column", ["release_speed", "release_spin_rate", "pfx_x", "pfx_z", "delta_pitcher_run_exp"])
def test_clean_pitches_drops_rows_missing_a_value(column):
    raw = make_raw(make_pitch(), make_pitch(pitch_number = 2, **{column: None}))
    out = clean_pitches(raw)
    assert list(out["pitch_number"]) == [1]

# Tests clean_pitches: an exact repeat of a pitch is collapsed to one row, but a different pitch in the same at-bat is kept
def test_clean_pitches_drops_duplicates():
    raw = make_raw(make_pitch(), make_pitch(), make_pitch(pitch_number = 2))
    out = clean_pitches(raw)
    assert list(out["pitch_number"]) == [1, 2]

# Tests clean_pitches: columns get their project names, and movement is converted from feet to inches
def test_clean_pitches_renames_columns_and_converts_feet_to_inches():
    raw = make_raw(make_pitch(pitcher = 777, release_speed = 92.5, release_spin_rate = 2100.0, pfx_x = -0.5, pfx_z = 1.25, delta_pitcher_run_exp = -0.3))
    out = clean_pitches(raw)
    row = out.iloc[0]
    assert row["pitcher_id"] == 777
    assert row["velo_mph"] == pytest.approx(92.5)
    assert row["spin_rpm"] == pytest.approx(2100.0)
    assert row["hb_in"] == pytest.approx(-6.0)
    assert row["ivb_in"] == pytest.approx(15.0)
    assert row["run_value"] == pytest.approx(-0.3)
    # The old names are gone, so nothing downstream can read feet by accident
    assert not {"pitcher", "release_speed", "release_spin_rate", "pfx_x", "pfx_z", "delta_pitcher_run_exp"} & set(out.columns)

# Tests clean_pitches: season comes from the game date, and game_date and game_type are not kept
def test_clean_pitches_adds_season_and_drops_date_and_game_type():
    raw = make_raw(make_pitch(game_date = "2024-06-15"), make_pitch(pitch_number = 2, game_date = "2025-06-15"))
    out = clean_pitches(raw)
    assert list(out["season"]) == [2024, 2025]
    assert "game_date" not in out.columns
    assert "game_type" not in out.columns

# Tests clean_pitches: columns come out with the memory-saving dtypes from the spec
def test_clean_pitches_sets_dtypes():
    out = clean_pitches(make_raw(make_pitch()))
    assert out["season"].dtype == "int16"
    assert out["pitcher_id"].dtype == "int64"
    for column in ["velo_mph", "spin_rpm", "ivb_in", "hb_in", "run_value"]:
        assert out[column].dtype == "float32"
    assert out["pitch_type"].dtype == "category"
    assert out["p_throws"].dtype == "category"

# Tests clean_pitches: the DataFrame passed in is not changed
def test_clean_pitches_does_not_modify_input():
    raw = make_raw(make_pitch(pitch_type = "CS"), make_pitch(pitch_number = 2, game_type = "S"))
    before = raw.copy()
    clean_pitches(raw)
    pd.testing.assert_frame_equal(raw, before)

# Tests clean_pitches: a day with no games (right columns, 0 rows) comes out empty without an error
def test_clean_pitches_handles_empty_input():
    out = clean_pitches(pd.DataFrame(columns = KEEP_COLUMNS))
    assert len(out) == 0

# Tests clean_pitches: the log line reports how many rows each kind of drop removed
def test_clean_pitches_logs_drop_counts(caplog):
    raw = make_raw(
        make_pitch(),
        make_pitch(pitch_number = 2, game_type = "S"),
        make_pitch(pitch_number = 3, release_speed = None),
        make_pitch(pitch_number = 4),
        make_pitch(pitch_number = 4),
    )
    with caplog.at_level(logging.INFO, logger = "pitchlab.clean"):
        clean_pitches(raw)
    assert "cleaned 5 rows -> 2 (dropped 3" in caplog.text
    assert "1 not regular season or not a kept pitch type, 1 missing a value, 1 duplicates" in caplog.text
