# Data

## Source

Baseball Savant's Statcast Search returns pitch-level CSV from a URL (the same request the
site's "Download CSV" button makes):

```
https://baseballsavant.mlb.com/statcast_search/csv
  ?all=true&hfGT=R%7C&hfSea=2026%7C&player_type=pitcher
  &game_date_gt=2026-09-01&game_date_lt=2026-09-01&type=details
```

(a single URL; wrapped here for readability). `hfGT=R%7C` limits to regular-season games.

Sample request, 2026-09-01: 4,681 rows, 119 columns, about 3.2 MB. Pitch type, speed, spin and
movement are blank on 11 rows (0.2%). Pitch codes present: FF, SI, CH, SL, ST, CU, FC, FS, KC, EP, SV.

Volume: roughly 180 game days per season, 2-3 MB per day of raw CSV.

Open items:
- Row limit per request: 25,000 is suspected; one day is far below it.
- Rate limits and terms of use have not been reviewed.

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

### Horizontal movement sign

Four-seam fastballs averaged -0.65 ft for right-handed pitchers and +0.70 ft for left-handed
pitchers on the sampled day, so one hand must be mirrored before horizontal movement is compared.

### Run value

`delta_pitcher_run_exp` is the change in expected runs caused by a pitch, from the pitcher's
point of view: **positive is good for the pitcher**. `delta_run_exp` is the same quantity from the
batting side, with the opposite sign. It is blank on the same 11 rows that lack pitch data.

Mean values on the sampled day, pitcher's view:

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

One June game day per season was sampled; values are the share of rows that have the field.

| Season | Rows that day | Spin rate | Movement | Run value |
|--------|---------------|-----------|----------|-----------|
| 2015   | 4,786         | 93%       | 100%     | 100%      |
| 2016   | 3,186         | 93%       | 100%     | 99%       |
| 2017   | 4,524         | 98%       | 99%      | 100%      |
| 2018   | 4,712         | 98%       | 99%      | 99%       |
| 2021   | 2,932         | 100%      | 100%     | 100%      |

- Spin rate is mostly complete from 2017, the first season used.
- 2020 was a 60-game season; season pairs involving 2020 are excluded.
- Whether measurements are comparable across tracking-system changes has not been checked.

## Qualifying pitchers

Two cutoffs, both counted in regular-season pitches (innings are not a column in the pitch file):

- **Input season N: at least 1,850 pitches** (about 115 innings). Keeps relievers out.
- **Forecast season N+1: at least 500 pitches** (about 30 innings). Enough for a run-value rate
  to mean something. A pitcher with no such season has no label and is dropped.

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

Training pairs (qualifier in N, pitcher in N+1) across the seven usable season pairs
(2017-18, 2018-19, 2021-22, 2022-23, 2023-24, 2024-25, 2025-26):

| Requirement in N+1      | Pairs |
|-------------------------|-------|
| >= 1,850 pitches        | 483   |
| >= 1,000 pitches        | 637   |
| >= 500 pitches          | 703   |

108 of 811 qualifiers (13%) threw fewer than 500 pitches the next season, or none, and are
dropped. Pairs per test season are about 95 to 115.

Pitch counts per pitcher-season can be cross-checked against `numberOfPitches` from this API.

## Player birth dates (for age)

The pitch file has no birth dates. The MLB Stats API returns `birthDate` (and `pitchHand`) per
player id, with several ids per request:

```
https://statsapi.mlb.com/api/v1/people?personIds=694819,592332,663903
```

Player ids are the same MLB ids as the `pitcher` column. The responses carry a copyright notice
pointing to terms of use, which should be read before heavy use. Only qualifying pitchers need to
be fetched, and results are cached locally. Age is computed as of June 30 of the season.

Alternative: the Chadwick Bureau register (`people-*.csv` on GitHub) has `key_mlbam` and
`birth_year/month/day`. The layout was verified; coverage of the newest players was not.

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

Its sign convention has not yet been compared with sums of `delta_pitcher_run_exp`; check this
before relying on it. Its pitch counts run well below season totals, so it cannot be used to
count qualifiers.

## Storage

- Raw downloads: one Parquet file per day under `data/raw/` (not committed).
- Results: a SQLite database under `data/` (not committed).

Table definitions are added here as they are implemented.
