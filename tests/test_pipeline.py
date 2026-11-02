from datetime import date
import subprocess
import sys
import pandas as pd
from pitchlab import pipeline
from pitchlab.pipeline import build_season, build_all
from pitchlab.db import read_pitches
from test_clean import make_pitch, make_raw

def write_day(raw_dir, name, *pitches):
    path = raw_dir / f"savant_{name}.parquet"
    make_raw(*pitches).to_parquet(path, index = False)
    return path

# Replaces download_range so no test touches the network. The pipeline then reads exactly these files
def fake_download(monkeypatch, paths):
    monkeypatch.setattr(pipeline, "download_range", lambda start, end, raw_dir: paths)

# Tests build_season: counts show what was read, what survived cleaning, and what was stored
def test_build_season_counts_and_stores_rows(tmp_path, monkeypatch):
    day1 = write_day(tmp_path, "2026-09-01",
        make_pitch(), make_pitch(pitch_number = 2), make_pitch(pitch_number = 3, game_type = "S"))
    day2 = write_day(tmp_path, "2026-09-02", make_pitch(game_pk = 200))
    fake_download(monkeypatch, [day1, day2])
    db_path = tmp_path / "pitches.db"

    result = build_season(2026, tmp_path, db_path)

    assert result == {"raw": 4, "clean": 3, "inserted": 3}
    assert len(read_pitches(db_path, 2026)) == 3

# Tests build_season: running it again over the same files stores nothing new, so a re-run can't create duplicates
def test_build_season_second_run_inserts_nothing(tmp_path, monkeypatch):
    day = write_day(tmp_path, "2026-09-01", make_pitch(), make_pitch(pitch_number = 2))
    fake_download(monkeypatch, [day])
    db_path = tmp_path / "pitches.db"

    build_season(2026, tmp_path, db_path)
    second = build_season(2026, tmp_path, db_path)

    assert second == {"raw": 2, "clean": 2, "inserted": 0}
    assert len(read_pitches(db_path, 2026)) == 2

# Tests build_season: an off-day file (0 rows) among real days is skipped and changes no count
def test_build_season_ignores_empty_off_day_files(tmp_path, monkeypatch):
    off_day = tmp_path / "savant_2026-09-03.parquet"
    pd.DataFrame(columns = list(make_pitch())).to_parquet(off_day, index = False)
    day = write_day(tmp_path, "2026-09-01", make_pitch())
    fake_download(monkeypatch, [off_day, day])

    result = build_season(2026, tmp_path, tmp_path / "pitches.db")

    assert result == {"raw": 1, "clean": 1, "inserted": 1}

# Tests build_season: with no files at all it returns zeros instead of crashing in pd.concat
def test_build_season_with_no_files_returns_zeros(tmp_path, monkeypatch):
    fake_download(monkeypatch, [])

    result = build_season(2026, tmp_path, tmp_path / "pitches.db")

    assert result == {"raw": 0, "clean": 0, "inserted": 0}

# Tests build_season: files that are all off-days count as no data, same as no files
def test_build_season_with_only_off_days_returns_zeros(tmp_path, monkeypatch):
    off_day = tmp_path / "savant_2026-09-03.parquet"
    pd.DataFrame(columns = list(make_pitch())).to_parquet(off_day, index = False)
    fake_download(monkeypatch, [off_day])

    result = build_season(2026, tmp_path, tmp_path / "pitches.db")

    assert result == {"raw": 0, "clean": 0, "inserted": 0}

# Tests build_season: it asks for March 15 to October 10 of the given year, into the given raw folder
def test_build_season_requests_the_season_window(tmp_path, monkeypatch):
    calls = []
    def fake_range(start, end, raw_dir):
        calls.append((start, end, raw_dir))
        return []
    monkeypatch.setattr(pipeline, "download_range", fake_range)

    build_season(2024, tmp_path, tmp_path / "pitches.db")

    assert calls == [(date(2024, 3, 15), date(2024, 10, 10), tmp_path)]

