"""One-shot entrypoint for the daily roster % snapshot (see modules/roster_pct_history.py).

Run by .github/workflows/roster-pct-snapshot.yml; needs SUPABASE_URL and
SUPABASE_SERVICE_ROLE_KEY in the environment.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import roster_pct_history


def main() -> int:
    stats = roster_pct_history.run_roster_pct_snapshot()
    print(json.dumps({"roster_pct_snapshot": stats}, indent=2))
    return 0 if stats.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
