"""Direct unit tests for modules/league_value_settings.py's cached
load -> filter -> apply_valuation_lens front door
(build_valued_players_frame_cached) — exercised here without the
Sleeper/FastAPI mocking tests/test_mobile_api_service.py needs for the full
endpoints, since this function takes just (league_id, lens, players_db_path).
"""

from __future__ import annotations

import threading
import time

import pandas as pd

from modules import league_value_settings, player_eligibility, rankings, sleeper


def _patch_cache_ingredients(monkeypatch):
    monkeypatch.setattr(sleeper, "get_league", lambda _league_id: {"league_id": "x", "settings": {}})
    monkeypatch.setattr(
        rankings, "load_players", lambda _db_path: pd.DataFrame([{"player_id": "p1", "name": "P1"}])
    )
    monkeypatch.setattr(
        player_eligibility, "filter_current_fantasy_players", lambda df, **_kwargs: df
    )


def test_build_valued_players_frame_cached_concurrent_misses_single_flight(monkeypatch):
    """Two concurrent cache misses for the same (league_id, lens, ...) key
    must run the expensive valuation pass (apply_valuation_lens, whose
    row-wise current_risk_multiplier `.apply(axis=1)` call is the dominant
    cost of this chain) exactly once, not once per caller.

    Same Redis-backed single-flight guarantee
    (modules.redis_cache.redis_single_flight_cache) modules.league_rankings
    and modules.waivers_ui already enforce for their own caches — see
    tests/test_league_rankings.py's equivalent test. tests/conftest.py's
    autouse fakeredis fixture backs this cache with a real (fake) Redis
    here, so this exercises the actual code path, not a mock of it."""

    _patch_cache_ingredients(monkeypatch)

    call_count = 0
    call_count_lock = threading.Lock()
    real_apply = league_value_settings.apply_valuation_lens

    def _slow_apply(df, *args, **kwargs):
        nonlocal call_count
        with call_count_lock:
            call_count += 1
        time.sleep(0.2)
        return real_apply(df, *args, **kwargs)

    monkeypatch.setattr(league_value_settings, "apply_valuation_lens", _slow_apply)

    league_id = "test-valued-players-frame-single-flight"
    results: list[pd.DataFrame] = []
    results_lock = threading.Lock()

    def _call():
        result = league_value_settings.build_valued_players_frame_cached(
            league_id=league_id, lens="Dynasty", players_db_path="unused.db"
        )
        with results_lock:
            results.append(result)

    threads = [threading.Thread(target=_call) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert call_count == 1, "concurrent misses for the same key must single-flight to one real computation"
    assert len(results) == 8
    for result in results:
        assert list(result["player_id"]) == ["p1"]


def test_build_valued_players_frame_cached_hit_avoids_recompute(monkeypatch):
    """A second call for the same (league_id, lens) within the cache's 30s
    window must be a genuine cache hit — apply_valuation_lens runs exactly
    once across both calls — while still returning the real, correctly
    valued frame (not a stale or wrong cached shape)."""

    _patch_cache_ingredients(monkeypatch)

    call_count = 0
    real_apply = league_value_settings.apply_valuation_lens

    def _counted_apply(df, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        return real_apply(df, *args, **kwargs)

    monkeypatch.setattr(league_value_settings, "apply_valuation_lens", _counted_apply)

    league_id = "test-valued-players-frame-cache-hit"
    first = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens="Dynasty", players_db_path="unused.db"
    )
    second = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens="Dynasty", players_db_path="unused.db"
    )

    assert call_count == 1, "second call within the cache window must be a cache hit, not a recomputation"
    assert list(first["player_id"]) == ["p1"]
    assert list(second["player_id"]) == ["p1"]


def test_build_valued_players_frame_cached_returns_independent_copies(monkeypatch):
    """Callers mutate the returned frame (adding `_overall_rating_col`,
    slicing to one roster, ...) — a cache hit must hand back a fresh copy
    each time, never the same mutable object/cached-entry backing array a
    previous caller could have already mutated."""

    _patch_cache_ingredients(monkeypatch)

    league_id = "test-valued-players-frame-copy-safety"
    first = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens="Dynasty", players_db_path="unused.db"
    )
    first["_overall_rating_col"] = 99

    second = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens="Dynasty", players_db_path="unused.db"
    )

    assert "_overall_rating_col" not in second.columns


def test_build_valued_players_frame_cached_returns_empty_frame_for_missing_league(monkeypatch):
    monkeypatch.setattr(sleeper, "get_league", lambda _league_id: {})

    result = league_value_settings.build_valued_players_frame_cached(
        league_id="missing-league", lens="Dynasty", players_db_path="unused.db"
    )

    assert result.empty


def test_taxi_slots_setting_is_detected_and_boosts_young_skill_players():
    lvs = league_value_settings
    league = {
        "roster_positions": ["QB", "RB", "WR", "TE", "FLEX"] + ["BN"] * 8,
        "settings": {"taxi_slots": 4, "reserve_slots": 0, "num_teams": 12},
    }
    settings = lvs.detect_league_value_settings_from_payload(league)
    assert settings["taxi_count"] == 4  # Sleeper never lists TAXI in roster_positions
    frame = pd.DataFrame({"position": ["WR", "WR", "RB"], "age": [22.0, 27.0, 23.0]})
    on = lvs.league_settings_adjustment_components(frame, settings)["league_adj_roster_depth"]
    off = lvs.league_settings_adjustment_components(frame, dict(settings, taxi_count=0))[
        "league_adj_roster_depth"
    ]
    assert on.iloc[0] / off.iloc[0] > 1.07  # 4 slots * 2% taxi boost
    assert on.iloc[1] == off.iloc[1] == 1.0  # age 27 is not a taxi stash candidate
