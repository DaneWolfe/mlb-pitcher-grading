import pandas as pd

FEATURES = ["pitch_type", "p_throws", "velo_mph", "spin_rpm", "ivb_in", "hb_arm_in"]
LABEL = "run_value_per100"
WEIGHT = "pitches"

def baseline_type_average(train: pd.DataFrame, rows: pd.DataFrame) -> pd.Series:
    types = train["pitch_type"].astype(str)

    weighted_sum = (train[LABEL] * train[WEIGHT]).groupby(types).sum()
    total_weight = train[WEIGHT].groupby(types).sum()

    averages = weighted_sum / total_weight

    return rows["pitch_type"].astype(str).map(averages)
