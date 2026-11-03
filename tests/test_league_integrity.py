"""modules.league_integrity: golden synthetic leagues (obvious tank, innocent
injury-ridden team, post-elimination vs still-alive, collusion pair, inactive
manager). Pure engine, no network and no players database."""

from __future__ import annotations

from modules import league_integrity as li

SLOTS = ["QB", "RB", "WR", "WR", "FLEX", "BN", "BN", "BN", "BN"]
# 6 teams, each with the same shape of roster; ability decides weekly points.
ABILITY = {"QB": 20, "RB1": 15, "RB2": 12, "WR1": 14, "WR2": 11, "WR3": 9, "RB3": 7, "WR4": 5}
POS = {"QB": "QB", "RB1": "RB", "RB2": "RB", "RB3": "RB", "WR1": "WR", "WR2": "WR", "WR3": "WR", "WR4": "WR"}
FULL = ["QB", "RB1", "WR1", "WR2", "RB2"]  # optimal lineup for the slots above
TEAMS = {1: "Alpha", 2: "Bravo", 3: "Charlie", 4: "Delta", 5: "Echo", 6: "Tanker"}
# Round robin pairs per week (matchup ids), 6 teams.
SCHEDULE = [
    [(1, 6), (2, 5), (3, 4)],
    [(1, 5), (2, 4), (3, 6)],
    [(1, 4), (2, 3), (5, 6)],
    [(1, 3), (2, 6), (4, 5)],
    [(1, 2), (3, 5), (4, 6)],
    [(1, 6), (2, 5), (3, 4)],
]


def pid(team: int, key: str) -> str:
    return f"{team}{key}"


def base_scale(team: int) -> float:
    return {1: 1.30, 2: 1.20, 3: 1.00, 4: 0.90, 5: 0.80, 6: 1.00}[team]


def build(lineups, *, zero=None, weeks=6, playoff_week_start=9, playoff_teams=2):
    """lineups: {team: callable(week) -> starter keys (len 5, may contain '0')}.
    zero: {(team, key, week)} players who score 0 that week."""

    zero = zero or set()
    meta = {pid(t, k): {"name": f"{TEAMS[t][:2]}-{k}", "position": POS[k], "team": "XXX"} for t in TEAMS for k in ABILITY}
    weekly: dict[int, list[dict]] = {}
    for w in range(1, weeks + 1):
        entries = []
        for mid, pair in enumerate(SCHEDULE[(w - 1) % len(SCHEDULE)], start=1):
            for t in pair:
                pts = {}
                for k, a in ABILITY.items():
                    wiggle = 1 + 0.03 * (((w * 7 + t * 3 + len(k)) % 5) - 2)
                    pts[pid(t, k)] = 0.0 if (t, k, w) in zero else round(a * base_scale(t) * wiggle, 2)
                keys = lineups[t](w)
                starters = [("0" if k == "0" else pid(t, k)) for k in keys]
                total = round(sum(pts.get(s, 0.0) for s in starters), 2)
                entries.append({
                    "roster_id": t, "matchup_id": mid, "points": total, "starters": starters,
                    "players": [pid(t, k) for k in ABILITY], "players_points": pts,
                    "starters_points": [pts.get(s, 0.0) for s in starters],
                })
        weekly[w] = entries
    league = {
        "roster_positions": SLOTS,
        "settings": {"playoff_week_start": playoff_week_start, "playoff_teams": playoff_teams, "best_ball": 0},
    }
    rosters = [{"roster_id": t, "reserve": [], "taxi": []} for t in TEAMS]
    profiles = {str(t): {"team_name": n, "owner_name": f"{n} owner"} for t, n in TEAMS.items()}
    return dict(league=league, rosters=rosters, weekly=weekly, player_meta=meta, profiles=profiles)


def active_moves():
    """One waiver add per team per week so 'no roster moves' never applies."""
    return [{"transaction_id": f"m{w}{t}", "type": "waiver", "status": "complete", "week": w, "roster_ids": [t],
             "draft_picks": [], "sides": [{"roster_id": t, "receives": [{"kind": "player", "player_id": "x"}], "drops": []}]}
            for w in range(1, 7) for t in TEAMS]


