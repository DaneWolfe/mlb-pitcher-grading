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
scores. It runs and exits; each step is safe to re-run. Built so far: download, clean and store
(`python -m pitchlab.pipeline build`). Features, training and scoring come in Phase 2. It can later be scheduled (GitHub Actions
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

1. **Unit of analysis:** one row per pitch, for every cleaned regular-season pitch (about 6.4
   million over the nine seasons; see "Cleaning losses" in [data.md](data.md)). All pitchers are
   included, relievers too.
2. **Inputs:**
   - Categories: pitch type (never grouped into families), the pitcher's throwing hand, the
     batter's side, and the count (one of 12 values, 0-0 through 3-2).
   - Pitch measurements: velocity, spin rate, vertical break and horizontal break. Left-handed
     pitchers' horizontal break is mirrored (sign flipped) so arm-side movement has the same sign
     for both hands: negative for arm-side, positive for glove-side, as raw Savant shows it for
     right-handers.
   - Location: horizontal position at the plate, mirrored for left-handed batters so the same
     sign means "away from the batter" for both sides; and height as a share of that batter's
     strike zone (0 = bottom edge, 1 = top edge), so tall and short batters compare directly.
   - Not inputs: the batter's identity, base-out state, sequencing, age and workload.
3. **Label:** that pitch's run value. Run value is measured against the count the pitch was
   thrown in, so the count input lets the model learn that the same miss costs more in some
   counts than in others. A single pitch is noisy; with millions of rows the model learns the
   average value of a pitch in a given spot and count.
4. **Model:** a small PyTorch neural network.
   - Inputs: each category as a learned embedding (a small trainable vector per value); the
     numbers standardized with the training seasons' mean and standard deviation.
   - Network: two hidden layers of 32 to 64 units.
   - Training: mean squared error, Adam optimizer, mini-batches, and early stopping on a
     validation split taken from the training seasons. The random seed is drawn fresh each run,
     then logged and saved with the results, so any run can be reproduced exactly.
   - Comparisons: a baseline that predicts each pitch type's average run value in each count,
     which the model must beat, and scikit-learn gradient boosting (`HistGradientBoostingRegressor`)
     as a reference. Gradient boosting is a strong default for tabular data like this, so if the
     network lands far below it, the training code is the first suspect. It runs with default
     settings and is not tuned or developed further; the network is the project's model.
5. **Outputs:**
   - **Pitch-type score:** the average predicted run value per 100 pitches of each pitch type a
     pitcher threw in a season (for the pitcher page and "top pitches").
   - **Cumulative pitcher score (main ranking):** the sum of the predicted run value of every
     pitch he threw. It rewards quality and workload.
   - **Rate score:** cumulative score per 100 of his pitches, for comparing quality alone.
   - **Gap:** actual run value minus the cumulative score.
   Rankings cover starters (at least 1,850 pitches in the season; counts in [data.md](data.md)).
   Per-pitch predictions are summed during scoring and not stored; only the per-pitch-type and
   per-pitcher results go into the database.

### Evaluation

- **Held-out seasons:** every season's scores come from a model trained on the other seasons only,
  so no pitch is scored by a model that saw its label.
- **Pitch level:** on held-out pitches, the error and correlation of predicted against actual run
  value, for the network, the gradient-boosting reference, and the pitch-type-and-count baseline.
  Single pitches are noisy, so the same comparison is also made per pitcher, season and pitch type
  (weighted by pitches).
- **Pitcher level:** Spearman rank correlation of pitcher scores with actual run value in the
  same season.
- **Stability:** correlation of a starter's score in one season with his score in the next,
  against the same correlation for his actual results.
- **Next season:** whether this season's score predicts next season's results better than this
  season's results do.

### Limitations

- The batter's identity, base-out state, sequencing and defense are not inputs; they remain in the
  actual run value and show up in the gap.
- Location cannot tell a deliberate ball from a miss; the score credits or charges it either way.
- Arsenal depth and how pitches play off each other are not modeled at the start. Candidate
  inputs, kept only if held-out results improve: number of pitch types thrown, and each pitch's
  speed and movement difference from the pitcher's main fastball.
- Training time on about 6 million rows per fit has not been measured. If it is too slow, the
  training seasons are subsampled; the held-out season is always scored in full.
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
