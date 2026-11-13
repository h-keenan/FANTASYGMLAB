"""One shard of the weekly league roster snapshot sweep.

    python scripts/run_league_roster_snapshot.py --dry-run --limit 20   # read-only: no Supabase writes
    python scripts/run_league_roster_snapshot.py --slot post_waivers --prune

Run by .github/workflows/league-roster-snapshot.yml (Wednesday and Sunday).
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, optional ROSTER_SNAPSHOT_SHARDS /
_SHARD_INDEX / _TIME_BUDGET_SECONDS / _MAX_CALLS_PER_MINUTE /
_RETENTION_SEASONS, ROSTER_SNAPSHOT_DISABLE=1 (kill switch). Exits non-zero on
an outage-level failure so the workflow's alert step fires. See
modules/league_roster_snapshots.py and docs/data-capture.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import league_roster_snapshots as lrs  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--slot", choices=sorted(lrs.SLOT_ORDER), help="default: pre_kickoff on Sundays (UTC), else post_waivers")
    parser.add_argument("--dry-run", action="store_true", help="read saved leagues + Sleeper, write nothing")
    parser.add_argument("--limit", type=int, help="only the first N leagues of this shard (testing)")
    parser.add_argument("--force", action="store_true", help="re-snapshot leagues already done for this slot")
    parser.add_argument("--no-picks", action="store_true", help="skip the traded-picks call")
    parser.add_argument("--prune", action="store_true", help="run the retention function afterwards")
    args = parser.parse_args(argv[1:])
    stats = lrs.run_sweep(
        slot=args.slot, dry_run=args.dry_run, limit=args.limit, force=args.force,
        include_picks=not args.no_picks, do_prune=args.prune,
    )
    print(json.dumps({"league_roster_snapshot": stats}, indent=2, default=str))
    return 0 if stats.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
