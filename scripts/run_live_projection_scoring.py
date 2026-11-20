"""Weekly scoring of the live projection forward log (see modules/live_projection_log.py).

Run by the live-projection-scoring workflow after Monday night games; needs
SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the environment. The markdown report
goes to stdout (and the job step summary when available) and one row per season-week
is upserted into public.live_projection_reports.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import live_projection_log


def main() -> int:
    stats = live_projection_log.run_weekly_scoring()
    markdown = stats.pop("markdown", "")
    print(markdown)
    print(json.dumps({"live_projection_scoring": stats}, indent=2))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and markdown:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(markdown + "\n")
    return 0 if stats.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
