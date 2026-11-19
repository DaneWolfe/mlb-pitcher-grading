# MLB Pitcher Grading

Scores MLB pitchers from raw Statcast data: what each pitch was worth given its type, velocity,
spin, movement, where it crossed the plate, the count, and the batter's side. A model learns this
from past seasons, then the pitches are summed into a score for each pitcher. No premade pitch
grades such as Stuff+ are used.

Example: rank the 2025 starters by what their pitches were worth, then compare with what they
actually allowed.

Scope: every pitcher's pitches train the model; rankings cover starters (at least 1,850 pitches,
about 115 innings, in the season).

## How it works

**Results are measured in run value.** Each pitch is credited with how much it changed the
expected number of runs, from the pitcher's side. Run value already depends on the count: a ball
in a 3-2 count costs more than a ball in 0-0.

**One row per pitch.** Inputs are the pitch type, the pitcher's and batter's hands, the count, the
pitch's velocity, spin rate, vertical and horizontal break, and where it crossed the plate
(horizontal position and height within that batter's strike zone). Pitch types are never grouped
into families, so a splitter and a changeup are different inputs. The label is that pitch's run
value. A single pitch is noisy, but over millions of pitches the model learns what a given pitch,
in a given spot and count, is worth on average.

**The model.** A small PyTorch neural network. It has to beat a simple baseline (each pitch type's
average run value in each count), and a scikit-learn gradient-boosting model is trained alongside
it as a reference.

**Pitchers are ranked by their pitches.** The main score is cumulative: the predicted run value of
every pitch he threw, summed over the season. It rewards both quality and workload. Shown next to
it: the rate per 100 pitches, and the gap between actual and predicted run value ("results beat or
lagged his pitches").

**Checks.** Each season is scored by a model trained without that season. Scores are compared with
actual results, tested for stability from one season to the next (against the stability of results
themselves), and tested for whether they predict the following season better than that season's
results do.

The system around the model (download, SQLite storage, a read-only FastAPI service, and a
frontend) is described in [docs/architecture.md](docs/architecture.md).

## Limitations

- The batter's identity, sequencing (what came before the pitch), base-out state and defense are
  not inputs. They still affect each pitch's actual run value, so they appear in the gap between
  actual and predicted value, not in the score.
- Location cannot tell a deliberate ball from a miss. The score credits or charges the location
  either way.
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
pauses alone take about 35 minutes. The size of `data/raw/` and `pitches.db` with all nine
seasons has not been measured yet.

## License

The code is released under the [MIT License](LICENSE). The data is not covered by it; see below.

## Data and attribution

Data comes from [Baseball Savant](https://baseballsavant.mlb.com/). This project is not
affiliated with or endorsed by MLB or Baseball Savant.
