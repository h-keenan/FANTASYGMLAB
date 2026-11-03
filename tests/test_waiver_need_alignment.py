"""Waivers: the need headline and the Priority Adds read ONE model.

Regression for coridian_'s report (2026-11-02): the header said "Biggest need:
QB" while the recommended adds were running backs. Causes pinned here: the
lineup model priced fourth-string quarterbacks (who never play) as starters, so
the QB "upgrade" was fiction; the Priority Adds ranked by a bare position list
and raw value instead of the model's need order and lineup points; and the
"Fills need" tag fired for any player at a need position.
"""

from __future__ import annotations

import pandas as pd

from modules import roster_value_model as rvm
from modules import waivers_logic
from tests.test_drop_candidates import (  # noqa: F401  (autouse fixture is shared)
    SF_POSITIONS,
    SF_SETTINGS,
    _byes,
    _core,
    _league_table,
    _make,
    _row,
)


def _weak_qb_table(*, qb=(8.0, 6.0)):
    table = _league_table()
    table["1"] = {**table["1"], "QB": list(qb)}
    for t in range(2, 13):
        table[str(t)]["QB"] = [20.0 - t * 0.2, 14.0]
    return table


def _qb(pid, value, ppg, *, depth=1, **extra):
    return _row(pid, "QB", value, ppg=ppg, age=26, depth_chart_order=depth, workload_trend="Stable", **extra)


def _wire(pool):
    df = pd.DataFrame(list(pool))
    df["stale_free_agent"] = False
    df["injury_replacement_fit"] = False
    return df


def _roster_with_poor_qb():
    # Starting QB is a 9-ppg arm; every other position is deep and healthy.
    return [r if r["player_id"] != "QB1" else _row("QB1", "QB", 2500, ppg=9) for r in _core()]


def _assess(rvc):
    return rvm.assess_needs(rvc, _weak_qb_table(), "1", dynasty=True)


def test_need_is_qb_and_a_starting_qb_is_on_the_wire_top_add_is_that_qb():
    pool = [_qb("FA_QB", 1500, 17), _row("FA_RB", "RB", 6500, ppg=9, age=22, workload_trend="Stable")]
    rvc = _make(_roster_with_poor_qb(), pool)
    needs = _assess(rvc)
    assert needs["biggest_need"] == "QB"
    qb = next(p for p in needs["positions"] if p["position"] == "QB")
    assert qb["wire_verdict"] == "upgrade" and qb["upgrade"]["player_id"] == "FA_QB"
    assert "Best add: FA_QB" in needs["headline"]

    ranked = waivers_logic.rank_priority_add_candidates(
        _wire(pool), score_field="dynasty_score", needed_positions=needs["needed_positions"],
        league_settings={}, roster_df=rvc.frame, needs_model=needs,
    )
    top = ranked.iloc[0]
    assert top["player_id"] == "FA_QB" and bool(top["priority_need_fit"])
    # Same headline, no extra "so the top add is..." clause: they already agree.
    assert waivers_logic.align_headline_with_adds(needs, ranked) == needs["headline"]


def test_no_qb_on_the_wire_would_start_says_so_next_to_the_need_and_explains_the_top_add():
    # The only quarterbacks on the wire sit behind a healthy starter (or have no
    # depth-chart rank) - the old model priced them as 15-ppg starters.
    pool = [
        _qb("BACKUP", 1800, 15, depth=2),
        _qb("UNRANKED", 1700, 14, depth=0),
        _row("FA_RB", "RB", 3000, ppg=16, age=24, workload_trend="Stable"),
    ]
    roster = _roster_with_poor_qb()
    roster[roster.index(next(r for r in roster if r["player_id"] == "RD1"))] = _row("RD1", "RB", 2500, ppg=4)
    roster.append(_qb("QB_AHEAD", 3000, 9, depth=1, team="T"))  # the healthy starter in front of them
    rvc = _make(roster, pool)
    needs = _assess(rvc)
    assert needs["biggest_need"] == "QB"
    qb = next(p for p in needs["positions"] if p["position"] == "QB")
    assert qb["wire_verdict"] == "none" and qb["wire"] == []
    assert "No QB on the wire would help your lineup" in needs["headline"]
    assert qb["stash"]["name"] == "BACKUP"  # the best stash, by value

    ranked = waivers_logic.rank_priority_add_candidates(
        _wire(pool), score_field="dynasty_score", needed_positions=needs["needed_positions"],
        league_settings={}, roster_df=rvc.frame, needs_model=needs,
    )
    qb_rows = ranked[ranked["position"] == "QB"]
    assert not qb_rows["priority_need_fit"].any()  # nobody there fills the need
    assert bool(qb_rows[qb_rows["player_id"] == "BACKUP"].iloc[0]["priority_stash_for_need"])


