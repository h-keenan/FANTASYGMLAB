"""Letter grades: coarse, noisy, deterministic, and the raw rating never reaches a client."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from modules.sim import game_grades as gg
from tests.test_sim_game_api import advance, finish_draft, hdr, make_app, new_game

BANNED_KEYS = {"value", "overall", "value_rank", "pos_value_rank", "adp_edge", "market", "user_net_before", "user_net_after", "total_value", "overall_rating", "overall_rank"}


def _snap(n=40, seed=5):
    players, pids = {}, []
    for i in range(n):
        pid = f"WR{i}"
        players[pid] = SimpleNamespace(pid=pid, pos="WR", value=float(i), mean=2.0 + i * 0.4, sd=3.0 + (i % 5), market=float(i * 2), age=22.0 + i % 12, extra={})
        pids.append(pid)
    return SimpleNamespace(players=players, pids=tuple(pids), seed=seed)


def test_bands_cover_the_scale_in_order():
    assert len(gg.LETTERS) == len(gg.CUTS) == 12
    assert gg.letter_of(1.0) == "A+" and gg.letter_of(0.0) == "F" and gg.letter_of(0.5) == "C"
    assert [gg.band_of(c) for c in gg.CUTS] == list(range(12))


def test_grade_is_deterministic_per_seed_player_season_and_varies_across_them():
    snap = _snap()
    a = [gg.grade_of(snap, p, 1)["letter"] for p in snap.pids]
    assert a == [gg.grade_of(snap, p, 1)["letter"] for p in snap.pids]
    other_season = [gg.grade_of(snap, p, 2)["letter"] for p in snap.pids]
    snap2 = _snap(seed=6)
    other_seed = [gg.grade_of(snap2, p, 1)["letter"] for p in snap2.pids]
    assert a != other_season and a != other_seed


def test_grade_is_a_noisy_band_not_a_rank():
    snap = _snap(200)
    idx = [gg.grade_of(snap, f"WR{i}", 1)["index"] for i in range(200)]
    assert idx[199] >= 10 and idx[0] <= 2  # informative at the extremes
    assert any(idx[i] > idx[i + 5] for i in range(0, 190))  # but not monotone in the hidden value


def test_thin_pool_gets_no_grade_and_picks_have_none():
    snap = SimpleNamespace(players={"a": SimpleNamespace(pid="a", pos="K", value=1.0, mean=1.0, sd=1.0, market=1.0, age=25.0, extra={})}, pids=("a",), seed=1)
    assert gg.grade_of(snap, "a", 1) is None
    assert gg.grade_fields(snap, "a", 1)["grade"] is None


def test_rookies_are_less_certain():
    snap = _snap(60)
    snap.players["WR59"].extra = {"is_rookie": 1.0}
    g = gg.grade_of(snap, "WR59", 1)
    assert g["uncertain"] is True
    vet = gg.grade_of(snap, "WR58", 1)
    assert not vet.get("uncertain")


def test_attributes_are_independent_of_the_overall():
    snap = _snap(80)
    attrs = gg.attributes_of(snap, "WR70", 1)
    assert [a["key"] for a in attrs][:2] == ["volume", "production"] or len(attrs) >= 3
    assert all(a["grade"] in gg.LETTERS for a in attrs)
    # position-specific sets
    assert [k for k, _ in gg.ATTRIBUTES["RB"]][0] == "volume" and len(gg.ATTRIBUTES["QB"]) == 6


def _scan(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            assert k not in BANNED_KEYS, f"{path}.{k} leaks the model rating"
            _scan(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _scan(v, f"{path}[{i}]")


@pytest.fixture()
def season():
    client, backend, _ = make_app()
    gid = new_game(client, user_slot=4)["game"]["id"]
    finish_draft(client, gid)
    return client, gid


def test_no_sim_api_response_contains_the_raw_rating(season):
    client, gid = season
    base = f"/v1/sim/games/{gid}"
    paths = [base, f"{base}/draft", f"{base}/players?page_size=60", f"{base}/players?sort=overall&page_size=60", f"{base}/players?sort=value&page_size=60",
             f"{base}/home", f"{base}/lineup", f"{base}/inbox", f"{base}/block", f"{base}/league", f"{base}/league/rosters", f"{base}/picks", f"{base}/dynasty", f"{base}/offseason",
             f"{base}/teams/1"]
    first = client.get(f"{base}/players?page_size=5", headers=hdr()).json()["items"]
    paths += [f"{base}/players/{first[0]['id']}", f"{base}/players/{first[0]['id']}/history"]
    seen = 0
    for path in paths:
        res = client.get(path, headers=hdr())
        if res.status_code != 200:
            continue
        _scan(res.json(), path)
        seen += 1
    assert seen >= 8
    advance(client, gid)
    _scan(client.get(f"{base}/league", headers=hdr()).json())
    detail = client.get(f"{base}/players/{first[0]['id']}", headers=hdr()).json()["player"]
    assert detail["grade"] in gg.LETTERS and detail["attributes"]
    # a trade verdict carries no trade-value numbers either
    others = client.get(f"{base}/league/rosters", headers=hdr()).json()["teams"]
    them = next(t for t in others if not t["is_you"])
    mine = next(t for t in others if t["is_you"])
    pv = client.post(f"{base}/trades/preview", json={"partner": them["team_id"], "give": [mine["players"][0]["id"]], "get": [them["players"][0]["id"]]}, headers=hdr())
    if pv.status_code == 200:
        _scan(pv.json())


def test_preview_players_carry_no_value(season):
    client, _ = season
    res = client.get("/v1/sim/preview/players?page_size=10", headers=hdr()).json()
    assert res["players"]
    _scan(res)
    assert client.get("/v1/sim/preview/players?sort=value", headers=hdr()).status_code == 200


def test_old_saves_replay_identically_with_grades_in_the_view(season):
    from tests.test_sim_game_engine import drafted

    a = drafted(7, user_slot=2)
    b = drafted(7, user_slot=2)
    assert a[1].to_dict() == b[1].to_dict()


def test_draft_room_and_grades_are_stable_and_leak_free():
    client, _, _ = make_app()
    gid = new_game(client, user_slot=4)["game"]["id"]
    base = f"/v1/sim/games/{gid}"
    board = client.get(f"{base}/draft", headers=hdr()).json()
    _scan(board)
    page = client.get(f"{base}/players?page_size=60", headers=hdr()).json()
    _scan(page)
    again = client.get(f"{base}/players?page_size=60", headers=hdr()).json()
    assert [p["grade"] for p in page["items"]] == [p["grade"] for p in again["items"]]  # same save, same season: same grade
    assert any(p["grade"] for p in page["items"]) and all(p["grade"] in (None, *gg.LETTERS) for p in page["items"])
    by_grade = client.get(f"{base}/players?sort=overall&page_size=60", headers=hdr()).json()["items"]
    idx = [gg.LETTERS.index(p["grade"]) if p["grade"] else -1 for p in by_grade]
    assert idx == sorted(idx, reverse=True)


def test_calibration_harness_runs_every_draft_bot():
    from modules.sim.calibration import grade_report as gr
    from modules.sim import game_scoring

    pool, byes = gr._pool()
    model_id = game_scoring.default_model().model_id
    for name, bot in gr.BOTS.items():
        res = gr.play(pool, byes, 1, bot, model_id)
        assert res["state"].status == "complete" and 0 <= res["wins"] <= 14, name
    rows = gr.outcomes(res)
    assert rows and all(0 <= r["grade"] <= 11 for r in rows)
