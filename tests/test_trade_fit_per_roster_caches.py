"""Per-roster caches in the trade fit path must not change any output.

Grading many packages for one roster (Trade Hub's Analyzer gate) shares the
before-trade half of the work. These tests pin that the shared (warm) result is
identical to a from-scratch (cold) evaluation of each package, and that the
indexed value-curve lookup equals the original linear scan.
"""

from __future__ import annotations

import json
import random

import pandas as pd
import pytest

from modules import nfl_schedule, trade_analyzer_fit as taf, trade_lineup_impact, trade_lineup_model as model

SETTINGS = {
    "league_format": "Dynasty", "qb_format": "1QB", "qb_count": 1, "rb_count": 2, "wr_count": 3,
    "te_count": 1, "k_count": 0, "def_count": 0, "flex_count": 1, "superflex_count": 0, "current_week": 8,
}


@pytest.fixture(autouse=True)
def _byes(monkeypatch):
    monkeypatch.setattr(nfl_schedule, "team_bye_week", lambda team, season, **kw: {"A": 8, "B": 9}.get(team, 99))


def _clear_caches():
    model._CONTEXT_CACHE.clear()
    model._BEFORE_SIDE_CACHE.clear()
    model._CURVE_INDEX_CACHE.clear()
    trade_lineup_impact._BEFORE_STATE_CACHE.clear()


def _row(rng, pid, pos, value, ppg, team, injury=""):
    return {
        "player_id": pid, "name": pid, "position": pos, "team": team, "status": "Active",
        "injury_status": injury, "age": rng.randint(21, 33), "value_score": value, "dynasty_score": value,
        "score": value, "ppg": ppg, "games_played": 7, "receptions": 0,
    }


def _scenario():
    rng = random.Random(7)
    rows = []
    for pos, n, top, bottom in (("QB", 30, 25, 8), ("RB", 80, 24, 2), ("WR", 120, 22, 2), ("TE", 40, 14, 1)):
        for i in range(n):
            rows.append(_row(rng, f"U_{pos}{i}", pos, 9000 * (1 - i / n) + 200, top - (top - bottom) * i / (n - 1),
                             rng.choice("ABCD"), rng.choice(["", "", "", "Questionable"])))
    universe = pd.DataFrame(rows)
    roster = universe.sample(24, random_state=3).reset_index(drop=True)
    others = universe[~universe.player_id.isin(roster.player_id)].sample(30, random_state=4).to_dict("records")
    waiver = universe[~universe.player_id.isin(roster.player_id)].sample(60, random_state=5)
    mine = roster.to_dict("records")

    def asset(r):
        return {"asset_type": "player", **r, "label": r["name"]}

    trades = []
    for _ in range(8):
        send = rng.sample(mine, rng.choice([1, 2]))
        recv = rng.sample(others, rng.choice([1, 2]))
        trades.append(([asset(x) for x in send], [asset(x) for x in recv]))
    trades.append(([asset(mine[0])], [{"asset_type": "pick", "label": "2027 R2", "season": 2027, "round": 2,
                                        "score": 4800, "value_score": 4800, "owner_roster_id": "1"}]))
    return universe, roster, waiver, trades


def _fit(roster, universe, waiver, send, recv, ctx):
    return taf.evaluate_trade_analyzer_fit(
        roster, universe, send, recv, None, "retool", SETTINGS, "dynasty_score",
        current_context=ctx, waiver_df=waiver,
    )


def _dump(obj):
    return json.dumps(obj, default=str, sort_keys=True)


def test_shared_roster_caches_match_cold_evaluation():
    universe, roster, waiver, trades = _scenario()

    _clear_caches()
    ctx = taf.prepare_current_roster_context(roster, None, "retool", SETTINGS, "dynasty_score")
    warm = [_dump(_fit(roster, universe, waiver, s, r, ctx)) for s, r in trades]

    cold = []
    for s, r in trades:
        _clear_caches()
        fresh_ctx = taf.prepare_current_roster_context(roster, None, "retool", SETTINGS, "dynasty_score")
        cold.append(_dump(_fit(roster, universe, waiver, s, r, fresh_ctx)))

    assert warm == cold
    assert any('"available": true' in w for w in warm)


def test_repeated_evaluation_is_stable_and_cache_is_not_mutated():
    universe, roster, waiver, trades = _scenario()
    _clear_caches()
    ctx = taf.prepare_current_roster_context(roster, None, "retool", SETTINGS, "dynasty_score")
    send, recv = trades[0]
    first = _dump(_fit(roster, universe, waiver, send, recv, ctx))
    for s, r in trades[1:]:
        fit = _fit(roster, universe, waiver, s, r, ctx)
        impact = fit.get("weekly_lineup") or {}
        if isinstance(impact.get("open_slots_before"), list):
            impact["open_slots_before"].append("MUTATED")
    assert _dump(_fit(roster, universe, waiver, send, recv, ctx)) == first


def test_value_curve_index_matches_linear_scan():
    rng = random.Random(11)
    pairs = sorted(((rng.choice([100.0, 500.0, 900.5, rng.uniform(0, 9000)]), rng.uniform(1, 25)) for _ in range(60)),
                   key=lambda item: -item[0])
    curves = {"RB": pairs, "QB": pairs[:3]}

    def reference(pos, value):
        ps = curves.get(pos) or []
        if len(ps) >= 6:
            ppgs = sorted((p for _, p in ps), reverse=True)
            rank = sum(1 for v, _ in ps if v > value)
            return float(ppgs[min(rank, len(ppgs) - 1)]), True
        top, repl = model.STATIC_ANCHORS.get(pos, (15.0, 4.0))
        share = max(0.0, min(1.0, value / model.STATIC_VALUE_TOP))
        return repl + (top - repl) * share, False

    probes = [0.0, 100.0, 500.0, 900.5, 9999.0] + [v for v, _ in pairs] + [rng.uniform(0, 9500) for _ in range(200)]
    for value in probes:
        for pos in ("RB", "QB", "WR"):
            assert model._value_curve_ppg(curves, pos, value) == reference(pos, value)
