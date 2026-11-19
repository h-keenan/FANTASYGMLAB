"""Season Wrapped deck: shape, Pro locks enforced server-side, partial decks, nothing invented."""

from __future__ import annotations

import json

import pytest

from modules.sim.game_wrapped import PRO_CARDS, build_wrapped
from tests.test_sim_wrapped_data import _play


@pytest.fixture(scope="module")
def played():
    return _play(1, 5)


def _fake_moves(snap, state):
    user = snap.user_team.tid
    mine = [p["pid"] for p in state.picks if p["team"] == user]
    other_t = next(t for t in snap.tids if t != user)
    theirs = [p["pid"] for p in state.picks if p["team"] == other_t]
    trade = {"type": "trade", "actor": "user", "week": 3, "payload": {"team_a": user, "team_b": other_t, "give": [mine[0]], "get": [theirs[0]]}}
    waiver = {"type": "waiver_result", "actor": "user", "week": 4, "payload": {"team": user, "ok": True, "add": theirs[1], "drop": mine[1]}}
    return [trade, waiver]


def test_full_deck_for_pro(played):
    snap, state, em = played
    deck = build_wrapped(snap, state, _fake_moves(snap, state), None, is_pro=True)
    json.dumps(deck, allow_nan=False)
    ids = [c["id"] for c in deck["cards"]]
    assert ids[0] == "intro" and ids[-1] == "persona"
    assert {"mvp", "weeks", "close", "luck", "journey", "grade", "trades", "waiver"} <= set(ids)
    assert not any(c["locked"] for c in deck["cards"])
    assert deck["partial"] is False


def test_free_viewer_gets_no_data_for_pro_cards(played):
    snap, state, em = played
    deck = build_wrapped(snap, state, _fake_moves(snap, state), None, is_pro=False)
    for c in deck["cards"]:
        if c["id"] in PRO_CARDS:
            assert c["pro"] and c["locked"] and c["data"] is None
        else:
            assert not c["locked"] and c["data"] is not None
    assert "persona" in [c["id"] for c in deck["cards"]]  # the personality card is free


def test_no_moves_means_no_trade_or_waiver_cards(played):
    snap, state, em = played
    ids = [c["id"] for c in build_wrapped(snap, state, [], None, is_pro=True)["cards"]]
    assert "trades" not in ids and "waiver" not in ids and "persona" in ids


def test_so_far_deck_is_partial_and_names_itself(played):
    snap, state, em = played
    import copy

    mid = copy.deepcopy(state)
    mid.status = "in_season"
    for k in [k for k in mid.recaps if int(k) > 6]:
        del mid.recaps[k]
    mid.history = [w for w in mid.history if w["week"] <= 6]
    deck = build_wrapped(snap, mid, [], None, is_pro=True)
    assert deck["partial"] is True
    grade = next(c for c in deck["cards"] if c["id"] == "grade")
    assert grade["eyebrow"] == "GRADE SO FAR"
    assert next(c for c in deck["cards"] if c["id"] == "intro")["data"]["weeks"] == 6


def test_too_early_has_no_cards(played):
    snap, state, em = played
    import copy

    early = copy.deepcopy(state)
    early.recaps = {}
    assert build_wrapped(snap, early, [], None, is_pro=True)["cards"] == []


def test_wrapped_endpoint_phases_and_pro_gate():
    from tests.test_sim_game_api import advance, finish_draft, hdr, make_app, new_game

    client, _, _ = make_app(pro=("pro",))
    gid = new_game(client, "pro", teams=8, user_slot=2)["game"]["id"]
    assert client.get(f"/v1/sim/games/{gid}/wrapped", headers=hdr("pro")).json().get("reason") == "wrong_phase"
    finish_draft(client, gid)
    for _ in range(4):
        advance(client, gid)
    body = client.get(f"/v1/sim/games/{gid}/wrapped", headers=hdr("pro")).json()
    assert body["wrapped"]["partial"] is True and body["wrapped"]["cards"][0]["id"] == "intro"


def _strip_player_objects(node):
    """Drop the player briefs (their full ``name`` is data the clients shorten); what is left is body copy."""
    if isinstance(node, dict):
        if "headshot_id" in node:
            return None
        return {k: _strip_player_objects(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_strip_player_objects(v) for v in node]
    return node


def test_body_copy_never_carries_a_full_player_name(played):
    from modules.sim.game_wrapped import short_name

    snap, state, em = played
    deck = build_wrapped(snap, state, _fake_moves(snap, state), None, is_pro=True)
    persona = next(c for c in deck["cards"] if c["id"] == "persona")
    assert any("alone was worth" in line for line in persona["data"]["lines"])
    copy = json.dumps(_strip_player_objects(deck["cards"]))
    for p in snap.players.values():
        if " " in p.name:
            assert p.name not in copy, p.name
    assert short_name("Owen Tillery") == "O. Tillery"
    assert short_name("Marvin Harrison Jr.") == "M. Harrison Jr."