def sensible(week):
    return list(FULL)


def team(report, rid):
    return next(t for t in report["teams"] if t["roster_id"] == rid)


def test_all_sensible_league_is_fine():
    data = build({t: sensible for t in TEAMS})
    report = li.build_league_integrity(**data, transactions=active_moves(), current_week=7)
    assert report["weeks_evaluated"] == 6
    assert {t["band"] for t in report["teams"]} == {li.BAND_FINE}
    assert report["collusion"] == [] and report["inactive"] == []


def tank_lineup(week):
    # From week 2 bench the stars, start the weakest bodies, leave a slot empty.
    if week == 1:
        return list(FULL)
    return ["0", "WR4", "RB3", "WR3", "RB3" if week % 2 else "WR4"][:5]


def tank_transactions():
    return [
        {"transaction_id": "t1", "type": "waiver", "status": "complete", "week": 4, "roster_ids": [6], "draft_picks": [],
         "sides": [{"roster_id": 6, "receives": [], "drops": [{"kind": "player", "player_id": "6RB2", "name": "Ta-RB2"}]}]},
        {"transaction_id": "t2", "type": "trade", "status": "complete", "week": 5, "roster_ids": [6, 1],
         "draft_picks": [{"to_roster_id": 6, "from_roster_id": 1}],
         "sides": [
             {"roster_id": 6, "receives": [], "drops": [{"kind": "player", "player_id": "6QB", "name": "Ta-QB"}]},
             {"roster_id": 1, "receives": [{"kind": "player", "player_id": "6QB", "name": "Ta-QB"}], "drops": []},
         ]},
        {"transaction_id": "t3", "type": "trade", "status": "complete", "week": 3, "roster_ids": [6, 2],
         "draft_picks": [{"to_roster_id": 6, "from_roster_id": 2}],
         "sides": [
             {"roster_id": 6, "receives": [], "drops": [{"kind": "player", "player_id": "6WR1", "name": "Ta-WR1"}]},
             {"roster_id": 2, "receives": [{"kind": "player", "player_id": "6WR1", "name": "Ta-WR1"}], "drops": []},
         ]},
    ]


def _tank_lineups():
    lineups = {t: sensible for t in TEAMS}
    lineups[6] = tank_lineup
    return lineups


def test_obvious_tank_is_strong_and_explained():
    data = build(_tank_lineups())
    values = {pid(6, k): {"value_score": 3000 + 100 * i} for i, k in enumerate(ABILITY)}
    report = li.build_league_integrity(
        **data, transactions=tank_transactions(), values=values, current_week=7,
        draft_rule=li.DRAFT_RULE_RECORD,
    )
    t = team(report, 6)
    assert t["band"] == li.BAND_STRONG, t
    assert t["context"] == "eliminated"
    assert t["interpretation"] == "possible_tanking"
    assert t["weeks"]["longest_streak"] >= 3
    assert t["factors"]["roster"]["sell_trades"] == 2
    assert t["factors"]["roster"]["productive_drops"] == 1
    kinds = {e["kind"] for e in t["evidence"]}
    assert {"lineup", "roster", "persistence", "context"} <= kinds
    assert t["innocent_explanations"]
    assert all(other["band"] == li.BAND_FINE for other in report["teams"] if other["roster_id"] != 6)


def test_lineup_alone_is_capped_at_worth_a_look():
    """Single factor group (lineup only, no roster behaviour): never Strong."""
    data = build(_tank_lineups())
    report = li.build_league_integrity(**data, current_week=7, draft_rule=li.DRAFT_RULE_RECORD)
    t = team(report, 6)
    assert t["band"] == li.BAND_LOOK
    assert t["factors"]["roster"]["score"] < li.STRONG_MIN_ROSTER


