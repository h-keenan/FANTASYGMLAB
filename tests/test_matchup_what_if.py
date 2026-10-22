import pytest
from fastapi import HTTPException

from modules import matchup_what_if as wi
from modules import matchup_win_probability as wp
from services import mobile_api_service as svc

ELIG = svc._SLOT_ELIGIBLE_POSITIONS


def p(pid, pos, pts, *, low=None, high=None, status="ok", **extra):
    row = {
        "player_id": pid,
        "name": pid.upper(),
        "position": pos,
        "actual_points": None,
        "game_started": False,
        "injury_label": "",
        "projection": {
            "status": status,
            "point_estimate": pts if status == "ok" else None,
            "low": (pts - 3 if low is None else low) if status == "ok" else None,
            "high": (pts + 3 if high is None else high) if status == "ok" else None,
            "opponent": "DAL" if status == "ok" else None,
        },
    }
    row.update(extra)
    return row


def pool_of(*players):
    return {x["player_id"]: x for x in players}


OPP = [p("o1", "QB", 20), p("o2", "RB", 14), p("o3", "WR", 13), p("o4", "WR", 12)]


def base_pool():
    return pool_of(
        p("qb", "QB", 20),
        p("rb1", "RB", 12),
        p("wr1", "WR", 11),
        p("wr2", "WR", 9),
        p("benchwr", "WR", 15, low=8, high=26),
        p("benchrb", "RB", 6),
        p("benchte", "TE", 10),
        p("byewr", "WR", 0, status="bye_week", on_bye=True),
        p("outwr", "WR", 14, ruled_out=True, injury_label="Out"),
        p("irwr", "WR", 30, roster_slot="ir"),
        p("qwr", "WR", 16, injury_label="Questionable"),
    )


LINEUP = [
    {"slot": "QB", "player_id": "qb"},
    {"slot": "RB", "player_id": "rb1"},
    {"slot": "WR", "player_id": "wr1"},
    {"slot": "FLEX", "player_id": "wr2"},
]


def cands(slot_index, lineup=LINEUP, pool=None):
    out = wi.candidates_for_slot(pool or base_pool(), lineup, slot_index, OPP, ELIG)
    return {c["player"]["player_id"]: c for c in out["candidates"]}, out


def test_candidates_respect_slot_eligibility():
    by, _ = cands(1)  # RB slot
    assert set(by) == {"benchrb"}
    by, _ = cands(3)  # FLEX: RB/WR/TE, never the QB
    assert "benchte" in by and "benchrb" in by and "benchwr" in by
    assert "qb" not in by


def test_ir_players_are_not_candidates():
    by, _ = cands(2)
    assert "irwr" not in by


def test_bye_and_out_are_listed_but_not_selectable():
    by, _ = cands(2)
    assert by["byewr"]["selectable"] is False and by["byewr"]["blocked_reason"] == "bye"
    assert by["outwr"]["selectable"] is False and by["outwr"]["blocked_reason"] == "out"
    assert "On a bye" in [b["text"] for b in by["byewr"]["bullets"]]
    assert "Ruled out" in [b["text"] for b in by["outwr"]["bullets"]]
    assert by["byewr"]["win_probability_delta"] is None
    assert by["benchwr"]["selectable"] is True


def test_questionable_is_selectable_with_a_flag():
    by, _ = cands(2)
    assert by["qwr"]["selectable"] is True
    assert "Questionable" in [b["text"] for b in by["qwr"]["bullets"]]


def test_started_game_locks_the_swap():
    pool = base_pool()
    pool["benchwr"]["game_started"] = True
    by, _ = cands(2, pool=pool)
    assert by["benchwr"]["blocked_reason"] == "locked" and not by["benchwr"]["selectable"]
    pool = base_pool()
    pool["wr1"]["game_started"] = True
    by, out = cands(2, pool=pool)
    assert out["slot_locked"] is True and not any(c["selectable"] for c in by.values())


def test_win_probability_delta_matches_scoreboard_function():
    pool = base_pool()
    by, _ = cands(2, pool=pool)
    before = wp.compute_live_win_probability(wi.lineup_starters(pool, LINEUP), OPP)
    swapped = [dict(e) for e in LINEUP]
    swapped[2]["player_id"] = "benchwr"
    after = wp.compute_live_win_probability(wi.lineup_starters(pool, swapped), OPP)
    expected = round(after["probability"] * 100) - round(before["probability"] * 100)
    assert by["benchwr"]["win_probability_delta"] == expected
    assert by["benchwr"]["points_delta"] == 4.0
    texts = [b["text"] for b in by["benchwr"]["bullets"]]
    assert "+4.0 projected pts" in texts
    assert any(t.startswith("Higher ceiling (26 vs 14)") for t in texts)
    assert len(texts) <= 4


