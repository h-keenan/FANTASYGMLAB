"""Entrypoint for .github/workflows/college-prospect-ingest.yml (Actions only)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import college_prospect_ingest as ingest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-classes", action="store_true", help="run the CFBD class listing even when it is not Monday")
    args = parser.parse_args()
    status = ingest.run(force_classes=args.force_classes)
    ingest.write_status(status, str(ROOT / ingest.STATUS_FILE))
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0 if status.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