def test_innocent_injury_ridden_team_is_fine():
    """Starters score 0 from week 3, but the whole bench is also out, so the
    best legal lineup is no better and nothing was left on the bench."""
    zero = {(6, k, w) for k in ABILITY for w in range(3, 7)}
    lineups = {t: sensible for t in TEAMS}
    data = build(lineups, zero=zero)
    report = li.build_league_integrity(**data, current_week=7)
    assert team(report, 6)["band"] == li.BAND_FINE


def test_one_off_bad_week_never_moves_a_band():
    lineups = {t: sensible for t in TEAMS}
    lineups[6] = lambda w: ["0", "WR4", "RB3", "WR3", "WR4"] if w == 4 else list(FULL)
    report = li.build_league_integrity(**build(lineups), current_week=7)
    assert team(report, 6)["band"] == li.BAND_FINE


def test_context_alive_vs_eliminated_changes_interpretation_and_score():
    # Make the sloppy team strong enough that it is still alive: playoff_teams=5 of 6.
    lineups = {t: sensible for t in TEAMS}
    lineups[6] = lambda w: list(FULL) if w == 1 else ["QB", "RB1", "WR4", "RB3", "WR3"]
    alive = li.build_league_integrity(**build(lineups, playoff_teams=5), current_week=7)
    elim = li.build_league_integrity(**build(lineups), current_week=7, draft_rule=li.DRAFT_RULE_RECORD)
    a, e = team(alive, 6), team(elim, 6)
    assert a["context"] == "alive" and a["interpretation"] == "possible_inactivity"
    assert e["context"] == "eliminated" and e["interpretation"] == "possible_tanking"
    assert 0 < a["score"] < e["score"]


def test_unknown_draft_rule_is_stated_not_assumed():
    report = li.build_league_integrity(**build(_tank_lineups()), current_week=7)
    t = team(report, 6)
    assert t["interpretation"] == "possible_tanking"
    assert any("cannot read the league's draft-order rule" in e["text"] for e in t["evidence"])


def test_bye_week_starter_is_not_blamed_when_no_swap_is_possible():
    # Everyone on the same fake NFL team; week 4 is its bye: nobody can be faulted.
    data = build({t: sensible for t in TEAMS})
    report = li.build_league_integrity(**data, current_week=7, on_bye=lambda team_code, week: week == 4)
    assert {t["band"] for t in report["teams"]} == {li.BAND_FINE}


def test_early_season_reports_not_enough_weeks():
    data = build(_tank_lineups(), weeks=2)
    report = li.build_league_integrity(**data, current_week=3)
    assert report["reason"] == "not_enough_weeks"
    assert {t["band"] for t in report["teams"]} == {li.BAND_NOT_ENOUGH}


def test_current_week_in_progress_is_not_evaluated():
    data = build({t: sensible for t in TEAMS}, weeks=4)
    report = li.build_league_integrity(**data, current_week=4)
    assert report["weeks_evaluated"] == 3


def test_best_ball_has_no_lineup_signals():
    data = build({t: sensible for t in TEAMS})
    data["league"]["settings"]["best_ball"] = 1
    report = li.build_league_integrity(**data, current_week=7)
    assert report["reason"] == "best_ball" and report["teams"] == []


def test_playoff_weeks_are_excluded():
    # Sloppy only in weeks that are playoff weeks (regular season = 4 weeks).
    lineups = {t: sensible for t in TEAMS}
    lineups[6] = lambda w: list(FULL) if w <= 4 else ["0", "WR4", "RB3", "WR3", "WR4"]
    report = li.build_league_integrity(**build(lineups, playoff_week_start=5), current_week=7)
    assert report["weeks_evaluated"] == 4
    assert team(report, 6)["band"] == li.BAND_FINE


def _trade(week, tid, giver, taker, sent_pid, got_pid):
    return {
        "transaction_id": tid, "type": "trade", "status": "complete", "week": week, "roster_ids": [giver, taker],
        "draft_picks": [],
        "sides": [
            {"roster_id": giver, "receives": [{"kind": "player", "player_id": got_pid, "name": got_pid}],
             "drops": [{"kind": "player", "player_id": sent_pid, "name": sent_pid}]},
            {"roster_id": taker, "receives": [{"kind": "player", "player_id": sent_pid, "name": sent_pid}],
             "drops": [{"kind": "player", "player_id": got_pid, "name": got_pid}]},
        ],
    }


