"""One-shot entrypoint for the automated push-trigger sweep.

Run by Render's fantasygm-lab-push-trigger-sweep cron job (see render.yaml)
on a schedule. Exits non-zero when Supabase service-role isn't
configured or the sweep failed closed (opt-outs unreadable) — per-account/per-league failures are logged and skipped
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
    receipt_stats = push_triggers.run_receipt_poll()
    print(
        json.dumps(
            {"briefing_sweep": stats, "trade_outcome_sweep": trade_outcome_stats, "receipts": receipt_stats},
            indent=2,
        )
    )
    # A red run is the freshness signal: the ops health check watches the age
    # of the last SUCCESSFUL "Push Trigger Sweep" run, so a sweep that could not
    # read opt-outs (and therefore sent nothing) must not look like a success.
    return 0 if stats.get("configured") and stats.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
