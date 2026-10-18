from datetime import date
from pitchlab.ingest import build_url, fetch_day
from pitchlab.config import KEEP_COLUMNS
import requests

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

def test_fetch_day_keeps_only_wanted_columns(monkeypatch):
    def fake_get(url, timeout):
        return FakeResponse()

    # Replace requests.get so the test never hits the network
    monkeypatch.setattr(requests, "get", fake_get)
    df = fetch_day(date(2026, 9, 1))
    assert len(df) == 2
    assert list(df.columns) == KEEP_COLUMNS