def test_collusion_pair_repeated_lopsided_trades():
    values = {"star1": {"value_score": 6000}, "star2": {"value_score": 5500}, "star3": {"value_score": 5000},
              "scrub1": {"value_score": 500}, "scrub2": {"value_score": 400}, "scrub3": {"value_score": 300}}
    txs = [_trade(2, "a", 3, 4, "star1", "scrub1"), _trade(4, "b", 3, 4, "star2", "scrub2"),
           _trade(5, "c", 3, 4, "star3", "scrub3")]
    report = li.build_league_integrity(**build({t: sensible for t in TEAMS}), transactions=txs, values=values, current_week=7)
    assert len(report["collusion"]) == 1
    pair = report["collusion"][0]
    assert pair["band"] == li.BAND_STRONG
    assert pair["beneficiary_roster_id"] == 4 and pair["giver_roster_id"] == 3
    assert pair["lopsided_same_direction"] == 3 and len(pair["evidence"]) == 3
    assert pair["innocent_explanations"]


def test_balanced_repeat_trades_and_pick_trades_are_not_flagged():
    values = {f"p{i}": {"value_score": 3000} for i in range(6)}
    even = [_trade(2, "a", 3, 4, "p0", "p1"), _trade(4, "b", 3, 4, "p2", "p3"), _trade(5, "c", 4, 3, "p4", "p5")]
    r1 = li.build_league_integrity(**build({t: sensible for t in TEAMS}), transactions=even, values=values, current_week=7)
    assert r1["collusion"] == []
    with_picks = [
        dict(_trade(w, f"a{w}", 3, 4, "star1", "scrub1"), draft_picks=[{"to_roster_id": 3, "from_roster_id": 4}])
        for w in (2, 3, 4)
    ]
    values2 = {"star1": {"value_score": 6000}, "scrub1": {"value_score": 500}}
    r2 = li.build_league_integrity(**build({t: sensible for t in TEAMS}), transactions=with_picks, values=values2, current_week=7)
    # A pick on the transaction that is not on either side cannot be priced: never scored.
    assert r2["collusion"] == []


def _pick(season, rnd, to, frm, orig=None):
    return {"kind": "pick", "season": str(season), "round": rnd, "name": f"{season} {rnd}", "to_roster_id": to,
            "from_roster_id": frm, "original_roster_id": orig or frm}


def _swap(week, tid, a, b, a_gets, b_gets, *, ts=0):
    """Two-party trade. a_gets / b_gets: lists of ('player', pid) or ('pick', season, round, orig)."""

    def assets(items, to, frm):
        out = []
        for it in items:
            out.append({"kind": "player", "player_id": it[1], "name": it[1]} if it[0] == "player"
                       else _pick(it[1], it[2], to, frm, it[3] if len(it) > 3 else frm))
        return out

    a_in, b_in = assets(a_gets, a, b), assets(b_gets, b, a)
    return {
        "transaction_id": tid, "type": "trade", "status": "complete", "week": week, "timestamp": ts or week * 1000,
        "roster_ids": [a, b],
        "draft_picks": [x for x in a_in + b_in if x["kind"] == "pick"],
        "sides": [
            {"roster_id": a, "receives": a_in, "drops": [x for x in b_in if x["kind"] == "player"]},
            {"roster_id": b, "receives": b_in, "drops": [x for x in a_in if x["kind"] == "player"]},
        ],
    }


PICK_VALUES = {f"v{i}": {"value_score": 3000} for i in range(8)} | {"scrub": {"value_score": 500}}


