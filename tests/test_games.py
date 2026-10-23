"""Games: season-sim what-if helpers, pick'em grading/lock, endpoints, gating."""

from __future__ import annotations

from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from modules import games, playoff_simulator


PROFILES = {
    "1": {"team_name": "Alpha", "owner_name": "a"},
    "2": {"team_name": "Bravo", "owner_name": "b"},
    "3": {"team_name": "Charlie", "owner_name": "c"},
    "4": {"team_name": "Delta", "owner_name": "d"},
}


def _week(points=(0, 0, 0, 0)):
    return [
        {"matchup_id": 1, "roster_id": 1, "points": points[0]},
        {"matchup_id": 1, "roster_id": 2, "points": points[1]},
        {"matchup_id": 2, "roster_id": 3, "points": points[2]},
        {"matchup_id": 2, "roster_id": 4, "points": points[3]},
        {"matchup_id": None, "roster_id": 5, "points": 0},
    ]


# --- pick'em pure logic --------------------------------------------------


def test_group_week_matchups_skips_byes_and_names_teams():
    grouped = games.group_week_matchups(_week(), PROFILES)
    assert [m["matchup_id"] for m in grouped] == ["1", "2"]
    assert grouped[0]["teams"][0]["team_name"] == "Alpha"


def test_week_phase_open_until_first_score_then_locked_then_final():
    open_week = games.group_week_matchups(_week(), PROFILES)
    assert games.week_phase(5, 5, open_week) == "open"
    started = games.group_week_matchups(_week((12.5, 0, 0, 0)), PROFILES)
    assert games.week_phase(5, 5, started) == "locked"
    assert games.week_phase(4, 5, open_week) == "final"


def test_matchup_winner_and_tie():
    grouped = games.group_week_matchups(_week((100, 90, 80, 80)), PROFILES)
    assert games.matchup_winner(grouped[0]) == "1"
    assert games.matchup_winner(grouped[1]) is None


def test_week_view_grades_only_final_weeks_and_never_ties():
    grouped = games.group_week_matchups(_week((100, 90, 80, 80)), PROFILES)
    final = games.build_week_view(4, 5, grouped, {"1": "2", "2": "3"})
    assert final["phase"] == "final"
    assert (final["correct"], final["graded"], final["picked"]) == (0, 1, 2)
    assert final["matchups"][0]["correct"] is False
    assert final["matchups"][1]["correct"] is None
    live = games.build_week_view(5, 5, grouped, {"1": "1"})
    assert live["phase"] == "locked"
    assert live["graded"] == 0 and live["matchups"][0]["winner_roster_id"] is None


def test_pick_error_requires_a_team_in_the_matchup():
    grouped = games.group_week_matchups(_week(), PROFILES)
    assert games.pick_error(grouped, "1", "2") == ""
    assert games.pick_error(grouped, "1", "3")
    assert games.pick_error(grouped, "9", "1")


def test_leaderboard_ranks_graded_totals_and_hides_ids():
    winners = {3: {"1": "1", "2": "3"}, 4: {"1": "2", "2": "4"}}
    rows = [
        {"user_id": "u1", "week": 3, "matchup_id": "1", "picked_roster_id": "1", "picker_roster_id": "1"},
        {"user_id": "u1", "week": 3, "matchup_id": "2", "picked_roster_id": "3", "picker_roster_id": "1"},
        {"user_id": "u2", "week": 3, "matchup_id": "1", "picked_roster_id": "2", "picker_roster_id": "2"},
        {"user_id": "u2", "week": 4, "matchup_id": "1", "picked_roster_id": "2", "picker_roster_id": "2"},
        {"user_id": "u3", "week": 9, "matchup_id": "1", "picked_roster_id": "1", "picker_roster_id": "3"},
    ]
    board = games.build_leaderboard(rows, winners, PROFILES, "u2")
    assert [r["team_name"] for r in board] == ["Alpha", "Bravo"]
    assert board[0]["correct"] == 2 and board[0]["accuracy"] == 100 and board[0]["rank"] == 1
    assert board[1]["mine"] is True and (board[1]["correct"], board[1]["graded"]) == (1, 2)
    assert all("user_id" not in r for r in board)


# --- what-if helpers -------------------------------------------------------


def _players():
    rows = []
    for i, (pos, score) in enumerate([("QB", 90), ("RB", 80), ("RB", 40), ("WR", 70), ("WR", 60), ("TE", 50), ("WR", 95)]):
        rows.append({"player_id": str(i), "position": pos, "dynasty_score": float(score), "name": f"P{i}"})
    return pd.DataFrame(rows)


