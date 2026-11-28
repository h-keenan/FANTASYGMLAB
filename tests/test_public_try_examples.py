"""Real-player /try examples: selection, determinism, fallback. Synthetic fixtures only (no db, no network)."""

from __future__ import annotations

from datetime import datetime, timezone

from modules import external_ad_api as ads
from modules import public_try_examples as T

NOW = datetime(2026, 11, 26, 15, 0, tzinfo=timezone.utc)


def _p(pid, name, pos, team, rank, score=3000, inj=None):
    return {"player_id": pid, "name": name, "position": pos, "team": team, "age": 25, "status": "Active", "injury_status": inj,
            "score": score, "overall_rank": rank + 20, "position_rank": rank, "overall_rating": 70}


def _d(avg):
    return {"weighted_points_allowed_per_game": avg, "games_sampled": 10, "low_sample": False, "rank": 1, "tier": "weak" if avg > 30 else "tough"}


BOARD = [
    _p("1", "Real Alpha", "WR", "AAA", 20),
    _p("2", "Real Bravo", "WR", "BBB", 22),
    _p("3", "Real Charlie", "WR", "CCC", 24, inj="Questionable"),
    _p("4", "Real Delta", "RB", "DDD", 18),
    _p("5", "Wire Echo", "WR", "AAA", 50),
    _p("6", "Wire Foxtrot", "RB", "BBB", 40),
    _p("7", "Hurt Golf", "WR", "AAA", 10, inj="Out"),
    _p("8", "Wire Hotel", "WR", "CCC", 55),
]
MATCHUPS = {t: {"opponent": o, "is_home": h} for t, o, h in (("AAA", "XXX", True), ("BBB", "YYY", False), ("CCC", "XXX", True), ("DDD", "YYY", True))}
DEFENSE = {
    "XXX": {"WR": _d(38.0), "RB": _d(30.0), "QB": _d(18.0), "TE": _d(10.0)},
    "YYY": {"WR": _d(24.0), "RB": _d(22.0), "QB": _d(18.0), "TE": _d(10.0)},
}
PROJ = {
    "1": 13.4, "2": 12.6, "3": 13.0, "4": 12.0,
}


def project(pid):
    if pid not in PROJ:
        return None
    pe = PROJ[pid]
    return {"status": "ok", "point_estimate": pe, "low": pe - 5, "high": pe + 7}


TRENDING = [{"player_id": "5", "count": 5400}, {"player_id": "6", "count": 3100}, {"player_id": "8", "count": 900}, {"player_id": "3", "count": 800}]
PCT = {"5": {"current": 12.0}, "6": {"current": 31.5}, "8": {"current": 70.0}}


def _build(**over):
    kw = dict(board=BOARD, matchups=MATCHUPS, defense=DEFENSE, trending=TRENDING, roster_pct=PCT, project=project, season=2026, week=12, now=NOW)
    kw.update(over)
    return T.build_examples(**kw)


def test_start_sit_is_a_close_same_position_pair_backed_by_the_matchup():
    move = _build()["start_sit"]["move"]
    assert move["start"]["name"] == "Real Alpha" and move["over"]["name"] == "Real Bravo"  # Bravo's matchup is worse, Alpha projects higher
    assert move["start"]["position"] == move["over"]["position"] == "WR"
    assert 0.3 <= move["gain"] <= 1.5 and move["gain"] == 0.8
    assert move["range"]["start"]["low"] == 8.4 and move["range"]["start"]["high"] == 20.4
    assert move["start"]["player_id"] == "1"  # real id so the avatar resolves
    note = _build()["start_sit"]["matchup_note"]
    assert "XXX" in note and "YYY" in note and "PPR points per game" in note


def test_start_sit_never_pairs_an_injured_player_or_a_matchup_that_contradicts_the_projection():
    # Charlie is Questionable (excluded). Make Alpha project LOWER than Bravo while Alpha has the better matchup: no pair.
    out = _build(project=lambda pid: project(pid) if pid != "1" else {"status": "ok", "point_estimate": 12.0, "low": 7.0, "high": 19.0})
    assert out["start_sit"] is None
    assert "Real Charlie" not in str(_build()["start_sit"])


