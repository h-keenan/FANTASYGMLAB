"""One-shot entrypoint for the daily rookie / dynasty ADP snapshot.

Run by the rookie-adp-snapshot workflow (GitHub Actions only; nothing runs on the
production box). See modules/rookie_adp.py and docs/audits/2026-11-rookie-adp-sources.md.
Prints unmatched names so the id map can be audited; an empty FFC window is not a failure.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import rookie_adp


def main() -> int:
    report = rookie_adp.run_snapshot()
    print(json.dumps({"rookie_adp_snapshot": report}, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
