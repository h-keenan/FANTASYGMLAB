#!/usr/bin/env python3
"""Rebuild a season's Sleeper weekly-stats aggregate and report completeness.

Backfills ``inactive_weeks`` and the completeness manifest on caches written before they
existed, and refetches any week a previous build failed to obtain. Safe to re-run: a
rebuild that obtains fewer weeks than the cache already holds never replaces it.

    python scripts/backfill_weekly_stats.py            # active season
    python scripts/backfill_weekly_stats.py 2025 2026  # explicit seasons

Run from the repo root on the host that owns ``data/`` (it writes the cache files).
Exit status 1 when a season is still incomplete afterwards.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules import sleeper  # noqa: E402


def main(argv: list[str]) -> int:
    seasons = [int(a) for a in argv] or [sleeper.default_player_stats_season()]
    bad = 0
    for season in seasons:
        before = sleeper.season_stats_completeness(season)
        sleeper.get_season_player_stats(season, refresh=True, retain_weekly=True)
        after = sleeper.season_stats_completeness(season)
        print(f"{season}: {before['status']} (missing {before['missing_weeks']}) -> {after['status']} (missing {after['missing_weeks']})")
        bad += after["status"] == "incomplete"
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
