# Pitchlab

Forecasts and ranks MLB pitchers for the coming season from raw pitch-tracking data: pitch type,
velocity, spin rate, and vertical and horizontal break, plus each pitcher's results. The model
learns from past seasons how one season's profile predicts the next; no premade pitch grades such
as Stuff+ are used.

Example backtest: predict the 2025 season from 2024 data, then compare with what actually happened
(including who received Cy Young votes).

Scope: starters (at least 1,850 pitches, about 115 innings, in the input season). The ranking assumes a healthy season;
injuries and trades are not modeled.

## How it works

**One row per pitcher-season.** Every pitch a pitcher threw in a season is boiled down to a single
row: age, workload, results, and, separately for fastballs, breaking balls and offspeed pitches,
how often each was thrown and its average velocity, spin rate, and vertical and horizontal break.

**Results are measured in run value.** Each pitch is credited with how much it changed the
expected number of runs, from the pitcher's side. Every kind of out counts in the pitcher's favor,
not only strikeouts, and walks and home runs count against him. A pitcher's season is judged by his run value
per 100 pitches.

**The model learns from pairs of seasons.** Each training example joins one season's row to the
same pitcher's run value per 100 pitches the following year. From a few hundred such pairs, a
scikit-learn regression model learns which parts of a profile carry over to next season. Applied to the
latest season, it predicts every qualifying pitcher's next season and ranks them.

**Backtests check it against the past.** To forecast a past season, the model is trained only on
seasons before it, then compared with what happened. Every result is shown next to the naive
forecast "next season equals this season"; if the model cannot beat that, the results will say so.

The system around the model (download, SQLite storage, a read-only FastAPI service, and a
frontend) is described in [docs/architecture.md](docs/architecture.md).

## Status

Planning complete; Phase 1 (data download, cleaning, storage) is next.

| Phase | Scope                                          | State       |
|-------|------------------------------------------------|-------------|
| 1     | Data: download, clean, store                   | In Progress |
| 2     | Forecast model and backtests                   | Not started |
| 3     | Backend: FastAPI over the stored forecasts     | Not started |
| 4     | Tests, CI, frontend, deployment                | Not started |

## Documentation

- [Architecture](docs/architecture.md): components, forecasting model, hosting
- [Data](docs/data.md): data source, columns, units, season coverage, known quirks

## Setup

Setup and usage instructions will be added with the first working pipeline.

## Data and attribution

Data comes from [Baseball Savant](https://baseballsavant.mlb.com/). This project is not
affiliated with or endorsed by MLB or Baseball Savant.
