"""The Draft & Watch report card and its endpoint."""

from __future__ import annotations

import json

from modules.sim.game_watch_report import build_watch_report
from tests.test_sim_watch import play


def _copy(node):
    """Body copy only: player briefs (their full name is data the clients shorten) are skipped."""
    if isinstance(node, dict):
        if "headshot_id" in node:
            return
        for v in node.values():
            yield from _copy(v)
    elif isinstance(node, list):
        for v in node:
            yield from _copy(v)
    elif isinstance(node, str):
        yield node


def test_report_card_shape_three_what_ifs_and_short_names():
    snap, state, em = play(5, watch=True, watch_waivers="aggressive", watch_trades="active")
    rep = build_watch_report(snap, state, em.events)
    json.dumps(rep, allow_nan=False)
    assert rep["draft"]["then"]["grade"] and rep["draft"]["now"]["grade"]
    assert rep["standing"]["rank"] >= 1 and rep["sliders"] == {"waivers": "aggressive", "trades": "active"}
    assert len(rep["what_ifs"]) == 3
    ids = [c["id"] for c in rep["cards"]]
    assert ids[0] == "watch_draft" and ids[-1] == "watch_standing" and "watch_whatif" in ids
    first = rep["cards"][0]["data"]
    assert first["rounds"] and all({"round", "actual", "expected"} <= set(r) for r in first["rounds"])
    for c in rep["cards"]:
        for r in (c["data"] or {}).get("rows", []):
            if isinstance(r, dict) and r.get("grade"):
                assert r["grade"][0] in "ABCD"  # a pick is graded, never failed
    assert rep["best_value"] is None or rep["best_value"]["over_round"] > 0
    if rep["bust"]:
        assert rep["bust"]["why"] and rep["bust"]["actual"] < rep["bust"]["projected"]
    copy = " ".join(_copy(rep))
    for p in snap.players.values():
        if " " in p.name:
            assert p.name not in copy, p.name


def test_report_endpoint_gates():
    from tests.test_sim_game_api import advance, finish_draft, hdr, make_app, new_game

    client, _, _ = make_app(pro=("pro",))
    plain = new_game(client, "pro", teams=8, user_slot=2)["game"]["id"]
    assert client.get(f"/v1/sim/games/{plain}/watch-report", headers=hdr("pro")).json()["reason"] == "not_watch"
    game = new_game(client, "pro", teams=8, user_slot=2, watch=True, watch_waivers="balanced", watch_trades="light")["game"]
    assert game["settings"]["watch_v"] == 1 and game["settings"]["auto_lineup"] is True
    gid = game["id"]
    finish_draft(client, gid)
    assert client.get(f"/v1/sim/games/{gid}/watch-report", headers=hdr("pro")).json()["reason"] == "not_complete"
    for _ in range(30):
        if advance(client, gid)["game"]["status"] == "complete":
            break
    rep = client.get(f"/v1/sim/games/{gid}/watch-report", headers=hdr("pro")).json()["report"]
    assert len(rep["what_ifs"]) == 3
