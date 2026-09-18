"""One-shot entrypoint for the automated push-trigger sweep.

Run by Render's fantasygm-lab-push-trigger-sweep cron job (see render.yaml)
on a schedule. Exits non-zero only when Supabase service-role isn't
configured at all — per-account/per-league failures are logged and skipped
inside modules.push_triggers.run_push_trigger_sweep so a single bad league
can't fail the whole sweep (and the cron job) for everyone else.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import push_triggers


def main() -> int:
    stats = push_triggers.run_push_trigger_sweep()
    trade_outcome_stats = push_triggers.run_trade_outcome_followup_sweep()
    print(json.dumps({"briefing_sweep": stats, "trade_outcome_sweep": trade_outcome_stats}, indent=2))
    return 0 if stats.get("configured") else 1


if __name__ == "__main__":
    raise SystemExit(main())
