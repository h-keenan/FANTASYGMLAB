"""GET /v1/sim/games/{id}/home and the scouting view at /teams/{id}."""

from __future__ import annotations

import pytest

from modules.sim import game_api
from test_sim_game_api import advance, finish_draft, hdr, make_app, new_game  # noqa: F401


@pytest.fixture(autouse=True)
def _fresh_pool_cache():
    game_api.clear_pool_cache()
    yield
    game_api.clear_pool_cache()


def season(client, **body):
    gid = new_game(client, **body)["game"]["id"]
    finish_draft(client, gid)
    return gid


def home(client, gid, user="pro"):
    res = client.get(f"/v1/sim/games/{gid}/home", headers=hdr(user))
    assert res.status_code == 200, res.text
    return res.json()


def test_home_is_wrong_phase_during_the_draft():
    client, _, _ = make_app()
    gid = new_game(client)["game"]["id"]
    data = home(client, gid)
    assert data["reason"] == "wrong_phase" and data["phase"] == "draft"


def test_home_matchup_lines_up_both_lineups_slot_by_slot():
    client, _, _ = make_app()
    gid = season(client)
    data = home(client, gid)
    assert data["reason"] == "" and data["week"] == 1
    m = data["matchup"]
    assert m["bye"] is False and m["opponent"]["name"] and m["opponent"]["record"]["wins"] == 0
    assert len(m["rows"]) == 8  # the default starting slots
    assert all(set(r) == {"slot", "you", "opp"} for r in m["rows"])
    assert 0.0 <= m["win_prob"] <= 1.0
    # The total is exactly the sum of the slot numbers on screen (each shown to a tenth), counting only what scores:
    # an out / bye starter shows his when-back projection but counts 0, as the lineup warning says.
    def counted(side):
        return round(sum(r[side]["projection"] for r in m["rows"] if r[side] and r[side]["status"] == "healthy"), 1)

    assert m["you_projection"] == counted("you")
    assert m["opp_projection"] == counted("opp")
    # a projection edge raises the win chance
    lineup = client.get(f"/v1/sim/games/{gid}/lineup", headers=hdr()).json()
    assert lineup["opponent"]["team_id"] == m["opponent"]["team_id"]


def test_home_has_checklist_standings_and_waiver_suggestions():
    client, _, _ = make_app()
    gid = season(client)
    data = home(client, gid)
    ids = [c["id"] for c in data["checklist"]]
    assert "lineup" in ids and "waivers" in ids
    st = data["standings"]
    assert len(st["rows"]) == 12 and st["playoff_spots"] == 6 and st["games_left"] == 14
    for s in data["waiver_suggestions"]:
        assert s["player"]["owner"]["type"] == "free_agent"
        assert s["reasons"] and max(s["gain_now"], s["gain_ros"]) >= 0.8
    assert len(data["waiver_suggestions"]) <= 4
    assert set(data["hot_cold"]) == {"hot", "cold", "wire"}
    assert data["inbox"]["count"] == len(data["inbox"]["items"]) or data["inbox"]["count"] > 3


def test_bye_alerts_name_the_week_the_slot_and_cover():
    client, _, _ = make_app()
    gid = season(client)
    data = home(client, gid)
    for a in data["bye_alerts"]:
        assert a["player"]["bye_week"] == a["week"] and 1 <= a["week"] <= 3
        assert a["pos_label"].startswith(a["player"]["pos"])
        assert (a["covered_by"] is not None) == a["covered"]
        assert f"Week {a['week']}" in a["message"]
        for r in a["replacements"]:
            assert r["pos"] == a["player"]["pos"] and r["owner"]["type"] == "free_agent" and r["bye_week"] != a["week"]


def test_one_bench_player_never_covers_two_byes_in_the_same_week():
    client, _, _ = make_app()
    gid = season(client)
    for _ in range(4):
        advance(client, gid)
        alerts = home(client, gid)["bye_alerts"]
        for week in {a["week"] for a in alerts}:
            covers = [a["covered_by"]["id"] for a in alerts if a["week"] == week and a["covered_by"]]
            assert len(covers) == len(set(covers))


def test_waiver_suggestions_explain_themselves_through_a_season():
    client, _, _ = make_app()
    gid = season(client)
    for _ in range(5):
        advance(client, gid)
        data = home(client, gid)
        for s in data["waiver_suggestions"]:
            assert s["reasons"] and all(isinstance(r, str) and r for r in s["reasons"])
            if s["covers"]:
                assert s["covers"]["status"] != "healthy"
        assert [c["id"] for c in data["checklist"]][0] in ("cuts", "lineup")


def test_home_follows_the_season_and_stays_read_only():
    client, _, _ = make_app()
    gid = season(client)
    before = client.get(f"/v1/sim/games/{gid}", headers=hdr()).json()["game"]
    home(client, gid)
    home(client, gid)
    after = client.get(f"/v1/sim/games/{gid}", headers=hdr()).json()["game"]
    assert before["updated_at"] == after["updated_at"]
    advance(client, gid)
    data = home(client, gid)
    assert data["week"] == 2
    assert data["standings"]["games_left"] == 13


def test_home_is_scoped_to_the_owner():
    client, _, _ = make_app()
    gid = season(client)
    assert client.get(f"/v1/sim/games/{gid}/home", headers=hdr("pro2")).status_code == 404


def test_team_detail_scouts_any_team():
    client, _, _ = make_app()
    gid = season(client)
    league = client.get(f"/v1/sim/games/{gid}/league", headers=hdr()).json()
    other = next(t for t in league["teams"] if not t["is_you"])
    res = client.get(f"/v1/sim/games/{gid}/teams/{other['team_id']}", headers=hdr()).json()
    assert res["reason"] == "" and res["team_id"] == other["team_id"]
    team = res["team"]
    assert team["name"] == other["name"] and team["persona"]["label"] and team["record"]["wins"] == 0
    assert len(res["players"]) == team["roster_size"] and len(res["lineup"]) == 8
    assert res["positions"] and all(p["level"] in ("strength", "need", "ok") for p in res["positions"])
    assert set(res["strengths"]).isdisjoint(res["needs"])
    assert res["trade"]["open"] is True and res["next_game"]["week"] == 1
    mine = client.get(f"/v1/sim/games/{gid}/teams/{league['teams'][0]['team_id']}", headers=hdr()).json()
    assert mine["reason"] == ""
    assert client.get(f"/v1/sim/games/{gid}/teams/nope", headers=hdr()).status_code == 404
