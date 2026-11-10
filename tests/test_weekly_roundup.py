from modules import weekly_roundup as wr

SLOTS = wr.starting_slots(["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "SUPER_FLEX", "K", "DEF", "BN", "BN", "IR"])


def _meta(spec):
    return {pid: {"name": f"P{pid}", "position": pos, "team": "XX"} for pid, pos in spec.items()}


def test_starting_slots_drop_bench_ir_taxi():
    assert SLOTS == ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "SUPER_FLEX", "K", "DEF"]


def test_slot_accepts_flex_rules_and_aliases():
    assert wr.slot_accepts("FLEX", "TE") and not wr.slot_accepts("FLEX", "QB")
    assert wr.slot_accepts("SUPER_FLEX", "QB")
    assert wr.slot_accepts("REC_FLEX", "WR") and not wr.slot_accepts("REC_FLEX", "RB")
    assert wr.slot_accepts("DL", "DE") and wr.slot_accepts("IDP_FLEX", "CB")
    assert not wr.slot_accepts("RB", "WR")


def test_optimal_lineup_handles_overlapping_flex_exactly():
    slots = ["WRRB_FLEX", "REC_FLEX", "FLEX"]
    positions = {"1": "WR", "2": "WR", "3": "RB", "4": "TE"}
    points = {"1": 20.0, "2": 18.0, "3": 10.0, "4": 9.0}
    best = wr.optimal_lineup(slots, points, positions)
    assert sum(points[p] for _, p in best if p) == 48.0  # WR, WR, RB (TE sits)
    assert all(p is not None for _, p in best)


def test_optimal_lineup_leaves_unfillable_slot_empty():
    best = wr.optimal_lineup(["QB", "K"], {"1": 12.0}, {"1": "QB"})
    assert best == [("QB", "1"), ("K", None)]


def _week(starters, points, spec, projections=None, excluded=()):
    return wr.build_week_roundup(
        week=5,
        slots=SLOTS,
        starters=starters,
        players_points=points,
        meta=_meta(spec),
        projections=projections,
        excluded_ids=excluded,
    )


SPEC = {"q": "QB", "r1": "RB", "r2": "RB", "r3": "RB", "w1": "WR", "w2": "WR", "w3": "WR", "t": "TE", "k": "K", "d": "DEF", "q2": "QB"}
STARTERS = ["q", "r1", "r2", "w1", "w2", "t", "w3", "q2", "k", "d"]


def test_week_finds_swap_and_total_gap():
    pts = {"q": 20, "q2": 15, "r1": 12, "r2": 3, "r3": 18, "w1": 10, "w2": 9, "w3": 8, "t": 7, "k": 5, "d": 6}
    out = _week(STARTERS, pts, SPEC)
    assert out["actual_points"] == 95.0
    # r3 (18) replaces r2 (3) in RB; flex stays w3(8)? r3 takes RB, r2 leaves: gain 15
    assert out["left_on_bench"] == 15.0
    assert len(out["swaps"]) == 1
    swap = out["swaps"][0]
    assert (swap["started"]["player_id"], swap["benched"]["player_id"], swap["gain"]) == ("r2", "r3", 15.0)
    assert out["unattributed_points"] == 0.0
    assert len(out["lineup"]) == len(SLOTS)


def test_perfect_lineup_is_clean_week():
    pts = {"q": 20, "q2": 15, "r1": 12, "r2": 11, "r3": 1, "w1": 10, "w2": 9, "w3": 8, "t": 7, "k": 5, "d": 6}
    out = _week(STARTERS, pts, SPEC)
    assert out["left_on_bench"] == 0.0 and out["swaps"] == []
    assert out["takeaway"].startswith("Clean week")
    assert "clean lineup week" in wr.push_headline(out)


def test_empty_slot_counts_as_miss():
    pts = {"q": 20, "q2": 15, "r1": 12, "r2": 11, "r3": 9, "w1": 10, "w2": 9, "w3": 8, "t": 7, "k": 5, "d": 6}
    starters = ["q", "r1", "r2", "w1", "w2", "t", "0", "q2", "k", "d"]
    out = _week(starters, pts, SPEC)
    assert out["left_on_bench"] == 9.0
    assert out["swaps"][0]["benched"]["player_id"] == "r3"


def test_ir_player_not_slotted_in_hindsight():
    pts = {"q": 20, "q2": 15, "r1": 12, "r2": 3, "r3": 50, "w1": 10, "w2": 9, "w3": 8, "t": 7, "k": 5, "d": 6}
    out = _week(STARTERS, pts, SPEC, excluded=["r3"])
    assert out["left_on_bench"] == 0.0


def test_predictability_foreseeable_coin_flip_unforeseeable():
    fav = {"points": 14.0, "sd": 4.0}
    low = {"points": 8.0, "sd": 4.0}
    # Projection clearly favoured the benched player.
    a = wr.swap_predictability(started_actual=3, benched_actual=18, started_proj=low, benched_proj=fav)
    assert a["predictability"] == wr.FORESEEABLE
    # Projection favoured the starter and benched player spiked far above range.
    b = wr.swap_predictability(started_actual=9, benched_actual=30, started_proj=fav, benched_proj=low)
    assert b["predictability"] == wr.UNFORESEEABLE
    # Nearly equal projections.
    c = wr.swap_predictability(
        started_actual=5, benched_actual=12, started_proj={"points": 10, "sd": 4}, benched_proj={"points": 10.5, "sd": 4}
    )
    assert c["predictability"] == wr.COIN_FLIP
    # In-range result when starter was favoured is just noise.
    d = wr.swap_predictability(started_actual=11, benched_actual=12, started_proj=fav, benched_proj=low)
    assert d["predictability"] == wr.COIN_FLIP
    # Missing projection never fabricates a tag.
    e = wr.swap_predictability(started_actual=1, benched_actual=9, started_proj=None, benched_proj=fav)
    assert e["predictability"] == wr.COIN_FLIP and e["edge"] is None


def test_foreseeable_points_and_takeaway_and_headline():
    pts = {"q": 20, "q2": 15, "r1": 12, "r2": 3, "r3": 18, "w1": 10, "w2": 9, "w3": 8, "t": 7, "k": 5, "d": 6}
    proj = {"r2": {"points": 7.0, "sd": 3.0}, "r3": {"points": 13.0, "sd": 3.0}}
    out = _week(STARTERS, pts, SPEC, projections=proj)
    assert out["swaps"][0]["predictability"] == wr.FORESEEABLE
    assert out["foreseeable_points"] == 15.0
    assert "visible before kickoff" in out["takeaway"]
    headline = wr.push_headline(out)
    assert "left 15.0 pts on the bench" in headline and "Pr2 (3.0) over Pr3 (18.0)" in headline
    assert "week 5" in headline


def test_season_tally():
    weeks = [
        {"week": 2, "actual_points": 90, "optimal_points": 100, "left_on_bench": 10, "foreseeable_points": 4},
        {"week": 1, "actual_points": 80, "optimal_points": 90, "left_on_bench": 10, "foreseeable_points": 6},
    ]
    tally = wr.season_tally(weeks)
    assert tally["weeks_reviewed"] == 2 and tally["total_left_on_bench"] == 20.0
    assert tally["avg_left_on_bench"] == 10.0 and tally["foreseeable_share"] == 0.5
    assert [w["week"] for w in tally["weeks"]] == [1, 2]
    assert "50%" in tally["summary"]
    assert wr.season_tally([])["summary"] == ""


def test_league_scoring_conversion():
    std = wr.league_scoring_profile({"scoring_settings": {"rec": 0}})
    assert wr.to_league_points(15.0, position="WR", receptions=5, scoring=std) == 10.0
    tep = wr.league_scoring_profile({"scoring_settings": {"rec": 1, "bonus_rec_te": 0.5}})
    assert wr.to_league_points(10.0, position="TE", receptions=4, scoring=tep) == 12.0
    assert wr.to_league_points(10.0, position="QB", receptions=0, scoring=std) == 10.0


def test_build_roundup_end_to_end_is_point_in_time():
    seen = {}

    def baseline(rows, *, weekly_by_player, as_of_week):
        seen["as_of"] = as_of_week
        return {r["player_id"]: {"ppg": 7.0 if r["player_id"] == "r2" else 13.0, "sd": 3.0} for r in rows if r["position"] == "RB"}

    pts = {"q": 20, "q2": 15, "r1": 12, "r2": 3, "r3": 18, "w1": 10, "w2": 9, "w3": 8, "t": 7, "k": 5, "d": 6}
    league = {"roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "SUPER_FLEX", "K", "DEF", "BN"], "scoring_settings": {"rec": 1}}
    roster = {"roster_id": 3, "reserve": [], "taxi": []}
    row = {"roster_id": 3, "starters": STARTERS, "players_points": pts}
    out = wr.build_roundup(
        league=league,
        roster=roster,
        matchups_by_week={4: [row], 5: [row, {"roster_id": 9, "starters": [], "players_points": {}}], 6: [row]},
        week=5,
        meta=_meta(SPEC),
        weekly_by_player={},
        baseline_fn=baseline,
    )
    assert out["roundup"]["week"] == 5 and out["season"]["weeks_reviewed"] == 2  # week 6 excluded
    assert seen["as_of"] in (4, 5)
    assert out["method"] == wr.METHOD_NOTE
    assert out["roundup"]["swaps"][0]["predictability"] == wr.FORESEEABLE


def test_build_roundup_without_matchup_row_degrades():
    out = wr.build_roundup(league={"roster_positions": ["QB"]}, roster={"roster_id": 1}, matchups_by_week={5: []}, week=5, meta={}, weekly_by_player={}, baseline_fn=lambda *a, **k: {})
    assert out["roundup"] is None and out["season"]["weeks_reviewed"] == 0