def test_validate_roster_change_rules():
    current = ["0", "1", "2"]
    known = {"0", "1", "2", "6"}
    assert games.validate_roster_change(current, ["6"], ["2"], known) == ""
    assert games.validate_roster_change(current, [], [], known)
    assert games.validate_roster_change(current, ["1"], [], known)
    assert games.validate_roster_change(current, [], ["6"], known)
    assert games.validate_roster_change(current, ["99"], [], known)
    assert games.validate_roster_change(current, ["6", "6"], [], known)


def test_adding_a_better_player_raises_roster_score_and_dropping_lowers_it():
    df = _players()
    settings = {"roster_positions": ["QB", "RB", "WR", "WR", "TE", "FLEX"]}
    base = ["0", "1", "2", "3", "4", "5"]
    before = games.score_roster(df, base, "dynasty_score", settings)
    better = games.score_roster(df, games.apply_roster_change(base, ["6"], ["4"]), "dynasty_score", settings)
    worse = games.score_roster(df, games.apply_roster_change(base, [], ["0"]), "dynasty_score", settings)
    assert better["total_score"] > before["total_score"]
    assert worse["total_score"] < before["total_score"]


def test_compare_odds_flags_noise():
    small = games.compare_odds({"playoff_probability": 50.0, "median_seed": 6}, {"playoff_probability": 51.0, "median_seed": 6})
    assert small["within_noise"] is True
    big = games.compare_odds({"playoff_probability": 50.0, "median_seed": 6}, {"playoff_probability": 61.4, "median_seed": 4})
    assert big["playoff_probability"] == 11.4 and big["median_seed"] == -2 and big["within_noise"] is False


def test_what_if_factors_cover_several_real_inputs():
    factors = games.what_if_factors(
        {"starter_score": 100, "bench_score": 10, "total_score": 110},
        {"starter_score": 120, "bench_score": 9, "total_score": 129},
        remaining_games=0,
        weeks_remaining=0,
        slope_fitted=False,
        games_used_for_fit=0,
    )
    labels = [f["label"] for f in factors]
    assert {"Lineup strength", "Depth", "Season left", "Win model"} <= set(labels)
    assert any("No games left" in f["detail"] for f in factors)


def test_power_overrides_move_the_overridden_team(monkeypatch):
    """The real assembly honors power_overrides: a stronger roster means better odds."""

    frame = pd.DataFrame(
        [
            {"roster_id": rid, "team_name": f"T{rid}", "owner_name": "o", "avatar_url": "", "record_label": "0-0",
             "wins": 0, "losses": 0, "ties": 0, "points_for": 0, "points_against": 0, "division_id": None,
             "power_score": 100.0 - rid}
            for rid in range(1, 5)
        ]
    )
    monkeypatch.setattr(playoff_simulator.sleeper, "get_league", lambda _id: {"settings": {"leg": 1, "playoff_week_start": 5}})
    monkeypatch.setattr(playoff_simulator.sleeper, "get_rosters", lambda _id: [])
    monkeypatch.setattr(playoff_simulator.sleeper, "get_league_roster_profiles", lambda _id: {})
    monkeypatch.setattr(playoff_simulator.league_rankings, "build_league_rankings_frame_cached", lambda **_k: frame)
    monkeypatch.setattr(
        playoff_simulator.league_standings,
        "build_league_standings_bundle",
        lambda **_k: {"available": True, "playoff_teams": 2, "frame": frame, "season": "2026"},
    )

    def matchups(_league, week):
        return [
            {"matchup_id": 1, "roster_id": 1, "points": 0},
            {"matchup_id": 1, "roster_id": 4, "points": 0},
            {"matchup_id": 2, "roster_id": 2, "points": 0},
            {"matchup_id": 2, "roster_id": 3, "points": 0},
        ]

    monkeypatch.setattr(playoff_simulator.sleeper, "get_matchups", matchups)

    def run(overrides):
        return playoff_simulator.build_league_playoff_odds(
            "L", players_db_path="x", n_trials=2000, rng=np.random.default_rng(7), power_overrides=overrides
        )

    base = {t["roster_id"]: t for t in run(None)["teams"]}
    boosted = {t["roster_id"]: t for t in run({"4": 500.0})["teams"]}
    assert boosted["4"]["playoff_probability"] > base["4"]["playoff_probability"]
    assert run(None)["teams"] == run(None)["teams"]


# --- endpoints -------------------------------------------------------------


