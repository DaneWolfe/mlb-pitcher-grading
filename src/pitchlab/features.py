import pandas as pd
from pitchlab.config import MIN_PITCH_TYPE_PITCHES

def add_arm_side_break(pitches: pd.DataFrame) -> pd.DataFrame:
    df = pitches.copy()

    sign = df["p_throws"].map({
        "R": 1,
        "L": -1
    })
    bad_rows = int(sign.isna().sum())
    if bad_rows > 0:
        raise ValueError(f"{bad_rows} rows have a p_throws other than L or R")

    df["hb_arm_in"] = (df["hb_in"] * sign.astype("float32")).astype("float32")
    return df

def build_pitch_seasons(pitches: pd.DataFrame) -> pd.DataFrame:
    df = pitches.copy()
    df["run_value"] = df["run_value"].astype("float64")

    season_pitches = df.groupby(["pitcher_id", "season"]).size().rename("season_pitches").reset_index()

    rows = (
        df.groupby(["pitcher_id", "season", "pitch_type"], observed = True)
        .agg(
            player_name = ("player_name", "first"),
            p_throws = ("p_throws", "first"),
            pitches = ("run_value", "size"),
            velo_mph = ("velo_mph", "mean"),
            spin_rpm = ("spin_rpm", "mean"),
            ivb_in = ("ivb_in", "mean"),
            hb_arm_in = ("hb_arm_in", "mean"),
            run_value_total = ("run_value", "sum")
        )
        .reset_index()
    )

    rows = rows[rows["pitches"] >= MIN_PITCH_TYPE_PITCHES]
    rows = rows.merge(season_pitches, on = ["pitcher_id", "season"])

    rows["usage"] = rows["pitches"] / rows["season_pitches"]
    rows["run_value_per100"] = rows["run_value_total"] / rows["pitches"] * 100
    return rows.reset_index(drop = True)