"""Cleaning step: raw Savant rows to the tidy pitches the database stores."""

import logging
import pandas as pd
from pitchlab.config import PITCH_TYPES, PITCH_TYPE_ALIASES

logger = logging.getLogger(__name__)

def clean_pitches(raw: pd.DataFrame) -> pd.DataFrame:
    """Return the cleaned copy of `raw` (the input is not changed)."""

    df = raw.copy()
    start_rows = len(df)

    df = df[df["game_type"] == "R"]

    # Rename first, then filter: filtering first would throw the slow curves (CS) away before they become CU
    df["pitch_type"] = df["pitch_type"].replace(PITCH_TYPE_ALIASES)
    df = df[df["pitch_type"].isin(PITCH_TYPES)]
    type_rows = len(df)

    df = df.dropna(subset = ["release_speed", "release_spin_rate", "pfx_x", "pfx_z", "delta_pitcher_run_exp", "stand", "balls", "strikes", "plate_x", "plate_z", "sz_top", "sz_bot"])
    complete_rows = len(df)

    df = df[df["balls"].between(0, 3) & df["strikes"].between(0, 2)]
    count_rows = len(df)

    df = df.drop_duplicates(subset = ["game_pk", "at_bat_number", "pitch_number"])

    df = df.rename(columns = {
        "pitcher": "pitcher_id",
        "release_speed": "velo_mph",
        "release_spin_rate": "spin_rpm",
        "pfx_z": "ivb_in",
        "pfx_x": "hb_in",
        "delta_pitcher_run_exp": "run_value",
        "plate_x": "plate_x_in",
        "plate_z": "plate_z_in",
        "sz_top": "sz_top_in",
        "sz_bot": "sz_bot_in"
    })
    # Savant gives movement and location in feet; the project uses inches
    for col in ["ivb_in", "hb_in", "plate_x_in", "plate_z_in", "sz_top_in", "sz_bot_in"]:
        df[col] = df[col] * 12

    df["season"] = pd.to_datetime(df["game_date"]).dt.year
    # Both are done once season exists: game_type is always "R" now, and the date is only needed for season
    df = df.drop(columns = ["game_date", "game_type"])

    # astype takes {column: dtype}. float32 and category keep millions of rows small in memory
    df = df.astype({
        "pitcher_id": "int64",
        "game_pk": "int64",
        "at_bat_number": "int64",
        "pitch_number": "int64",
        "season": "int16",
        "velo_mph": "float32",
        "spin_rpm": "float32",
        "ivb_in": "float32",
        "hb_in": "float32",
        "run_value": "float32",
        "pitch_type": "category",
        "p_throws": "category",
        "balls": "int8",
        "strikes": "int8",
        "plate_x_in": "float32",
        "plate_z_in": "float32",
        "sz_top_in": "float32",
        "sz_bot_in": "float32",
        "stand": "category"
    })

    logger.info(
        "cleaned %d rows -> %d (dropped %d: %d not regular season or not a kept pitch type, %d missing a value, %d invalid count, %d duplicates)",
        start_rows, len(df), start_rows - len(df),
        start_rows - type_rows, type_rows - complete_rows, complete_rows - count_rows, count_rows - len(df),
    )
    return df
