"""Suggested drops and the roster-value need model (one shared model).

Golden cases: superflex QB depth, contender vs rebuild, injured stash,
untouchable, roster-full league, "no good drop", the need model's regression
(a real weak position is surfaced; "none" only when true), and the failure
markers. Frames are synthetic league-wide universes with real-looking PPG so
the lineup model calibrates the way it does in production.
"""

from __future__ import annotations

import pandas as pd
import pytest

from modules import drop_candidates as dc
from modules import model_status, nfl_schedule
from modules import roster_value_model as rvm
from modules.trade_grade import SeasonWindow

WINDOW = SeasonWindow(current_week=8, remaining_weeks=10, in_season=True, source="league")

BASE_SETTINGS = {
    "league_format": "Dynasty",
    "qb_format": "1QB",
    "qb_count": 1,
    "rb_count": 2,
    "wr_count": 3,
    "te_count": 1,
    "k_count": 0,
    "def_count": 0,
    "flex_count": 1,
    "regular_flex_count": 1,
    "superflex_count": 0,
    "starter_count": 7,
    "current_week": 8,
}
SF_SETTINGS = {**BASE_SETTINGS, "qb_format": "Superflex", "superflex_count": 1, "starter_count": 8}
BASE_POSITIONS = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX"]
SF_POSITIONS = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "SUPER_FLEX"]


@pytest.fixture(autouse=True)
def _byes(monkeypatch):
    monkeypatch.setattr(nfl_schedule, "team_bye_week", lambda team, season, **kw: 99)


def _row(pid, pos, value, *, ppg=None, status="Active", injury="", age=26, **extra):
    row = {
        "player_id": pid, "name": pid, "position": pos, "team": "T", "status": status,
        "injury_status": injury, "age": age, "years_exp": max(0, int(age) - 21), "value_score": value,
        "dynasty_score": value, "score": value, "ppg": ppg, "games_played": 7 if ppg is not None else 0,
        "receptions": 0 if ppg is not None else None,
    }
    row.update(extra)
    return row


def _universe():
    rows = []
    for pos, n, top, bottom in (("QB", 20, 25, 12), ("RB", 50, 24, 3), ("WR", 70, 22, 3), ("TE", 25, 14, 2)):
        for i in range(n):
            rows.append(_row(f"U_{pos}{i}", pos, 9000 * (1 - i / n) + 200, ppg=top - (top - bottom) * i / (n - 1)))
    return pd.DataFrame(rows)


def _make(roster, pool=(), *, settings=BASE_SETTINGS, positions=BASE_POSITIONS, strategy="retool",
          reserve=(), taxi=(), reserve_slots=0, league_extra=None, total_rosters=12, limit=None):
    ids = [r["player_id"] for r in roster]
    roster_df = pd.DataFrame(roster)
    pool_df = pd.DataFrame(list(pool)) if pool else pd.DataFrame(columns=roster_df.columns)
    universe = _universe()
    all_df = pd.concat([universe, roster_df, pool_df], ignore_index=True)
    active = len(ids) - len(reserve) - len(taxi)
    limit = active + 3 if limit is None else limit  # default: three open spots
    league = {
        "total_rosters": total_rosters,
        "roster_positions": list(positions) + ["BN"] * max(0, limit - len(positions)),
        "settings": {"reserve_slots": reserve_slots, "taxi_slots": 0, **(league_extra or {})},
    }
    my_roster = {"players": ids, "reserve": list(reserve), "taxi": list(taxi)}
    values = list(universe["dynasty_score"]) + list(roster_df["dynasty_score"])
    return rvm.build_context(
        roster_df=roster_df, all_players_df=all_df, pool=pool_df, my_roster=my_roster, league=league,
        settings=settings, score_field="dynasty_score", strategy=strategy, window=WINDOW,
        league_rostered_values=values,
    )


def _core():
    return [
        _row("QB1", "QB", 6000, ppg=20), _row("RB1", "RB", 6500, ppg=17), _row("RB2", "RB", 5500, ppg=14),
        _row("WR1", "WR", 6500, ppg=16), _row("WR2", "WR", 5500, ppg=14), _row("WR3", "WR", 5000, ppg=12),
        _row("TE1", "TE", 5500, ppg=10), _row("FLX", "WR", 4500, ppg=11),
        # Cover behind the starters (bye/injury depth), so a bench add-on is not
        # "the only cover" at its position.
        _row("QB2", "QB", 2500, ppg=8), _row("RD1", "RB", 2500, ppg=6), _row("RD2", "RB", 2400, ppg=5.5),
        _row("WD1", "WR", 2500, ppg=7), _row("WD2", "WR", 2400, ppg=6.5), _row("TE2", "TE", 2000, ppg=4),
    ]


