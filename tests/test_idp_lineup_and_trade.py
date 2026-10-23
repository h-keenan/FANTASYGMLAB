"""IDP in suggested lineups, the swap planner, Trade Analyzer and Trade Hub.

Non-IDP leagues must be untouched; defenders only appear with real model
values (no invented numbers).
"""

from __future__ import annotations

import pandas as pd

from modules import idp_roster_rows, league_value_settings, matchup_what_if, team_eval, trade_hub_engine
from services import mobile_api_service as svc

IDP_POSITIONS = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "DL", "DL", "LB", "DB", "IDP_FLEX", "BN", "BN"]
OFFENSE_POSITIONS = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BN", "BN"]

RESULT = {
    "idp": True,
    "players": [
        {"player_id": "d1", "name": "Edge One", "family": "DL", "team": "SF", "age": 26.0, "injury_status": None, "value": 900, "confidence": "high"},
        {"player_id": "d2", "name": "Edge Two", "family": "DL", "team": "SF", "age": 27.0, "injury_status": None, "value": 500, "confidence": "medium"},
        {"player_id": "d3", "name": "Edge Three", "family": "DL", "team": "SF", "age": 28.0, "injury_status": None, "value": 400, "confidence": "high"},
        {"player_id": "l1", "name": "Backer One", "family": "LB", "team": "DAL", "age": 24.5, "injury_status": None, "value": 700, "confidence": "high"},
        {"player_id": "l2", "name": "Backer Two", "family": "LB", "team": "DAL", "age": 25.0, "injury_status": None, "value": 650, "confidence": "low"},
        {"player_id": "b1", "name": "Safety One", "family": "DB", "team": "KC", "age": 27.0, "injury_status": None, "value": 300, "confidence": "high"},
    ],
    "below_replacement_ids": ["x1"],
    "below_replacement_players": [
        {"player_id": "x1", "name": "Low Corner", "position": "CB", "family": "DB", "team": "NYJ", "age": 23.0, "injury_status": None, "value": None, "confidence": "low"}
    ],
}


def _offense_frame(score_field="dynasty_score"):
    rows = []
    for i, pos in enumerate(["QB", "RB", "RB", "WR", "WR", "TE", "RB"], start=1):
        rows.append(
            {
                "player_id": f"o{i}", "name": f"Off {i}", "position": pos, "team": "KC", "age": 26,
                "status": "Active", "injury_status": None, "score": 3000 - i, "value_score": 3000 - i,
                "dynasty_score": 3000 - i, "rebuild_score": 3000 - i,
            }
        )
    return pd.DataFrame(rows)


def test_detect_settings_reports_idp_slots_only_for_idp_leagues():
    idp = league_value_settings.detect_league_value_settings_from_payload({"roster_positions": IDP_POSITIONS, "scoring_settings": {}})
    assert idp["idp_slots"] == {"DL": 2, "LB": 1, "DB": 1, "IDP_FLEX": 1}
    off = league_value_settings.detect_league_value_settings_from_payload({"roster_positions": OFFENSE_POSITIONS, "scoring_settings": {}})
    assert "idp_slots" not in off


def test_suggested_lineup_fills_idp_slots_best_first_and_flex_takes_the_next_best():
    settings = {"idp_slots": {"DL": 2, "LB": 1, "DB": 1, "IDP_FLEX": 1}}
    defenders = pd.DataFrame(
        [
            {"player_id": e["player_id"], "name": e["name"], "position": e["family"], "team": e["team"], "age": e["age"],
             "status": "Active", "injury_status": None, "dynasty_score": e["value"]}
            for e in RESULT["players"]
        ]
    )
    frame = pd.concat([_offense_frame(), defenders], ignore_index=True)
    lineup = team_eval.suggest_optimal_lineup(frame, settings, score_field="dynasty_score")
    slots = dict(zip(lineup["player_id"], lineup["slot"]))
    assert slots["d1"] == "DL" and slots["d2"] == "DL"
    assert slots["l1"] == "LB" and slots["b1"] == "DB"
    assert slots["l2"] == "IDP_FLEX"  # best leftover defender
    assert slots["d3"] == "BENCH"
    assert not (set(team_eval.lineup_open_slots(lineup, settings)) & {"DL", "LB", "DB", "IDP_FLEX"})


