# MLB Pitcher Grading

Scores MLB pitchers by their pitches alone: pitch type, velocity, spin rate, and vertical and
horizontal break. A model learns from past seasons what pitches with these traits are worth, then
grades each pitcher's arsenal. No premade pitch grades such as Stuff+ are used, and pitch location
is deliberately left out.

Example: rank the 2025 starters by what their arsenals were worth, then compare with what they
actually allowed.

Scope: every pitcher's pitches train the model; rankings cover starters (at least 1,850 pitches,
about 115 innings, in the season).

## How it works

**One row per pitch type, per pitcher, per season.** Every pitch type a pitcher threw at least 30
times in a season becomes a row: its average velocity, spin rate, vertical break and horizontal
break, the pitch type itself, and the pitcher's throwing hand. Pitch types are never grouped into
families, so a splitter and a changeup are different inputs. A pitcher with five pitches has five
rows; one with three has three.

**Results are measured in run value.** Each pitch is credited with how much it changed the
expected number of runs, from the pitcher's side. A row's label is that pitch's run value per 100
pitches over the whole season, so chases, deliberate balls, misses and hard contact all count. A
single pitch is too noisy to judge; a season of them is not.

**The model learns what pitch traits are worth.** A small PyTorch neural network learns how type,
speed, spin and movement relate to run value. It has to beat a simple
baseline (each pitch type's average run value), and a scikit-learn gradient-boosting model is
trained alongside it as a reference. Its prediction for a row is that pitch's stuff value:
what a pitch with those traits is worth on average, independent of location, count or luck.

**Pitchers are ranked by their arsenals.** The main score is cumulative: each pitch's predicted
value per 100 pitches times how many he threw, summed over his arsenal. It rewards both quality and
workload. A rate score (stuff value per 100 pitches) is shown next to it, along with the gap between
actual and predicted run value ("results beat or lagged his stuff").

**Checks.** Each season is scored by a model trained without that season. Scores are compared with
actual results, tested for stability from one season to the next (against the stability of results
themselves), and tested for whether they predict the following season better than that season's
results do.

The system around the model (download, SQLite storage, a read-only FastAPI service, and a
frontend) is described in [docs/architecture.md](docs/architecture.md).

## Limitations

- Location, count, batter, sequencing and defense are not inputs. They still affect each pitch's
  actual run value, so they appear in the gap between actual and predicted value, not in the score.
- Arsenal depth (how many pitches a pitcher can use) is not measured directly; an extra pitch adds
  to the cumulative score only if it is good on its own.
- The cumulative score rewards workload, so a pitcher who missed time ranks lower even with elite
  stuff; the rate score shows that case.
- Pitch types are Savant's classifications, which have changed over the years (see
  [docs/data.md](docs/data.md)).

## Status

Phase 1 is finished: all nine seasons (2017-2019, 2021-2026) are downloaded, cleaned and stored.
Phase 2 is in progress.

| Phase | Scope                                          | State       |
|-------|------------------------------------------------|-------------|
| 1     | Data: download, clean, store, CI               | Finished    |
| 2     | Pitch model, pitcher scores, evaluation        | In progress |
| 3     | Backend: FastAPI over the stored scores        | Not started |
| 4     | Frontend, deployment                           | Not started |

## Documentation

- [Architecture](docs/architecture.md): components, pitch model, hosting
- [Data](docs/data.md): data source, columns, units, pitch types, season coverage, known quirks

## Setup

Requires Python 3.13.

```powershell
git clone https://github.com/DaneWolfe/mlb-pitcher-grading.git
cd mlb-pitcher-grading
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell; on macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

`pip install -e ".[dev]"` installs the project's package, `pitchlab` (the code in `src/pitchlab/`),
plus pytest for the tests. `requirements.txt` lists the exact package versions of a known working
setup, if you need to match them.

## Usage

```powershell
python -m pitchlab.pipeline build              # every season: 2017-2019 and 2021-2026
python -m pitchlab.pipeline build --year 2025  # one season
```

For each season, `build` downloads every day from March 15 to October 10 from Baseball Savant
into `data/raw/` (one file per day), cleans the pitches (see [docs/data.md](docs/data.md)) and
stores them in `data/pitches.db`, a SQLite database. Days already downloaded are skipped and
pitches already stored are not added twice, so a stopped run can simply be started again.

The first full build sends about 1,900 requests and pauses 1.1 seconds after each one, so the
pauses alone take about 35 minutes. Afterward `data/raw/` holds about 105 MB and `pitches.db`
about 605 MB.

## License

The code is released under the [MIT License](LICENSE). The data is not covered by it; see below.

## Data and attribution

Data comes from [Baseball Savant](https://baseballsavant.mlb.com/). This project is not
affiliated with or endorsed by MLB or Baseball Savant.