def _pool(*items):
    return [_row(f"FA_{pos}{i}", pos, v, ppg=ppg, age=24) for i, (pos, v, ppg) in enumerate(items)]


def _ids(rvc, **kw):
    ids, protected = dc.candidate_pool(rvc, untouchable=kw.get("untouchable", set()), usage=kw.get("usage", {}),
                                       add_positions=kw.get("add_positions", ()))
    return set(ids), {p["player_id"]: p for p in protected}


# --- protections -------------------------------------------------------------


def test_core_starters_and_high_value_are_never_candidates():
    roster = _core() + [_row("BN_WR", "WR", 700, ppg=4, age=30), _row("BIGBN", "RB", 9500, ppg=3, age=25)]
    rvc = _make(roster)
    ids, protected = _ids(rvc)
    assert protected["QB1"]["protected_by"] == "core_starter"
    assert protected["BIGBN"]["protected_by"] in {"high_value", "young_upside"}
    assert "BN_WR" in ids and "QB1" not in ids


def test_untouchable_is_never_suggested_even_when_the_cheapest_cut():
    roster = _core() + [_row("BN_WR", "WR", 700, ppg=4, age=30), _row("BN_RB", "RB", 900, ppg=4, age=30)]
    rvc = _make(roster, _pool(("WR", 1500, 9)), limit=len(roster))
    ids, protected = _ids(rvc, untouchable={"BN_WR"})
    assert protected["BN_WR"]["protected_by"] == "untouchable"
    result = dc.suggest_drop_for_add(rvc, rvc.pool.iloc[0].to_dict(), untouchable={"BN_WR"}, usage={})
    assert result["drop"]["player_id"] != "BN_WR"
    assert all(a["player_id"] != "BN_WR" for a in result["alternatives"])


def test_superflex_qb_depth_is_protected_but_a_swap_at_qb_is_allowed():
    roster = [
        _row("QB1", "QB", 6000, ppg=20), _row("QB2", "QB", 4000, ppg=17), _row("RB1", "RB", 6500, ppg=17),
        _row("RB2", "RB", 5500, ppg=14), _row("WR1", "WR", 6500, ppg=16), _row("WR2", "WR", 5500, ppg=14),
        _row("WR3", "WR", 5000, ppg=12), _row("TE1", "TE", 5500, ppg=10), _row("FLX", "WR", 4500, ppg=11),
        _row("QB3", "QB", 600, ppg=5, age=33),
    ] + [r for r in _core() if r["player_id"] in {"RD1", "RD2", "WD1", "WD2", "TE2"}]
    rvc = _make(roster, settings=SF_SETTINGS, positions=SF_POSITIONS)
    # Superflex fills a second QB slot, so QB3 is the bye/injury cover.
    ids, protected = _ids(rvc, add_positions=["WR"])
    assert protected["QB3"]["protected_by"] == "depth_floor"
    assert "QB3" not in ids
    ids_qb, _ = _ids(rvc, add_positions=["QB"])
    assert "QB3" in ids_qb  # replacing him with a QB keeps the depth


def test_posture_decides_whether_a_young_mid_value_player_is_protected():
    prospect = _row("PROSPECT", "WR", 0, ppg=3, age=22)
    for strategy, expected in (("rebuild", True), ("contender", False)):
        base = _make(_core() + [prospect], strategy=strategy)
        # a value that sits between the rebuild floor and the contender floor
        target = 0.2 * base.high_value
        roster = _core() + [{**prospect, "value_score": target, "dynasty_score": target, "score": target}]
        rvc = _make(roster, strategy=strategy)
        ids, protected = _ids(rvc)
        assert ("PROSPECT" in protected) is expected, strategy
        if expected:
            assert protected["PROSPECT"]["protected_by"] == "young_upside"


def test_hot_streak_player_is_protected():
    roster = _core() + [_row("HOT", "WR", 800, ppg=4, age=28)]
    rvc = _make(roster)
    hot = {"HOT": {"hot": True, "explanation": "targets are up"}}
    ids, protected = _ids(rvc, usage=hot)
    assert protected["HOT"]["protected_by"] == "hot_streak"


