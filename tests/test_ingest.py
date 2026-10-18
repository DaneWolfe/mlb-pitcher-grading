from datetime import date, timedelta
from pitchlab import ingest
from pitchlab.ingest import build_url, fetch_day, download_range
from pitchlab.config import KEEP_COLUMNS
import requests
import pandas as pd

# Tests build_url: the URL asks Savant for exactly one day (same start and end date) in the right season
def test_build_url_contains_date_and_season():
    url = build_url(date(2026, 9, 1))
    assert "game_date_gt=2026-09-01" in url
    assert "game_date_lt=2026-09-01" in url
    assert "hfSea=2026" in url

class FakeResponse:
    # Stand-in for requests.Response; the extra "zone" column should be filtered out by fetch_day
    text = (
        ",".join(KEEP_COLUMNS) + ",zone\n"
        "FF,2026-09-01,95.1,Doe John,123456,R,R,-0.8,1.3,2300,1,1,1,0.02,5\n"
        "SL,2026-09-01,86.0,Doe John,123456,R,R,0.5,0.1,2500,1,1,2,-0.01,6\n"
    )
    def raise_for_status(self):
        pass

# Tests fetch_day: given a CSV with an extra column, it returns every row and only the KEEP_COLUMNS
def test_fetch_day_keeps_only_wanted_columns(monkeypatch):
    def fake_get(url, timeout):
        return FakeResponse()

    # Replace requests.get so the test never hits the network
    monkeypatch.setattr(requests, "get", fake_get)
    df = fetch_day(date(2026, 9, 1))
    assert len(df) == 2
    assert list(df.columns) == KEEP_COLUMNS

# Tests download_range: a 5-day range saves 5 files and returns their 5 paths
def test_download_range_writes_one_file_per_day(tmp_path, monkeypatch):
    def fake_fetch_day(day):
        return pd.DataFrame({
            "game_date": [day.isoformat()]
        })

    monkeypatch.setattr(ingest, "fetch_day", fake_fetch_day)
    paths = download_range(date(2026, 9, 1), date(2026, 9, 5), raw_dir = tmp_path)
    assert len(paths) == 5
    assert all(p.exists() for p in paths)

# Tests download_range: a day already saved on disk is not requested again (a re-run makes zero requests)
def test_download_range_skips_existing_files(tmp_path, monkeypatch):
    # Each call records its day, so the length of calls is the number of requests made
    calls = []
    def fake_fetch_day(day):
        calls.append(day)
        return pd.DataFrame({"game_date": [day.isoformat()]})

    monkeypatch.setattr(ingest, "fetch_day", fake_fetch_day)
    download_range(date(2026, 9, 1), date(2026, 9, 3), raw_dir = tmp_path)
    assert len(calls) == 3

    # Second run: every file is on disk, so no new requests, but the paths are still returned
    paths = download_range(date(2026, 9, 1), date(2026, 9, 3), raw_dir = tmp_path)
    assert len(calls) == 3
    assert len(paths) == 3

# Tests download_range: a day with no games still gets a (0-row) file, so it isn't requested again either
def test_download_range_saves_empty_day(tmp_path, monkeypatch):
    # An off-day comes back with the right columns and 0 rows; the file must still be written
    def fake_fetch_day(day):
        return pd.DataFrame(columns = KEEP_COLUMNS)

    monkeypatch.setattr(ingest, "fetch_day", fake_fetch_day)
    paths = download_range(date(2026, 9, 1), date(2026, 9, 1), raw_dir = tmp_path)
    assert len(paths) == 1
    assert paths[0].exists()
    assert len(pd.read_parquet(paths[0])) == 0

# Tests download_range: today and future days are never fetched, since today's games may be unfinished
def test_download_range_never_fetches_today(tmp_path, monkeypatch):
    calls = []
    def fake_fetch_day(day):
        calls.append(day)
        return pd.DataFrame({"game_date": [day.isoformat()]})

    monkeypatch.setattr(ingest, "fetch_day", fake_fetch_day)
    # The range starts two days ago and runs two days past today, so only the two days before today are valid
    today = date.today()
    paths = download_range(today - timedelta(days = 2), today + timedelta(days = 2), raw_dir = tmp_path)
    assert today not in calls
    assert len(paths) == 2
