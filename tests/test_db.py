import sqlite3
from contextlib import closing
import pandas as pd
import pytest
from pitchlab.db import init_db, insert_pitches, read_pitches, write_table

# The 13 columns clean_pitches returns, in order. If clean_pitches gains or loses a column, this
# list and the table must change together
PITCH_COLUMNS = [
    "game_pk", "at_bat_number", "pitch_number", "pitcher_id", "player_name", "p_throws",
    "pitch_type", "velo_mph", "spin_rpm", "hb_in", "ivb_in", "run_value", "season",
]

def insert_pitch(conn, game_pk = 100, at_bat_number = 1, pitch_number = 1):
    # Every column gets a value; only the three key columns vary between rows
    values = [game_pk, at_bat_number, pitch_number, 123456, "Doe, John", "R", "FF", 95.0, 2300.0, -6.0, 12.0, 0.1, 2026]
    placeholders = ", ".join("?" * len(PITCH_COLUMNS))
    conn.execute(f"INSERT INTO pitches ({', '.join(PITCH_COLUMNS)}) VALUES ({placeholders})", values)

# Tests init_db: the pitches table exists afterward
def test_init_db_creates_pitches_table(tmp_path):
    db_path = tmp_path / "pitches.db"
    init_db(db_path)

    with closing(sqlite3.connect(db_path)) as conn:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()

    assert ("pitches",) in tables

# Tests init_db: the table has exactly the columns clean_pitches returns, in order
def test_init_db_has_the_columns_clean_pitches_returns(tmp_path):
    db_path = tmp_path / "pitches.db"
    init_db(db_path)

    with closing(sqlite3.connect(db_path)) as conn:
        # Row 1 of table_info is the column name; the list keeps the table's column order
        columns = [row[1] for row in conn.execute("PRAGMA table_info(pitches)")]

    assert columns == PITCH_COLUMNS

# Tests init_db: a missing parent folder is created instead of raising an error
def test_init_db_creates_missing_parent_folder(tmp_path):
    db_path = tmp_path / "does" / "not" / "exist" / "pitches.db"
    init_db(db_path)

    assert db_path.exists()

# Tests init_db: calling it again does not recreate the table, so loaded rows survive
def test_init_db_twice_keeps_existing_rows(tmp_path):
    db_path = tmp_path / "pitches.db"
    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            insert_pitch(conn)

    # A second init must not recreate the table: that would wipe the data already loaded
    init_db(db_path)

    with closing(sqlite3.connect(db_path)) as conn:
        count = conn.execute("SELECT COUNT(*) FROM pitches").fetchone()[0]
    assert count == 1

# Tests the primary key: the same game, at-bat and pitch number cannot be stored twice
def test_same_pitch_cannot_be_inserted_twice(tmp_path):
    db_path = tmp_path / "pitches.db"
    init_db(db_path)

    with closing(sqlite3.connect(db_path)) as conn:
        insert_pitch(conn)
        # Same game, at-bat and pitch number: the primary key must refuse it
        with pytest.raises(sqlite3.IntegrityError):
            insert_pitch(conn)

# Tests the primary key: pitches that differ in any one key column are different pitches
def test_pitches_differing_in_any_key_column_are_all_kept(tmp_path):
    db_path = tmp_path / "pitches.db"
    init_db(db_path)

    with closing(sqlite3.connect(db_path)) as conn:
        # Each row differs from the first in exactly one key column. If the key were only one or
        # two of the three columns, one of these would be wrongly rejected
        insert_pitch(conn)
        insert_pitch(conn, game_pk = 101)
        insert_pitch(conn, at_bat_number = 2)
        insert_pitch(conn, pitch_number = 2)
        count = conn.execute("SELECT COUNT(*) FROM pitches").fetchone()[0]

    assert count == 4

