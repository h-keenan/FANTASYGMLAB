"""The Season in Review payload: JSON-safe, deterministic, read-only, and sane."""

from __future__ import annotations

import copy
import json

from modules.sim.game_result import build_result
from modules.sim.game_review import build_review
from tests.test_sim_game_engine import season

AWARD_KINDS = {"trade", "waiver", "draft", "boom", "bust", "injury"}


def _review(seed=7, **kw):
    snap, state, em, _ = season(seed, user_slot=3, **kw)
    result = build_result(snap, seed, em.events, state, explain=False)
    return snap, state, em, result


def test_review_is_json_safe_and_shaped():
    snap, state, em, result = _review()
    rv = result["review"]
    json.dumps(rv, allow_nan=False)
    assert {"awards", "season_stats", "injuries", "leaders", "games", "rank_journey", "champion_path"} <= set(rv)
    for a in rv["awards"]:
        assert a["kind"] in AWARD_KINDS and a["tone"] in ("good", "bad")
        assert all({"id", "name", "pos"} <= set(p) for p in a["players"])
    assert rv["rank_journey"] and all(1 <= r["rank"] <= rv["team_count"] for r in rv["rank_journey"])
    assert rv["champion_path"]["rounds"]
    assert len(rv["games"]["closest_league"]) == 3
    margins = [g["margin"] for g in rv["games"]["closest_league"]]
    assert margins == sorted(margins)
    for grp in rv["leaders"]["league"]:
        pts = [r["pts"] for r in grp["rows"]]
        assert pts == sorted(pts, reverse=True)


def test_review_is_deterministic_and_does_not_mutate():
    snap, state, em, _ = season(9, user_slot=5)
    before = state.digest()
    events = copy.deepcopy(em.events)
    draft = build_result(snap, 9, em.events, state, explain=False)["draft"]
    a = build_review(snap, em.events, state, {"your_team": draft})
    b = build_review(snap, em.events, state, {"your_team": draft})
    assert a == b and state.digest() == before and events == em.events


def test_review_never_breaks_the_grade():
    snap, state, em, _ = season(4, user_slot=2)
    assert build_review(snap, em.events, state, {}) is not None
    assert build_review(snap, [{"bad": 1}], state, {}) == {}


def test_trade_award_matches_points_swing():
    for seed in range(1, 8):
        snap, state, em, result = _review(seed)
        trades = [a for a in result["review"]["awards"] if a["kind"] == "trade"]
        if trades:
            assert trades[0]["key"] == "best_trade" and trades[0]["delta"]["unit"] == "pts"
            return


def test_route_includes_review_and_backfills_results_stored_without_it():
    from tests.test_sim_game_result_shapes import _complete_game
    from tests.test_sim_game_api import hdr, make_app

    client, backend, _ = make_app()
    gid = _complete_game(client)
    first = client.get(f"/v1/sim/games/{gid}/result", headers=hdr()).json()["result"]
    assert first["review"]["awards"] and first["review"]["rank_journey"]
    old = {k: v for k, v in first.items() if k != "review"}
    backend.tables["sim_games"][0]["result"] = old
    again = client.get(f"/v1/sim/games/{gid}/result", headers=hdr()).json()["result"]
    assert again["review"]["rank_journey"] == first["review"]["rank_journey"]
    assert "review" in backend.tables["sim_games"][0]["result"]
