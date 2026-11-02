import sqlite3
import pandas as pd
from contextlib import closing
from pathlib import Path

# insert_pitches sends values by position, not by name, so this order must match the CREATE TABLE in
# init_db. A mismatch would not raise an error, instead quietly storing values under the wrong columns
PITCH_COLUMNS = ["game_pk", "at_bat_number", "pitch_number", "pitcher_id", "player_name", "p_throws", "pitch_type", "velo_mph", "spin_rpm", "hb_in", "ivb_in", "run_value", "season"]

def init_db(path: Path) -> None:
    path.parent.mkdir(parents = True, exist_ok = True)

    with closing(sqlite3.connect(path)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pitches (
                game_pk INTEGER,
                at_bat_number INTEGER,
                pitch_number INTEGER,
                pitcher_id INTEGER,
                player_name TEXT,
                p_throws TEXT,
                pitch_type TEXT,
                velo_mph REAL,
                spin_rpm REAL,
                hb_in REAL,
                ivb_in REAL,
                run_value REAL,
                season INTEGER,
                PRIMARY KEY (game_pk, at_bat_number, pitch_number)
            )
        """)

def insert_pitches(df: pd.DataFrame, path: Path) -> int:
    rows = df[PITCH_COLUMNS].astype(object).values.tolist()

    with closing(sqlite3.connect(path)) as conn:
        before = conn.execute("SELECT COUNT(*) FROM pitches").fetchone()[0]
        with conn:
            conn.executemany("INSERT OR IGNORE INTO pitches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
        after = conn.execute("SELECT COUNT(*) FROM pitches").fetchone()[0]

    return after - before

def read_pitches(path: Path, season: int) -> pd.DataFrame:
    with closing(sqlite3.connect(path)) as conn:
        return pd.read_sql_query("SELECT * FROM pitches WHERE season = ?", conn, params = (season,))

def write_table(df: pd.DataFrame, table: str, path: Path) -> None:
    if not table.isidentifier():
        raise ValueError(f"Not a valid table name: {table!r}")
    # to_sql with if_exists = "replace" (below) drops the table and rebuilds it without the primary key.
    # On pitches that would erase every row and the duplicate protection, so it is refused
    if table == "pitches":
        raise ValueError("write_table would replace the pitches table; use insert_pitches")

    with closing(sqlite3.connect(path)) as conn:
        df.to_sql(table, conn, if_exists = "replace", index = False)