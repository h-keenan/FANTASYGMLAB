"""One-shot entrypoint for the quiet "did this trade actually work?" sweep.

Run by Render's fantasygm-lab-trade-outcome-result-sweep cron job (see
render.yaml) on its own daily schedule — deliberately separate from
scripts/run_push_trigger_sweep.py's */30 * * * * schedule, since this sweep
sends no push/popup at all and, unlike that one, does real (cached) player
valuation + season-stats work on a run that finds eligible rows. See
modules/trade_outcome_results.py's module docstring for the full design.

Exits non-zero only when Supabase service-role isn't configured at all —
per-row failures are logged and skipped inside
modules.trade_outcome_results.run_trade_outcome_result_sweep so one bad row
can't fail the whole sweep (and the cron job) for everyone else.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import trade_outcome_results


def main() -> int:
    stats = trade_outcome_results.run_trade_outcome_result_sweep()
    print(json.dumps({"trade_outcome_result_sweep": stats}, indent=2))
    return 0 if stats.get("configured") else 1


if __name__ == "__main__":
    raise SystemExit(main())
