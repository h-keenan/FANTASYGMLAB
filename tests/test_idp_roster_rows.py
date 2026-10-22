from modules import idp_roster_rows
from services import mobile_api_service

RESULT = {
    "idp": True,
    "players": [
        {"player_id": "1", "name": "Edge One", "family": "DL", "team": "SF", "age": 26.0, "injury_status": None, "value": 900},
        {"player_id": "2", "name": "Backer Two", "family": "LB", "team": "DAL", "age": 24.5, "injury_status": "questionable", "value": 600},
        {"player_id": "3", "name": "Free Three", "family": "DB", "team": "KC", "age": 27.0, "injury_status": None, "value": 300},
    ],
    "below_replacement_ids": ["4", "5"],
}
LOOKUP = {"4": {"position": "CB", "first_name": "Low", "last_name": "Four", "team": "NYJ"}}


def test_roster_rows_use_only_model_values_and_keep_below_replacement_players():
    rows = idp_roster_rows.roster_idp_rows(RESULT, ["2", "1", "4", "5"], LOOKUP)
    assert [r["player_id"] for r in rows] == ["1", "2", "4"]  # 5 has no lookup info: not invented
    assert rows[0]["position"] == "DL" and rows[0]["score"] == 900
    assert rows[1]["injury_label"] == "Questionable"
    assert rows[2]["position"] == "DB" and rows[2]["score"] is None
    assert all(r["tier"] is None and r["overall_rating"] is None for r in rows)


def test_free_agent_rows_exclude_rostered_defenders():
    rows = idp_roster_rows.free_agent_idp_rows(RESULT, ["1", "2"])
    assert [r["player_id"] for r in rows] == ["3"]
    assert rows[0]["position"] == "DB" and rows[0]["score"] == 300
    assert rows[0]["position_rank"] is None and rows[0]["opponent"] is None


def test_non_idp_league_gets_no_rows():
    off = {"idp": False, "players": []}
    assert idp_roster_rows.roster_idp_rows(off, ["1"], LOOKUP) == []
    assert idp_roster_rows.free_agent_idp_rows(off, []) == []


def test_league_without_defender_slots_skips_the_model(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("IDP model must not run for a non-IDP league")

    monkeypatch.setattr("modules.idp_league_values.cached_league_idp_values", boom)
    league = {"roster_positions": ["QB", "RB", "WR", "TE", "FLEX", "BN"]}
    assert mobile_api_service._my_team_idp_rows("L", league, ["1"], {}) == []
    assert mobile_api_service._waivers_idp_rows("L", league, [{"players": ["1"]}]) == []


def test_idp_failure_never_breaks_the_endpoints(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("stats down")

    monkeypatch.setattr("modules.idp_league_values.cached_league_idp_values", boom)
    league = {"roster_positions": ["QB", "DL", "BN"]}
    assert mobile_api_service._my_team_idp_rows("L", league, ["1"], {}) == []