# Tests build_all: it builds every season in SEASONS exactly once, in order, and returns each season's counts
def test_build_all_builds_each_season_once(monkeypatch):
    calls = []
    def fake_build_season(year):
        calls.append(year)
        return {"raw": year, "clean": 1, "inserted": 1}
    monkeypatch.setattr(pipeline, "build_season", fake_build_season)
    monkeypatch.setattr(pipeline, "SEASONS", (2024, 2025))

    results = build_all()

    assert calls == [2024, 2025]
    assert results == {
        2024: {"raw": 2024, "clean": 1, "inserted": 1},
        2025: {"raw": 2025, "clean": 1, "inserted": 1},
    }

# Tests build_season: a pitch that appears in two day files is stored once. Duplicates are removed after the files
# are combined, so a day downloaded twice or a game spanning two files can't double-count
def test_build_season_removes_duplicates_across_files(tmp_path, monkeypatch):
    day1 = write_day(tmp_path, "2026-09-01", make_pitch(), make_pitch(pitch_number = 2))
    day2 = write_day(tmp_path, "2026-09-02", make_pitch(pitch_number = 2), make_pitch(pitch_number = 3))
    fake_download(monkeypatch, [day1, day2])

    result = build_season(2026, tmp_path, tmp_path / "pitches.db")

    assert result == {"raw": 4, "clean": 3, "inserted": 3}

# Tests build_season: the resume case. Days that arrive after an earlier run add only their own rows
def test_build_season_adds_only_new_days_on_a_later_run(tmp_path, monkeypatch):
    day1 = write_day(tmp_path, "2026-09-01", make_pitch(), make_pitch(pitch_number = 2))
    db_path = tmp_path / "pitches.db"
    fake_download(monkeypatch, [day1])
    build_season(2026, tmp_path, db_path)

    day2 = write_day(tmp_path, "2026-09-02", make_pitch(game_pk = 200), make_pitch(game_pk = 200, pitch_number = 2))
    fake_download(monkeypatch, [day1, day2])
    result = build_season(2026, tmp_path, db_path)

    assert result == {"raw": 4, "clean": 4, "inserted": 2}
    assert len(read_pitches(db_path, 2026)) == 4

# Runs the real __main__ block in a subprocess with download_range replaced by one that finds no files, so
# nothing is downloaded. run_module re-executes pipeline.py, and its "from pitchlab.ingest import download_range"
# picks up the replacement. Only init_db touches the real database, and that is CREATE TABLE IF NOT EXISTS
RUN_MAIN = """
import runpy, sys
import pitchlab.ingest as ingest
ingest.download_range = lambda start, end, raw_dir: []
sys.argv = ["pitchlab.pipeline", "build", "--year", "2025"]
runpy.run_module("pitchlab.pipeline", run_name = "__main__")
"""

# Tests the command line: a valid year runs to the end, exits cleanly, and the log reaches the terminal. This is
# the only test of the __main__ block, where a typo (like a misspelled logging.INFO) would otherwise only
# show up on the first real run
def test_command_line_runs_and_logs():
    result = subprocess.run([sys.executable, "-c", RUN_MAIN], capture_output = True, text = True)

    assert result.returncode == 0
    assert "2025: no pitches downloaded" in result.stderr

# Tests the command line: a year outside SEASONS (2009 has no spin data, 2020 is excluded on purpose) is rejected
# with a usage error before any download or database work starts
def test_command_line_rejects_year_outside_seasons():
    for year in ("2009", "2020"):
        result = subprocess.run(
            [sys.executable, "-m", "pitchlab.pipeline", "build", "--year", year],
            capture_output = True, text = True,
        )

        assert result.returncode == 2
        assert "invalid choice" in result.stderr

# Tests the command line: an unknown command is rejected with a usage error instead of silently doing nothing
def test_command_line_rejects_unknown_command():
    result = subprocess.run(
        [sys.executable, "-m", "pitchlab.pipeline", "delete"],
        capture_output = True, text = True,
    )

    assert result.returncode == 2
    assert "invalid choice" in result.stderr