def test_pick_priced_lopsided_repeat_trades_are_seen():
    # Team 4 keeps paying 1st-round picks for a low-value player: invisible before picks were priced.
    txs = [
        _swap(2, "a", 3, 4, [("pick", 2027, 1, 4)], [("player", "scrub")]),
        _swap(4, "b", 3, 4, [("pick", 2028, 1, 4)], [("player", "scrub")]),
        _swap(5, "c", 3, 4, [("pick", 2026, 1, 4), ("pick", 2026, 2, 4)], [("player", "scrub")]),
    ]
    report = li.build_league_integrity(**build({t: sensible for t in TEAMS}), transactions=txs, values=PICK_VALUES, current_week=7)
    pair = report["collusion"][0]
    assert "lopsided" in pair["patterns"] and pair["lopsided_same_direction"] == 3
    assert pair["beneficiary_roster_id"] == 3 and pair["giver_roster_id"] == 4
    assert pair["band"] == li.BAND_STRONG
    assert any("2027 1" in line for line in pair["evidence"])  # the priced pick is named in the evidence


def test_two_pick_lopsided_trades_is_only_worth_a_look():
    txs = [_swap(2, "a", 3, 4, [("pick", 2027, 1, 4)], [("player", "scrub")]),
           _swap(4, "b", 3, 4, [("pick", 2028, 1, 4)], [("player", "scrub")])]
    report = li.build_league_integrity(**build({t: sensible for t in TEAMS}), transactions=txs, values=PICK_VALUES, current_week=7)
    assert report["collusion"][0]["band"] == li.BAND_LOOK


def test_balanced_pick_for_pick_trades_are_not_flagged():
    txs = [_swap(2, "a", 3, 4, [("pick", 2027, 1, 4)], [("pick", 2027, 1, 3)]),
           _swap(4, "b", 3, 4, [("pick", 2028, 2, 4)], [("pick", 2028, 2, 3)]),
           _swap(5, "c", 4, 3, [("pick", 2029, 2, 3)], [("pick", 2029, 2, 4)])]
    report = li.build_league_integrity(**build({t: sensible for t in TEAMS}), transactions=txs, values=PICK_VALUES, current_week=7)
    assert report["collusion"] == []


def test_same_picks_moved_back_and_forth_three_times_is_worth_a_look():
    # Real pattern (league 1312122984617476096, rosters 3 and 9): same picks A->B->A->B in week 1.
    picks = [("pick", 2026, 2, 9), ("pick", 2027, 2, 9)]  # ~6400 priced vs 6000 of players: not lopsided
    txs = [_swap(1, "a", 3, 4, picks, [("player", "v0"), ("player", "v1")], ts=1),
           _swap(1, "b", 4, 3, picks, [("player", "v2"), ("player", "v3")], ts=2),
           _swap(1, "c", 3, 4, picks, [("player", "v4"), ("player", "v5")], ts=3)]
    report = li.build_league_integrity(**build({t: sensible for t in TEAMS}), transactions=txs, values=PICK_VALUES, current_week=7)
    pair = report["collusion"][0]
    assert pair["patterns"] == ["round_trip"] and pair["band"] == li.BAND_LOOK and pair["confidence"] == "low"
    assert pair["beneficiary_roster_id"] is None and pair["lopsided_same_direction"] == 0
    assert "went back and forth" in pair["evidence"][0]
    # Never accusing language.
    text = " ".join(pair["evidence"] + [pair["summary"], pair["headline"]]).lower()
    assert not any(w in text for w in ("collu", "cheat", "fraud", "rigg"))
    assert pair["innocent_explanations"]


def test_three_trades_between_a_pair_in_one_week_is_worth_a_look():
    # Real pattern (rosters 3 and 6, week 4): three separate, otherwise balanced trades in one week.
    txs = [_swap(4, "a", 3, 4, [("player", "v0")], [("player", "v1")], ts=1),
           _swap(4, "b", 3, 4, [("player", "v2")], [("player", "v3")], ts=2),
           _swap(4, "c", 3, 4, [("player", "v4")], [("player", "v5")], ts=3)]
    report = li.build_league_integrity(**build({t: sensible for t in TEAMS}), transactions=txs, values=PICK_VALUES, current_week=7)
    pair = report["collusion"][0]
    assert pair["patterns"] == ["burst"] and pair["band"] == li.BAND_LOOK
    assert "3 trades between them in week 4" in pair["evidence"][0]