# --- roster-full vs open spot, IR --------------------------------------------


def test_open_roster_spot_means_no_drop_required():
    rvc = _make(_core() + [_row("BN", "WR", 700, ppg=4, age=30)])
    result = dc.suggest_drop_for_add(rvc, _make(_core()).pool.iloc[0].to_dict() if False else
                                     _row("FA_X", "WR", 1500, ppg=9, age=24), untouchable=set(), usage={})
    assert rvc.limits.active_limit == len(_core()) + 1 + 3 and not rvc.limits.is_full
    assert result["drop_required"] is False and result["drop"] is None
    assert "open roster spot" in result["why"]


def test_full_roster_suggests_the_cheapest_real_cut_with_net_effect():
    bench = [_row(f"B{i}", "WR", 600 + 40 * i, ppg=3, age=30) for i in range(8)]
    roster = _core() + bench
    rvc = _make(roster, _pool(("WR", 1800, 9)), limit=len(roster))
    assert rvc.limits.is_full
    result = dc.suggest_drop_for_add(rvc, rvc.pool.iloc[0].to_dict(), untouchable=set(), usage={})
    assert result["drop_required"] is True and result["no_good_drop"] is False
    assert result["drop"]["player_id"] == "B0"  # lowest value, never starts
    assert result["drop"]["effect"]["value_delta"] > 0
    assert "Add FA_WR0, drop B0" in result["why"]
    assert len(result["alternatives"]) <= 2


def test_no_good_drop_is_reported_honestly():
    # Every bench player is worth far more than the add and none is protected.
    bench = [_row(f"B{i}", "WR", 3000 + 10 * i, ppg=3, age=29) for i in range(8)]
    roster = _core() + bench
    rvc = _make(roster, _pool(("WR", 400, 3)), limit=len(roster))
    result = dc.suggest_drop_for_add(rvc, rvc.pool.iloc[0].to_dict(), untouchable=set(), usage={})
    assert result["no_good_drop"] is True and result["drop"] is None
    assert result["why"].startswith("No good drop for FA_WR0")


def test_injured_low_value_stash_moves_to_ir_when_the_league_allows_it():
    bench = [_row(f"B{i}", "WR", 1200 + 50 * i, ppg=3, age=26) for i in range(7)]
    hurt = _row("HURT", "RB", 900, ppg=6, age=29, status="Injured Reserve", injury="IR")
    roster = _core() + bench + [hurt]
    rvc = _make(roster, _pool(("WR", 2500, 9)), reserve_slots=2, limit=len(roster),
                league_extra={"reserve_allow_out": 1})
    assert rvc.limits.is_full and rvc.limits.open_ir_slots == 2
    result = dc.suggest_drop_for_add(rvc, rvc.pool.iloc[0].to_dict(), untouchable=set(), usage={})
    assert result["drop"]["player_id"] == "HURT" and result["drop"]["action"] == "move_to_ir"
    assert "move to IR" in result["why"]
    # no IR slot -> he is an ordinary (cheap) drop candidate, not an IR move
    full_ir = _make(roster, _pool(("WR", 2500, 9)), reserve_slots=0, limit=len(roster))
    again = dc.suggest_drop_for_add(full_ir, full_ir.pool.iloc[0].to_dict(), untouchable=set(), usage={})
    assert again["drop"]["action"] == "drop"


def test_high_value_injured_stash_is_protected_not_dropped():
    star = _row("STAR", "RB", 9500, ppg=18, age=24, status="Injured Reserve", injury="IR")
    rvc = _make(_core() + [star] + [_row(f"B{i}", "WR", 800, ppg=3, age=30) for i in range(7)])
    ids, protected = _ids(rvc)
    assert "STAR" not in ids


def test_ir_eligibility_follows_league_settings():
    league = {"settings": {"reserve_allow_out": 0, "reserve_allow_doubtful": 1}}
    assert rvm.ir_eligible("Injured Reserve", "IR", league)
    assert not rvm.ir_eligible("Active", "Out", league)
    assert rvm.ir_eligible("Active", "Doubtful", league)
    assert rvm.ir_eligible("Active", "Out", {"settings": {"reserve_allow_out": 1}})
    assert not rvm.ir_eligible("Active", "Questionable", {"settings": {"reserve_allow_out": 1}})


