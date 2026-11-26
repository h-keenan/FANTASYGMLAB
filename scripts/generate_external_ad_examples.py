"""Generate the representative example responses in docs/external-api-contract.md
("Adaptive advertising API") from the real builders with the synthetic fixtures in
tests/external_ad_fixtures.py. Never hand-edit the example blocks.

    python scripts/generate_external_ad_examples.py --write   # rewrite the docs blocks
    python scripts/generate_external_ad_examples.py           # print them

tests/test_external_ad_api.py fails if the docs drift from this output.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

import external_ad_fixtures as F  # noqa: E402

from modules import external_ad_api as A  # noqa: E402

DOC = ROOT / "docs" / "external-api-contract.md"


def _clock(phase="regular", week=15):
    return lambda today=None: {"season": 2026, "phase": phase, "week": week, "source": "sleeper"}


def examples() -> dict:
    """name -> response. Providers are patched to the fixtures, so no network or database is touched."""

    saved = {n: getattr(A, n) for n in dir(A) if n.startswith("load_") or n == "clock_info"}
    try:
        A.load_board = lambda db, fmt: (F.BOARD, F.BOARD_AS_OF)
        A.load_games = lambda: F.games()
        A.load_defense = lambda season: F.DEFENSE
        A.load_trending = lambda: F.TRENDING
        A.load_roster_pct = lambda ids: F.ROSTER_PCT
        A.load_rookie_adp = lambda: F.ROOKIE_ADP
        A.load_sleeper_players = lambda: F.SLEEPER_PLAYERS
        A.load_depth_snapshots = lambda: F.DEPTH_SNAPSHOTS
        A.load_rating_snapshots = lambda days: {
            "latest": F.LATEST_RATINGS, "baseline": F.BASELINE_RATINGS, "latest_date": "2026-12-07", "baseline_date": "2026-11-30",
        }
        A.clock_info = _clock()
        n = F.NOW
        return {
            "plan": A.endpoint_plan(as_of="2026-12-15", league_type="both", exclude_ids=[], limit=3, now=n),
            "playoff_sos": A.endpoint_playoff_sos(season=2026, start_week=15, end_week=17, position="WR", limit=1, now=n),
            "waivers": A.endpoint_waiver_replacements(db_path="x", fmt="superflex", limit=1, now=n),
            "lineup": A.endpoint_lineup_decisions(db_path="x", fmt="superflex", week=16, season=2026, limit=1, now=n),
            "value_changes": A.endpoint_value_changes(db_path="x", fmt="superflex", days=7, limit=1, now=n),
            "rookies": A.endpoint_rookies(db_path="x", fmt="superflex", limit=1, now=n),
            "changes": A.endpoint_changes(db_path="x", fmt="superflex", limit=1, now=n),
            "roster_construction": A.endpoint_roster_construction(now=n),
            "demo": A.endpoint_demo_scenarios(scenario_type="trade", now=n),
        }
    finally:
        for name, fn in saved.items():
            setattr(A, name, fn)


def block(name: str, payload: dict) -> str:
    return f"<!-- example:{name} -->\n```json\n{json.dumps(payload, indent=2)}\n```\n<!-- /example:{name} -->"


def main() -> None:
    data = examples()
    if "--write" not in sys.argv:
        for name, payload in data.items():
            print(block(name, payload))
        return
    text = DOC.read_text()
    for name, payload in data.items():
        pattern = re.compile(rf"<!-- example:{name} -->.*?<!-- /example:{name} -->", re.S)
        if not pattern.search(text):
            raise SystemExit(f"docs marker missing for example:{name}")
        text = pattern.sub(lambda _m: block(name, payload), text)
    DOC.write_text(text)


if __name__ == "__main__":
    main()