def test_week_one_offseason_trades_never_count_as_a_burst():
    txs = [_swap(1, "a", 3, 4, [("player", "v0")], [("player", "v1")], ts=1),
           _swap(1, "b", 3, 4, [("player", "v2")], [("player", "v3")], ts=2),
           _swap(1, "c", 3, 4, [("player", "v4")], [("player", "v5")], ts=3)]
    report = li.build_league_integrity(**build({t: sensible for t in TEAMS}), transactions=txs, values=PICK_VALUES, current_week=7)
    assert report["collusion"] == []


def test_returns_months_apart_are_ordinary_trading_not_a_pattern():
    day = 24 * 3600 * 1000
    picks = [("pick", 2027, 2, 4), ("pick", 2027, 4, 4)]
    txs = [_swap(1, "a", 3, 4, [("player", "v0")], [("player", "v1")], ts=1 * day),
           _swap(4, "b", 3, 4, picks, [("player", "v2"), ("player", "v3")], ts=40 * day),
           _swap(8, "c", 4, 3, picks, [("player", "v4"), ("player", "v5")], ts=80 * day)]
    report = li.build_league_integrity(**build({t: sensible for t in TEAMS}), transactions=txs, values=PICK_VALUES, current_week=9)
    assert report["collusion"] == []


def test_a_single_undone_trade_is_below_the_minimum_sample():
    txs = [_swap(2, "a", 3, 4, [("player", "v0")], [("player", "v1")]), _swap(3, "b", 3, 4, [("player", "v1")], [("player", "v0")])]
    report = li.build_league_integrity(**build({t: sensible for t in TEAMS}), transactions=txs, values=PICK_VALUES, current_week=7)
    assert report["collusion"] == []


def test_trade_with_unpriceable_pick_is_not_scored():
    bad = _swap(2, "a", 3, 4, [("pick", 2027, 1, 4)], [("player", "scrub")])
    bad["draft_picks"][0]["round"] = None
    bad["sides"][0]["receives"][0]["round"] = None
    legs = li.trade_legs([bad], PICK_VALUES)
    assert legs[0]["valued"] is False


def test_pick_price_comes_from_the_trade_analyzer_pick_table():
    from modules.trade_ideas import canonical_pick_identity_value

    legs = li.trade_legs([_swap(2, "a", 3, 4, [("pick", 2027, 1, 4)], [("player", "scrub")])], PICK_VALUES)
    assert legs[0]["legs"][3]["received"] == canonical_pick_identity_value({"round": 1})
    assert legs[0]["legs"][3]["sent"] == 500


def test_inactive_manager_same_lineup_no_moves_and_empty_slots():
    lineups = {t: sensible for t in TEAMS}
    lineups[5] = lambda w: ["QB", "RB1", "WR1", "0", "RB2"]
    # Everyone else makes a move every week so only roster 5 stands out for "no moves".
    txs = [{"transaction_id": f"m{w}{t}", "type": "waiver", "status": "complete", "week": w, "roster_ids": [t],
            "draft_picks": [], "sides": []} for w in range(1, 7) for t in (1, 2, 3, 4, 6)]
    report = li.build_league_integrity(**build(lineups), transactions=txs, current_week=7)
    ids = [m["roster_id"] for m in report["inactive"]]
    assert ids == [5]
    assert len(report["inactive"][0]["evidence"]) == 2


def test_best_lineup_flex_and_superflex_nesting():
    cands = {"a": ("QB", 20.0), "b": ("QB", 18.0), "c": ("RB", 10.0), "d": ("WR", 12.0), "e": ("TE", 5.0)}
    chosen, total = li.best_lineup(["QB", "SUPER_FLEX", "FLEX"], cands)
    assert total == 20 + 18 + 12
    assert set(chosen.values()) == {"a", "b", "d"}