def test_superflex_second_quarterback_slot_is_priced_by_the_lineup_model():
    roster = [r for r in _core() if r["player_id"] != "QB2"]
    roster.append(_row("QB2", "QB", 1200, ppg=5))
    pool = [_qb("FA_QB", 2000, 16)]
    rvc = _make(roster, pool, settings=SF_SETTINGS, positions=SF_POSITIONS)
    options = rvm.wire_options(rvc, "QB")
    assert options and options[0]["player_id"] == "FA_QB"
    assert options[0]["ppw"] >= rvm.FILLS_NEED_MIN_PPW  # fills the SUPER_FLEX slot


def test_injured_rostered_qb_is_covered_by_a_real_wire_qb():
    roster = [r if r["player_id"] != "QB1" else _row("QB1", "QB", 6000, ppg=20, status="Active", injury="Out") for r in _core()]
    rvc = _make(roster, [_qb("FA_QB", 1500, 14)])
    options = rvm.wire_options(rvc, "QB")
    assert options[0]["player_id"] == "FA_QB" and options[0]["ppw"] > rvm.FILLS_NEED_MIN_PPW


def test_has_path_to_play_requires_a_live_depth_chart_role_for_quarterbacks():
    ahead = _qb("S", 4000, 20, depth=1, team="AAA")
    pool = pd.DataFrame([
        _qb("starter", 1000, 15, depth=1, team="BBB"),
        _qb("behind_healthy", 1000, 15, depth=2, team="AAA"),
        _qb("behind_hurt", 1000, 15, depth=2, team="CCC"),
        _qb("unranked", 1000, 15, depth=0, team="DDD"),
        _qb("blocked", 1000, 15, depth=1, team="EEE", **{}),
        _row("rb", "RB", 1000, ppg=5, workload_trend="Stable"),
    ])
    pool.loc[pool["player_id"] == "blocked", "workload_trend"] = "Blocked"
    hurt_starter = _qb("S2", 4000, 20, depth=1, team="CCC", injury="Out")
    allp = pd.concat([pool, pd.DataFrame([ahead, hurt_starter])], ignore_index=True)
    ok = rvm.has_path_to_play(pool, allp)
    got = dict(zip(pool["player_id"], ok))
    assert got == {
        "starter": True, "behind_healthy": False, "behind_hurt": True,
        "unranked": False, "blocked": False, "rb": True,
    }


def test_fills_need_tag_follows_the_model_not_the_position_list():
    # RB is a listed need but this add is worth nothing to the lineup.
    pool = [_row("FA_RB_DEAD", "RB", 900, ppg=1, age=30, workload_trend="Stable"),
            _row("FA_RB_GOOD", "RB", 4000, ppg=18, age=24, workload_trend="Stable")]
    roster = [r for r in _core() if r["player_id"] not in {"RB2", "RD1", "RD2"}]
    roster += [_row("RB2", "RB", 800, ppg=3), _row("RD1", "RB", 700, ppg=2)]
    rvc = _make(roster, pool)
    table = _league_table()
    table["1"] = {**table["1"], "RB": [14.0, 3.0]}
    needs = rvm.assess_needs(rvc, table, "1", dynasty=True)
    assert "RB" in needs["needed_positions"]
    ranked = waivers_logic.rank_priority_add_candidates(
        _wire(pool), score_field="dynasty_score", needed_positions=needs["needed_positions"],
        league_settings={}, roster_df=rvc.frame, needs_model=needs,
    )
    fit = dict(zip(ranked["player_id"], ranked["priority_need_fit"]))
    assert fit["FA_RB_GOOD"] is True or bool(fit["FA_RB_GOOD"])
    assert not bool(fit.get("FA_RB_DEAD", False))
    assert ranked.iloc[0]["player_id"] == "FA_RB_GOOD"


def test_surfaces_without_free_agent_data_say_nothing_about_the_wire():
    rvc = _make(_roster_with_poor_qb(), [])
    rvc.pool = None
    needs = rvm.assess_needs(rvc, _weak_qb_table(), "1", dynasty=True)
    qb = next(p for p in needs["positions"] if p["position"] == "QB")
    assert qb["wire_verdict"] == "unknown" and "wire" not in needs["headline"]