def test_bullets_come_from_values_only():
    by, _ = cands(2)
    for cand in by.values():
        for bullet in cand["bullets"]:
            assert bullet["tone"] in {"pro", "con", "neutral"} and bullet["text"]
    # a worse swap reads as a con
    worse = wi.candidates_for_slot(base_pool(), LINEUP, 3, OPP, ELIG)
    te = next(c for c in worse["candidates"] if c["player"]["player_id"] == "benchrb")
    assert te["points_delta"] == -3.0
    assert {"tone": "con", "text": "−3.0 projected pts"} in te["bullets"]


def test_starter_in_other_slot_trades_places_only_if_legal():
    lineup = [
        {"slot": "QB", "player_id": "qb"},
        {"slot": "WR", "player_id": "wr1"},
        {"slot": "TE", "player_id": "benchte"},
    ]
    # Picking wr1 for TE would strand benchte nowhere legal? TE can't fill WR: not offered.
    out = wi.candidates_for_slot(base_pool(), lineup, 2, OPP, ELIG)
    assert "wr1" not in {c["player"]["player_id"] for c in out["candidates"]}


def test_validate_lineup_rejects_bad_proposals():
    pool = base_pool()
    with pytest.raises(wi.LineupError):
        wi.validate_lineup(pool, [{"slot": "RB", "player_id": "qb"}], ELIG)
    with pytest.raises(wi.LineupError):
        wi.validate_lineup(pool, [{"slot": "WR", "player_id": "wr1"}, {"slot": "FLEX", "player_id": "wr1"}], ELIG)
    with pytest.raises(wi.LineupError):
        wi.validate_lineup(pool, [{"slot": "WR", "player_id": "stranger"}], ELIG)
    with pytest.raises(wi.LineupError):
        wi.validate_lineup(pool, [{"slot": "BOGUS", "player_id": None}], ELIG)
    wi.validate_lineup(pool, LINEUP, ELIG)


def _patch_page(monkeypatch, *, best_ball=False, live=False):
    pool = base_pool()
    starters = [dict(pool[e["player_id"]], slot=e["slot"]) for e in LINEUP]
    bench = [v for k, v in pool.items() if k not in {e["player_id"] for e in LINEUP}]
    opp = {"has_live_data": live, "real_starters": OPP, "starters": OPP}
    my = {"starters": starters, "real_starters": starters if live else [], "has_live_data": live}

    def fake(league_id, lens, user, state=None):
        if state is not None:
            state.update(my_side=my, opponent_side=opp, my_bench=bench, league={})
        return {"ok": True, "best_ball": best_ball, "reason": ""}

    monkeypatch.setattr(svc, "_build_matchup", fake)
    return starters


def call(**kw):
    return svc.post_league_matchup_what_if(svc.MatchupWhatIfRequest(**kw), league_id="L", user={"id": "u"})


def test_endpoint_reset_equals_original_and_matches_scoreboard(monkeypatch):
    starters = _patch_page(monkeypatch, live=True)
    scoreboard = wp.compute_live_win_probability(starters, OPP)
    original = call(lineup=LINEUP)
    assert original["win_probability"] == scoreboard
    edited = call(lineup=[*LINEUP[:2], {"slot": "WR", "player_id": "benchwr"}, LINEUP[3]])
    assert edited["win_probability"]["my_projected_total"] == scoreboard["my_projected_total"] + 4.0
    assert edited["position_edges"]
    # reset: sending the original lineup again reproduces the original exactly
    assert call(lineup=LINEUP)["win_probability"] == scoreboard


def test_endpoint_returns_candidates_for_edit_index(monkeypatch):
    _patch_page(monkeypatch)
    out = call(lineup=LINEUP, edit_index=2)
    assert out["candidates"]["slot"] == "WR"
    assert out["candidates"]["candidates"]
    with pytest.raises(HTTPException) as err:
        call(lineup=LINEUP, edit_index=9)
    assert err.value.status_code == 422


def test_endpoint_rejects_ineligible_lineup(monkeypatch):
    _patch_page(monkeypatch)
    with pytest.raises(HTTPException) as err:
        call(lineup=[{"slot": "RB", "player_id": "qb"}])
    assert err.value.status_code == 422


def test_endpoint_hidden_for_best_ball(monkeypatch):
    _patch_page(monkeypatch, best_ball=True)
    out = call(lineup=LINEUP, edit_index=0)
    assert out["best_ball"] is True and out["reason"] == "best_ball" and "lineup" not in out


def test_bench_players_are_listed_before_other_starters():
    """Swapping a starter out should lead with the bench, not with the other
    starters who would merely trade places (owner feedback)."""

    pool = base_pool()
    # A starter who would be a strong swap candidate for the FLEX slot.
    pool["wr1"] = p("wr1", "WR", 30)
    result = wi.candidates_for_slot(pool, LINEUP, 3, OPP, ELIG)
    selectable = [c for c in result["candidates"] if c["selectable"]]
    flags = [bool(c["currently_starting"]) for c in selectable]
    assert any(flags) and not all(flags)
    # Once a starter appears, no bench player may follow.
    first_starter = flags.index(True)
    assert all(flags[first_starter:])
    assert not flags[0]
