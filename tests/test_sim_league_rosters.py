"""GET /v1/sim/games/{id}/league/rosters: every team's roster in one payload."""

from __future__ import annotations

import pytest

from modules.sim import game_api
from test_sim_game_api import finish_draft, hdr, make_app, new_game  # noqa: F401


@pytest.fixture(autouse=True)
def _fresh_pool_cache():
    game_api.clear_pool_cache()
    yield
    game_api.clear_pool_cache()


def test_rosters_wrong_phase_during_the_draft():
    client, _, _ = make_app()
    gid = new_game(client)["game"]["id"]
    data = client.get(f"/v1/sim/games/{gid}/league/rosters", headers=hdr()).json()
    assert data["reason"] == "wrong_phase" and data["phase"] == "draft"


def test_every_team_with_its_roster_needs_and_top_assets_in_one_request():
    client, _, _ = make_app()
    gid = new_game(client)["game"]["id"]
    finish_draft(client, gid)
    res = client.get(f"/v1/sim/games/{gid}/league/rosters", headers=hdr())
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["reason"] == "" and len(data["teams"]) == 12
    assert sum(t["is_you"] for t in data["teams"]) == 1
    seen = set()
    for t in data["teams"]:
        assert t["players"], t["name"]
        assert len(t["players"]) >= t["roster_size"]
        assert all(p["owner"]["team_id"] == t["team_id"] and p["squad"] in ("roster", "ir", "taxi") for p in t["players"])
        assert [p["id"] for p in t["top_assets"]] == [p["id"] for p in t["players"][:3]]
        from modules.sim.game_grades import LETTERS

        grades = [LETTERS.index(p["grade"]) if p["grade"] else -1 for p in t["players"]]
        assert grades == sorted(grades, reverse=True)
        assert {p["pos"] for p in t["positions"]} >= {"QB", "RB", "WR", "TE"}
        assert set(t["needs"]) | set(t["strengths"]) | set(t["surplus"]) <= {p["pos"] for p in t["positions"]}
        assert not set(t["needs"]) & set(t["surplus"])  # never "needs WR" and "deep WR" on one card
        assert all(p["depth"] >= 2 for p in t["positions"] if p["pos"] in t["surplus"])
        assert t["record"]["rank"] >= 1 and 1 <= t["power_rank"] <= 12 and t["persona"]["label"]
        for p in t["players"]:
            assert p["id"] not in seen  # nobody is on two teams
            seen.add(p["id"])
    assert sorted(t["power_rank"] for t in data["teams"]) == list(range(1, 13))
    # the team sheet agrees on who is on the roster and now carries IR and taxi too
    mine = next(t for t in data["teams"] if t["is_you"])
    sheet = client.get(f"/v1/sim/games/{gid}/teams/{mine['team_id']}", headers=hdr()).json()
    assert {p["id"] for p in sheet["players"]} | {p["id"] for p in sheet["ir"]} | {p["id"] for p in sheet["taxi"]} == {p["id"] for p in mine["players"]}