def test_idp_slots_are_open_when_no_defender_is_rostered_and_absent_in_non_idp():
    settings = {"idp_slots": {"DL": 1}}
    lineup = team_eval.suggest_optimal_lineup(_offense_frame(), settings, score_field="dynasty_score")
    assert "DL" in team_eval.lineup_open_slots(lineup, settings)
    plain = team_eval.suggest_optimal_lineup(_offense_frame(), {}, score_field="dynasty_score")
    assert not (set(plain["slot"]) & {"DL", "LB", "DB", "IDP_FLEX"})
    assert not (set(team_eval.lineup_open_slots(plain, {})) & {"DL", "LB", "DB", "IDP_FLEX"})


def test_weekly_mode_never_gives_a_defender_an_offensive_projection():
    settings = {"idp_slots": {"DL": 1}}
    defenders = pd.DataFrame(
        [
            {"player_id": "d1", "name": "Edge One", "position": "DL", "team": "SF", "age": 26, "status": "Active", "injury_status": None, "dynasty_score": 900},
            {"player_id": "d2", "name": "Edge Two", "position": "DL", "team": "SF", "age": 26, "status": "Active", "injury_status": None, "dynasty_score": 500},
        ]
    )
    frame = pd.concat([_offense_frame(), defenders], ignore_index=True)
    points = {f"o{i}": 10.0 + i for i in range(1, 8)}
    lineup = team_eval.suggest_optimal_lineup(frame, settings, score_field="dynasty_score", weekly_points=points, bye_player_ids=set())
    by_id = lineup.set_index("player_id")
    assert by_id.loc["d1", "slot"] == "DL" and by_id.loc["d2", "slot"] == "BENCH"
    assert pd.isna(by_id.loc["d1", "lineup_points"])
    assert by_id.loc["d1", "lineup_points_basis"] == "value"
    assert by_id.loc["o1", "lineup_points_basis"] == "projection"


def test_my_team_lineup_includes_rostered_defenders_incl_below_replacement():
    valued = _offense_frame()
    roster = {"players": [f"o{i}" for i in range(1, 8)] + ["d1", "l1", "x1"], "starters": []}
    settings = league_value_settings.detect_league_value_settings_from_payload({"roster_positions": IDP_POSITIONS, "scoring_settings": {}})
    lookup = {"x1": {"position": "CB", "first_name": "Low", "last_name": "Corner", "team": "NYJ"}}
    starters, bench = svc._suggested_lineup_split(
        valued, roster, settings, "dynasty_score", players_lookup=lookup, idp_result=RESULT
    )
    by_id = {p["player_id"]: p for p in starters + bench}
    assert by_id["d1"]["slot"] == "DL" and by_id["d1"]["score"] == 900
    assert by_id["l1"]["slot"] == "LB"
    assert by_id["x1"]["score"] is None  # below replacement: no invented number


def test_non_idp_league_lineup_ignores_idp_result():
    valued = _offense_frame()
    roster = {"players": [f"o{i}" for i in range(1, 8)], "starters": []}
    settings = league_value_settings.detect_league_value_settings_from_payload({"roster_positions": OFFENSE_POSITIONS, "scoring_settings": {}})
    with_idp = svc._suggested_lineup_split(valued, roster, settings, "dynasty_score", idp_result=RESULT)
    without = svc._suggested_lineup_split(valued, roster, settings, "dynasty_score")
    assert with_idp == without


def test_swap_planner_offers_only_defenders_for_idp_slots():
    pool = {
        "d1": {"player_id": "d1", "name": "Edge One", "position": "DL", "score": 900},
        "d2": {"player_id": "d2", "name": "Edge Two", "position": "DL", "score": 500},
        "l1": {"player_id": "l1", "name": "Backer One", "position": "LB", "score": 700},
        "o1": {"player_id": "o1", "name": "Off 1", "position": "RB", "score": 3000},
    }
    lineup = [{"slot": "DL", "player_id": "d1"}, {"slot": "IDP_FLEX", "player_id": "l1"}]
    matchup_what_if.validate_lineup(pool, lineup, svc._SLOT_ELIGIBLE_POSITIONS)
    result = matchup_what_if.candidates_for_slot(pool, lineup, 0, [], svc._SLOT_ELIGIBLE_POSITIONS)
    assert {c["player"]["player_id"] for c in result["candidates"]} == {"d2"}  # no LB or RB in a DL slot


def test_trade_pool_rows_value_none_for_below_replacement_and_only_when_wanted():
    assert [r["player_id"] for r in idp_roster_rows.trade_pool_rows(RESULT)] == ["d1", "d2", "d3", "l1", "l2", "b1"]
    rows = idp_roster_rows.trade_pool_rows(RESULT, ["x1"])
    assert rows[-1]["player_id"] == "x1" and rows[-1]["value"] is None
    assert idp_roster_rows.trade_pool_rows({"idp": False, "players": []}, ["x1"]) == []


