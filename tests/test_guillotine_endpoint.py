from unittest.mock import Mock, patch

import pandas as pd
import pytest

AUTH = {"Authorization": "Bearer good-token"}


def _league(**kw):
    base = {"name": "Dynasty Lads", "status": "in_season", "settings": {"leg": 5}}
    base.update(kw)
    return base


def _client(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    from services import mobile_api_service as svc

    monkeypatch.setattr(svc, "_fetch_profile_fields", lambda *a, **k: {"entitlement": "free"})
    return TestClient(svc.app), svc


def _auth():
    resp = Mock(status_code=200)
    resp.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    return patch("requests.get", side_effect=[resp])


def _wire(monkeypatch, svc, *, league, rosters, weeks, override=None, me=1):
    mine = next(r for r in rosters if r["roster_id"] == me)
    monkeypatch.setattr(svc, "_resolve_my_roster", lambda *a, **k: (mine, ""))
    monkeypatch.setattr(svc, "_stored_league_type_override", lambda *a, **k: override)
    monkeypatch.setattr("modules.sleeper.get_league", lambda *a, **k: league)
    monkeypatch.setattr("modules.sleeper.get_rosters", lambda *a, **k: rosters)
    monkeypatch.setattr("modules.sleeper.get_matchups", lambda lid, w: weeks.get(w, []))


def _weeks(upto, zero_after=None):
    out = {}
    for w in range(1, upto + 1):
        out[w] = [
            {"roster_id": 1, "points": 100.0, "starters": ["a"]},
            {"roster_id": 2, "points": 90.0 if not zero_after or w <= zero_after else 0, "starters": ["b"]},
            {"roster_id": 3, "points": 95.0, "starters": ["c"]},
        ]
    return out


def _project(monkeypatch, svc, pts):
    monkeypatch.setattr(
        "modules.league_value_settings.build_valued_players_frame_cached",
        lambda **k: pd.DataFrame([{"player_id": "a"}]),
    )
    monkeypatch.setattr(svc, "_build_projection_context", lambda week: object())
    monkeypatch.setattr(
        svc,
        "_real_current_lineup",
        lambda entry, *a, **k: {"real_starters": [{"pts": pts[str(entry["roster_id"])]}], "real_empty_slots": []},
    )
    monkeypatch.setattr("modules.matchup_win_probability.starter_expected_points", lambda s: s["pts"])


def test_requires_auth(monkeypatch):
    client, _ = _client(monkeypatch)
    assert client.get("/v1/leagues/abc/guillotine").status_code == 401


def test_normal_league_with_empty_roster_stays_standard(monkeypatch):
    client, svc = _client(monkeypatch)
    rosters = [{"roster_id": 1, "players": ["a"]}, {"roster_id": 2, "players": []}, {"roster_id": 3, "players": ["c"]}]
    weeks = _weeks(4)
    for entries in weeks.values():
        entries[1]["points"] = 0  # abandoned team: never scored, never chopped
    _wire(monkeypatch, svc, league=_league(), rosters=rosters, weeks=weeks)
    with _auth():
        body = client.get("/v1/leagues/abc/guillotine", headers=AUTH).json()
    assert body["is_guillotine"] is False and body["reason"] == "not_guillotine"


def test_chop_history_detects_without_name(monkeypatch):
    client, svc = _client(monkeypatch)
    rosters = [{"roster_id": 1, "players": ["a"]}, {"roster_id": 2, "players": []}, {"roster_id": 3, "players": ["c"]}]
    _wire(monkeypatch, svc, league=_league(), rosters=rosters, weeks=_weeks(4, zero_after=2), me=2)
    with _auth():
        body = client.get("/v1/leagues/abc/guillotine", headers=AUTH).json()
    assert body["source"] == "chop_history"
    assert body["alive"] is False and body["weeks_survived"] == 2
    assert body["teams_alive"] == 2 and body["chop_line"] is None


def test_chop_line_from_real_projections(monkeypatch):
    client, svc = _client(monkeypatch)
    rosters = [{"roster_id": 1, "players": ["a"]}, {"roster_id": 3, "players": ["c"]}]
    _wire(monkeypatch, svc, league=_league(), rosters=rosters, weeks=_weeks(5), override="guillotine")
    _project(monkeypatch, svc, {"1": 101.5, "3": 88.0})
    with _auth():
        body = client.get("/v1/leagues/abc/guillotine", headers=AUTH).json()
    assert body["source"] == "override" and body["alive"] is True
    assert body["chop_line"] == {"line": 88.0, "my_projected": 101.5, "margin": 13.5, "at_risk": False}


def test_chop_line_silent_when_a_projection_is_missing(monkeypatch):
    client, svc = _client(monkeypatch)
    rosters = [{"roster_id": 1, "players": ["a"]}, {"roster_id": 3, "players": ["c"]}]
    _wire(monkeypatch, svc, league=_league(), rosters=rosters, weeks=_weeks(5), override="guillotine")
    _project(monkeypatch, svc, {"1": 101.5, "3": None})
    with _auth():
        body = client.get("/v1/leagues/abc/guillotine", headers=AUTH).json()
    assert body["is_guillotine"] and body["chop_line"] is None


def test_override_standard_beats_name(monkeypatch):
    client, svc = _client(monkeypatch)
    rosters = [{"roster_id": 1, "players": ["a"]}]
    _wire(monkeypatch, svc, league=_league(name="Chopped"), rosters=rosters, weeks={}, override="standard")
    with _auth():
        body = client.get("/v1/leagues/abc/guillotine", headers=AUTH).json()
    assert body["is_guillotine"] is False and body["league_type_override"] == "standard"


def test_set_league_type_stores_and_clears(monkeypatch):
    client, svc = _client(monkeypatch)
    saved = {}
    monkeypatch.setattr(svc.account_store, "fetch_user_settings", lambda *a, **k: ({"settings": dict(saved)}, None))
    monkeypatch.setattr(svc.account_store, "build_user_settings_payload", lambda user_id, settings: settings)

    def upsert(config, token, payload):
        saved.clear()
        saved.update(payload)
        return True, None

    monkeypatch.setattr(svc.account_store, "upsert_user_settings", upsert)
    with _auth():
        r = client.post("/v1/leagues/abc/league-type", json={"league_type": "guillotine"}, headers=AUTH)
    assert r.json() == {"ok": True, "league_type": "guillotine"}
    assert saved["league_type_override_by_league"] == {"abc": "guillotine"}
    with _auth():
        r = client.post("/v1/leagues/abc/league-type", json={"league_type": "auto"}, headers=AUTH)
    assert r.json()["league_type"] is None and saved["league_type_override_by_league"] == {}
    with _auth():
        assert client.post("/v1/leagues/abc/league-type", json={"league_type": "x"}, headers=AUTH).status_code == 422
