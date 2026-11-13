"""Live-aware freshness: TTL policy, single-flight under concurrency, as_of,
and the live projected final (pure logic, no network)."""

from __future__ import annotations

import threading
import uuid
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from modules import live_policy, matchup_win_probability as mwp, sleeper, sleeper_cache

def _id(prefix):
    return prefix + "-" + uuid.uuid4().hex


KICKOFF = datetime(2026, 11, 12, 1, 15, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _clean():
    sleeper_cache.reset_for_tests()
    live_policy.reset_for_tests()
    yield
    sleeper_cache.reset_for_tests()
    live_policy.reset_for_tests()


def test_ttl_short_only_for_the_live_week():
    with patch.object(live_policy, "live_nfl_week", return_value=10):
        assert live_policy.matchups_ttl(10) == live_policy.LIVE_TTL_SECONDS <= 30
        assert live_policy.matchups_ttl(9) == live_policy.IDLE_TTL_SECONDS
        assert live_policy.poll_hint_seconds(10) == live_policy.LIVE_POLL_SECONDS
        assert live_policy.poll_hint_seconds(9) is None
    with patch.object(live_policy, "live_nfl_week", return_value=None):
        assert live_policy.matchups_ttl(10) == live_policy.IDLE_TTL_SECONDS
        assert live_policy.poll_hint_seconds(10) is None


def test_live_window_from_kickoffs():
    with patch("modules.nfl_schedule.load_games", return_value=None), patch(
        "modules.nfl_schedule.week_kickoffs", return_value=[KICKOFF]
    ), patch("modules.trade_grade.estimate_nfl_week", return_value=10), patch(
        "modules.sleeper.default_player_stats_season", return_value=2026
    ):
        assert live_policy.live_nfl_week(KICKOFF + timedelta(minutes=45)) == 10
        assert live_policy.live_nfl_week(KICKOFF - timedelta(minutes=10)) == 10
        assert live_policy.live_nfl_week(KICKOFF - timedelta(hours=3)) is None
        assert live_policy.live_nfl_week(KICKOFF + timedelta(hours=5)) is None


def test_worst_case_layer_sum_while_live_is_under_60s():
    # Server: one shared cache (no extra lru layer) => age <= TTL at read.
    # Client: poll interval. Total <= TTL + poll (+ one request RTT).
    assert live_policy.LIVE_TTL_SECONDS + live_policy.LIVE_POLL_SECONDS <= 60


def _resp(points):
    r = Mock(status_code=200)
    r.json.return_value = [{"roster_id": 1, "points": points}]
    return r


def test_live_matchups_single_flight_one_upstream_call_per_interval():
    lid = _id("L")
    calls = []

    def slow_get(*_a, **_k):
        calls.append(1)
        time.sleep(0.15)
        return _resp(50.0)

    results = []
    with patch.object(live_policy, "live_nfl_week", return_value=3), patch("requests.get", side_effect=slow_get):
        threads = [threading.Thread(target=lambda: results.append(sleeper.get_matchups(lid, 3))) for _ in range(40)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        sleeper.get_matchups(lid, 3)
    assert len(calls) == 1
    assert all(r and r[0]["points"] == 50.0 for r in results)


def test_live_refetches_after_ttl_and_exposes_fetched_at():
    lid = _id("L")
    with patch.object(live_policy, "current_live_ttl", return_value=0.05), patch.object(live_policy, "live_nfl_week", return_value=3), patch(
        "requests.get", side_effect=[_resp(10.0), _resp(22.0)]
    ) as get:
        assert sleeper.get_matchups(lid, 3)[0]["points"] == 10.0
        t0 = sleeper.matchups_fetched_at(lid, 3)
        assert t0 is not None and abs(time.time() - t0) < 5
        time.sleep(0.12)
        assert sleeper.get_matchups(lid, 3)[0]["points"] == 22.0
    assert get.call_count == 2


def test_idle_week_keeps_long_ttl():
    lid = _id("L")
    with patch.object(live_policy, "current_live_ttl", return_value=0.05), patch.object(live_policy, "live_nfl_week", return_value=None), patch(
        "requests.get", return_value=_resp(1.0)
    ) as get:
        sleeper.get_matchups(lid, 3)
        time.sleep(0.12)  # longer than a live TTL, far inside the idle TTL
        sleeper.get_matchups(lid, 3)
    assert get.call_count == 1


def test_live_read_not_deferred_by_free_tier_budget():
    lid = _id("L")
    with patch.object(live_policy, "live_nfl_week", return_value=3), patch(
        "modules.sleeper_budget.should_defer", return_value=True
    ), patch("modules.sleeper_budget.last_known", return_value=([{"old": 1}], time.time() - 400)), patch(
        "requests.get", return_value=_resp(77.0)
    ):
        assert sleeper.get_matchups(lid, 3)[0]["points"] == 77.0


def test_matchup_freshness_payload():
    from services import mobile_api_service as svc

    with patch.object(live_policy, "live_nfl_week", return_value=3), patch(
        "modules.sleeper.matchups_fetched_at", return_value=time.time() - 12
    ):
        f = svc._matchup_freshness("L", 3, False)
    assert 11 <= f["as_of_age_seconds"] <= 14
    assert f["live"] is True and f["poll_after_seconds"] == live_policy.LIVE_POLL_SECONDS
    assert f["as_of"].endswith("+00:00")


# ---------------------------------------------------------------- projected final
def _starter(actual, mean=20.0, elapsed=0.5, **extra):
    kickoff = datetime.now(timezone.utc) - mwp.GAME_WALL_CLOCK * elapsed
    s = {
        "actual_points": actual,
        "game_started": True,
        "game_final": False,
        "game_kickoff_at": kickoff.isoformat(),
        "projection": {"status": "ok", "point_estimate": mean, "low": mean - 6, "high": mean + 6},
    }
    s.update(extra)
    return s


def test_projected_final_on_pace_equals_projection():
    assert mwp.projected_final(_starter(10.0, elapsed=0.5)) == pytest.approx(20.0, abs=0.2)


def test_projected_final_pace_adjustment_is_capped():
    hot = mwp.projected_final(_starter(20.0, elapsed=0.5))  # pace gap +10
    naive = 20.0 + 0.5 * 20.0
    assert naive < hot < naive + 0.25 * 10.0 + 0.1
    # early big score barely moves it
    early = mwp.projected_final(_starter(15.0, elapsed=0.1))
    assert early == pytest.approx(15.0 + 0.9 * 20.0, abs=0.9 * 0.25 * 13.0 * 0.2 + 0.2)


def test_projected_final_injury_exit_stops_projection():
    assert mwp.projected_final(_starter(6.2, injury_status="Out")) == 6.2
    assert mwp.projected_final(_starter(6.2, exited_game=True)) == 6.2


def test_projected_final_none_when_not_live():
    s = _starter(5.0)
    s["game_final"] = True
    assert mwp.projected_final(s) is None
    s = _starter(5.0)
    s["game_started"] = False
    assert mwp.projected_final(s) is None


def test_win_probability_uses_exit_rule_and_projected_final():
    me = [_starter(6.0, injury_status="Out") for _ in range(3)]
    them = [_starter(6.0) for _ in range(3)]
    out = mwp.compute_live_win_probability(me, them)
    assert out["available"]
    assert out["my_projected_total"] == pytest.approx(18.0, abs=0.1)
    assert out["opponent_projected_total"] > out["my_projected_total"]
    assert out["probability"] < 0.5