def test_roster_limits_exclude_ir_and_taxi_from_the_active_count():
    league = {"roster_positions": ["QB", "BN", "BN", "BN"], "settings": {"reserve_slots": 1, "taxi_slots": 1}}
    limits = rvm.roster_limits(league, {"players": ["a", "b", "c", "d", "e"], "reserve": ["d"], "taxi": ["e"]})
    assert limits.active_limit == 4 and limits.active_count == 3 and not limits.is_full
    assert limits.open_spots == 1 and limits.open_ir_slots == 0


# --- standalone list ---------------------------------------------------------


def test_standalone_list_is_worst_first_and_only_where_true():
    bench = [_row("DEAD1", "WR", 300, ppg=2, age=33), _row("DEAD2", "RB", 450, ppg=2, age=32),
             _row("KEEP", "WR", 4200, ppg=6, age=27)]
    rvc = _make(_core() + bench, _pool(("WR", 500, 6), ("RB", 500, 6)), limit=len(_core() + bench))
    out = dc.droppable_players(rvc, untouchable=set(), usage={})
    names = [p["player_id"] for p in out["players"]]
    assert names[:2] == ["DEAD1", "DEAD2"]
    assert "KEEP" not in names  # real value: not a free drop
    assert any("wire" in r or "never starts" in r for r in out["players"][0]["reasons"])


# --- need model --------------------------------------------------------------


def _league_table(my_rank_wr=11, teams=12):
    table = {}
    for t in range(1, teams + 1):
        table[str(t)] = {"QB": [20.0 - t * 0.2, 12.0], "RB": [20.0 - t * 0.3, 15.0 - t * 0.2],
                         "WR": [18.0 - t * 0.2, 15.0 - t * 0.2, 12.0 - t * 0.2], "TE": [12.0 - t * 0.2]}
    table["1"] = {"QB": [21.0, 13.0], "RB": [21.0, 16.0], "WR": [10.0, 9.0, 8.0], "TE": [13.0]}
    return table


def test_need_model_surfaces_the_weakest_position_with_the_numbers():
    rvc = _make(_core(), _pool(("WR", 1500, 11)))
    needs = rvm.assess_needs(rvc, _league_table(), "1", dynasty=True)
    wr = next(p for p in needs["positions"] if p["position"] == "WR")
    assert wr["weakest_slot"]["rank"] >= 10 and wr["weakest_slot"]["of"] == 12
    assert needs["weakest_position"] == "WR" and needs["no_need"] is False
    assert needs["biggest_need"] == "WR" and "WR" in needs["needed_positions"]
    assert needs["headline"].startswith(("Biggest need: WR", "Top need: WR"))
    assert needs["model_version"] == rvm.MODEL_VERSION


def test_need_model_says_no_need_only_when_every_position_is_covered():
    table = {str(t): {"QB": [18.0, 12.0], "RB": [18.0, 14.0], "WR": [16.0, 13.0, 11.0], "TE": [10.0]} for t in range(2, 13)}
    table["1"] = {"QB": [24.0, 14.0], "RB": [24.0, 20.0], "WR": [22.0, 20.0, 18.0], "TE": [14.0]}
    rvc = _make(_core(), _pool(("WR", 300, 3), ("RB", 300, 3), ("QB", 300, 3), ("TE", 300, 2)))
    needs = rvm.assess_needs(rvc, table, "1", dynasty=True)
    assert needs["no_need"] is True and needs["biggest_need"] is None
    assert needs["headline"].startswith("No urgent need")
    assert needs["positions"][0]["weakest_slot"]["rank"] == 1 or needs["positions"][0]["tier"] in {"watch", "covered"}


def test_need_model_reads_a_real_dynasty_scale_not_a_zero_to_hundred_one():
    # The legacy coverage check called every rostered player "playable" because
    # 4,000-9,000 clears a 0-100 threshold, so no dynasty roster ever had a
    # need. The model never reads the value scale for coverage.
    rvc = _make(_core(), _pool(("WR", 1500, 11)))
    assert all(v > 1000 for v in rvc.healthy_value.values())
    needs = rvm.assess_needs(rvc, _league_table(), "1", dynasty=True)
    assert needs["needed_positions"], "a roster ranked 11th of 12 at WR must have a need"


