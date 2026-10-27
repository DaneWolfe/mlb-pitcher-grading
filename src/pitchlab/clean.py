import logging
import pandas as pd
from pitchlab.config import PITCH_TYPES, PITCH_TYPE_ALIASES

logger = logging.getLogger(__name__)

def clean_pitches(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    start_rows = len(df)

    df = df[df["game_type"] == "R"]

    # Rename first, then filter: filtering first would throw the slow curves (CS) away before they become CU
    df["pitch_type"] = df["pitch_type"].replace(PITCH_TYPE_ALIASES)
    df = df[df["pitch_type"].isin(PITCH_TYPES)]
    type_rows = len(df)

    df = df.dropna(subset = ["release_speed", "release_spin_rate", "pfx_x", "pfx_z", "delta_pitcher_run_exp"])
    complete_rows = len(df)

    df = df.drop_duplicates(subset = ["game_pk", "at_bat_number", "pitch_number"])

    df = df.rename(columns = {
        "pitcher": "pitcher_id",
        "release_speed": "velo_mph",
        "release_spin_rate": "spin_rpm",
        "pfx_z": "ivb_in",
        "pfx_x": "hb_in",
        "delta_pitcher_run_exp": "run_value"
    })
    # Savant gives movement in feet; the project uses inches
    df["ivb_in"] = df["ivb_in"] * 12
    df["hb_in"] = df["hb_in"] * 12

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
    })

    logger.info(
        "cleaned %d rows -> %d (dropped %d: %d not regular season or not a kept pitch type, %d missing a value, %d duplicates)",
        start_rows, len(df), start_rows - len(df),
        start_rows - type_rows, type_rows - complete_rows, complete_rows - len(df),
    )
    return df
