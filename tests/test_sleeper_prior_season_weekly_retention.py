"""Prior-season weekly stats are now retained on disk, not evicted.

Historical context: on Render, ``get_season_player_stats`` deliberately
dropped weekly granularity for any non-current season (``retain_weekly``
defaulted to ``False`` whenever ``season != default_player_stats_season()``)
to keep the on-disk cache small under Render's storage constraints. The app
has since moved to a self-hosted server with abundant local disk, and the
product owner asked twice to stop throwing away prior-season weekly history.
These tests pin the fix: a prior-season rebuild now retains ``weekly`` rows
by default, the same as the current season, and ``get_prior_season_player_
stats`` no longer forces ``retain_weekly=False``.
"""

from __future__ import annotations

import json

from unittest.mock import patch

from modules import sleeper


def _week_payload(player_id: str, week: int, points: float) -> dict:
    return {
        player_id: {
            "gp": 1,
            "rec_tgt": 5,
            "rec": 3,
            "rush_att": 0,
            "pass_att": 0,
            "pts_ppr": points,
        }
    }


def test_prior_season_rebuild_retains_weekly_by_default(tmp_path, monkeypatch, cached_2025_stats_season):
    """A from-network rebuild of a non-current season no longer drops weekly rows."""

    cache_template = str(tmp_path / "sleeper_player_stats_{season}.json")
    monkeypatch.setattr(sleeper, "PLAYER_STATS_CACHE_TEMPLATE", cache_template)

    def fake_request(_label, url, **_kwargs):
        # One real payload on week 1, empty elsewhere, to keep the test fast.
        if url.endswith("/2024/1"):
            return _week_payload("4046", 1, 18.4)
        return None

    with patch.object(sleeper, "_request_json", side_effect=fake_request):
        # Prior season relative to the pinned default (2025) is 2024 — no
        # retain_weekly argument passed, exercising the function's own default.
        result = sleeper.get_season_player_stats(season=2024, refresh=True, max_week=1)

    assert "4046" in result
    weekly = result["4046"].get("weekly")
    assert weekly and weekly[0]["week"] == 1
    assert weekly[0]["fantasy_points_ppr"] == 18.4

    # And it actually landed on disk, under the increased-storage cache path.
    on_disk = json.loads((tmp_path / "sleeper_player_stats_2024.json").read_text(encoding="utf-8"))
    on_disk_weekly = on_disk["4046"]["weekly"]
    assert on_disk_weekly and on_disk_weekly[0]["week"] == 1
    assert on_disk_weekly[0]["fantasy_points_ppr"] == 18.4


def test_cached_season_player_weekly_returns_rows_for_a_prior_season(tmp_path, monkeypatch):
    """Read side: a prior-season cache file with weekly rows is no longer treated as empty."""

    cache_template = str(tmp_path / "sleeper_player_stats_{season}.json")
    monkeypatch.setattr(sleeper, "PLAYER_STATS_CACHE_TEMPLATE", cache_template)
    (tmp_path / "sleeper_player_stats_2022.json").write_text(
        json.dumps({"4046": {"weekly": [{"week": 3, "fantasy_points_ppr": 21.0}]}}),
        encoding="utf-8",
    )

    with patch.object(sleeper, "_request_json", side_effect=AssertionError("no network")):
        assert sleeper.cached_season_player_weekly("4046", 2022) == [
            {"week": 3, "fantasy_points_ppr": 21.0}
        ]


def test_get_prior_season_player_stats_requests_weekly_retention():
    """``get_prior_season_player_stats`` must ask for weekly retention explicitly.

    It used to pass ``retain_weekly=False`` to force-evict weekly rows for
    storage reasons; it must now opt in instead of relying on (or fighting)
    the underlying default.
    """

    with patch.object(sleeper, "get_season_player_stats", return_value={}) as mock_stats:
        sleeper.get_prior_season_player_stats()
    _, kwargs = mock_stats.call_args
    assert kwargs.get("retain_weekly") is True


def test_get_season_player_stats_default_keeps_weekly_for_both_seasons(
    tmp_path, monkeypatch, cached_2025_stats_season
):
    """Without an explicit ``retain_weekly``, both the current and prior season retain weekly."""

    cache_template = str(tmp_path / "sleeper_player_stats_{season}.json")
    monkeypatch.setattr(sleeper, "PLAYER_STATS_CACHE_TEMPLATE", cache_template)

    def fake_request(_label, url, **_kwargs):
        if url.endswith("/2024/1"):
            return {"4046": {"gp": 1, "pts_ppr": 9.0}}
        if url.endswith("/2025/1"):
            return {"4046": {"gp": 1, "pts_ppr": 11.0}}
        return None

    with patch.object(sleeper, "_request_json", side_effect=fake_request):
        current = sleeper.get_season_player_stats(season=2025, refresh=True, max_week=1)
        prior = sleeper.get_season_player_stats(season=2024, refresh=True, max_week=1)

    assert "weekly" in current["4046"]
    assert "weekly" in prior["4046"]
