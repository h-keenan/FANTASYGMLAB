"""API surface for Fleaflicker / MFL import (preview, save, my-roster, gating).

Network and player data are replaced through the modules' provider hooks, with
the recorded fixtures used by tests/test_fleaflicker_mfl_leagues.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import pandas as pd
import pytest

from modules import external_leagues, fleaflicker_leagues, mfl_leagues

FIXTURES = Path(__file__).parent / "fixtures"
MFL_KEY = "mfl:10015:2025"
FF_KEY = "fleaflicker:206154:2025"
USER = {"id": "user-mfl-1", "email": "gm@example.com", "_access_token": "token"}


def _load(folder: str, name: str):
    return json.loads((FIXTURES / folder / name).read_text())


@pytest.fixture
def api(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    from services import mobile_api_service as svc

    mfl_ids = {p["id"]: f"S-{p['id']}" for p in _load("mfl", "players.json")["players"]["player"] if p["id"] != "99999"}
    ff_ids = {
        str(p["proPlayer"]["id"]): f"F-{p['proPlayer']['id']}"
        for entry in _load("fleaflicker", "FetchLeagueRosters.json")["rosters"]
        for p in entry["players"]
        if p["proPlayer"]["id"] not in (99999999, 1)
    }
    monkeypatch.setattr(
        mfl_leagues,
        "fetch_provider",
        lambda season, params: _load("mfl", params["TYPE"] + ".json"),
    )
    monkeypatch.setattr(fleaflicker_leagues, "fetch_provider", lambda endpoint, params: _load("fleaflicker", endpoint + ".json"))
    for module, ids in ((mfl_leagues, mfl_ids), (fleaflicker_leagues, ff_ids)):
        monkeypatch.setattr(module, "crosswalk_provider", lambda ids=ids: ids)
        monkeypatch.setattr(module, "players_frame_provider", lambda: pd.DataFrame())
        monkeypatch.setattr(module, "sleeper_players_provider", lambda: {})
    external_leagues.clear_snapshot_caches()
    mfl_leagues.clear_players_cache()

    rows: list[dict] = []
    monkeypatch.setitem(svc.app.dependency_overrides, svc.require_user, lambda: USER)
    monkeypatch.setattr(svc, "_fetch_profile_fields", lambda *a, **k: {"entitlement": "free", "sleeper_username": "", "status": "ok"})
    monkeypatch.setattr(svc.account_store, "fetch_rows", lambda *a, **k: ([dict(r) for r in rows], ""))
    monkeypatch.setattr(svc.account_store, "fetch_saved_leagues", lambda *a, **k: ([dict(r) for r in rows], ""))

    def upsert(_config, _token, payload):
        rows.append(dict(payload))
        return True, ""

    monkeypatch.setattr(svc.account_store, "upsert_saved_league", upsert)
    yield SimpleNamespace(client=TestClient(svc.app), rows=rows)
    external_leagues.clear_snapshot_caches()
    mfl_leagues.clear_players_cache()


def test_preview_save_my_roster_and_gating_for_mfl(api):
    assert api.client.post("/v1/import/preview", json={"platform": "yahoo", "league_id": "1", "season": 2025}).status_code == 422
    body = api.client.post("/v1/import/preview", json={"platform": "mfl", "league_id": "10015", "season": 2025}).json()
    assert body["ok"] is True and body["league"]["league_key"] == MFL_KEY
    assert [t["roster_id"] for t in body["teams"]] == ["1", "2"]

    enc = quote(MFL_KEY, safe="")
    assert api.client.get(f"/v1/leagues/{enc}/my-roster").json()["reason"] == "espn_team_not_selected"
    assert api.client.post("/v1/leagues/save", json={"league_id": MFL_KEY}).json()["reason"] == "espn_team_not_selected"
    saved = api.client.post("/v1/leagues/save", json={"league_id": MFL_KEY, "roster_id": "2"}).json()
    assert saved["ok"] is True and saved["league"]["platform"] == "mfl"
    assert api.rows[0]["league_id"] == MFL_KEY and api.rows[0]["sleeper_username"] == ""
    roster = api.client.get(f"/v1/leagues/{enc}/my-roster").json()["roster"]
    assert roster["roster_id"] == 2 and roster["players"]

    for route in ("waivers", "trade-hub", "alerts"):
        response = api.client.get(f"/v1/leagues/{enc}/{route}")
        assert response.status_code == 409
        assert response.json()["detail"] == "Not available for MFL leagues yet."


def test_preview_and_gating_for_fleaflicker(api):
    body = api.client.post("/v1/import/preview", json={"platform": "fleaflicker", "league_id": "206154", "season": 2025}).json()
    assert body["league"]["league_key"] == FF_KEY and body["platform_label"] == "Fleaflicker"
    # The two unmappable fixture players are listed, not guessed.
    assert {p["name"] for p in body["diagnostics"]["unmapped_players"]} == {"Zzyzx Unmappable"}
    assert body["ok"] is True
    response = api.client.get(f"/v1/leagues/{quote(FF_KEY, safe='')}/waivers")
    assert response.status_code == 409 and response.json()["detail"] == "Not available for Fleaflicker leagues yet."
