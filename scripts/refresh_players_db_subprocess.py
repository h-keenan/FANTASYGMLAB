"""Standalone worker invoked as a subprocess to rebuild data/players.db.

Exists solely so modules.players_refresh_flight can run the expensive part
of a player-database refresh (modules.rankings.build_players_table: fetch
from Sleeper/FantasyCalc, normalize and score the ~1700-2000 player
universe) in a separate OS process instead of a background thread inside
the request-serving process.

That distinction matters because the work is CPU-bound (pandas
normalization/scoring), not just network I/O — a background *thread*
doing this still holds Python's GIL for the CPU-bound portions, which was
found to correlate with periodic p95 latency spikes (15-18+ seconds) on
services/mobile_api_service.py's single instance, since every other
in-flight request on that same process needs the GIL to make progress. A
separate process has its own interpreter and GIL, so it can't stall the
parent's request handling no matter how long the rebuild takes; the parent
picks up the result by simply reading the same on-disk SQLite file
afterward (modules.rankings.load_players already does this cheaply via its
own process-level cache).

Usage: python scripts/refresh_players_db_subprocess.py <db_path>
Exit code 0 + a non-empty players.db means success; any other outcome
(exit 1, timeout, crash) is treated by the caller as a failed refresh —
the previous players.db is left untouched either way, since
build_players_table only overwrites it after successfully building a new
frame.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import rankings


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: refresh_players_db_subprocess.py <db_path>", file=sys.stderr)
        return 2
    db_path = argv[1]
    frame = rankings.build_players_table(db_path, refresh=True)
    empty = bool(getattr(frame, "empty", frame is None))
    print(f"rows={0 if empty else len(frame)}")
    return 1 if empty else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