def test_trusted_ids_need_high_confidence():
    assert idp_roster_rows.trusted_idp_ids(RESULT) == {"d1", "d3", "l1", "b1"}
    assert idp_roster_rows.trusted_idp_ids({"idp": False, "players": RESULT["players"]}) == set()


def test_with_idp_trade_rows_adds_defenders_with_model_value_and_zero_for_below_replacement():
    valued = _offense_frame()
    out = svc._with_idp_trade_rows(valued, RESULT, "dynasty_score", {"x1"})
    by_id = out.set_index("player_id")
    assert by_id.loc["d1", "dynasty_score"] == 900 and by_id.loc["d1", "position"] == "DL"
    assert by_id.loc["x1", "dynasty_score"] == 0
    assert len(out) == len(valued) + 7
    assert svc._with_idp_trade_rows(valued, {"idp": False, "players": []}, "dynasty_score", set()) is valued
    # below-replacement defenders not asked for are not added
    assert "x1" not in set(svc._with_idp_trade_rows(valued, RESULT, "dynasty_score", set())["player_id"])


def test_trade_hub_engine_drops_defender_rows_and_leaves_offense_frames_alone():
    frame = _offense_frame()
    assert trade_hub_engine.exclude_idp_rows(frame) is frame
    mixed = pd.concat([frame, pd.DataFrame([{"player_id": "d1", "name": "E", "position": "DL", "dynasty_score": 900}])], ignore_index=True)
    out = trade_hub_engine.exclude_idp_rows(mixed)
    assert "d1" not in set(out["player_id"]) and len(out) == len(frame)


def test_real_lineup_resolves_defender_starters_from_the_idp_model():
    matchup_entry = {"starters": ["o1", "d1", "0"], "starters_points": [10.0, 7.5, 0], "points": 17.5}
    out = svc._real_current_lineup(
        matchup_entry, _offense_frame(), "dynasty_score", roster_positions=["RB", "DL", "LB", "BN"], idp_result=RESULT
    )
    defender = out["real_starters"][1]
    assert defender["name"] == "Edge One" and defender["position"] == "DL" and defender["slot"] == "DL"
    assert defender["score"] == 900 and defender["actual_points"] == 7.5
    assert out["real_empty_slots"] == ["LB"]


def _analyzer_post(monkeypatch, body, rosters):
    from unittest.mock import Mock, patch

    from tests.test_mobile_api_service import _TRADE_ANALYZER_LEAGUE, _client, _fake_roster_frame

    client = _client(monkeypatch)
    auth = Mock(status_code=200)
    auth.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    profile = Mock(status_code=200)
    profile.json.return_value = [{"entitlement": "free", "sleeper_username": "gm_dynasty"}]
    league = {**_TRADE_ANALYZER_LEAGUE, "roster_positions": _TRADE_ANALYZER_LEAGUE["roster_positions"] + ["DL", "LB", "IDP_FLEX"]}
    with patch("requests.get", side_effect=[auth, profile]), patch(
        "modules.sleeper_leagues.resolve_sleeper_user_id", return_value="sleeper-user-1"
    ), patch("modules.sleeper.get_rosters", return_value=rosters), patch(
        "modules.sleeper.get_league", return_value=league
    ), patch("modules.rankings.load_players", return_value=_fake_roster_frame()), patch(
        "modules.player_eligibility.filter_current_fantasy_players", side_effect=lambda df, **kw: df
    ), patch.object(svc, "_league_idp_result", return_value=RESULT):
        return client.post(
            "/v1/leagues/abc/trade-analyzer", json=body, headers={"Authorization": "Bearer good-token"}
        )


def test_trade_analyzer_resolves_idp_players_as_assets(monkeypatch):
    mine = [f"my{i}" for i in range(1, 10)] + ["my_bench_rb", "d1", "x1"]
    rosters = [{"roster_id": 1, "owner_id": "sleeper-user-1", "players": mine}]
    sent = _analyzer_post(monkeypatch, {"send_player_ids": ["d1"], "receive_player_ids": ["target_rb"], "strategy": "contender"}, rosters)
    assert sent.status_code == 200
    body = sent.json()
    assert body["reason"] == "" and body["verdict"] is not None
    # a below-replacement defender resolves too (zero value), instead of "assets_not_found"
    below = _analyzer_post(monkeypatch, {"send_player_ids": ["x1"], "receive_player_ids": ["target_rb"], "strategy": "contender"}, rosters)
    assert below.json()["reason"] == ""
    assert below.json()["verdict"]["value_delta"] > 0
