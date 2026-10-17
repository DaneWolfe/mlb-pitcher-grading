# Architecture

## Overview

```
 OFFLINE (run manually or on a schedule)                  ONLINE (always on)
 ----------------------------------------------           -------------------------------
 Baseball Savant --CSV--> [pipeline] --writes--> SQLite --reads--> [API] --JSON--> [Browser]
                          download               file             FastAPI         frontend
                          clean
                          train / forecast
```

Forecasts are precomputed: the pipeline trains the model and ranks pitchers ahead of time and
stores the results, and the API only looks them up. The server therefore needs no pandas, no
downloads and no model training at request time, and keeps serving the last good data if the
pipeline fails.

## Components

### Pipeline
Python script (`pitchlab.pipeline`) that downloads, cleans, stores, builds features, trains and
forecasts. It runs and exits; each step is safe to re-run. Forecasts change once a year, so it can
later be scheduled (GitHub Actions cron or Windows Task Scheduler).

### Storage
- **Raw downloads:** Parquet, one file per day under `data/raw/`. Compact, typed, and lets an
  interrupted download resume.
- **Cleaned pitches and derived results:** SQLite (`sqlite3` from the standard library). The
  pipeline is the only writer and the API only reads, so a server database is unnecessary. All SQL
  lives in `db.py`, with parameterized queries.

### API
FastAPI served by uvicorn. Read-only `GET` endpoints over the stored forecasts and backtests
(forecast rankings, per-pitcher forecast, pitcher search, backtest results). FastAPI generates
request validation and interactive docs (`/docs`) from type hints. CORS is enabled for the
frontend's origin.

### Frontend
Not yet decided. The scope is small: a forecast table, a backtest table and a pitcher detail
page, all reading from the API. Candidates are React, Svelte, Vue, or plain HTML and JavaScript.
The choice is made at the start of Phase 4.

### Tests and CI
`pytest`, run on every push by GitHub Actions (`.github/workflows/`).

## Forecasting model

1. **Unit of analysis:** one row per pitcher per season. Only pitchers with at least 1,850
   pitches (about 115 innings) in the input season are included, which also separates starters
   from relievers without a role feature (counts in [data.md](data.md)). The forecast season
   needs only 500 pitches.
2. **Inputs (season N):** age; workload (pitches, games, pitches per game); results (total run
   value and run value per 100 pitches); and for fastballs, breaking balls and offspeed pitches
   separately: usage, velocity, spin rate, vertical break and horizontal break. Left-handers'
   horizontal break is mirrored so one set of parameters serves both hands.
3. **Label (season N+1):** run value per 100 pitches. It is a rate so playing time does not
   matter; seasons under 500 pitches are dropped, and rows are weighted by that season's pitch count.
4. **Model:** scikit-learn. Ridge regression first, then a shallow gradient-boosting model;
   imputation and scaling happen inside the scikit-learn pipeline.
5. **Output:** pitchers ranked by predicted run value per 100 pitches. A variant that multiplies
   by last season's pitch count (a rough full-season value) is also backtested.

### Evaluation

- **Time-ordered backtests:** to forecast season S, train only on pairs whose label season is
  before S (e.g. forecast 2025 from 2024 data).
- **Baseline:** persistence, "next season equals this season". The model has to beat it.
- **Metrics:** Spearman rank correlation of predicted against actual values, and overlap between
  the predicted top 20 and each league's actual top-10 Cy Young vote-getters. Award votes are used
  for evaluation only, never for training.

### Limitations

- Injuries and trades are not modeled; the ranking assumes a healthy season. Role changes, pitch
  location, sequencing and defense are not inputs.
- Pitchers without a qualifying prior season (rookies) cannot be forecast.
- About 700 training pairs, so models are kept simple.
- Results are conditional on a pitcher throwing at least 500 pitches in the forecast season,
  which flatters accuracy (a pitcher who pitches badly may lose his rotation spot and drop out).
- A top-20 list from roughly 95-115 eligible pitchers overlaps the real one somewhat by chance,
  so every result is shown next to the persistence baseline.

## Hosting

Development runs on localhost. For publication:

- **API host:** a platform that runs uvicorn continuously (Render, Fly.io or Railway), deployed
  from the GitHub repository with a small results-only SQLite file.
- **Static host** for the frontend: GitHub Pages, Netlify or Vercel.

Free tiers change and commonly sleep idle apps; check them when choosing. The project needs no
secrets; any host configuration goes in environment variables and is never committed.
