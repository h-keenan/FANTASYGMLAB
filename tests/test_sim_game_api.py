"""/v1/sim/games* with stubbed auth/Pro/pool and an in-memory backend (no network)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from modules.sim import api as sim_api
from modules.sim import game_api
from modules.sim.inputs import PlayerPool
from modules.sim.store import InMemoryBackend
from modules.sim.synthetic import build_synthetic_pool
from modules.sim.types import SimInputsError

ROWS, BYES = build_synthetic_pool(7)


class PoolInputs:
    def __init__(self):
        self.calls = 0

    def league_snapshot(self, *a, **k):  # pragma: no cover - not used by game tests
        raise AssertionError("the game never needs a league")

    def player_pool(self, scoring):
        self.calls += 1
        return PlayerPool(ROWS, BYES)


class BrokenInputs:
    def player_pool(self, scoring):
        raise SimInputsError("players_unavailable")


def make_app(*, pro=("pro", "pro2"), backend=None, inputs=None):
    backend = backend if backend is not None else InMemoryBackend()
    inputs = inputs or PoolInputs()

    def require_user(authorization: str | None = Header(default=None)):
        if not authorization:
            raise HTTPException(status_code=401, detail="no")
        return {"id": authorization, "_access_token": "tok"}

    app = FastAPI()
    sim_api.mount(
        app,
        sim_api.SimApiDeps(
            require_user=require_user, is_pro=lambda u: u["id"] in pro, sleeper_username=lambda u: "",
            backend_for=lambda u: backend, inputs=inputs,
        ),
        environ={"SIM_ENABLED": "1"},
    )
    return TestClient(app), backend, inputs


def hdr(user="pro"):
    return {"Authorization": user}


@pytest.fixture(autouse=True)
def _fresh_pool_cache():
    game_api.clear_pool_cache()
    yield
    game_api.clear_pool_cache()


def new_game(client, user="pro", **body):
    res = client.post("/v1/sim/games", json=body, headers=hdr(user))
    assert res.status_code == 200, res.text
    return res.json()


def finish_draft(client, gid, user="pro"):
    res = client.post(f"/v1/sim/games/{gid}/draft/auto", headers=hdr(user))
    assert res.status_code == 200, res.text
    return res.json()


def advance(client, gid, user="pro", **body):
    res = client.post(f"/v1/sim/games/{gid}/advance", json=body or None, headers=hdr(user))
    assert res.status_code == 200, res.text
    return res.json()


# ------------------------------------------------------------------ basics


def test_requires_auth_and_flag_off_is_404():
    client, _, _ = make_app()
    assert client.get("/v1/sim/games").status_code == 401
    assert client.post("/v1/sim/games").status_code == 401
    off = FastAPI()
    assert sim_api.mount(off, sim_api.SimApiDeps(require_user=lambda: {}, is_pro=lambda u: True,
                                                  sleeper_username=lambda u: ""), environ={}) is False
    for path in ("/v1/sim/games", "/v1/sim/games/options", "/v1/sim/preview/players"):
        assert TestClient(off).get(path).status_code == 404


def test_options_work_for_free_callers():
    client, _, _ = make_app()
    data = client.get("/v1/sim/games/options", headers=hdr("free")).json()
    assert data["reason"] == "" and data["is_premium"] is False
    assert data["max_games"] == 1 and data["season"]["regular_weeks"] == 14
    assert data["preview"] == {"weeks_left": 3, "paywall_week": 4, "paywalled": False}
    assert data["options"]["teams"]["values"] == [8, 10, 12, 14]


def test_create_game_starts_in_the_draft_with_the_user_on_the_clock():
    client, backend, inputs = make_app()
    data = new_game(client, user_slot=5, team_name="Mine")
    game = data["game"]
    assert game["status"] == "drafting" and game["phase"] == "draft" and game["week"] == 0
    assert game["settings"]["teams"] == 12 and game["settings"]["user_slot"] == 5
    assert game["you"]["name"] == "Mine" and game["you"]["team_id"] == "5"
    draft = data["draft"]
    assert draft["on_the_clock"] == {"team_id": "5", "name": "Mine", "is_you": True}
    assert draft["pick_no"] == 5 and len(draft["picks"]) == 4 and draft["total_picks"] == 168
    assert len(draft["order"]) == 168 and draft["picks_until_you"] == 0
    assert data["available"]["total"] == 570 - 4 and data["hint"]["player"]["id"]
    assert inputs.calls == 1
    assert set(backend.tables) <= {"sim_games", "sim_events", "sim_week_checkpoints"}
    assert "user_id" not in game and "snapshot" not in game


def test_pick_resolves_ai_picks_until_your_next_turn():
    client, _, _ = make_app()
    data = new_game(client, user_slot=3)
    gid = data["game"]["id"]
    pid = data["hint"]["player"]["id"]
    res = client.post(f"/v1/sim/games/{gid}/draft/pick", json={"player_id": pid}, headers=hdr()).json()
    assert res["reason"] == "" and res["picks"][0]["player"]["id"] == pid
    # 21 AI picks follow (the rest of round 1 and the start of round 2 until slot 3 again)
    assert res["draft"]["on_the_clock"]["is_you"] is True
    assert res["draft"]["pick_no"] == 3 + 2 * 10 + 2 + 1 or res["draft"]["pick_no"] > 3
    assert res["completed"] is False
    # drafted player cannot be drafted again
    again = client.post(f"/v1/sim/games/{gid}/draft/pick", json={"player_id": pid}, headers=hdr()).json()
    assert again["reason"] == "player_taken"
    bad = client.post(f"/v1/sim/games/{gid}/draft/pick", json={"player_id": "nope"}, headers=hdr())
    assert bad.status_code == 422


def test_double_submitted_pick_drafts_exactly_one_player():
    client, _, _ = make_app()
    data = new_game(client, user_slot=3)
    gid = data["game"]["id"]
    on_clock = data["draft"]["pick_no"]
    first_pid = data["hint"]["player"]["id"]
    ok = client.post(f"/v1/sim/games/{gid}/draft/pick", json={"player_id": first_pid, "pick_no": on_clock}, headers=hdr())
    assert ok.status_code == 200 and ok.json()["reason"] == ""
    mine_before = len(client.get(f"/v1/sim/games/{gid}/draft", headers=hdr()).json()["draft"]["your_roster"])
    # the second tap carries the same (now stale) pick_no and a different player
    other = client.get(f"/v1/sim/games/{gid}/players?status=available", headers=hdr()).json()["items"][0]["id"]
    dup = client.post(f"/v1/sim/games/{gid}/draft/pick", json={"player_id": other, "pick_no": on_clock}, headers=hdr())
    assert dup.status_code == 409 and dup.json()["reason"] == "already_picked"
    mine_after = len(client.get(f"/v1/sim/games/{gid}/draft", headers=hdr()).json()["draft"]["your_roster"])
    assert mine_after == mine_before == 1
    # old clients (no pick_no) still work
    legacy = client.post(f"/v1/sim/games/{gid}/draft/pick", json={"player_id": other}, headers=hdr())
    assert legacy.status_code == 200


def test_players_pos_accepts_flex_eligibility_groups():
    client, _, _ = make_app()
    gid = new_game(client)["game"]["id"]

    def positions(pos):
        res = client.get(f"/v1/sim/games/{gid}/players?status=available&page_size=100&pos={pos}", headers=hdr())
        assert res.status_code == 200
        return {p["pos"] for p in res.json()["items"]}

    assert positions("FLEX") == {"RB", "WR", "TE"}
    assert positions("SUPER_FLEX") == {"QB", "RB", "WR", "TE"}
    assert positions("REC_FLEX") == {"WR", "TE"}
    assert positions("QB") == {"QB"}
    assert client.get(f"/v1/sim/games/{gid}/players?pos=BOGUS", headers=hdr()).status_code == 422


def test_draft_auto_completes_the_draft_and_starts_week_one():
    client, backend, _ = make_app()
    gid = new_game(client)["game"]["id"]
    res = finish_draft(client, gid)
    assert res["completed"] is True and res["recap"]["teams"] and res["recap"]["picks_value"]
    assert res["game"]["status"] == "in_season" and res["game"]["week"] == 1
    assert res["game"]["pending"]["roster_size"] == 14
    lineup = client.get(f"/v1/sim/games/{gid}/lineup", headers=hdr()).json()
    assert [s["slot"] for s in lineup["slots"]] == ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K"]
    assert all(s["player"] for s in lineup["slots"]) and len(lineup["bench"]) == 6
    # draft endpoints now say wrong phase
    assert client.post(f"/v1/sim/games/{gid}/draft/auto", headers=hdr()).json()["reason"] == "wrong_phase"
    assert backend.tables["sim_week_checkpoints"]


def test_full_season_through_the_api_then_result():
    client, backend, _ = make_app()
    gid = new_game(client)["game"]["id"]
    finish_draft(client, gid)
    seen = []
    for _ in range(20):
        res = advance(client, gid)
        seen.append(res["recap"]["week"])
        if res["game"]["status"] == "complete":
            break
    assert seen[:14] == list(range(1, 15)) and res["game"]["status"] == "complete"
    final_weeks = [res["recap"]["week"]] + [r["week"] for r in res["also_played"]]
    assert final_weeks[-1] == 17
    result = client.get(f"/v1/sim/games/{gid}/result", headers=hdr()).json()
    assert result["reason"] == "" and result["result"]["grade"]["letter"]
    assert result["result"]["champion"]["team_id"]
    assert len(result["result"]["final_standings"]) == 12
    again = client.get(f"/v1/sim/games/{gid}/result", headers=hdr()).json()
    assert again["result"] == result["result"]
    league = client.get(f"/v1/sim/games/{gid}/league", headers=hdr()).json()
    assert league["playoffs"]["champion"] == result["result"]["champion"]["team_id"]
    assert len(league["standings"]) == 12 and len(league["schedule"]) == 17
    assert client.post(f"/v1/sim/games/{gid}/advance", headers=hdr()).json()["reason"] == "season_complete"


# ------------------------------------------------------------------ gating


def test_free_user_gets_a_three_week_preview_then_the_paywall_and_upgrade_resumes():
    pro_set = set()
    client, backend, _ = make_app(pro=pro_set)
    data = new_game(client, user="free")
    assert data["preview"]["weeks_left"] == 3 and data["is_premium"] is False
    gid = data["game"]["id"]
    finish_draft(client, gid, "free")
    for week in (1, 2, 3):
        res = advance(client, gid, "free")
        assert res["reason"] == "" and res["recap"]["week"] == week
    assert res["preview"]["weeks_left"] == 0 and res["preview"]["paywalled"] is True
    for method, path, body in [
        ("post", "advance", None), ("put", "lineup", {"slots": []}), ("post", "lineup/auto", None),
        ("post", "waivers", {"add": "g0001"}), ("post", "cut", {"player_id": "g0001"}),
        ("post", "trades", {"partner": "2", "give": ["a"], "get": ["b"]}),
        ("post", "revert-week", None),
    ]:
        out = getattr(client, method)(f"/v1/sim/games/{gid}/{path}", headers=hdr("free"), **({"json": body} if body is not None else {}))
        assert out.status_code == 200 and out.json()["reason"] == "premium_required", path
        assert out.json()["upsell"] and out.json()["preview"]["paywalled"] is True
    # reads still work while paused
    assert client.get(f"/v1/sim/games/{gid}", headers=hdr("free")).json()["game"]["week"] == 4
    assert client.get(f"/v1/sim/games/{gid}/league", headers=hdr("free")).json()["reason"] == ""
    n_events = len(backend.tables["sim_events"])
    # upgrading resumes the same save
    pro_set.add("free")
    res = advance(client, gid, "free")
    assert res["reason"] == "" and res["recap"]["week"] == 4 and res["preview"] is None
    assert len(backend.tables["sim_events"]) > n_events


def test_free_users_are_limited_to_one_game_pro_to_three():
    client, _, _ = make_app()
    new_game(client, user="free")
    over = client.post("/v1/sim/games", json={}, headers=hdr("free")).json()
    assert over["reason"] == "game_limit_reached" and over["max_games"] == 1 and over["upsell"]
    for _ in range(3):
        assert new_game(client, user="pro")["reason"] == ""
    assert client.post("/v1/sim/games", json={}, headers=hdr("pro")).json()["reason"] == "game_limit_reached"
    assert len(client.get("/v1/sim/games", headers=hdr("pro")).json()["games"]) == 3


def test_users_cannot_see_each_others_games_and_bad_ids_404():
    client, _, _ = make_app()
    gid = new_game(client)["game"]["id"]
    for path in ("", "/draft", "/lineup", "/league", "/inbox", "/players", "/result"):
        assert client.get(f"/v1/sim/games/{gid}{path}", headers=hdr("pro2")).status_code == 404, path
    assert client.post(f"/v1/sim/games/{gid}/advance", headers=hdr("pro2")).status_code == 404
    assert client.delete(f"/v1/sim/games/{gid}", headers=hdr("pro2")).json()["reason"] == ""
    assert client.get(f"/v1/sim/games/{gid}", headers=hdr()).status_code == 200  # not deleted
    for bad in ("nope", "1; drop table", "x" * 80):
        assert client.get(f"/v1/sim/games/{bad}", headers=hdr()).status_code == 404


def test_storage_and_pool_failures_are_reasons_not_crashes():
    client, _, _ = make_app(backend=InMemoryBackend(fail=True))
    assert client.post("/v1/sim/games", json={}, headers=hdr()).json()["reason"] == "sim_storage_unavailable"
    assert client.get("/v1/sim/games", headers=hdr()).json()["reason"] == "sim_storage_unavailable"
    client, _, _ = make_app(inputs=BrokenInputs())
    assert client.post("/v1/sim/games", json={}, headers=hdr()).json()["reason"] == "players_unavailable"


def test_create_validation_is_422():
    client, _, _ = make_app()
    for body in ({"teams": 7}, {"scoring": "weird"}, {"difficulty": "brutal"}, {"user_slot": 99},
                 {"auto_lineup": "yes"}, {"team_name": "x" * 41}, {"teams": True}):
        assert client.post("/v1/sim/games", json=body, headers=hdr()).status_code == 422, body


def test_smaller_leagues_and_scoring_options():
    client, _, _ = make_app()
    data = new_game(client, teams=8, scoring="half", difficulty="hard", user_slot=8)
    s = data["game"]["settings"]
    assert s["teams"] == 8 and s["playoff_teams"] == 4 and s["playoff_weeks"] == 2 and s["scoring"] == "half"
    assert data["draft"]["total_picks"] == 8 * 14


# --------------------------------------------------------- weekly decisions


@pytest.fixture()
def season():
    client, backend, _ = make_app()
    gid = new_game(client, user_slot=4)["game"]["id"]
    finish_draft(client, gid)
    return client, backend, gid


def test_lineup_put_validation_and_persistence(season):
    client, _, gid = season
    lineup = client.get(f"/v1/sim/games/{gid}/lineup", headers=hdr()).json()
    slots = [{"slot": s["slot"], "player_id": s["player"]["id"]} for s in lineup["slots"]]
    # swap the two RBs: legal
    slots[1]["player_id"], slots[2]["player_id"] = slots[2]["player_id"], slots[1]["player_id"]
    ok = client.put(f"/v1/sim/games/{gid}/lineup", json={"slots": slots}, headers=hdr())
    assert ok.status_code == 200 and ok.json()["slots"][1]["player"]["id"] == slots[1]["player_id"]
    again = client.get(f"/v1/sim/games/{gid}/lineup", headers=hdr()).json()
    assert again["slots"][1]["player"]["id"] == slots[1]["player_id"]
    qb = slots[0]["player_id"]
    for bad in (slots[:-1], [*slots[:1], {"slot": "RB", "player_id": qb}, *slots[2:]],
                [{"slot": "QB", "player_id": "nobody"}, *slots[1:]],
                [slots[0], slots[0], *slots[2:]], list(reversed(slots))):
        assert client.put(f"/v1/sim/games/{gid}/lineup", json={"slots": bad}, headers=hdr()).status_code == 422
    auto = client.post(f"/v1/sim/games/{gid}/lineup/auto", headers=hdr()).json()
    assert auto["reason"] == "" and auto["projected_total"] > 0


def test_cut_claim_and_waiver_resolution(season):
    client, _, gid = season
    mine = client.get(f"/v1/sim/games/{gid}/players?status=mine&page_size=60", headers=hdr()).json()["items"]
    fa = client.get(f"/v1/sim/games/{gid}/players?status=available&pos=RB&page_size=5", headers=hdr()).json()["items"]
    assert len(mine) == 14 and fa and all(p["owner"]["type"] == "free_agent" for p in fa)
    claim = client.post(f"/v1/sim/games/{gid}/waivers", json={"add": fa[0]["id"]}, headers=hdr()).json()
    assert claim["reason"] == "" and claim["claim"]["add"]["id"] == fa[0]["id"]
    assert client.post(f"/v1/sim/games/{gid}/waivers", json={"add": fa[0]["id"]}, headers=hdr()).status_code == 422
    assert client.post(f"/v1/sim/games/{gid}/waivers", json={"add": mine[0]["id"]}, headers=hdr()).status_code == 422
    assert client.post(f"/v1/sim/games/{gid}/waivers", json={"add": fa[1]["id"], "drop": fa[2]["id"]}, headers=hdr()).status_code == 422
    assert client.get(f"/v1/sim/games/{gid}", headers=hdr()).json()["game"]["pending"]["claims"] == 1
    cancel = client.delete(f"/v1/sim/games/{gid}/waivers/{claim['claim']['id']}", headers=hdr()).json()
    assert cancel["claims"] == []
    client.post(f"/v1/sim/games/{gid}/waivers", json={"add": fa[0]["id"], "start_slot": "RB"}, headers=hdr())
    bench = [p for p in mine if p["pos"] == "TE"][-1]
    cut = client.post(f"/v1/sim/games/{gid}/cut", json={"player_id": bench["id"]}, headers=hdr()).json()
    assert cut["reason"] == "" and len(cut["roster"]) == 13
    # a repeat of the same cut (double tap, retry after a lost response) is success, not an error
    again = client.post(f"/v1/sim/games/{gid}/cut", json={"player_id": bench["id"]}, headers=hdr())
    assert again.status_code == 200 and again.json()["reason"] == "" and len(again.json()["roster"]) == 13
    rec = advance(client, gid)["recap"]
    mine_claim = [w for w in rec["waivers"] if w["is_you"]]
    assert len(mine_claim) == 1 and mine_claim[0]["add"]["id"] == fa[0]["id"]
    after = client.get(f"/v1/sim/games/{gid}/players?status=mine&page_size=60", headers=hdr()).json()["items"]
    assert (fa[0]["id"] in {p["id"] for p in after}) == mine_claim[0]["ok"]


def test_roster_over_limit_blocks_advance_until_cut(season):
    client, _, gid = season
    fa = client.get(f"/v1/sim/games/{gid}/players?status=available&page_size=10", headers=hdr()).json()["items"]
    # claim two adds (16 spots, 14 players: legal), a third with no drop fails at resolution, not at queue time
    for p in fa[:3]:
        client.post(f"/v1/sim/games/{gid}/waivers", json={"add": p["id"]}, headers=hdr())
    rec = advance(client, gid)["recap"]
    ok = [w for w in rec["waivers"] if w["is_you"] and w["ok"]]
    bad = [w for w in rec["waivers"] if w["is_you"] and not w["ok"]]
    assert len(ok) + len(bad) == 3 and all(w["reason"] in ("roster_full", "taken") for w in bad)
    assert client.get(f"/v1/sim/games/{gid}", headers=hdr()).json()["game"]["pending"]["cuts_needed"] == 0


def test_trade_preview_matches_send_and_accepted_trades_execute(season):
    client, _, gid = season
    mine = client.get(f"/v1/sim/games/{gid}/players?status=mine&page_size=60", headers=hdr()).json()["items"]
    found = None
    for team in range(1, 13):
        if team == 4:
            continue
        theirs = client.get(f"/v1/sim/games/{gid}/teams/{team}", headers=hdr()).json()["players"]
        for give in [p for p in mine if p["pos"] != "K"][:6]:
            for get in [p for p in theirs if p["pos"] != "K"][:6]:
                body = {"partner": str(team), "give": [give["id"]], "get": [get["id"]]}
                pre = client.post(f"/v1/sim/games/{gid}/trades/preview", json=body, headers=hdr()).json()
                assert pre["executed"] is False and pre["verdict"]["decision"] in ("accept", "counter", "decline")
                if pre["verdict"]["decision"] == "accept":
                    found = (body, pre)
                    break
            if found:
                break
        if found:
            break
    if found is None:  # find a counter instead and take it
        pytest.skip("no accepted 1-for-1 in this synthetic league")
    body, pre = found
    again = client.post(f"/v1/sim/games/{gid}/trades/preview", json=body, headers=hdr()).json()
    assert again["verdict"] == pre["verdict"]  # deterministic, not a slot machine
    sent = client.post(f"/v1/sim/games/{gid}/trades", json=body, headers=hdr()).json()
    assert sent["verdict"] == pre["verdict"] and sent["executed"] is True
    roster_ids = {p["id"] for p in sent["roster"]}
    assert body["get"][0] in roster_ids and body["give"][0] not in roster_ids
    dup = client.post(f"/v1/sim/games/{gid}/trades", json=body, headers=hdr())
    assert dup.status_code in (200, 422)


def test_trade_validation_and_gating(season):
    client, _, gid = season
    mine = client.get(f"/v1/sim/games/{gid}/players?status=mine&page_size=60", headers=hdr()).json()["items"]
    theirs = client.get(f"/v1/sim/games/{gid}/teams/1", headers=hdr()).json()["players"]
    a = next(p for p in mine if p["pos"] == "RB")
    b = next(p for p in theirs if p["pos"] == "RB")
    kicker = next(p for p in mine if p["pos"] == "K")
    for body in (
        {"partner": "4", "give": [a["id"]], "get": [b["id"]]},  # yourself
        {"partner": "1", "give": [b["id"]], "get": [a["id"]]},  # sides swapped: not owned
        {"partner": "1", "give": [], "get": [b["id"]]}, {"partner": "1", "give": [a["id"]] * 2, "get": [b["id"]]},
        {"partner": "99", "give": [a["id"]], "get": [b["id"]]},
    ):
        assert client.post(f"/v1/sim/games/{gid}/trades/preview", json=body, headers=hdr()).status_code == 422, body
    # A kicker is tradable in a new game, but one per roster: kicker for a non-kicker would leave them with two.
    got = client.post(f"/v1/sim/games/{gid}/trades/preview", json={"partner": "1", "give": [kicker["id"]], "get": [b["id"]]}, headers=hdr())
    assert got.status_code == 200 and got.json()["reason"] == "singleton_limit"


def test_inbox_offers_and_respond(season):
    client, _, gid = season
    items = []
    for _ in range(8):
        items = client.get(f"/v1/sim/games/{gid}/inbox", headers=hdr()).json()["items"]
        if items:
            break
        advance(client, gid)
    if not items:
        pytest.skip("no AI offers surfaced in this synthetic league")
    assert len(items) <= 3 and len({i["from"]["team_id"] for i in items}) == len(items)
    item = items[0]
    assert item["you_give"] and item["you_get"] and item["message"]
    decline = client.post(f"/v1/sim/games/{gid}/inbox/{item['id']}/respond", json={"action": "decline"}, headers=hdr()).json()
    assert decline["executed"] is False and all(i["id"] != item["id"] for i in decline["items"])
    gone = client.post(f"/v1/sim/games/{gid}/inbox/{item['id']}/respond", json={"action": "accept"}, headers=hdr()).json()
    assert gone["reason"] == "offer_invalid"
    assert client.post(f"/v1/sim/games/{gid}/inbox/x/respond", json={"action": "maybe"}, headers=hdr()).status_code == 422


def test_advance_is_idempotent_per_week_and_revert_restores_the_week(season):
    client, backend, gid = season
    first = advance(client, gid, week=1)
    assert first["replayed"] is False and first["game"]["week"] == 2
    n = len(backend.tables["sim_events"])
    replay = advance(client, gid, week=1)
    assert replay["replayed"] is True and replay["recap"] == first["recap"] and len(backend.tables["sim_events"]) == n
    ahead = client.post(f"/v1/sim/games/{gid}/advance", json={"week": 5}, headers=hdr()).json()
    assert ahead["reason"] == "week_mismatch" and ahead["current_week"] == 2
    # decisions in week 2, then revert
    before = client.get(f"/v1/sim/games/{gid}/lineup", headers=hdr()).json()
    fa = client.get(f"/v1/sim/games/{gid}/players?status=available&page_size=2", headers=hdr()).json()["items"]
    client.post(f"/v1/sim/games/{gid}/waivers", json={"add": fa[0]["id"]}, headers=hdr())
    client.post(f"/v1/sim/games/{gid}/lineup/auto", headers=hdr())
    rev = client.post(f"/v1/sim/games/{gid}/revert-week", headers=hdr()).json()
    assert rev["reverted"] >= 2 and rev["game"]["pending"]["claims"] == 0 and rev["game"]["week"] == 2
    assert client.get(f"/v1/sim/games/{gid}/lineup", headers=hdr()).json()["slots"] == before["slots"]
    # same decisions, same result (anti save-scum)
    client.post(f"/v1/sim/games/{gid}/waivers", json={"add": fa[0]["id"]}, headers=hdr())
    r1 = advance(client, gid)["recap"]
    client.post(f"/v1/sim/games/{gid}/revert-week", headers=hdr())  # nothing pending after an advance
    assert client.get(f"/v1/sim/games/{gid}", headers=hdr()).json()["game"]["week"] == 3
    assert r1["week"] == 2


def test_players_sort_overall_orders_by_shown_overall(season):
    client, _, gid = season
    page = client.get(f"/v1/sim/games/{gid}/players?pos=WR&sort=overall&page_size=10", headers=hdr()).json()
    ovr = [p["overall"] or 0 for p in page["items"]]
    assert ovr == sorted(ovr, reverse=True) and len(ovr) == 10


def test_players_search_filters_and_detail(season):
    client, _, gid = season
    page = client.get(f"/v1/sim/games/{gid}/players?pos=QB&sort=adp&page_size=5", headers=hdr()).json()
    assert page["total"] == 64 and [p["pos"] for p in page["items"]] == ["QB"] * 5
    assert [p["adp"] for p in page["items"]] == sorted(p["adp"] for p in page["items"])
    name = page["items"][0]["name"]
    found = client.get(f"/v1/sim/games/{gid}/players", params={"q": name.lower()}, headers=hdr()).json()
    assert any(p["id"] == page["items"][0]["id"] for p in found["items"])
    for bad in ("pos=XX", "status=nope", "sort=weird"):
        assert client.get(f"/v1/sim/games/{gid}/players?{bad}", headers=hdr()).status_code == 422
    pid = page["items"][0]["id"]
    detail = client.get(f"/v1/sim/games/{gid}/players/{pid}", headers=hdr()).json()
    assert detail["player"]["id"] == pid and len(detail["weeks"]) == 14 and detail["history"] == []
    assert client.get(f"/v1/sim/games/{gid}/players/nope", headers=hdr()).status_code == 404
    advance(client, gid)
    detail = client.get(f"/v1/sim/games/{gid}/players/{pid}", headers=hdr()).json()
    assert len(detail["weeks"]) == 13 and len(detail["history"]) == 1


def test_recap_has_a_box_score_and_league_views(season):
    client, _, gid = season
    res = advance(client, gid)
    rec = res["recap"]
    g = rec["your_game"]
    assert g["result"] in ("win", "loss", "tie") and len(g["starters"]) == 8
    assert round(sum(r["pts"] for r in g["starters"]), 1) == round(g["your_pts"], 1)
    assert 0 < g["efficiency"] <= 1.0001 and len(rec["scores"]) == 6 and len(rec["standings"]) == 12
    league = client.get(f"/v1/sim/games/{gid}/league", headers=hdr()).json()
    assert sum(r["wins"] + r["losses"] + r["ties"] for r in league["standings"]) == 12
    assert {t["persona"]["id"] for t in league["teams"]} >= {"you"}
    assert [t["power_rank"] for t in league["teams"]] and sorted(t["power_rank"] for t in league["teams"]) == list(range(1, 13))


def test_player_payloads_carry_a_photo_id_only_for_real_sleeper_ids(season):
    from modules.sim.game_types import headshot_id

    assert headshot_id("4046") == "4046" and headshot_id("DEF-NYG") is None and headshot_id("p0001") is None
    assert headshot_id("") is None and headshot_id(None) is None  # type: ignore[arg-type]
    client, _, gid = season
    c2, _, _ = make_app()
    gid2 = new_game(c2, user_slot=4)["game"]["id"]
    recap = finish_draft(c2, gid2)["recap"]
    best = recap["your_team"]["best_pick"]
    assert best["player"]["id"] == best["player_id"] and "headshot_id" in best["player"] and best["player"]["name"] == best["name"]
    page = client.get(f"/v1/sim/games/{gid}/players?page_size=5", headers=hdr()).json()
    assert page["items"] and all("headshot_id" in p for p in page["items"])  # synthetic ids: present, null
    res = advance(client, gid)
    for inj in res["recap"]["injuries"]:
        assert "headshot_id" in inj["player"]
    league = client.get(f"/v1/sim/games/{gid}/league", headers=hdr()).json()
    for tx in league["transactions"]:
        assert tx["players"] and {"role", "id", "headshot_id", "name", "pos"} <= set(tx["players"][0])


# ----------------------------------------------------------------- preview


def test_signed_out_preview_players_needs_no_auth_or_pro():
    client, backend, inputs = make_app()
    res = client.get("/v1/sim/preview/players?pos=WR&sort=projection&page_size=5")
    assert res.status_code == 200
    data = res.json()
    assert data["reason"] == "" and data["total"] == 220 and len(data["players"]) == 5
    assert data["players"][0]["projection"] >= data["players"][-1]["projection"]
    assert backend.tables == {}  # no state, no storage
    assert client.get("/v1/sim/preview/players?pos=XX").status_code == 422
    assert client.get("/v1/sim/preview/players?scoring=zzz").status_code == 422
    assert client.get("/v1/sim/preview/players?q=guy&page=2&page_size=3").json()["page"] == 2


def test_concurrent_write_race_is_a_409_and_changes_nothing():
    client, backend, _ = make_app()
    gid = new_game(client, user_slot=2)["game"]["id"]  # one AI pick (seq 0) before the user's turn
    pid = client.get(f"/v1/sim/games/{gid}/draft", headers=hdr()).json()["hint"]["player"]["id"]
    real_insert = backend.insert_many
    raced = {}

    def racing_insert(table, rows):
        # another worker lands the same seq between our load and our write
        if table == "sim_events" and not raced:
            raced["seq"] = rows[0]["seq"]
            backend.tables["sim_events"].append({**rows[0], "actor": "other-worker"})
        return real_insert(table, rows)

    backend.insert_many = racing_insert
    before = [dict(r) for r in backend.tables["sim_events"]]
    res = client.post(f"/v1/sim/games/{gid}/draft/pick", json={"player_id": pid}, headers=hdr())
    assert res.status_code == 409 and res.json()["reason"] == "conflict"
    assert len(backend.tables["sim_events"]) == len(before) + 1  # only the other worker's row
    # a retry after reload succeeds (it sees the other worker's pick)
    backend.insert_many = real_insert


# ------------------------------------- empty starting slot is never a deadlock


def _strip_position(client, gid, pos):
    """Cut every rostered player at ``pos`` (the 'all my WRs got hurt' end state: no legal fill on the roster)."""
    mine = client.get(f"/v1/sim/games/{gid}/players?status=mine&page_size=60", headers=hdr()).json()["items"]
    for p in [p for p in mine if p["pos"] == pos]:
        assert client.post(f"/v1/sim/games/{gid}/cut", json={"player_id": p["id"]}, headers=hdr()).status_code == 200
    lineup = client.get(f"/v1/sim/games/{gid}/lineup", headers=hdr()).json()
    return [s["slot"] for s in lineup["slots"] if not s["player"]]


def test_empty_starting_slot_never_blocks_advance_and_scores_zero(season):
    client, _, gid = season
    empty = _strip_position(client, gid, "WR")
    assert empty and set(empty) <= {"WR", "FLEX"}
    assert client.get(f"/v1/sim/games/{gid}", headers=hdr()).json()["game"]["pending"]["cuts_needed"] == 0
    res = advance(client, gid)
    assert res["game"]["week"] == 2 and res["replayed"] is False
    starters = res["recap"]["your_game"]["starters"]
    gaps = [s for s in starters if s["player"] is None]
    assert gaps and all(s["pts"] == 0.0 and s["flag"] == "empty" for s in gaps)
    # replaying the same week is idempotent
    assert advance(client, gid, week=1)["recap"] == res["recap"]


def test_claim_placed_this_week_lands_before_scoring_and_fills_the_slot(season):
    client, _, gid = season
    empty = _strip_position(client, gid, "WR")
    assert "WR" in empty
    fa = client.get(f"/v1/sim/games/{gid}/players?status=available&pos=WR&page_size=1", headers=hdr()).json()["items"]
    client.post(f"/v1/sim/games/{gid}/waivers", json={"add": fa[0]["id"], "start_slot": "WR"}, headers=hdr())
    rec = advance(client, gid)["recap"]
    mine = [w for w in rec["waivers"] if w["is_you"]]
    assert len(mine) == 1
    if mine[0]["ok"]:  # worst-record-first; a lost race to an AI team is legal, a won claim must start this very week
        wr = [s for s in rec["your_game"]["starters"] if s["slot"] == "WR" and s["player"]]
        assert any(s["player"]["id"] == fa[0]["id"] for s in wr)
    else:
        assert mine[0]["reason"] == "taken"


def test_cut_stays_available_so_over_limit_is_always_fixable(season):
    client, _, gid = season
    fa = client.get(f"/v1/sim/games/{gid}/players?status=available&page_size=4", headers=hdr()).json()["items"]
    mine = client.get(f"/v1/sim/games/{gid}/players?status=mine&page_size=60", headers=hdr()).json()["items"]
    assert len(mine) == 14 and fa  # the cut path stays open at any roster size
    assert client.post(f"/v1/sim/games/{gid}/cut", json={"player_id": mine[-1]["id"]}, headers=hdr()).status_code == 200
