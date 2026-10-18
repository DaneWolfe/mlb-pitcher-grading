# Architecture

## Overview

```
 OFFLINE (run manually or on a schedule)                  ONLINE (always on)
 ----------------------------------------------           -------------------------------
 Baseball Savant --CSV--> [pipeline] --writes--> SQLite --reads--> [API] --JSON--> [Browser]
                          download               file             FastAPI         frontend
                          clean
                          train / score
```

Scores are precomputed: the pipeline trains the model and ranks pitchers ahead of time and
stores the results, and the API only looks them up. The server therefore needs no pandas, no
downloads and no model training at request time, and keeps serving the last good data if the
pipeline fails.

## Components

### Pipeline
Python script (`pitchlab.pipeline`) that downloads, cleans, stores, builds features, trains and
scores. It runs and exits; each step is safe to re-run. It can later be scheduled (GitHub Actions
cron or Windows Task Scheduler) to refresh the current season.

### Storage
- **Raw downloads:** Parquet, one file per day under `data/raw/`. Compact, typed, and lets an
  interrupted download resume.
- **Cleaned pitches and derived results:** SQLite (`sqlite3` from the standard library). The
  pipeline is the only writer and the API only reads, so a server database is unnecessary. All SQL
  lives in `db.py`, with parameterized queries.

### API
FastAPI served by uvicorn. Read-only `GET` endpoints over the stored scores and evaluation
results (season rankings, per-pitcher arsenal, top pitches, pitcher search, evaluation). FastAPI generates
request validation and interactive docs (`/docs`) from type hints. CORS is enabled for the
frontend's origin.

### Frontend
Not yet decided. The scope is small: a ranking table, an evaluation table and a pitcher detail
page (one line per pitch), all reading from the API. Candidates are React, Svelte, Vue, or plain HTML and JavaScript.
The choice is made at the start of Phase 4.

### Tests and CI
`pytest`, run on every push by GitHub Actions (`.github/workflows/`).

## Pitch model

1. **Unit of analysis:** one row per pitcher, season and pitch type, for every pitch type thrown
   at least 30 times that season. All pitchers are included, relievers too, which gives far more
   rows than one row per pitcher. A pitcher's arsenal is however many rows he has, so arsenals of
   any size fit without fixed slots.
2. **Inputs:** pitch type (a category; never grouped into families), the pitcher's throwing hand,
   and that pitch's season averages of velocity, spin rate, vertical break and horizontal break.
   Left-handers' horizontal break is mirrored so arm-side movement has the same sign for both hands.
   Location, count, age and workload are deliberately not inputs: the score is about the pitches.
3. **Label:** the same row's run value per 100 pitches over the season. Season totals average out
   the noise of single pitches; deliberate balls, chases, misses and hard contact all count. Rows
   are weighted by pitch count.
4. **Model:** scikit-learn. Gradient boosting (`HistGradientBoostingRegressor`) first, because it
   handles the pitch-type category and interactions such as "spin matters differently for a
   curveball than a fastball" without hand-built features. Ridge regression with one-hot pitch
   types is a simple comparison.
5. **Outputs:**
   - **Pitch score:** the predicted run value per 100 pitches for each row (its stuff value).
   - **Cumulative pitcher score (main ranking):** the sum over his pitches of predicted value per
     100 times pitches thrown, divided by 100. It rewards quality and workload.
   - **Rate score:** cumulative score per 100 of his pitches, for comparing quality alone.
   - **Gap:** actual run value minus the cumulative score.
   Rankings cover starters (at least 1,850 pitches in the season; counts in [data.md](data.md)).

### Evaluation

- **Held-out seasons:** every season's scores come from a model trained on the other seasons only,
  so no row is scored by a model that saw its label.
- **Pitch level:** weighted correlation of predicted against actual run value per 100 on held-out
  rows, compared with a baseline that predicts each pitch type's average.
- **Pitcher level:** Spearman rank correlation of pitcher scores with actual run value in the
  same season.
- **Stability:** correlation of a starter's score in one season with his score in the next,
  against the same correlation for his actual results.
- **Next season:** whether this season's score predicts next season's results better than this
  season's results do.

### Limitations

- Location, count, batter, sequencing and defense are not inputs; they remain in the actual run
  value and show up in the gap.
- Arsenal depth and how pitches play off each other are not modeled at the start. Candidate
  inputs, kept only if held-out results improve: number of pitch types thrown, and each pitch's
  speed and movement difference from the pitcher's main fastball.
- The cumulative score rewards workload; the rate score is shown alongside it.
- Pitch types are Savant's classifications, which changed over the years (see [data.md](data.md));
  rare types such as forkballs have few rows, so the model leans on their physical measurements.
- 2020 (60 games) is excluded. Whether tracking measurements are comparable across system changes
  has not been checked.

## Hosting

Development runs on localhost. For publication:

- **API host:** a platform that runs uvicorn continuously (Render, Fly.io or Railway), deployed
  from the GitHub repository with a small results-only SQLite file.
- **Static host** for the frontend: GitHub Pages, Netlify or Vercel.

Free tiers change and commonly sleep idle apps; check them when choosing. The project needs no
secrets; any host configuration goes in environment variables and is never committed.
