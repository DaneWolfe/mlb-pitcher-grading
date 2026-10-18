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
  and any other code not listed above, such as intentional or automatic balls.
- `SV` and `FO` are rare (2 to 39 and 0 to 5 pitches per sampled day), so they contribute few rows.

Sample days (one June day per season, all regular-season pitches):

| Day        | Pitches | `ST` (sweeper)  | `SV` | `FS` | `FO` | `CS` | Dropped codes seen   |
|------------|---------|-----------------|------|------|------|------|----------------------|
| 2019-06-15 | 4,399   | 20 (0.5%)       | 2    | 108  | 0    | 1    | `PO`                 |
| 2022-06-15 | 4,419   | 136 (3.1%)      | 39   | 21   | 0    | 0    | `EP`, `FA`, `KN`     |
| 2023-06-15 | 3,120   | 206 (6.6%)      | 24   | 106  | 5    | 0    | `SC`, `PO`           |

The sweeper share rose sharply. Part of that is real (the pitch became popular), but older seasons
may still label some sweepers `SL`; one day per season cannot separate the two. The `ST` share per
season should be checked once full seasons are downloaded.

Changeups and splitters on the same days (horizontal break mirrored to arm side):

| Day        | Type | Pitches | Speed (mph) | Spin (rpm) | Vertical break (in) | Arm-side break (in) |
|------------|------|---------|-------------|------------|---------------------|---------------------|
| 2019-06-15 | `CH` | 508     | 85.1        | 1,709      | 7.1                 | 13.7                |
| 2019-06-15 | `FS` | 108     | 85.3        | 1,400      | 3.6                 | 10.6                |
| 2023-06-15 | `CH` | 249     | 85.6        | 1,763      | 6.5                 | 12.9                |
| 2023-06-15 | `FS` | 106     | 87.2        | 1,459      | 3.7                 | 12.3                |

Splitters averaged about 300 rpm less spin and half the vertical break, so the measurements
usually separate the two even without the label; the pitch-type input covers the cases that overlap.

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
- 2020 was a 60-game season and is excluded.
- Whether measurements are comparable across tracking-system changes has not been checked.

## Cutoffs

Counted in regular-season pitches (innings are not a column in the pitch file):

- **Model rows: at least 30 pitches** of a pitch type in a season. Every pitcher counts,
  relievers included. Rows are weighted by pitch count, so small rows have little influence.
- **Rankings: at least 1,850 pitches** in the season (about 115 innings). Keeps relievers out of
  the starter rankings.

## Starters (ranking cutoff)

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
`pitch_seasons` table. Its sign convention has not yet been compared with sums of
`delta_pitcher_run_exp`; check this before relying on it. Its pitch counts run well below season
totals, so it cannot be used to count qualifiers.

## Storage

- Raw downloads: one Parquet file per day under `data/raw/` (not committed).
- Results: a SQLite database under `data/` (not committed).

Table definitions are added here as they are implemented.
