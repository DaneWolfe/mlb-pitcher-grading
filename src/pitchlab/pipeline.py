import logging
import argparse
import pandas as pd
from datetime import date
from pathlib import Path

from pitchlab.clean import clean_pitches
from pitchlab.config import DATA_DIR, DB_PATH, SEASONS
from pitchlab.db import init_db, insert_pitches
from pitchlab.ingest import download_range

logger = logging.getLogger(__name__)

def build_season(year: int, raw_dir: Path = DATA_DIR / "raw", db_path: Path = DB_PATH) -> dict[str, int]:
    init_db(db_path)

    # March 15 and Oct 10 to safely cover the entire regular season
    paths = download_range(date(year, 3, 15), date(year, 10, 10), raw_dir)

    # Off-days are saved as 0-row files; leaving them in can change column dtypes when the frames are combined
    frames = [df for df in (pd.read_parquet(p) for p in paths) if len(df) > 0]
    # pd.concat([]) raises, so a season with no data (every day today or later) returns zeros instead
    if not frames:
        logger.warning("%d: no pitches downloaded", year)
        return {
            "raw": 0,
            "clean": 0,
            "inserted": 0
        }
    raw = pd.concat(frames, ignore_index = True)

    clean = clean_pitches(raw)

    inserted = insert_pitches(clean, db_path)

    logger.info("%d: %d raw -> %d clean, %d new rows inserted", year, len(raw), len(clean), inserted)
    return {
        "raw": len(raw),
        "clean": len(clean),
        "inserted": inserted
    }

def build_all() -> dict[int, dict[str, int]]:
    # No try/except on purpose: a failed season should stop the run with its real error. Downloaded days are
    # cached and inserts skip existing rows, so running it again picks up where it stopped
    results = {}

    for year in SEASONS:
        results[year] = build_season(year)

    total_raw = sum(r["raw"] for r in results.values())
    total_clean = sum(r["clean"] for r in results.values())
    total_inserted = sum(r["inserted"] for r in results.values())

    logger.info("all seasons: %d raw -> %d clean, %d new rows inserted", total_raw, total_clean, total_inserted)

    return results

if __name__ == "__main__":
    logging.basicConfig(level = logging.INFO)
    parser = argparse.ArgumentParser(prog = "pitchlab.pipeline")
    parser.add_argument("command", choices = ["build"])
    # choices stops a year outside SEASONS (like 2020 or 2009) from starting a long download of unusable data
    parser.add_argument("--year", type = int, choices = SEASONS, metavar = "YEAR")
    args = parser.parse_args()

    if args.year is not None:
        build_season(args.year)
    else:
        build_all()