from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "pitches.db"

# Columns kept from the Savant CSV. Location (plate_x, plate_z, zone) and count columns are left
# out on purpose: the model grades the pitch itself, and a ball thrown on purpose can't be told
# apart from a miss. They still count inside delta_pitcher_run_exp, the label.
KEEP_COLUMNS = [
    "game_date",
    "game_pk",
    "at_bat_number",
    "pitch_number",
    "game_type",
    "pitcher",
    "player_name",
    "p_throws",
    "pitch_type",
    "release_speed",
    "release_spin_rate",
    "pfx_x",
    "pfx_z",
    "delta_pitcher_run_exp",
]

# Pitch types the model sees. Types are never grouped into families (a splitter and a changeup
# stay separate inputs). Left out: knuckleball, eephus, screwball, pitchout and Savant's catch-all
# codes, because they are rare and would only add noise.
PITCH_TYPES = frozenset([
    "FF",  # four-seam
    "SI",  # sinker
    "FC",  # cutter
    "SL",  # slider
    "ST",  # sweeper
    "SV",  # slurve
    "CU",  # curveball
    "KC",  # knuckle curve
    "CH",  # changeup
    "FS",  # splitter
    "FO",  # forkball
])

# Codes renamed before the PITCH_TYPES filter. A slow curve is treated as a curveball. The order
# matters: filtering first would throw the slow curves away.
PITCH_TYPE_ALIASES = {"CS": "CU"}

# 2020 is excluded: a 60-game season is too small and unlike the others.
SEASONS = tuple(y for y in range(2017, 2027) if y != 2020)

# A pitch type needs this many pitches in a season to become a row. Fewer than that and the
# season average of velocity, spin and run value is mostly noise.
MIN_PITCH_TYPE_PITCHES = 30

# Rankings only include starters. 1,850 pitches is about 115 innings, above every non-starter's
# season total in 2017-2026 (checked in docs/data.md). Relievers still train the model.
MIN_STARTER_PITCHES = 1850

# Seconds to pause after each request to Savant. The full download is about 1,600 requests, and a
# pause keeps it from hammering their server. 1.1 is a cautious guess, not a measured limit.
REQUEST_DELAY_SECONDS = 1.1

# Total tries per day, counting the first one. With 1,600 requests a network hiccup is nearly certain,
# so a failed day is tried again before the whole download gives up.
MAX_ATTEMPTS = 3

# Base wait in seconds after a failed try. The wait grows with each failure (5 s, then 10 s), which
# gives a struggling server time to recover instead of being hit again right away.
RETRY_WAIT_SECONDS = 5