# A DataFrame shaped like clean_pitches output, including its dtypes (category and float32), because
# those are what insert_pitches has to convert. Each tuple is (game_pk, at_bat_number, pitch_number)
def make_df(*keys):
    df = pd.DataFrame([
        {
            "game_pk": game_pk, "at_bat_number": at_bat_number, "pitch_number": pitch_number,
            "pitcher_id": 123456, "player_name": "Doe, John", "p_throws": "R", "pitch_type": "FF",
            "velo_mph": 95.5, "spin_rpm": 2300.0, "hb_in": -6.0, "ivb_in": 12.0, "run_value": 0.25,
            "season": 2026,
        }
        for game_pk, at_bat_number, pitch_number in keys
    ])
    return df.astype({
        "pitch_type": "category", "p_throws": "category",
        "velo_mph": "float32", "spin_rpm": "float32", "hb_in": "float32", "ivb_in": "float32", "run_value": "float32",
    })

def count_pitches(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        return conn.execute("SELECT COUNT(*) FROM pitches").fetchone()[0]

# Tests insert_pitches: rows are saved and the return value is the number added
def test_insert_pitches_saves_rows_and_returns_how_many(tmp_path):
    db_path = tmp_path / "pitches.db"
    init_db(db_path)

    inserted = insert_pitches(make_df((100, 1, 1), (100, 1, 2), (100, 2, 1)), db_path)

    assert inserted == 3
    assert count_pitches(db_path) == 3

# Tests insert_pitches: every value lands in the right column, with categories stored as text
def test_insert_pitches_stores_each_value_in_its_own_column(tmp_path):
    db_path = tmp_path / "pitches.db"
    init_db(db_path)
    insert_pitches(make_df((100, 1, 1)), db_path)

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM pitches").fetchone()

    # Category columns come back as plain text, and float32 values round-trip to within float32 precision
    assert (row["game_pk"], row["at_bat_number"], row["pitch_number"]) == (100, 1, 1)
    assert row["pitcher_id"] == 123456
    assert row["player_name"] == "Doe, John"
    assert row["p_throws"] == "R"
    assert row["pitch_type"] == "FF"
    assert row["velo_mph"] == pytest.approx(95.5)
    assert row["spin_rpm"] == pytest.approx(2300.0)
    assert row["hb_in"] == pytest.approx(-6.0)
    assert row["ivb_in"] == pytest.approx(12.0)
    assert row["run_value"] == pytest.approx(0.25)
    assert row["season"] == 2026

# Tests insert_pitches: the DataFrame's column order does not matter
def test_insert_pitches_ignores_dataframe_column_order(tmp_path):
    db_path = tmp_path / "pitches.db"
    init_db(db_path)
    df = make_df((100, 1, 1))
    # Reversed order: values must still land in the right columns, which only works if columns are picked by name
    insert_pitches(df[list(reversed(df.columns))], db_path)

    with closing(sqlite3.connect(db_path)) as conn:
        row = conn.execute("SELECT pitcher_id, pitch_type, season FROM pitches").fetchone()

    assert row == (123456, "FF", 2026)

# Tests insert_pitches: loading the same data twice adds nothing the second time
def test_loading_same_pitches_twice_adds_nothing(tmp_path):
    db_path = tmp_path / "pitches.db"
    init_db(db_path)
    df = make_df((100, 1, 1), (100, 1, 2), (100, 2, 1))

    first = insert_pitches(df, db_path)
    second = insert_pitches(df, db_path)

    assert first == 3
    assert second == 0
    assert count_pitches(db_path) == 3

# Tests insert_pitches: when some rows are already stored, only the new ones are counted
def test_overlapping_load_counts_only_the_new_pitches(tmp_path):
    db_path = tmp_path / "pitches.db"
    init_db(db_path)
    insert_pitches(make_df((100, 1, 1), (100, 1, 2)), db_path)

    # Two already stored, two new
    inserted = insert_pitches(make_df((100, 1, 1), (100, 1, 2), (100, 2, 1), (101, 1, 1)), db_path)

    assert inserted == 2
    assert count_pitches(db_path) == 4

# Tests insert_pitches: an error partway through undoes the rows already inserted
def test_failed_load_leaves_no_partial_rows(tmp_path):
    db_path = tmp_path / "pitches.db"
    init_db(db_path)
    df = make_df((100, 1, 1), (100, 1, 2), (100, 1, 3))
    # A dict is a value SQLite cannot store. It is in the last row, so the first two are inserted
    # before the error, and the load must undo them
    df["pitch_type"] = pd.Series(["FF", "FF", {"bad": "value"}], dtype = object)

    with pytest.raises(sqlite3.Error):
        insert_pitches(df, db_path)

    assert count_pitches(db_path) == 0

# Tests read_pitches: only the requested season's rows come back
def test_read_pitches_returns_only_the_requested_season(tmp_path):
    db_path = tmp_path / "pitches.db"
    init_db(db_path)
    df = make_df((100, 1, 1), (100, 1, 2), (101, 1, 1))
    df["season"] = [2025, 2026, 2026]
    insert_pitches(df, db_path)

    result = read_pitches(db_path, 2026)

    assert len(result) == 2
    assert set(result["season"]) == {2026}
    assert sorted(result["game_pk"]) == [100, 101]

# Tests read_pitches: the stored values come back under the table's column names
def test_read_pitches_returns_stored_values_in_table_columns(tmp_path):
    db_path = tmp_path / "pitches.db"
    init_db(db_path)
    insert_pitches(make_df((100, 1, 1)), db_path)

    result = read_pitches(db_path, 2026)

    assert list(result.columns) == PITCH_COLUMNS
    row = result.iloc[0]
    assert row["player_name"] == "Doe, John"
    assert row["pitch_type"] == "FF"
    assert row["velo_mph"] == pytest.approx(95.5)

# Tests read_pitches: a season with no data gives an empty DataFrame that still has the columns
def test_read_pitches_unknown_season_gives_empty_frame_with_columns(tmp_path):
    db_path = tmp_path / "pitches.db"
    init_db(db_path)
    insert_pitches(make_df((100, 1, 1)), db_path)

    result = read_pitches(db_path, 1999)

    assert len(result) == 0
    assert list(result.columns) == PITCH_COLUMNS

# Tests write_table: the DataFrame is saved with its columns and values
def test_write_table_saves_the_dataframe(tmp_path):
    db_path = tmp_path / "pitches.db"
    df = pd.DataFrame({"pitcher_id": [1, 2], "score": [0.5, 1.5], "pitch_type": pd.Categorical(["FF", "SL"])})

    write_table(df, "pitcher_scores", db_path)

    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute("SELECT pitcher_id, score, pitch_type FROM pitcher_scores ORDER BY pitcher_id").fetchall()
        columns = [row[1] for row in conn.execute("PRAGMA table_info(pitcher_scores)")]
    assert rows == [(1, 0.5, "FF"), (2, 1.5, "SL")]
    assert columns == ["pitcher_id", "score", "pitch_type"]

# Tests write_table: writing the same table name again replaces the old rows
def test_write_table_replaces_the_previous_version(tmp_path):
    db_path = tmp_path / "pitches.db"
    write_table(pd.DataFrame({"pitcher_id": [1, 2, 3], "score": [1.0, 2.0, 3.0]}), "pitcher_scores", db_path)
    write_table(pd.DataFrame({"pitcher_id": [9], "score": [7.0]}), "pitcher_scores", db_path)

    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute("SELECT pitcher_id, score FROM pitcher_scores").fetchall()
    assert rows == [(9, 7.0)]

# Tests write_table: the pitches table is refused, and its rows and primary key are untouched
def test_write_table_refuses_the_pitches_table_and_keeps_its_data(tmp_path):
    db_path = tmp_path / "pitches.db"
    init_db(db_path)
    insert_pitches(make_df((100, 1, 1), (100, 1, 2)), db_path)

    with pytest.raises(ValueError):
        write_table(pd.DataFrame({"a": [1]}), "pitches", db_path)

    assert count_pitches(db_path) == 2
    with closing(sqlite3.connect(db_path)) as conn:
        key_columns = [row[1] for row in conn.execute("PRAGMA table_info(pitches)") if row[5] > 0]
    assert key_columns == ["game_pk", "at_bat_number", "pitch_number"]

# Tests write_table: names that are not plain identifiers are refused
@pytest.mark.parametrize("name", ["", "my table", "1scores", "scores; DROP TABLE pitches", "a-b"])
def test_write_table_refuses_invalid_table_names(tmp_path, name):
    db_path = tmp_path / "pitches.db"
    init_db(db_path)
    insert_pitches(make_df((100, 1, 1)), db_path)

    with pytest.raises(ValueError):
        write_table(pd.DataFrame({"a": [1]}), name, db_path)

    assert count_pitches(db_path) == 1
