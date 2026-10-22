from unittest.mock import Mock, patch

import pytest

from modules import idp_league_values, sleeper

IDP_LEAGUE = {
    "roster_positions": ["QB", "RB", "WR", "TE", "FLEX", "DL", "LB", "DB", "BN"],
    "scoring_settings": {"rec": 1.0, "idp_tkl_solo": 1.0, "idp_tkl_ast": 0.5, "idp_sack": 4.0, "idp_int": 4.0},
    "total_rosters": 12,
}
OFFENSE_LEAGUE = {"roster_positions": ["QB", "RB", "WR", "TE", "FLEX", "K", "DEF", "BN"], "scoring_settings": {"rec": 1.0}, "total_rosters": 12}


def _weeks(n, snaps=55, solo=5.0, ast=2.0, sack=0.0):
    return [
        {"week": w, "defensive_snaps": snaps, "def_snap_share": 0.9, "idp_tkl_solo": solo, "idp_tkl_ast": ast, **({"idp_sack": sack} if sack else {})}
        for w in range(1, n + 1)
    ]


def _fixture():
    players = {
        "1": {"full_name": "Tackle Machine", "position": "LB", "team": "DAL", "status": "Active", "birth_date": "1999-03-01"},
        "2": {"full_name": "Edge Rusher", "position": "DE", "team": "SF", "status": "Active", "birth_date": "1997-05-05"},
        "3": {"full_name": "Retired Guy", "position": "LB", "team": None, "status": "Inactive", "birth_date": "1990-01-01"},
        "4": {"full_name": "Wide Receiver", "position": "WR", "team": "KC", "status": "Active"},
    }
    prior = {
        "1": {"weekly": _weeks(17)},
        "2": {"weekly": _weeks(17, snaps=50, solo=2.0, ast=1.0, sack=1.0)},
        "3": {"weekly": _weeks(17)},
        "4": {"weekly": [{"week": 1, "games_played": 1}]},
    }
    for i in range(40):  # replacement-level depth so the two stars sit above it
        for pos in ("DE", "LB"):
            pid = f"f{pos}{i}"
            players[pid] = {"full_name": f"Filler {pos} {i}", "position": pos, "team": "NYJ", "status": "Active", "birth_date": "1999-01-01"}
            prior[pid] = {"weekly": _weeks(17, snaps=25, solo=1.0, ast=0.5)}
    return {2025: prior, 2026: {}, 2024: {}}, players


def test_offense_only_league_gets_no_idp_rows():
    assert idp_league_values.build_league_idp_values(OFFENSE_LEAGUE) == {"idp": False, "players": []}


def test_idp_league_values_defenders_only_and_skips_retired():
    stats, players = _fixture()
    out = idp_league_values.build_league_idp_values(IDP_LEAGUE, season=2026, stats_by_season=stats, players=players)
    assert out["idp"] is True and out["slots"] == {"DL": 1, "LB": 1, "DB": 1}
    names = [p["name"] for p in out["players"]]
    assert "Retired Guy" not in names and "Wide Receiver" not in names
    assert {"Tackle Machine", "Edge Rusher"} <= set(names)
    assert all(not n.startswith("Filler") for n in names[:2])
    assert all(0 <= p["value"] <= 9000 and p["confidence"] in {"low", "medium", "high"} for p in out["players"])
    assert [p["idp_rank"] for p in out["players"]] == list(range(1, len(out["players"]) + 1))
    assert out["below_replacement_ids"]  # filler sits at/below replacement and is reported by id, not valued
    assert "model value" in out["method"].lower()


def test_idp_league_without_idp_scoring_says_so_instead_of_inventing_values():
    league = {**IDP_LEAGUE, "scoring_settings": {"rec": 1.0}}
    out = idp_league_values.build_league_idp_values(league, season=2026, stats_by_season=_fixture()[0], players=_fixture()[1])
    assert out["players"] == [] and out["reason"] == "no_idp_scoring"


def test_old_cache_without_defensive_fields_is_reported_unavailable():
    old = {"1": {"weekly": [{"week": 1, "games_played": 1, "snap_share": 0.0}]}}
    out = idp_league_values.build_league_idp_values(IDP_LEAGUE, season=2026, stats_by_season={2025: old, 2026: {}, 2024: {}}, players={})
    assert out["players"] == [] and out["reason"] == "defensive_stats_unavailable"


def _client(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    from services import mobile_api_service

    return TestClient(mobile_api_service.app)


def test_endpoint_requires_auth_and_serves_idp_flag(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/v1/leagues/abc/idp/values").status_code == 401
    auth = Mock(status_code=200)
    auth.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    with patch("requests.get", return_value=auth), patch("modules.sleeper.get_league", return_value=OFFENSE_LEAGUE):
        response = client.get("/v1/leagues/abc/idp/values", headers={"Authorization": "Bearer good-token"})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "idp": False, "players": []}
    with patch("requests.get", return_value=auth), patch("modules.sleeper.get_league", return_value={}):
        missing = client.get("/v1/leagues/abc/idp/values", headers={"Authorization": "Bearer good-token"})
    assert missing.status_code == 404
