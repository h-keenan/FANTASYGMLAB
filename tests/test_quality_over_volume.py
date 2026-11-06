"""Roster/team logic must reward quality (top-end starters), not headcount."""

import pandas as pd

from modules import team_eval, trade_analyzer_fit, trade_grade, trade_ideas


def _roster(wr, rb=(6000, 5000, 4000), qb=(6000,), te=(4000,)):
    rows = []
    for pos, vals in (("QB", qb), ("RB", rb), ("WR", wr), ("TE", te)):
        rows += [{"position": pos, "dynasty_score": float(v), "value_score": float(v)} for v in vals]
    return pd.DataFrame(rows)


DEEP_MEDIOCRE_WR = [2600] * 10
ELITE_WR = [9000, 8000, 7000]


def test_raw_roster_score_prefers_elite_top_end_over_depth():
    deep = team_eval._score_starter_weighted_roster(_roster(DEEP_MEDIOCRE_WR))
    elite = team_eval._score_starter_weighted_roster(_roster(ELITE_WR))
    assert elite["raw_roster_score"] > deep["raw_roster_score"]
    assert elite["wr_score"] > deep["wr_score"]


def test_extra_fillers_add_nothing():
    base = team_eval._score_starter_weighted_roster(_roster(ELITE_WR + [6500, 6000, 5500]))
    padded = team_eval._score_starter_weighted_roster(_roster(ELITE_WR + [6500, 6000, 5500] + [800] * 12))
    assert padded["raw_roster_score"] == base["raw_roster_score"]
    assert padded["wr_score"] == base["wr_score"]


def test_bench_is_capped_and_above_replacement():
    lots = team_eval._score_starter_weighted_roster(_roster(ELITE_WR + [3000] * 12))
    cap = team_eval._bench_score_limit(None)
    expected = lots["starter_score"] + cap * (3000 - team_eval.REPLACEMENT_LEVEL)
    assert lots["raw_roster_score"] == expected


def test_position_value_map_is_not_a_sum_of_all_players():
    deep = pd.DataFrame({"position": ["WR"] * 10, "value_score": [2600.0] * 10})
    elite = pd.DataFrame({"position": ["WR"] * 3, "value_score": [9000.0, 8000.0, 7000.0]})
    mins = {"QB": 1, "RB": 3, "WR": 4, "TE": 1}
    d = trade_ideas._position_value_map(deep, "value_score", mins)["WR"]
    e = trade_ideas._position_value_map(elite, "value_score", mins)["WR"]
    assert e > d


def test_fit_depth_counts_startable_players_only():
    df = pd.DataFrame({"position": ["WR"] * 6, "value_score": [8000, 6000, 700, 600, 500, 400]})
    assert trade_analyzer_fit._team_position_counts(df)["WR"] == 6
    assert trade_analyzer_fit._team_position_counts(df, "value_score")["WR"] == 2


def test_team_fit_ignores_filler_in_headcount():
    shape = {"counts": {"WR": 6}, "startable_counts": {"WR": 3}, "minimums": {"WR": 3}}
    out = [{"asset_type": "player", "position": "WR", "score": 6000}]
    inc = [{"asset_type": "player", "position": "WR", "score": 500}]
    res = trade_ideas._team_fit_assessment(shape, out, inc, team_label="You", is_you=True)
    assert any("WR depth" in n for n in res["negatives"])
    # the same swap judged on raw headcount would look harmless
    res_old = trade_ideas._team_fit_assessment(
        {"counts": {"WR": 6}, "minimums": {"WR": 3}}, out, inc, team_label="You", is_you=True
    )
    assert not any("WR depth" in n for n in res_old["negatives"])


def test_consolidation_applies_to_even_counts_with_clear_headliner_gap():
    star = {"score": 9000}
    credit, _ = trade_grade.user_consolidation_adjustment(
        [{"score": 4500}, {"score": 4000}], [star, {"score": 3000}]
    )
    assert credit > 0
    debit, _ = trade_grade.user_consolidation_adjustment(
        [star, {"score": 3000}], [{"score": 4500}, {"score": 4000}]
    )
    assert debit < 0
    same, _ = trade_grade.user_consolidation_adjustment(
        [{"score": 5000}, {"score": 3000}], [{"score": 4800}, {"score": 3200}]
    )
    assert same == 0


def test_return_bundle_pieces_are_discounted():
    pair = [{"score": 4000}, {"score": 4000}]
    assert trade_ideas._package_fairness_value(pair) == 4000 + int(
        round(4000 * trade_ideas.PACKAGE_DEPTH_PIECE_WEIGHT)
    )
    assert trade_ideas._package_fairness_value([{"score": 7000}]) == 7000
