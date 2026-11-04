import pandas as pd

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