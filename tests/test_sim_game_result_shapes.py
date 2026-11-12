"""The stored final result must be JSON-safe, fully shaped, and survive every outcome type.

Regression: the web/mobile final screen rendered ``grade.summary`` (an object:
record/finish/points_rank/...) as a text child, which crashed React/RN and showed
the generic "something went wrong" page for every completed game. The backend
contract pinned here is what the clients' ``normalizeSimResult`` is written against.
"""

from __future__ import annotations

import copy
import json

import pytest

from modules.sim import game_api
from modules.sim.analysis import PLAYOFF_VALUE
from modules.sim.game_result import build_result
from modules.sim.store import SimStoreError
from tests.test_sim_game_api import advance, finish_draft, hdr, make_app, new_game
from tests.test_sim_game_engine import season

KNOWN_OUTCOMES = set(PLAYOFF_VALUE)
SUMMARY_KEYS = {"record", "finish", "points_rank", "playoff_result", "lineup_efficiency", "luck_wins", "draft_grade"}


def check_shape(result, teams):
    json.dumps(result, allow_nan=False)  # no NaN/inf, no tuples-as-keys, no datetimes
    grade = result["grade"]
    assert isinstance(grade["letter"], str) and grade["letter"]
    assert isinstance(grade["summary"], dict) and set(grade["summary"]) == SUMMARY_KEYS
    assert isinstance(grade["components"], list) and len(grade["components"]) == 5
    assert len(result["final_standings"]) == teams
    assert all(r["playoff_result"] in KNOWN_OUTCOMES for r in result["final_standings"])
    assert sum(1 for r in result["final_standings"] if r["is_you"]) == 1
    assert result["user"]["playoff_result"] in KNOWN_OUTCOMES
    assert result["champion"] is None or {"team_id", "name"} <= set(result["champion"])
    assert isinstance(result["decisions_that_mattered"], list)
    assert {"grade", "rank", "best_pick", "worst_pick"} <= set(result["draft"])
    assert all({"week", "opponent", "you", "them", "result"} <= set(w) for w in result["weeks"])


CONFIGS = [
    {"teams": 8}, {"teams": 10, "superflex": True}, {"teams": 12, "include_def": True, "include_k": False},
    {"teams": 14, "scoring": "half"}, {"teams": 12, "include_k": False},
]


@pytest.mark.parametrize("opts", CONFIGS, ids=lambda o: "-".join(f"{k}={v}" for k, v in o.items()))
def test_result_is_json_safe_and_fully_shaped(opts):
    outcomes = set()
    for seed in (1, 2, 3):
        teams = opts["teams"]
        snap, state, em, _ = season(seed, user_slot=(seed * 3) % teams + 1, **opts)
        result = build_result(snap, seed, em.events, state, explain=False)
        check_shape(result, teams)
        outcomes.add(result["user"]["playoff_result"])
        assert result["user"]["made_playoffs"] == (result["user"]["playoff_result"] != "missed")
    assert outcomes


def test_every_outcome_type_grades_and_serializes():
    """Force each playoff label onto the user (champion .. missed) and re-grade."""

    snap, state, em, _ = season(5, user_slot=4)
    user = snap.user_team.tid
    for label in sorted(KNOWN_OUTCOMES):
        alt = copy.deepcopy(state)
        alt.playoff["results"][user] = label
        if label == "champion":
            alt.champion = user
        result = build_result(snap, 5, em.events, alt, explain=False)
        assert result["user"]["playoff_result"] == label
        check_shape(result, 12)


def test_no_playoff_bracket_and_no_champion_edge_cases():
    snap, state, em, _ = season(6, user_slot=2)
    alt = copy.deepcopy(state)
    alt.playoff = None
    alt.champion = None
    result = build_result(snap, 6, em.events, alt, explain=False)
    assert result["champion"] is None and result["user"]["playoff_result"] == "missed"
    json.dumps(result, allow_nan=False)


def test_real_outcome_variety_across_seeds_includes_champion_or_deep_run_and_missed():
    seen = set()
    for seed in range(1, 9):
        snap, state, em, _ = season(seed, user_slot=(seed % 12) + 1)
        seen.add(build_result(snap, seed, em.events, state, explain=False)["user"]["playoff_result"])
    assert "missed" in seen or len(seen) >= 2


def _complete_game(client):
    gid = new_game(client)["game"]["id"]
    finish_draft(client, gid)
    for _ in range(20):
        if advance(client, gid)["game"]["status"] == "complete":
            return gid
    raise AssertionError("game did not complete")


def test_route_returns_the_shape_the_clients_render_and_stores_the_letter():
    client, backend, _ = make_app()
    gid = _complete_game(client)
    body = client.get(f"/v1/sim/games/{gid}/result", headers=hdr()).json()
    check_shape(body["result"], 12)
    assert body["game"]["grade_letter"] == body["result"]["grade"]["letter"]
    stored = backend.tables["sim_games"][0]
    assert stored["grade_letter"] == body["result"]["grade"]["letter"] and json.dumps(stored["result"], allow_nan=False)


def test_route_reports_a_specific_reason_when_grading_fails(monkeypatch):
    client, backend, _ = make_app()
    gid = _complete_game(client)

    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(game_api, "build_result", boom)
    res = client.get(f"/v1/sim/games/{gid}/result", headers=hdr())
    assert res.status_code == 200
    body = res.json()
    assert body["reason"] == "result_build_failed" and "result" not in body
    assert "grade" in body["message"] and "kaboom" not in res.text
    assert not backend.tables["sim_games"][0].get("result")


def test_route_serves_the_grade_even_if_saving_it_fails(monkeypatch):
    client, backend, _ = make_app()
    gid = _complete_game(client)

    def nope(self, *a, **k):
        raise SimStoreError("down")

    monkeypatch.setattr(game_api.GameStore, "save_result", nope)
    body = client.get(f"/v1/sim/games/{gid}/result", headers=hdr()).json()
    assert body["reason"] == "" and body["result"]["grade"]["letter"]


def test_route_rejects_a_non_finite_result_before_storage(monkeypatch):
    client, _, _ = make_app()
    gid = _complete_game(client)
    real = game_api.build_result

    def nan_result(*a, **k):
        r = real(*a, **k)
        r["grade"]["score"] = float("nan")
        return r

    monkeypatch.setattr(game_api, "build_result", nan_result)
    assert client.get(f"/v1/sim/games/{gid}/result", headers=hdr()).json()["reason"] == "result_build_failed"
