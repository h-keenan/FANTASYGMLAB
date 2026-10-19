"""One-shot entrypoint for the daily player-rating snapshot sweep.

Run by .github/workflows/player-rating-snapshot.yml on its own daily
schedule, separate from every other scheduled job in this repo (see that
workflow's own comments for why this time slot was picked). Builds the
canonical global 0-99 overall-rating pool and upserts one row per player
for today's date into Supabase (docs/supabase_player_rating_snapshots.sql)
— see modules/player_rating_history.py's module docstring for the full
design.

Exits non-zero only when Supabase service-role isn't configured, or when
the whole run failed to store anything at all — a pool-build hiccup or a
handful of rejected rows are logged but don't need to fail the whole
scheduled job's exit code beyond what modules.player_rating_history.
run_player_rating_snapshot_sweep already reports via its own `ok` flag.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import player_rating_history


def main() -> int:
    stats = player_rating_history.run_player_rating_snapshot_sweep()
    print(json.dumps({"player_rating_snapshot_sweep": stats}, indent=2))
    return 0 if stats.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