def test_start_sit_requires_projections_that_are_actually_close():
    far = lambda pid: {"status": "ok", "point_estimate": {"1": 20.0, "2": 12.0}.get(pid, 12.0), "low": 5.0, "high": 25.0}
    assert _build(project=far)["start_sit"] is None


def test_waivers_are_low_rostered_trending_healthy_players_with_real_reasons_and_bids():
    adds = _build()["waivers"]["adds"]
    assert [a["name"] for a in adds] == ["Wire Echo", "Wire Foxtrot"]  # Hotel is 70% rostered, Charlie is injured
    echo = adds[0]
    assert echo["roster_pct"] == 12.0 and echo["trending_adds_24h"] == 5400
    assert "5,400 adds" in echo["reason"] and "12% rostered" in echo["reason"] and "WR50" in echo["reason"]
    assert echo["injury_cover_for"] == "Hurt Golf" and "Hurt Golf (Out)" in echo["reason"]
    assert echo["bid"]["budget"] == 100 and 0 <= echo["bid"]["low"] <= echo["bid"]["high"] <= 100


def test_waivers_skip_players_without_a_verified_roster_pct():
    assert _build(roster_pct={})["waivers"] is None


def test_selection_is_deterministic_and_the_weekly_hash_is_stable():
    assert _build() == _build()
    assert T._pick_key(2026, 12, "1", "2") == T._pick_key(2026, 12, "1", "2") != T._pick_key(2026, 13, "1", "2")
    shuffled = _build(board=list(reversed(BOARD)), trending=list(TRENDING))
    assert shuffled["start_sit"] == _build()["start_sit"] and shuffled["waivers"] == _build()["waivers"]


def test_fallback_sections_are_none_never_fabricated():
    out = _build(matchups={}, trending=[])
    assert out["start_sit"] is None and out["waivers"] is None


def test_offseason_is_unavailable_and_not_cached(monkeypatch):
    T._cache.clear()
    monkeypatch.setattr(ads, "clock_info", lambda: {"season": 2026, "phase": "offseason", "week": None, "source": "t"})
    out = T.get_public_try_examples("unused", now=NOW)
    assert out["start_sit"] is None and out["waivers"] is None and "offseason" in out["unavailable_reason"]
    assert not T._cache


def test_in_season_payload_is_cached_for_the_week_but_empty_is_not(monkeypatch):
    T._cache.clear()
    monkeypatch.setattr(ads, "clock_info", lambda: {"season": 2026, "phase": "regular", "week": 12, "source": "t"})
    monkeypatch.setattr(ads, "load_board", lambda db, fmt: (BOARD, "x"))
    monkeypatch.setattr(ads, "load_trending", lambda: TRENDING)
    monkeypatch.setattr(ads, "load_roster_pct", lambda ids: PCT)
    monkeypatch.setattr(ads, "load_games", lambda: None)
    monkeypatch.setattr(ads, "_team_aliases", lambda: {})
    monkeypatch.setattr(ads, "week_matchups", lambda games, s, w, a: MATCHUPS)
    monkeypatch.setattr(ads, "load_defense", lambda s: DEFENSE)
    monkeypatch.setattr("modules.player_projections.project_player_week", lambda pid, week, season=None: project(pid))
    first = T.get_public_try_examples("unused", now=NOW)
    assert first["start_sit"] and first["waivers"] and (2026, 12) in T._cache
    assert T.get_public_try_examples("unused", now=datetime(2026, 11, 27, tzinfo=timezone.utc)) is first
    T._cache.clear()
    monkeypatch.setattr(ads, "load_trending", lambda: [])
    monkeypatch.setattr(ads, "week_matchups", lambda *a: {})
    empty = T.get_public_try_examples("unused", now=NOW)
    assert empty["start_sit"] is None and empty["waivers"] is None and empty["unavailable_reason"] and not T._cache
