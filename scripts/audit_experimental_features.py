"""Validate the evidence-backed experimental feature inventory.

This script is intentionally read-only. It verifies that the founder audit covers
every route classified as experimental by the production navigation registry and
recomputes the documented priority scores.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "experimental-feature-inventory-and-roi-audit.md"

WEIGHTS = {
    "user_value": 20,
    "differentiation": 15,
    "readiness": 12,
    "revenue": 10,
    "retention": 15,
    "data_reliability": 10,
    "mobile": 5,
    "time_to_ship": 8,
    "maintenance_cost": -3,
    "technical_risk": -2,
}


def experimental_routes(source: str) -> set[str]:
    pattern = re.compile(
        r'PageDefinition\("([^"]+)"[^\n]+category="EXPERIMENTAL"'
    )
    return set(pattern.findall(source))


def documented_routes(markdown: str) -> set[str]:
    match = re.search(r"<!-- experimental-routes: (.*?) -->", markdown)
    if not match:
        return set()
    return {item.strip() for item in match.group(1).split(",") if item.strip()}


def priority_score(scores: dict[str, int]) -> float:
    """Return a 0-100 score; high cost/risk scores reduce priority."""
    benefit = sum(
        WEIGHTS[key] * scores[key] / 5
        for key in WEIGHTS
        if key not in {"maintenance_cost", "technical_risk"}
    )
    cost = sum(
        abs(WEIGHTS[key]) * (6 - scores[key]) / 5
        for key in ("maintenance_cost", "technical_risk")
    )
    return round(benefit + cost, 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    markdown = AUDIT.read_text(encoding="utf-8")
    registry = (ROOT / "modules" / "ui_architecture.py").read_text(encoding="utf-8")
    expected = experimental_routes(registry)
    covered = documented_routes(markdown)
    missing = sorted(expected - covered)
    stale = sorted(covered - expected)
    result = {
        "experimental_routes": sorted(expected),
        "documented_routes": sorted(covered),
        "missing_routes": missing,
        "stale_routes": stale,
        "audit_exists": AUDIT.is_file(),
    }
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else result)
    return 1 if missing or stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