@pytest.fixture()
def client(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    from services import mobile_api_service as svc

    svc.app.dependency_overrides[svc.require_user] = lambda: {"id": "user-1", "_access_token": "tok"}
    svc.app.dependency_overrides[svc.require_league_access] = lambda: "999"
    yield TestClient(svc.app), svc
    svc.app.dependency_overrides.clear()


def test_games_endpoints_require_auth(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    from services import mobile_api_service as svc

    c = TestClient(svc.app)
    assert c.get("/v1/leagues/999/games/season-sim").status_code == 401
    assert c.post("/v1/leagues/999/games/season-sim/what-if", json={"add": ["1"]}).status_code == 401
    assert c.get("/v1/leagues/999/games/pickem").status_code == 401
    assert c.post("/v1/leagues/999/games/pickem/pick", json={"week": 1, "matchup_id": "1", "roster_id": "1"}).status_code == 401


def test_what_if_is_premium_gated(client, monkeypatch):
    c, svc = client
    monkeypatch.setattr(svc, "_fetch_profile_fields", lambda *_a, **_k: {"entitlement": "free"})
    body = c.post("/v1/leagues/999/games/season-sim/what-if", json={"add": ["1"]}).json()
    assert body["is_premium"] is False and body["upsell"]["title"]
    assert "baseline" not in body


def _pickem_setup(svc, monkeypatch, *, points=(0, 0, 0, 0)):
    monkeypatch.setattr(svc.sleeper, "get_league", lambda _id: {"season": "2026", "settings": {"leg": 5, "playoff_week_start": 15}})
    monkeypatch.setattr(svc.sleeper, "get_league_roster_profiles", lambda _id: PROFILES)
    monkeypatch.setattr(svc.sleeper, "get_matchups", lambda _id, _w: _week(points))
    monkeypatch.setattr(svc, "_resolve_my_roster", lambda *_a, **_k: ({"roster_id": 1, "players": []}, ""))


def test_pickem_degrades_when_table_missing(client, monkeypatch):
    c, svc = client
    _pickem_setup(svc, monkeypatch)

    def boom(*_a, **_k):
        raise games.Unavailable("docs/supabase_games.sql")

    monkeypatch.setattr(svc.games, "fetch_my_picks", boom)
    body = c.get("/v1/leagues/999/games/pickem").json()
    assert body["available"] is False and "matchups" not in body


def test_pickem_view_shows_my_picks_and_leaderboard_falls_back_to_me(client, monkeypatch):
    c, svc = client
    _pickem_setup(svc, monkeypatch)
    monkeypatch.setattr(
        svc.games, "fetch_my_picks",
        lambda *_a, **_k: [{"week": 5, "matchup_id": "1", "picked_roster_id": "2", "picker_roster_id": "1"}],
    )
    monkeypatch.setattr(svc.games, "fetch_league_picks", lambda *_a, **_k: None)
    body = c.get("/v1/leagues/999/games/pickem").json()
    assert body["available"] is True and body["phase"] == "open" and body["week"] == 5
    assert body["matchups"][0]["my_pick"] == "2" and body["picked"] == 1
    assert body["leaderboard_scope"] == "you" and body["leaderboard"] == []


def test_pick_is_saved_before_lock_and_rejected_after(client, monkeypatch):
    c, svc = client
    _pickem_setup(svc, monkeypatch)
    saved = []
    monkeypatch.setattr(svc.games, "upsert_pick", lambda _c, _t, row: saved.append(row))
    ok = c.post("/v1/leagues/999/games/pickem/pick", json={"week": 5, "matchup_id": "1", "roster_id": "2"}).json()
    assert ok["ok"] is True
    assert saved[0]["user_id"] == "user-1" and saved[0]["picker_roster_id"] == "1" and saved[0]["season"] == "2026"

    bad = c.post("/v1/leagues/999/games/pickem/pick", json={"week": 5, "matchup_id": "1", "roster_id": "3"})
    assert bad.status_code == 422

    old = c.post("/v1/leagues/999/games/pickem/pick", json={"week": 4, "matchup_id": "1", "roster_id": "1"}).json()
    assert old == {"ok": False, "available": True, "reason": "locked"}

    _pickem_setup(svc, monkeypatch, points=(10.2, 0, 0, 0))
    locked = c.post("/v1/leagues/999/games/pickem/pick", json={"week": 5, "matchup_id": "1", "roster_id": "2"}).json()
    assert locked["reason"] == "locked" and len(saved) == 1


def test_pick_when_not_a_league_member_is_refused(client, monkeypatch):
    c, svc = client
    _pickem_setup(svc, monkeypatch)
    monkeypatch.setattr(svc, "_resolve_my_roster", lambda *_a, **_k: (None, "not_a_member_of_league"))
    body = c.post("/v1/leagues/999/games/pickem/pick", json={"week": 5, "matchup_id": "1", "roster_id": "2"}).json()
    assert body["ok"] is False and body["reason"] == "not_a_member_of_league"
