import logging
import pickle
import pandas as pd
from pitchlab.config import DB_PATH, SEASONS, DATA_DIR
from pitchlab.db import read_pitches
from pitchlab.features import add_arm_side_break, add_location
from pitchlab.model import PITCH, baseline_type_average, fit, predict, split_by_season, weighted_rmse

TEST_SEASONS = [2025, 2026]

def load_pitches() -> pd.DataFrame:

    frames = [read_pitches(DB_PATH, season) for season in SEASONS]
    pitches = pd.concat(frames, ignore_index = True)

    return add_location(add_arm_side_break(pitches))

def main() -> None:
    logging.basicConfig(level = logging.INFO)

    pitches = load_pitches()
    train, test = split_by_season(pitches, TEST_SEASONS)

    model = fit(train)

    with open(DATA_DIR / "model.pkl", "wb") as f:
        pickle.dump(model, f)

    model_rmse = weighted_rmse(predict(model, test), test, PITCH)
    baseline_rmse = weighted_rmse(baseline_type_average(train, test, PITCH), test, PITCH)

    print(f"Seed: {model.seed}")
    print(f"Test seasons: {TEST_SEASONS}")
    print(f"Model RMSE: {model_rmse:.4f}")
    print(f"Baseline RMSE: {baseline_rmse:.4f}")

if __name__ == "__main__":
    main()