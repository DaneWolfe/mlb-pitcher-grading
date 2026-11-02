from datetime import date, timedelta
from pathlib import Path
from pitchlab.config import KEEP_COLUMNS, DATA_DIR, REQUEST_DELAY_SECONDS, MAX_ATTEMPTS, RETRY_WAIT_SECONDS
import io
import pandas as pd
import requests
import time
import logging

logger = logging.getLogger(__name__)

def build_url(day: date) -> str:
    # hfGT=R%7C = regular season games only ("R|", URL-encoded); gt/lt with the same date = a single day
    return f"https://baseballsavant.mlb.com/statcast_search/csv?all=true&hfGT=R%7C&hfSea={day.year}%7C&player_type=pitcher&game_date_gt={day.isoformat()}&game_date_lt={day.isoformat()}&type=details"

def fetch_day(day: date) -> pd.DataFrame:
    url = build_url(day)
    response = requests.get(url, timeout = 60)
    response.raise_for_status()
    # usecols drops the ~100 other Savant columns at parse time, so they never enter memory
    return pd.read_csv(io.StringIO(response.text), usecols = KEEP_COLUMNS)

def fetch_day_with_retry(day: date) -> pd.DataFrame:
    for i in range(1, MAX_ATTEMPTS + 1):
        try:
            return fetch_day(day)
        # RequestException covers timeouts, dropped connections and the HTTP errors from raise_for_status().
        # Anything else (a wrong column name, say) is a real bug, so it is not caught and crashes right away
        except requests.RequestException as e:
            # Last try failed: re-raise so the run stops loudly. A re-run skips the days already saved
            if i == MAX_ATTEMPTS:
                raise

            logger.warning("%s attempt %d failed (%s), retrying", day, i, e)

            # Wait longer after each failure: 5 s, then 10 s
            time.sleep(RETRY_WAIT_SECONDS * i)

def download_range(start: date, end: date, raw_dir: Path = DATA_DIR / "raw") -> list[Path]:
    raw_dir.mkdir(parents = True, exist_ok = True)
    paths = []

    day = start
    # day < today: A file saved while games are still being played would be incomplete, and the
    # exists() check below would then never replace it
    while day <= end and day < date.today():
        path = raw_dir / f"savant_{day.isoformat()}.parquet"
        # An existing file means the day is done. Off-days are saved too (0 rows), so they aren't re-requested
        if not path.exists():
            fetch_day_with_retry(day).to_parquet(path, index = False)
            # Inside the if on purpose: only a real request needs a pause, so a re-run over cached days stays fast
            time.sleep(REQUEST_DELAY_SECONDS)

            logger.info("Downloaded %s", day)
        # Appended whether downloaded now or already on disk: the list is every file for the range
        paths.append(path)
        day = day + timedelta(days = 1)
    return paths