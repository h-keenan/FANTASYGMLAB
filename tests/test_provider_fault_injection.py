"""Fault injection for the critical data providers: DOWN, SLOW (timeout) and GARBAGE.

Contract under test (docs/audits/2026-11-dependency-and-freshness.md, section "Degradation contract"):
a provider failure must never raise into a request, never blank a page that has last-known-good
data, and never overwrite good data with garbage. Runs offline in CI; no network.
"""

from __future__ import annotations

import json
import time

import pandas as pd
import pytest
import requests

from modules import fantasycalc, nfl_schedule, sleeper, sleeper_budget

SLEEPER_URL = "https://api.sleeper.app/v1/league/999"


class _Resp:
    def __init__(self, status=200, payload=None, text=None):
        self.status_code = status
        self._payload = payload
        self._text = text

    def json(self):
        if self._text is not None:
            raise requests.exceptions.JSONDecodeError("Expecting value", self._text, 0)
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    monkeypatch.setattr(sleeper, "SLEEPER_REQUEST_RETRY_BACKOFF_SECONDS", 0)
    monkeypatch.setattr(sleeper_budget, "should_defer", lambda: False)


FAULTS = {
    "down_connection": lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("down")),
    "slow_timeout": lambda *a, **k: (_ for _ in ()).throw(requests.Timeout("slow")),
    "http_500": lambda *a, **k: _Resp(500),
    "rate_limited_429": lambda *a, **k: _Resp(429),
    "garbage_html_200": lambda *a, **k: _Resp(200, text="<html>maintenance</html>"),
}


@pytest.mark.parametrize("fault", sorted(FAULTS))
def test_sleeper_fault_without_last_known_returns_none_never_raises(monkeypatch, fault):
    monkeypatch.setattr(sleeper_budget, "last_known", lambda url: None)
    monkeypatch.setattr(requests, "get", FAULTS[fault])
    assert sleeper._request_json("fault_test", SLEEPER_URL, max_retries=0) is None


@pytest.mark.parametrize("fault", sorted(FAULTS))
def test_sleeper_fault_serves_last_known_good(monkeypatch, fault):
    good = {"league_id": "999", "name": "Dynasty"}
    monkeypatch.setattr(sleeper_budget, "last_known", lambda url: (good, time.time() - 3600))
    monkeypatch.setattr(requests, "get", FAULTS[fault])
    assert sleeper._request_json("fault_test", SLEEPER_URL, max_retries=0) == good


def test_season_stats_all_weeks_failing_keeps_the_existing_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(sleeper, "PLAYER_STATS_CACHE_TEMPLATE", str(tmp_path / "sleeper_player_stats_{season}.json"))
    path = sleeper.PLAYER_STATS_CACHE_TEMPLATE.format(season=2026)
    cached = {"1": {"stats_season": 2026, "fantasy_points_ppr": 12.0, "weekly": [{"week": 1, "games_played": 1}]}}
    with open(path, "w") as handle:
        json.dump(cached, handle)
    monkeypatch.setattr(sleeper, "_fetch_weekly_stat_payloads", lambda season, weeks: [])
    result = sleeper.get_season_player_stats(2026, refresh=True)
    assert result["1"]["fantasy_points_ppr"] == 12.0
    with open(path) as handle:
        assert json.load(handle) == cached


# ------------------------------------------------------------------ FantasyCalc


@pytest.fixture
def fc_cache(tmp_path, monkeypatch):
    path = str(tmp_path / "fantasycalc_values.csv")
    monkeypatch.setattr(fantasycalc, "FANTASYCALC_CACHE_PATH", path)
    pd.DataFrame([{"name": "A", "position": "WR", "team": "DEN", "value": 5000, "sleeper_id": "1", "mfl_id": "2"}]).to_csv(path, index=False)
    # Expired: older than the 6h TTL, so the normal path refetches.
    old = time.time() - 3 * fantasycalc.FANTASYCALC_CACHE_TTL_SECONDS
    import os

    os.utime(path, (old, old))
    return path


FC_FAULTS = {
    "down": lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("down")),
    "slow": lambda *a, **k: (_ for _ in ()).throw(requests.Timeout("slow")),
    "http_503": lambda *a, **k: _Resp(503),
    "garbage_html": lambda *a, **k: _Resp(200, text="<html>"),
    "garbage_shape": lambda *a, **k: _Resp(200, payload={"error": "nope"}),
    "empty_list": lambda *a, **k: _Resp(200, payload=[]),
}


@pytest.mark.parametrize("fault", sorted(FC_FAULTS))
def test_fantasycalc_fault_serves_stale_values_with_as_of_and_keeps_file(fc_cache, monkeypatch, fault):
    monkeypatch.setattr(requests, "get", FC_FAULTS[fault])
    before = open(fc_cache).read()
    df = fantasycalc.get_dynasty_values()
    assert list(df["name"]) == ["A"]  # stale beats an empty page
    assert df.attrs["as_of"] < time.time() - fantasycalc.FANTASYCALC_CACHE_TTL_SECONDS  # honest "as of"
    assert open(fc_cache).read() == before  # garbage never overwrites good data


def test_fantasycalc_down_with_no_cache_is_empty_not_an_exception(tmp_path, monkeypatch):
    monkeypatch.setattr(fantasycalc, "FANTASYCALC_CACHE_PATH", str(tmp_path / "none.csv"))
    monkeypatch.setattr(requests, "get", FC_FAULTS["down"])
    assert fantasycalc.get_dynasty_values().empty


# ------------------------------------------------------------------ nflverse schedule


@pytest.mark.parametrize("fault", ["down", "slow", "http_503"])
def test_schedule_fault_serves_stale_games_csv(tmp_path, monkeypatch, fault):
    path = tmp_path / "nfl_games.csv"
    pd.DataFrame([{"game_id": "2026_01_DEN_KC", "season": 2026, "week": 1, "home_team": "KC", "away_team": "DEN"}]).to_csv(path, index=False)
    import os

    old = time.time() - 3 * nfl_schedule.GAMES_CACHE_TTL_SECONDS
    os.utime(path, (old, old))
    monkeypatch.setattr(nfl_schedule, "GAMES_CACHE_PATH", str(path))
    monkeypatch.setattr(requests, "get", FC_FAULTS[fault])
    games = nfl_schedule._load_games_uncached(refresh=True)
    assert len(games) == 1
