"""This week's pairing and lineups for imported leagues (modules.external_matchups),
and how Matchup / Dashboard use them.

No network and no data/players.db. The fixtures under tests/fixtures/ are trimmed
recordings of the real public endpoints (Fleaflicker FetchLeagueScoreboard /
FetchRoster, MFL TYPE=liveScoring, recorded 2026-10-23), with the players swapped
for the fixture leagues' (one deliberately unmappable starter per league).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

from modules import espn_leagues, external_leagues, external_matchups, fleaflicker_leagues, mfl_leagues, this_week

FIXTURES = Path(__file__).parent / "fixtures"
FF_KEY = "fleaflicker:206154:2025"
MFL_KEY = "mfl:10015:2025"
ESPN_KEY = "espn:42654852:2025"


def _load(folder: str, name: str):
    return json.loads((FIXTURES / folder / name).read_text())


FF_IDS = {
    str(p["proPlayer"]["id"]): f"F-{p['proPlayer']['id']}"
    for entry in _load("fleaflicker", "FetchLeagueRosters.json")["rosters"]
    for p in entry["players"]
    if p["proPlayer"]["id"] not in (99999999, 1)
}
MFL_IDS = {p["id"]: f"S-{p['id']}" for p in _load("mfl", "players.json")["players"]["player"] if p["id"] != "99999"}


@pytest.fixture
def calls(monkeypatch):
    log: list[tuple] = []

    def ff_fetch(endpoint, params):
        log.append(("ff", endpoint, dict(params)))
        if endpoint == "FetchRoster":
            return _load("fleaflicker", f"FetchRoster_{params['team_id']}.json")
        return _load("fleaflicker", f"{endpoint}.json")

    def mfl_fetch(season, params):
        log.append(("mfl", params["TYPE"], dict(params)))
        return _load("mfl", f"{params['TYPE']}.json")

    monkeypatch.setattr(fleaflicker_leagues, "fetch_provider", ff_fetch)
    monkeypatch.setattr(mfl_leagues, "fetch_provider", mfl_fetch)
    for module, ids in ((fleaflicker_leagues, FF_IDS), (mfl_leagues, MFL_IDS)):
        monkeypatch.setattr(module, "crosswalk_provider", lambda ids=ids: ids)
        monkeypatch.setattr(module, "players_frame_provider", lambda: pd.DataFrame())
        monkeypatch.setattr(module, "sleeper_players_provider", lambda: {})
    external_leagues.clear_snapshot_caches()
    mfl_leagues.clear_players_cache()
    external_matchups.clear_caches()
    yield log
    external_leagues.clear_snapshot_caches()
    mfl_leagues.clear_players_cache()
    external_matchups.clear_caches()


# --- Fleaflicker -------------------------------------------------------------


def test_fleaflicker_week_state_comes_from_one_scoreboard_call(calls):
    state = external_matchups.week_state(FF_KEY)
    assert state["week"] == 7 and state["platform"] == "fleaflicker"
    assert state["pairs"] == [{"a": 1373393, "b": 1371776, "a_points": 61.4, "b_points": 48.0}]
    assert calls == [("ff", "FetchLeagueScoreboard", {"sport": "NFL", "league_id": "206154", "season": 2025})]
    pairing = external_matchups.opponent_of(state, 1371776)
    assert pairing == {"mine": 1371776, "theirs": 1373393, "mine_points": 48.0, "theirs_points": 61.4}
    assert external_matchups.opponent_of(state, 999) is None  # unpaired team: no opponent invented


def test_fleaflicker_lineup_maps_starters_and_lists_what_it_could_not(calls):
    state = external_matchups.week_state(FF_KEY)
    mine = external_matchups.lineup_for(FF_KEY, 1373393, state)
    assert mine["starters"] == ["F-8598", "F-12929", "F-12197", "F-6611"]
    assert mine["slot_labels"] == ["QB", "RB", "WR", "TE"]
    assert mine["starters_points"] == [18.0, 11.0, 20.4, 12.0]
    assert mine["projected_points"]["F-12197"] == 15.0
    assert mine["bench"] == ["F-11373"] and mine["unmapped"] == [] and mine["empty_slots"] == []

    theirs = external_matchups.lineup_for(FF_KEY, 1371776, state)
    assert theirs["starters"] == ["F-14759", "F-11177", "F-14677"]
    assert theirs["starters_points"] == [14.2, 9.5, 6.1]
    assert [u["name"] for u in theirs["unmapped"]] == ["Zzyzx Unmappable"]
    assert theirs["unmapped"][0]["fantasy_team"] == "Winter Hill Black Shamrocks"
    # The open FLEX slot is reported as empty, not filled; IR/taxi are not played this week.
    assert theirs["empty_slots"] == ["FLEX"]
    assert theirs["bench"] == ["F-15528"]


def test_fleaflicker_is_cached_and_stays_within_three_calls(calls):
    state = external_matchups.week_state(FF_KEY)
    for _ in range(2):
        pair = external_matchups.matchup_entries(FF_KEY, 1373393, external_matchups.week_state(FF_KEY))
    assert [c[1] for c in calls] == ["FetchLeagueScoreboard", "FetchLeagueRosters", "FetchLeagueStandings", "FetchLeagueRules", "FetchRoster", "FetchRoster"]
    # snapshot (3) + scoreboard (1) + the two lineups (2); a second page load adds nothing within 30s.
    mine, theirs = pair
    assert (mine["roster_id"], theirs["roster_id"]) == (1373393, 1371776)
    assert mine["matchup_id"] == theirs["matchup_id"] and mine["points"] == 61.4 and theirs["points"] == 48.0
    assert state["week"] == 7


# --- MFL ---------------------------------------------------------------------


def test_mfl_live_scoring_is_one_call_with_starters_and_scores(calls):
    state = external_matchups.week_state(MFL_KEY)
    assert state["week"] == 7 and state["pairs"] == [{"a": 1, "b": 2, "a_points": 40.7, "b_points": 38.5}]
    assert calls == [("mfl", "liveScoring", {"TYPE": "liveScoring", "L": "10015"})]

    mine = external_matchups.lineup_for(MFL_KEY, 1, state)
    assert mine["starters"] == ["S-11244", "S-12626", "S-15757"]
    assert mine["starters_points"] == [18.2, 12.5, 6.0]
    # MFL sends no slot names: no labels at all rather than guessed ones.
    assert mine["slot_labels"] == []
    # The unmappable fixture player is named; MFL's non-player id "0001" is skipped, not "unmapped".
    assert [u["name"] for u in mine["unmapped"]] == ["Zzyzx Unmappable"]
    theirs = external_matchups.lineup_for(MFL_KEY, 2, state)
    assert theirs["starters"] == ["S-14833", "S-14071", "S-14779"] and theirs["unmapped"] == []


# --- ESPN --------------------------------------------------------------------


def _espn_league():
    def player(pid, name, pos, team, slot):
        return SimpleNamespace(playerId=pid, name=name, position=pos, proTeam=team, lineupSlot=slot)

    def team(team_id, name, roster):
        return SimpleNamespace(
            team_id=team_id, team_name=name, owners=[], roster=roster, wins=1, losses=1, ties=0,
            points_for=100.0, points_against=90.0, schedule=[], scores=[],
        )

    one = team(1, "Austin", [
        player(1, "Puka Nacua", "WR", "LAR", "WR"),
        player(2, "Nobody Known", "RB", "KC", "RB"),
        player(3, "Kenneth Walker III", "RB", "KC", "BE"),
    ])
    two = team(2, "Boston", [player(4, "Jahmyr Gibbs", "RB", "DET", "RB")])
    one.schedule, one.scores = [two, two], [110.5, 0.0]
    two.schedule, two.scores = [one, one], [98.0, 0.0]
    settings = SimpleNamespace(
        name="E", team_count=2, playoff_team_count=2,
        position_slot_counts={"QB": 0, "RB": 1, "WR": 1, "BE": 3}, scoring_format=[], _raw_scoring_settings={},
    )
    return SimpleNamespace(settings=settings, teams=[one, two], year=2025, current_week=2)


def test_espn_week_lineups_and_pairing_come_from_the_one_league_load(monkeypatch):
    plays = pd.DataFrame(
        [
            {"player_id": "9493", "name": "Puka Nacua", "position": "WR", "team": "LAR"},
            {"player_id": "9221", "name": "Jahmyr Gibbs", "position": "RB", "team": "DET"},
        ]
    )
    factory_calls = []
    monkeypatch.setattr(espn_leagues, "league_factory_provider", lambda: lambda **kw: factory_calls.append(kw) or _espn_league())
    monkeypatch.setattr(espn_leagues, "players_frame_provider", lambda: plays.copy())
    monkeypatch.setattr(espn_leagues, "sleeper_players_provider", lambda: {})
    monkeypatch.setattr(espn_leagues, "espn_crosswalk_provider", lambda _p: {})
    espn_leagues.clear_snapshot_cache()
    external_matchups.clear_caches()
    try:
        state = external_matchups.week_state(ESPN_KEY)
        # Week 2 pairing; a score of 0 (not played yet) stays unknown, never a fake 0.
        assert state["week"] == 2 and state["pairs"] == [{"a": 1, "b": 2, "a_points": None, "b_points": None}]
        mine = external_matchups.lineup_for(ESPN_KEY, 1, state)
        assert mine["starters"] == ["9493"] and mine["slot_labels"] == ["WR"]
        assert [u["name"] for u in mine["unmapped"]] == ["Nobody Known"]
        assert mine["bench"] == []
        pair = external_matchups.matchup_entries(ESPN_KEY, 2, state)
        assert pair[0]["roster_id"] == 2 and pair[1]["roster_id"] == 1
        assert len(factory_calls) == 1  # no second ESPN load
    finally:
        espn_leagues.clear_snapshot_cache()
        external_matchups.clear_caches()


# --- Matchup endpoint --------------------------------------------------------


def _valued_frame():
    rows = []
    for pid, name, position in (
        ("F-8598", "Russell Wilson", "QB"), ("F-12929", "Dalvin Cook", "RB"), ("F-12197", "Tyreek Hill", "WR"),
        ("F-6611", "Rob Gronkowski", "TE"), ("F-11373", "Mike Davis", "RB"),
        ("F-14759", "Tony Pollard", "RB"), ("F-11177", "Amari Cooper", "WR"), ("F-14677", "T.J. Hockenson", "TE"),
    ):
        rows.append(
            {
                "player_id": pid, "name": name, "position": position, "team": "KC", "age": 27, "years_exp": 5,
                "status": "Active", "injury_status": None, "player_tier": "Solid", "opportunity_label": "Rotational",
                "score": 1500, "dynasty_score": 1500, "value_score": 1500, "rebuild_score": 1500,
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture
def matchup_world(calls, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    from services import mobile_api_service as svc

    my_roster = {"roster_id": 1373393, "owner_id": "fleaflicker-team-1373393", "settings": {"wins": 0, "losses": 0}}
    with patch.object(svc, "_resolve_my_roster", return_value=(my_roster, "")), patch.object(
        svc, "_fetch_profile_fields", return_value={}
    ), patch.object(svc.sleeper, "default_player_stats_season", return_value=2025), patch.object(
        svc.sleeper, "get_players", return_value={}
    ), patch.object(svc, "_build_projection_context", return_value=None), patch(
        "modules.league_value_settings.build_valued_players_frame_cached", return_value=_valued_frame()
    ), patch("modules.player_eligibility.filter_current_fantasy_players", side_effect=lambda df, **kw: df), patch(
        "modules.nfl_schedule.load_games", return_value=pd.DataFrame()
    ):
        yield svc


def test_matchup_for_a_fleaflicker_league_shows_both_real_lineups_and_names_the_unmapped(matchup_world):
    svc = matchup_world
    body = svc._build_matchup(FF_KEY, "Dynasty", {"id": "u", "_access_token": "t"})
    assert body["ok"] is True and body["reason"] == "" and body["week"] == 7
    assert body["platform"] == "fleaflicker"

    mine, theirs = body["my_team"], body["opponent"]
    assert mine["team_name"] == "Philadelphia Fire" and theirs["team_name"] == "Winter Hill Black Shamrocks"
    # Real lineups with the platform's own slots and points; team totals are the platform's own.
    assert [p["player_id"] for p in mine["real_starters"]] == ["F-8598", "F-12929", "F-12197", "F-6611"]
    assert [p["slot"] for p in mine["real_starters"]] == ["QB", "RB", "WR", "TE"]
    assert [p["actual_points"] for p in mine["real_starters"]] == [18.0, 11.0, 20.4, 12.0]
    assert mine["real_points"] == 61.4 and theirs["real_points"] == 48.0
    assert body["real_comparison"]["edge"] == "you"
    assert theirs["real_empty_slots"] == ["FLEX"]
    assert [p["name"] for p in body["unmapped_players"]] == ["Zzyzx Unmappable"]
    # Odds are withheld, with the reason, because a real starter has no projection.
    assert body["win_probability"] == {"available": False, "reason": "unmapped_starters"}
    # The roster comparison (suggested lineups by value) is still there.
    assert body["comparison"] is not None


def test_matchup_for_an_old_imported_season_says_there_is_no_current_week(matchup_world):
    svc = matchup_world
    with patch.object(svc.sleeper, "default_player_stats_season", return_value=2026):
        body = svc._build_matchup(FF_KEY, "Dynasty", {"id": "u", "_access_token": "t"})
    assert body["reason"] == "no_current_week" and body["my_team"] is None


def test_matchup_reports_a_bye_when_the_team_is_unpaired(matchup_world):
    svc = matchup_world
    with patch.object(svc, "_resolve_my_roster", return_value=({"roster_id": 4242, "settings": {}}, "")):
        body = svc._build_matchup(FF_KEY, "Dynasty", {"id": "u", "_access_token": "t"})
    assert body["reason"] == "bye_week" and body["week"] == 7


def test_matchup_for_mfl_has_no_slot_labels_and_no_fabricated_win_odds(matchup_world):
    svc = matchup_world
    frame = pd.DataFrame(
        [
            {
                "player_id": f"S-{pid}", "name": f"P {pid}", "position": position, "team": "KC", "age": 27, "years_exp": 5,
                "status": "Active", "injury_status": None, "player_tier": "Solid", "opportunity_label": "Rotational",
                "score": 1500, "dynasty_score": 1500, "value_score": 1500, "rebuild_score": 1500,
            }
            for pid, position in (("11244", "TE"), ("12626", "RB"), ("15757", "WR"), ("14833", "WR"), ("14071", "RB"), ("14779", "QB"))
        ]
    )
    with patch("modules.league_value_settings.build_valued_players_frame_cached", return_value=frame), patch.object(
        svc, "_resolve_my_roster", return_value=({"roster_id": 2, "settings": {}}, "")
    ):
        body = svc._build_matchup(MFL_KEY, "Dynasty", {"id": "u", "_access_token": "t"})
    assert body["ok"] is True and body["week"] == 7 and body["platform"] == "mfl"
    assert [p["player_id"] for p in body["my_team"]["real_starters"]] == ["S-14833", "S-14071", "S-14779"]
    assert all(p["slot"] is None for p in body["my_team"]["real_starters"])
    assert body["my_team"]["real_points"] == 38.5 and body["opponent"]["real_points"] == 40.7
    assert body["real_comparison"]["edge"] == "opponent"
    assert [p["name"] for p in body["unmapped_players"]] == ["Zzyzx Unmappable"]
    assert body["win_probability"]["available"] is False


# --- Dashboard ---------------------------------------------------------------


def test_dashboard_context_adds_the_week_and_a_fully_mapped_lineup(matchup_world):
    svc = matchup_world
    league = {"season": "2025", "status": "in_season", "settings": {"num_teams": 2}}
    roster = {"roster_id": 1373393, "players": ["F-8598"], "starters": []}
    new_league, new_roster = svc._external_dashboard_context(FF_KEY, league, roster)
    assert new_league["settings"]["leg"] == 7 and "leg" not in league["settings"]  # the cached payload is never mutated
    assert new_roster["starters"] == ["F-8598", "F-12929", "F-12197", "F-6611"]
    assert roster["starters"] == []


def test_dashboard_leaves_the_lineup_row_out_when_a_starter_is_unmapped(matchup_world):
    svc = matchup_world
    league = {"season": "2025", "status": "in_season", "settings": {}}
    roster = {"roster_id": 1371776, "players": [], "starters": []}
    new_league, new_roster = svc._external_dashboard_context(FF_KEY, league, roster)
    assert new_league["settings"]["leg"] == 7
    assert new_roster["starters"] == []  # half a lineup is never presented as "set"
    payload = this_week.build_this_week(
        league=new_league, roster=new_roster, roster_rows={}, bye_player_ids=[], items=[], trade_records=None
    )
    assert payload is None  # no lineup row, no waiver row, no trade row: nothing invented


def test_dashboard_this_week_has_only_the_lineup_row_for_an_imported_league(matchup_world):
    svc = matchup_world
    league = {"season": "2025", "status": "in_season", "settings": {}}
    roster = {"roster_id": 1373393, "players": [], "starters": []}
    new_league, new_roster = svc._external_dashboard_context(FF_KEY, league, roster)
    rows_by_player = {
        pid: {"name": pid, "position": "RB", "status": "Active", "injury_status": None} for pid in new_roster["starters"]
    }
    payload = this_week.build_this_week(
        league=new_league, roster=new_roster, roster_rows=rows_by_player, bye_player_ids=[], items=[], trade_records=None
    )
    assert payload["week"] == 7 and [row["key"] for row in payload["rows"]] == ["lineup"]
    assert payload["rows"][0]["status"] == "Set"


def test_dashboard_context_is_fail_soft_when_the_platform_is_down(matchup_world):
    svc = matchup_world
    league = {"season": "2025", "status": "in_season", "settings": {}}
    roster = {"roster_id": 1, "players": [], "starters": []}
    with patch.object(external_matchups, "week_state", side_effect=RuntimeError("down")):
        assert svc._external_dashboard_context(FF_KEY, league, roster) == (league, roster)


# --- Dashboard endpoint end to end -------------------------------------------


@pytest.fixture
def dashboard_client(calls, monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    from services import mobile_api_service as svc

    user = {"id": "user-ff-1", "email": "gm@example.com", "_access_token": "token"}
    rows = [{"league_id": FF_KEY, "roster_id": "1373393", "sleeper_username": "", "league_name": "FF"}]
    monkeypatch.setitem(svc.app.dependency_overrides, svc.require_user, lambda: user)
    monkeypatch.setattr(svc, "_fetch_profile_fields", lambda *a, **k: {"entitlement": "free", "sleeper_username": "", "status": "ok"})
    monkeypatch.setattr(svc.account_store, "fetch_rows", lambda *a, **k: ([dict(r) for r in rows], ""))
    monkeypatch.setattr(svc.account_store, "fetch_saved_leagues", lambda *a, **k: ([dict(r) for r in rows], ""))
    monkeypatch.setattr(svc, "_fetch_team_stance", lambda *a, **k: "")
    monkeypatch.setattr(svc.sleeper, "default_player_stats_season", lambda: 2025)
    # The dashboard must never run the trade-idea search or the waiver engine for an imported league.
    monkeypatch.setattr(
        svc.trade_hub_engine, "generate_trade_idea_records_cached", lambda **k: pytest.fail("trade ideas for an imported league")
    )
    monkeypatch.setattr(
        "modules.dashboard_engine.select_top_waiver_opportunity", lambda *a, **k: pytest.fail("waiver engine for an imported league")
    )
    frame = _valued_frame()
    with patch("modules.league_value_settings.build_valued_players_frame_cached", return_value=frame), patch(
        "modules.player_eligibility.filter_current_fantasy_players", side_effect=lambda df, **kw: df
    ), patch("modules.nfl_schedule.load_games", return_value=pd.DataFrame()), patch.object(
        svc.dashboard_engine, "build_news_tiles", return_value=[]
    ):
        yield TestClient(svc.app)


def test_dashboard_for_a_fleaflicker_league_has_record_rank_and_lineup_but_no_waiver_or_trade(dashboard_client):
    from urllib.parse import quote

    response = dashboard_client.get(f"/v1/leagues/{quote(FF_KEY, safe='')}/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True and body["team_snapshot"] is not None
    assert "Fleaflicker" in body["platform_notice"]
    assert not [item for item in body["items"] if item.get("destination") == "waivers"]
    week = body["this_week"]
    assert week["week"] == 7
    assert [row["key"] for row in week["rows"]] == ["lineup"]  # no waiver row, no trade row
    assert week["rows"][0]["status"] == "Set"