def test_aging_starter_without_young_cover_is_a_dynasty_future_gap():
    roster = [_row("OLD_RB1", "RB", 5000, ppg=17, age=31), _row("OLD_RB2", "RB", 4000, ppg=14, age=30)] + [
        r for r in _core() if r["position"] != "RB"
    ]
    rvc = _make(roster)
    table = _league_table()
    table["1"]["RB"] = [20.0, 15.0]
    dyn = rvm.assess_needs(rvc, table, "1", dynasty=True)
    red = rvm.assess_needs(rvc, table, "1", dynasty=False)
    rb_dyn = next(p for p in dyn["positions"] if p["position"] == "RB")
    rb_red = next(p for p in red["positions"] if p["position"] == "RB")
    assert rb_dyn["future_gap"] is True and rb_red["future_gap"] is False


# --- failure markers ---------------------------------------------------------


def test_model_status_messages_exist_for_every_new_marker():
    for code in ("need_model_failed", "untouchable_lookup_failed", "drop_model_failed", "usage_trends_unavailable"):
        assert code in model_status.MESSAGES


# --- one definition for cards and list ---------------------------------------


def _board(roster, pool, *, cap=2):
    rvc = _make(roster, pool, limit=len(roster))
    adds = [(r["player_id"], r) for r in pool]
    return rvc, *dc.build_drop_board(rvc, adds, untouchable=set(), usage={}, standalone_cap=cap)


def _assert_consistent(suggestions, droppable, rvc):
    named = {s["drop"]["player_id"] for s in suggestions.values() if s.get("drop")}
    listed = {p["player_id"] for p in droppable["players"]}
    # Every cut a card names is in the list, and the list is empty only if no card names one.
    assert named <= listed
    if named:
        assert droppable["players"]
    # A card that says "no good drop" never coexists with a free cut by the shared bar.
    free = {p["player_id"] for p in droppable["players"] if not p["named_for"]}
    if any(s.get("no_good_drop") for s in suggestions.values()):
        assert not free


def test_cards_and_list_share_one_definition_when_a_free_cut_exists():
    bench = [_row("DEAD", "WR", 300, ppg=2, age=33)] + [_row(f"B{i}", "WR", 2600 + 50 * i, ppg=3, age=29) for i in range(5)]
    roster = _core() + bench
    rvc, suggestions, droppable = _board(roster, _pool(("WR", 1800, 9), ("WR", 1500, 8)))
    _assert_consistent(suggestions, droppable, rvc)
    assert {s["drop"]["player_id"] for s in suggestions.values()} == {"DEAD"}
    assert droppable["players"][0]["player_id"] == "DEAD" and droppable["players"][0]["named_for"]


def test_an_upgrade_swap_cut_is_listed_even_though_it_is_not_free():
    # Bench players are worth real value (not free) but each add is worth more.
    bench = [_row(f"B{i}", "WR", 1500 + 40 * i, ppg=3, age=29) for i in range(6)]
    roster = _core() + bench
    rvc, suggestions, droppable = _board(roster, _pool(("WR", 4200, 9)))
    assert suggestions["FA_WR0"]["drop"] is not None
    _assert_consistent(suggestions, droppable, rvc)
    entry = next(p for p in droppable["players"] if p["named_for"])
    assert "cheapest cut to make room for FA_WR0" in entry["reasons"][0]


def test_no_good_drop_cards_never_coexist_with_a_free_cut_in_the_list():
    bench = [_row(f"B{i}", "WR", 3000 + 10 * i, ppg=3, age=29) for i in range(6)]
    roster = _core() + bench
    rvc, suggestions, droppable = _board(roster, _pool(("WR", 400, 3)))
    assert suggestions["FA_WR0"]["no_good_drop"] is True
    assert droppable["players"] == []
    _assert_consistent(suggestions, droppable, rvc)


def test_named_cuts_are_listed_even_beyond_the_free_cap():
    bench = [_row("DEAD", "WR", 300, ppg=2, age=33), _row("DEAD2", "RB", 350, ppg=2, age=33)]
    roster = _core() + bench
    rvc, suggestions, droppable = _board(roster, _pool(("WR", 1800, 9)), cap=0)
    named = {s["drop"]["player_id"] for s in suggestions.values() if s.get("drop")}
    assert named and named <= {p["player_id"] for p in droppable["players"]}
    assert droppable["locked_count"] >= 0
