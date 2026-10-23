"""Points By Week — the web Player Quick View's weekly trend chart.

Covers the data read (cache-only by default, on-demand fetch only when a
prior season is asked for) and the SVG builder's normal, single-point, and
empty cases.
"""

import json
import re
from unittest.mock import patch

import pytest

from modules import sleeper


def _week(week: int, points: float | None, **extra) -> dict:
    row = {"week": week, **extra}
    if points is not None:
        row["fantasy_points_ppr"] = points
    return row


def test_cached_season_player_weekly_reads_disk_without_fetching(tmp_path, monkeypatch):
    cache = tmp_path / "sleeper_player_stats_{season}.json"
    monkeypatch.setattr(sleeper, "PLAYER_STATS_CACHE_TEMPLATE", str(cache))
    (tmp_path / "sleeper_player_stats_2025.json").write_text(
        json.dumps(
            {
                "4046": {"weekly": [{"week": 1, "fantasy_points_ppr": 12.0}, "junk"]},
                "9999": {"stats_season": 2025},
            }
        ),
        encoding="utf-8",
    )

    with patch.object(sleeper, "_request_json", side_effect=AssertionError("no network")):
        assert sleeper.cached_season_player_weekly("4046", 2025) == [
            {"week": 1, "fantasy_points_ppr": 12.0}
        ]
        # Unknown player, a season with no cache file on disk yet, and a
        # blank id all fail soft rather than fetching.
        assert sleeper.cached_season_player_weekly("9999", 2025) == []
        assert sleeper.cached_season_player_weekly("4046", 2024) == []
        assert sleeper.cached_season_player_weekly("", 2025) == []


class _NullContext:
    def __enter__(self):
        return self

    def __exit__(self, *exception):
        return False
