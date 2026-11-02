# Data

What the project downloads, what it keeps, and what the data looks like. Most sections answer a
question that shaped a design choice. The numbers come from two places, and each section says
which:

- **Sample days:** a single day's download, looked at during planning, before full seasons
  existed. They show patterns, not season totals.
- **Full seasons:** the downloaded 2017-2019 and 2021-2026 seasons (2020 is excluded).

## Source

Statcast is MLB's system that measures every pitch (speed, spin, movement) and every play.
Baseball Savant is MLB's public site for that data. Its Statcast Search returns pitch-level CSV
from a URL (the same request the site's "Download CSV" button makes):

```
https://baseballsavant.mlb.com/statcast_search/csv
  ?all=true&hfGT=R%7C&hfSea=2026%7C&player_type=pitcher
  &game_date_gt=2026-09-01&game_date_lt=2026-09-01&type=details
```

(a single URL; wrapped here for readability). `hfGT=R%7C` limits to regular-season games.

Sample request, 2026-09-01: 4,681 rows, 119 columns, about 3.2 MB. Pitch type, speed, spin and
movement are blank on 11 rows (0.2%). Pitch codes present: FF, SI, CH, SL, ST, CU, FC, FS, KC, EP, SV.

Volume: 179 to 185 game days per season, 2-3 MB per day of raw CSV. Only the kept columns
(below) are saved, so all nine seasons take about 105 MB as Parquet files.

The pipeline requests one day at a time, pauses 1.1 seconds after each request, and tries a
failed day up to 3 times with growing waits (settings in `config.py`).

Open items:
- Row limit per request: 25,000 is suspected; one day is far below it.
- Rate limits and terms of use have not been reviewed. The 1.1-second pause is a cautious
  guess, not a known limit.

## Columns used

| Column              | Unit / type | Notes                                                       |
|---------------------|-------------|-------------------------------------------------------------|
| `game_date`         | date        |                                                             |
| `game_pk`, `at_bat_number`, `pitch_number` | int | Together identify a single pitch            |
| `game_type`         | text        | `R` = regular season                                        |
| `pitcher`           | int         | MLB player id                                               |
| `player_name`       | text        |                                                             |
| `p_throws`          | `L` / `R`   | Pitcher handedness                                          |
| `pitch_type`        | text        | Pitch code (above)                                          |
| `release_speed`     | mph         |                                                             |
| `release_spin_rate` | rpm         |                                                             |
| `pfx_x`             | **feet**    | Horizontal movement; sign depends on handedness (below)     |
| `pfx_z`             | **feet**    | Vertical movement                                           |
| `description`       | text        | Pitch result (ball, called_strike, swinging_strike, foul, hit_into_play, ...) |
| `events`            | text        | Plate-appearance result on the final pitch (strikeout, field_out, single, home_run, ...) |
| `bb_type`           | text        | Batted-ball type on balls in play: ground_ball, fly_ball, line_drive, popup |
| `delta_pitcher_run_exp` | runs    | Change in expected runs from this pitch, pitcher's perspective (below) |

The last three text columns (`description`, `events`, `bb_type`) were read from the 2026-09-01
sample only, to check what run value measures (see "Run value"). The pipeline does not keep them,
so the saved daily files do not contain them.

The file also has location columns (`plate_x`, `plate_z`, `zone`, `sz_top`, `sz_bot`) and the
count (`balls`, `strikes`). They are deliberately not kept: whether a pitch off the plate was a
purposeful ball or a miss cannot be told from the data, and the scores are meant to describe the
pitches themselves.

## Pitch types

Kept (`PITCH_TYPES`), each as its own category, never grouped into families:

| Code | Pitch            |   | Code | Pitch         |
|------|------------------|---|------|---------------|
| `FF` | Four-seam        |   | `CU` | Curveball     |
| `SI` | Sinker           |   | `KC` | Knuckle curve |
| `FC` | Cutter           |   | `CH` | Changeup      |
| `SL` | Slider           |   | `FS` | Splitter      |
| `ST` | Sweeper          |   | `FO` | Forkball      |
| `SV` | Slurve           |   |      |               |

- Relabeled: `CS` (slow curve) becomes `CU`. The relabel happens before filtering.
- Dropped: `KN` (knuckleball), `EP` (eephus), `SC` (screwball), `PO` (pitchout), `FA` (other),
  any other code not listed above, such as intentional or automatic balls, and rows with no
  pitch type at all.
- `SV` and `FO` are rare (2 to 39 and 0 to 5 pitches per day in the sample-day table below), so
  they contribute few rows.

Sample days (one June day per season, all regular-season pitches). Counted from each day's
downloaded file, to see which codes appear, how rare `SV` and `FO` are, and how the sweeper share
changes between seasons. One day is a small sample: it shows a pattern, not season totals.

| Day        | Pitches | `ST` (sweeper)  | `SV` | `FS` | `FO` | `CS` | Dropped codes seen   |
|------------|---------|-----------------|------|------|------|------|----------------------|
| 2019-06-15 | 4,399   | 20 (0.5%)       | 2    | 108  | 0    | 1    | `PO`                 |
| 2022-06-15 | 4,419   | 136 (3.1%)      | 39   | 21   | 0    | 0    | `EP`, `FA`, `KN`     |
| 2023-06-15 | 3,120   | 206 (6.6%)      | 24   | 106  | 5    | 0    | `SC`, `PO`           |

The sweeper share rose sharply. Part of that is real (the pitch became popular), but older seasons
may still label some sweepers `SL`; one day per season cannot separate the two. The `ST` share per
season has not been checked on the full seasons yet.

Splitters and changeups are kept as separate pitch types. This table checks whether the
measurements alone tell them apart, or whether the pitch-type label has to. It uses the 2019 and
2023 days from the table above (2022 had only 21 splitters), and only `CH` and `FS` rows.
Vertical break is `pfx_z` in inches. Arm-side break is `pfx_x` in inches with left-handers
flipped so both hands point the same way (see "Horizontal movement sign" below).

| Day        | Type | Pitches | Speed (mph) | Spin (rpm) | Vertical break (in) | Arm-side break (in) |
|------------|------|---------|-------------|------------|---------------------|---------------------|
| 2019-06-15 | `CH` | 508     | 85.1        | 1,709      | 7.1                 | 13.7                |
| 2019-06-15 | `FS` | 108     | 85.3        | 1,400      | 3.6                 | 10.6                |
| 2023-06-15 | `CH` | 249     | 85.6        | 1,763      | 6.5                 | 12.9                |
| 2023-06-15 | `FS` | 106     | 87.2        | 1,459      | 3.7                 | 12.3                |

What it shows: speed is nearly the same for both (85.1 vs 85.3 mph in 2019, 85.6 vs 87.2 in
2023) and so is arm-side break in 2023 (12.9 vs 12.3 inches). Spin and vertical break differ
both days: splitters have about 300 rpm less spin and about half the vertical break (3.6 vs 7.1
inches in 2019, 3.7 vs 6.5 in 2023). So spin and vertical break usually separate the two, and
speed and arm-side break do not. Where the measurements overlap, the pitch-type label is what
separates them, which is why pitch type is a model input. Limits: two days, with 106 to 108
splitters each, so these are patterns and not season averages.

### Horizontal movement sign

On 2026-09-01 (the sample request in "Source"), four-seam fastballs averaged -0.65 ft for
right-handed pitchers (991 pitches) and +0.69 ft for left-handed pitchers (540 pitches). The two
hands have opposite signs, so one hand must be mirrored before horizontal movement is compared.

### Run value

`delta_pitcher_run_exp` is the change in expected runs caused by a pitch, from the pitcher's
point of view: **positive is good for the pitcher**. `delta_run_exp` is the same quantity from the
batting side, with the opposite sign. It is blank on the same 11 rows that lack pitch data.

Mean run value by outcome, pitcher's view, from the 2026-09-01 sample. The table shows the sign
and the scale: a home run costs the pitcher almost two runs, an out gains about a quarter run.
The saved daily files do not keep `description`, `events` or `bb_type`, so these means cannot be
recomputed from `data/raw`.

| Outcome            | Mean   |   | Batted-ball type (balls in play) | Mean   |
|--------------------|--------|---|----------------------------------|--------|
| home run           | -1.84  |   | line drive                       | -0.29  |
| single             | -0.45  |   | fly ball                         | -0.16  |
| walk               | -0.24  |   | ground ball                      | +0.01  |
| ball               | -0.05  |   | popup                            | +0.23  |
| called strike      | +0.05  |   |                                  |        |
| strikeout          | +0.22  |   |                                  |        |
| field out          | +0.26  |   |                                  |        |

## Season coverage

An early look, before full seasons were downloaded, at whether spin and movement exist in older
seasons. One June game day per season was sampled; values are the share of rows that have the
field. 2015 and 2016 are not used and are not in `data/raw`, so those rows cannot be rechecked.
Full-season numbers for the seasons used are under "Cleaning losses" below.

| Season | Rows that day | Spin rate | Movement | Run value |
|--------|---------------|-----------|----------|-----------|
| 2015   | 4,786         | 93%       | 100%     | 100%      |
| 2016   | 3,186         | 93%       | 100%     | 99%       |
| 2017   | 4,524         | 98%       | 99%      | 100%      |
| 2018   | 4,712         | 98%       | 99%      | 99%       |
| 2021   | 2,932         | 100%      | 100%     | 100%      |

- Spin rate is mostly complete from 2017, the first season used.
- 2020 was a 60-game season and is excluded.
- Whether measurements are comparable across tracking-system changes has not been checked.

## Cleaning losses

How many pitches the cleaning step (`clean_pitches`) removes and why. Removed rows never reach the
model, so a loss that is concentrated in one kind of pitch would bias it. Counted over full
seasons, from the daily files before and after cleaning. Every downloaded row is a
regular-season pitch (`hfGT=R`), and no season has duplicate pitches.

| Season | Downloaded | Kept    | Dropped | Share  | Pitch type blank or dropped | Missing a value |
|--------|------------|---------|---------|--------|-----------------------------|-----------------|
| 2017   | 724,627    | 703,150 | 21,477  | 2.96%  | 9,661                       | 11,816          |
| 2018   | 724,452    | 706,607 | 17,845  | 2.46%  | 7,589                       | 10,256          |
| 2019   | 735,090    | 714,727 | 20,363  | 2.77%  | 7,938                       | 12,425          |
| 2021   | 712,320    | 705,774 | 6,546   | 0.92%  | 3,922                       | 2,624           |
| 2022   | 710,210    | 704,339 | 5,871   | 0.83%  | 3,920                       | 1,951           |
| 2023   | 720,684    | 711,644 | 9,040   | 1.25%  | 4,996                       | 4,044           |
| 2024   | 711,899    | 703,463 | 8,436   | 1.18%  | 5,143                       | 3,293           |
| 2025   | 712,528    | 706,000 | 6,528   | 0.92%  | 4,667                       | 1,861           |
| 2026   | 716,792    | 710,845 | 5,947   | 0.83%  | 4,864                       | 1,083           |

The 2026-09-01 sample had 0.2% of rows blank (see "Source"), which suggested a similar share
would be dropped. Every full season is higher.

- The largest part of every season is a blank `pitch_type` (2,054 to 7,329 rows). The rest are
  the codes dropped on purpose (`EP`, `FA`, `KN`, `PO`, `SC`, `UN`). Why Savant leaves the type
  blank on those rows has not been checked.
- Nearly all of "missing a value" is spin rate, not speed, movement or run value.

### Sliders without spin rate, 2017-2019

Before 2021, most of the rows missing spin rate are sliders:

| Season | Sliders | Missing spin | Share |
|--------|---------|--------------|-------|
| 2017   | 109,351 | 8,701        | 8.0%  |
| 2018   | 112,772 | 8,053        | 7.1%  |
| 2019   | 119,233 | 9,332        | 7.8%  |
| 2021   | 118,000 | 394          | 0.3%  |

What the data shows:

- It is not a few bad games. No game has all of its sliders missing (one game in 2019), so rows
  are lost inside games.
- It is uneven across pitchers. Among pitchers with 30 or more sliders, the median pitcher loses
  3.3% to 4.6% and the 90th percentile loses 22.5% to 24.7%. In each season 27 to 45 pitchers lose
  more than a quarter of their sliders. None lose more than half.
- The 30-pitch cutoff is barely affected: 6 to 9 pitcher-seasons per season drop under 30
  sliders (for example 446 to 437 in 2017).
- The lost sliders are not like the kept ones. They are 0.3 to 0.7 mph slower and have about
  1.0 to 1.6 inches less vertical movement. Run value per pitch is nearly the same (within 0.005).
  This compares all lost sliders to all kept sliders, not the same pitcher's pitches, so part of
  the gap may be different pitchers. That has not been separated.

Result: in 2017-2019 a pitcher's slider averages (speed, spin, movement) come only from the
sliders that had spin, which skew slightly faster and with more vertical movement. Run value for
the pitch is nearly unaffected. The cause of the missing spin has not been found. 2021 onward is
clean for sliders. Other pitch types lose a smaller share in 2017-2019 (in 2017, about 2% of
curveballs and about 5% of splitters); only 2017 was checked by type.

The rows are left as they are. Open check for the model phase: train with and without the
2017-2019 sliders and see whether slider results move.

## Cutoffs

Counted in regular-season pitches (innings are not a column in the pitch file):

- **Model rows: at least 30 pitches** of a pitch type in a season. Every pitcher counts,
  relievers included. Rows are weighted by pitch count, so small rows have little influence.
- **Rankings: at least 1,850 pitches** in the season (about 115 innings). Keeps relievers out of
  the starter rankings.

## Starters (ranking cutoff)

Rankings cover starters only, and the pitch file has no innings or starts column, so the cutoff
has to separate starters from relievers by pitch count alone. The tables below check where
1,850 pitches falls.

Counts come from MLB Stats API season totals, which include `numberOfPitches`, `gamesStarted`,
`gamesPlayed` and `outs` per pitcher (seasons 2017-2019 and 2021-2026):

```
https://statsapi.mlb.com/api/v1/stats?stats=season&group=pitching&season=2025
  &gameType=R&playerPool=ALL&sportIds=1&limit=3000
```

Largest single-season pitch totals, 2017-2026 (excluding 2020):

| Group                                | Max pitches |
|--------------------------------------|-------------|
| Never started a game                 | 1,640 (2026) |
| At most 3 to 5 starts                | 1,821 (2019) |
| At most 8 starts                     | 2,398 (2018) |

Pitchers with 6 to 8 starts and 140+ innings work like starters; a cutoff high enough to exclude
them (about 2,400) would also remove more than half of all pitchers with 10 or more starts.

Qualifiers at 1,850 pitches:

| Season | Qualifiers |
|--------|------------|
| 2017   | 123 |
| 2018   | 126 |
| 2019   | 118 |
| 2021   | 108 |
| 2022   | 115 |
| 2023   | 113 |
| 2024   | 113 |
| 2025   | 113 |
| 2026   | 121 |

Season pairs (a starter in season N, the same pitcher in N+1), used only by the stability and
next-season checks, across the seven usable pairs (2017-18, 2018-19, 2021-22, 2022-23, 2023-24,
2024-25, 2025-26):

| Requirement in N+1      | Pairs |
|-------------------------|-------|
| >= 1,850 pitches        | 483   |
| >= 1,000 pitches        | 637   |
| >= 500 pitches          | 703   |

Pitch counts per pitcher-season can be cross-checked against `numberOfPitches` from this API.

## Cross-check sources

Not used as inputs; for verifying computed per-pitcher values.

Savant pitch movement leaderboard (columns `pitcher_id`, `pitch_type`, `avg_speed`, `pitches_thrown`):

```
https://baseballsavant.mlb.com/leaderboard/pitch-movement
  ?year=2026&team=&min=q&pitch_type=FF&hand=&csv=true
```

Savant pitch arsenal leaderboard (columns `player_id`, `pitch_type`, `pitches`, `run_value_per_100`,
`run_value`, `whiff_percent`):

```
https://baseballsavant.mlb.com/leaderboard/pitch-arsenal-stats
  ?type=pitcher&pitchType=&year=2026&team=&min=100&csv=true
```

Its per-pitch-type rows match this project's unit, so it is the main spot-check for the
`pitch_seasons` table (planned for Phase 2: one row per pitcher, season and pitch type). Its sign convention has not yet been compared with sums of
`delta_pitcher_run_exp`; check this before relying on it. Its pitch counts run well below season
totals, so it cannot be used to count qualifiers.

## Storage

- Raw downloads: one Parquet file per day under `data/raw/`, named `savant_YYYY-MM-DD.parquet`.
  Days with no games are saved as empty files so they are not requested again. Not committed.
- Database: `data/pitches.db`, SQLite, about 605 MB with all nine seasons. Not committed.

More tables are added here as they are implemented.

### `pitches`

One row per cleaned pitch, written by `insert_pitches` in `db.py`. The primary key is
`(game_pk, at_bat_number, pitch_number)`, so loading the same pitch twice stores it once. Rows
per season are the "Kept" column under "Cleaning losses".

| Column          | Type    | From Savant column      | Notes                                         |
|-----------------|---------|-------------------------|-----------------------------------------------|
| `game_pk`       | INTEGER | `game_pk`               | Game id                                       |
| `at_bat_number` | INTEGER | `at_bat_number`         | Plate appearance within the game              |
| `pitch_number`  | INTEGER | `pitch_number`          | Pitch within the plate appearance             |
| `pitcher_id`    | INTEGER | `pitcher`               | MLB player id                                 |
| `player_name`   | TEXT    | `player_name`           | "Last, First"                                 |
| `p_throws`      | TEXT    | `p_throws`              | `L` or `R`                                    |
| `pitch_type`    | TEXT    | `pitch_type`            | After the `CS` to `CU` relabel                |
| `velo_mph`      | REAL    | `release_speed`         | mph                                           |
| `spin_rpm`      | REAL    | `release_spin_rate`     | rpm                                           |
| `hb_in`         | REAL    | `pfx_x`                 | Inches (feet x 12). Not yet mirrored by hand  |
| `ivb_in`        | REAL    | `pfx_z`                 | Inches (feet x 12)                            |
| `run_value`     | REAL    | `delta_pitcher_run_exp` | Positive is good for the pitcher              |
| `season`        | INTEGER | year of `game_date`     |                                               |

`game_date` and `game_type` are dropped after cleaning: every row is regular season, and the
date is only needed to get the season.
