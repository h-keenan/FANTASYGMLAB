"""Adaptive live TTL: hysteresis, active-league gating, and a 5-minute
simulation of 1000 live leagues x 4 users against the Sleeper call budget."""

from __future__ import annotations

import random
from collections import deque
from unittest.mock import patch

import pytest

from modules import live_policy, sleeper_budget
from modules.live_policy import AdaptiveTtl


def test_tiers_follow_pressure():
    a = AdaptiveTtl()
    assert [a.update(p) for p in (0.1, 0.45, 0.65, 0.85, 0.95)] == [20, 30, 45, 75, 90]


def test_hysteresis_does_not_flap():
    a = AdaptiveTtl()
    assert a.update(0.41) == 30
    assert a.update(0.38) == 30  # inside the band: stays
    assert a.update(0.34) == 20  # below enter - 0.05: steps down
    assert a.update(0.39) == 20


def test_cold_league_gets_idle_ttl_and_active_one_gets_live():
    live_policy.reset_for_tests()
    with patch.object(live_policy, "live_nfl_week", return_value=5), patch.object(
        live_policy, "pressure_fraction", return_value=0.1
    ):
        assert live_policy.matchups_ttl(5, league_id="Lx") == live_policy.IDLE_TTL_SECONDS  # first touch
        assert 17 <= live_policy.matchups_ttl(5, league_id="Lx") <= 23  # watched, jittered
    live_policy.reset_for_tests()


def test_poll_hint_never_faster_than_server_ttl():
    with patch.object(live_policy, "live_nfl_week", return_value=5), patch.object(
        live_policy, "pressure_fraction", return_value=0.95
    ):
        live_policy.reset_for_tests()
        assert live_policy.poll_hint_seconds(5) >= 90
    live_policy.reset_for_tests()


def test_severe_defer_is_age_bounded():
    assert live_policy.SEVERE_DEFER_MAX_AGE_SECONDS <= 180
    with patch.object(live_policy, "pressure_fraction", return_value=0.95):
        assert live_policy.is_severe_pressure()


def test_simulation_1000_live_leagues_stays_inside_budget():
    leagues, users, seconds, baseline_per_min = 1000, 4, 300, 150
    rng = random.Random(7)
    adaptive = AdaptiveTtl()
    budget = sleeper_budget.BUDGET_PER_MINUTE
    calls: deque[float] = deque()  # timestamps of every upstream call
    fetched_at: dict[int, float] = {}
    last_request: dict[int, float] = {}
    poll_interval = 30.0
    # each user: (league, next request time); they follow the server's hint
    users_next = [(lg, rng.uniform(0, 120)) for lg in range(leagues) for _ in range(users)]
    nxt = [t for _, t in users_next]
    lg_of = [lg for lg, _ in users_next]
    hint = [poll_interval] * len(nxt)
    per_minute = [0] * (seconds // 60 + 1)
    worst_age = 0.0
    served_ttl_max = 0

    def pressure(now: float) -> float:
        while calls and calls[0] < now - 60:
            calls.popleft()
        return (len(calls) + baseline_per_min) / budget

    # event loop at 1 s resolution
    for t in range(seconds):
        now = float(t)
        for i in range(len(nxt)):
            if nxt[i] > now:
                continue
            lg = lg_of[i]
            prev = last_request.get(lg)
            last_request[lg] = now
            watched = prev is not None and now - prev <= live_policy.ACTIVE_LEAGUE_WINDOW_SECONDS
            ttl = live_policy.league_jittered_ttl(adaptive.update(pressure(now)), str(lg)) if watched else live_policy.IDLE_TTL_SECONDS
            served_ttl_max = max(served_ttl_max, ttl)
            if lg not in fetched_at or now - fetched_at[lg] >= ttl:
                fetched_at[lg] = now
                calls.append(now)
                per_minute[int(now // 60)] += 1
            if t >= 60:  # after the cold-start minute
                worst_age = max(worst_age, now - fetched_at[lg])
            hint[i] = max(live_policy.LIVE_POLL_SECONDS, adaptive.update(pressure(now)))
            nxt[i] = now + hint[i] * (1 + 0.1 * rng.random())
    print(f"sim per_minute={per_minute} worst_age={worst_age:.1f}s")
    # total upstream (+ the other Sleeper traffic) stays under 5 minutes of budget
    assert sum(per_minute) + baseline_per_min * 5 < budget * 5
    # steady state (after the cold-start minute): every minute fits the budget
    assert all(c + baseline_per_min <= budget for c in per_minute[1:5]), per_minute
    # worst staleness is bounded by the adaptive ceiling (+ one poll grace)
    assert worst_age <= live_policy.ADAPTIVE_TIERS[-1][1] * 1.15 + 1, worst_age
    assert served_ttl_max <= live_policy.ADAPTIVE_TIERS[-1][1] * 1.15 + 0.01
