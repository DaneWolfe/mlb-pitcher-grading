from datetime import date
from pitchlab.config import KEEP_COLUMNS
import io
import pandas as pd
import requests

def build_url(day: date) -> str:
    return f"https://baseballsavant.mlb.com/statcast_search/csv?all=true&hfGT=R%7C&hfSea={day.year}%7C&player_type=pitcher&game_date_gt={day.isoformat()}&game_date_lt={day.isoformat()}&type=details"

def fetch_day(day: date) -> pd.DataFrame:
    url = build_url(day)
    response = requests.get(url, timeout = 60)
    response.raise_for_status()
    return pd.read_csv(io.StringIO(response.text), usecols = KEEP_COLUMNS)