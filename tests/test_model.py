import pandas as pd
import pytest
from pitchlab.model import baseline_type_average

# A plain mean of the two FF rows would be 2.5; weighting by pitches pulls it toward the 300-pitch row
def test_baseline_is_the_pitch_weighted_average_per_type():
    train = pd.DataFrame({
        "pitch_type": pd.Categorical(["FF", "FF", "SL"]),
        "run_value_per100": [1.0, 4.0, 2.0],
        "pitches": [300, 100, 50],
    })
    rows = pd.DataFrame({"pitch_type": pd.Categorical(["SL", "FF"])})
    assert baseline_type_average(train, rows).tolist() == pytest.approx([2.0, 1.75])
