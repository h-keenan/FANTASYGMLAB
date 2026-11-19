"""Snapshot builders for the scale-aware-threshold goldens and invariance tests.

``classification_snapshot`` sweeps every absolute-point cutoff in ``modules/trade_ideas`` that is reachable through a
pure function (market classification, tier labels, fair-value windows, consolidation credit). It takes the module as an
argument so the flag-OFF golden could be captured from the pre-change source. ``hub_ideas`` runs the real Hub
builder on a fixture league, optionally with every value multiplied by ``k`` (a uniformly rescaled league).
"""

from __future__ import annotations

import hashlib
import json
import os
from unittest import mock

import pandas as pd

FLAG = "DYNASTYGM_SCALE_AWARE_THRESHOLDS_V1"
SCORES = [0, 300, 900, 1799, 1800, 1801, 2600, 3200, 3201, 4200, 5000, 5200, 5201, 5400, 6000, 6500, 7000, 7600, 7601,
          9000, 9800, 10500]
TIERS = ["", "depth", "contributor", "starter", "core starter", "star", "elite"]
POSITIONS = ["QB", "RB", "WR", "TE"]
AGES = [0, 22, 24, 25, 26, 28, 30]
OPPS = ["", "Buried Depth", "Elite Opportunity"]
FORMATS = [{"qb_format": "1QB"}, {"qb_format": "Superflex", "te_premium": True}]
SCORE_COLS = ("value_score", "dynasty_score", "base_score", "market_value", "redraft_score", "fantasycalc_value")
SPECS = (
    ("10t-1qb", 10, 22, "1QB", False),
    ("12t-sf-tep", 12, 24, "Superflex", True),
    ("14t-1qb-tep", 14, 22, "1QB", True),
    ("10t-sf", 10, 24, "Superflex", False),
    ("12t-1qb", 12, 22, "1QB", False),
    ("14t-sf", 14, 24, "Superflex", False),
)
POSTURES = ("contender", "fringe_contender", "retool", "rebuild", "tank")


def _digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=repr).encode()).hexdigest()[:16]


def _pack(results: list) -> dict:
    results = json.loads(json.dumps(results, default=repr))
    return {"n": len(results), "digest": _digest(results), "head": results[:30]}


def _asset(pos, age, score, tier, opp=""):
    return {"asset_type": "player", "position": pos, "age": age, "score": score, "player_tier": tier,
            "opportunity_label": opp, "label": "X", "player_id": "x"}


def classification_snapshot(ti) -> dict:
    out = {}
    for name, fn in (("throw_in", ti._is_throw_in_asset), ("core_protected", ti._is_core_or_protected_starter),
                     ("long_term", ti._is_long_term_starter_asset)):
        out[name] = _pack([fn(_asset(p, a, s, t, o)) for p in POSITIONS[:2] for a in AGES for s in SCORES
                           for t in TIERS[:5:2] for o in OPPS])
    for name, fn in (("premium", ti._is_premium_market_asset), ("cornerstone", ti._is_cornerstone_asset)):
        out[name] = _pack([fn(_asset(p, a, s, t, o), f) for p in POSITIONS for a in AGES for s in SCORES
                           for t in TIERS for o in OPPS for f in FORMATS])
    out["tier_label"] = _pack([ti._asset_tier_label({"score": s}) for s in range(0, 11000, 50)])
    out["value_band"] = _pack([list(ti.finder_value_band(v)) for v in range(0, 12000, 100)])
    out["value_fits_default"] = _pack([ti._value_fits(100, 100 + d) for d in range(-3000, 3001, 50)])
    out["value_fits_explicit"] = _pack([ti._value_fits(100, 100 + d, low=-1800, high=900) for d in range(-3000, 3001, 50)])
    out["consolidation"] = _pack([list(ti._cornerstone_consolidation_premium(target_score=t, headliner_ratio=r, first_round_count=f))
                                  for t in (2000, 5000, 8000) for r in (0.2, 0.6, 1.0) for f in (0, 1, 2)])
    out["finder_overpay"] = _pack([ti.finder_is_overpay({"trade_gain": g}) for g in range(-1000, 500, 25)])
    return out


def _scaled_players(players: pd.DataFrame, k: float) -> pd.DataFrame:
    """Every value column (players and the league summary's roster totals) multiplied by ``k``."""

    players = players.copy()
    for col in players.columns:
        if pd.api.types.is_numeric_dtype(players[col]) and (col.endswith("_score") or col in SCORE_COLS):
            # Engine scores are ints: start from even whole numbers so x0.5 stays whole and the rescaled league is an
            # exact copy of the base one (otherwise int() truncation at a cutoff would be a rounding artefact).
            even = (players[col] // 4) * 4
            players[col] = even * k if k != 1.0 else even
    return players


def hub_ideas(spec, posture: str, k: float = 1.0, *, flag: bool, max_ideas: int = 8) -> list[dict]:
    """Hub ideas on a fixture league whose every value is multiplied by ``k`` (picks via the pick multiplier)."""

    from modules import trade_hub_engine, trade_ideas
    from scripts.profile_trade_hub import FixtureSpec, build_fixture

    label, teams, size, qbf, tep = spec
    with mock.patch.dict(os.environ, {FLAG: "1" if flag else "0"}):
        fx = build_fixture(FixtureSpec(label, teams, size, qbf, te_premium=tep, strategy="contender"))
        fx["settings"] = dict(fx["settings"], current_week=8)
        pool = trade_hub_engine.apply_strategy_age_curve(_scaled_players(fx["players"], k), posture, "value_score")
        fx["summary"] = _scaled_players(fx["summary"], k)
        multiplier = trade_hub_engine.strategy_adjusted_pick_score_multiplier(1.0, posture) * k
        trade_ideas.clear_team_shape_memos()
        hub = trade_ideas._build_trade_ideas_impl(
            pool, "fixture-league", fx["summary"], 1, [], [], {}, max_ideas=max_ideas, score_field="value_score",
            pick_score_multiplier=multiplier, team_strategy=posture, league_settings=fx["settings"],
            draft_status={"draft_year": 2026, "current_year_picks_active": True}, adapter=fx["adapter"],
        )
    return [
        {"send": [str(a.get("player_id") or a.get("label") or "") for a in idea.get("send_assets") or ()],
         "receive": [str(a.get("player_id") or a.get("label") or "") for a in idea.get("receive_assets") or ()],
         "my_score": idea.get("my_score"), "their_score": idea.get("their_score"), "gain": idea.get("trade_gain")}
        for idea in hub
    ]


def selection(ideas: list[dict]) -> list[tuple]:
    return [(tuple(i["send"]), tuple(i["receive"])) for i in ideas]


def hub_snapshot(specs=SPECS, postures=POSTURES, *, flag: bool) -> dict:
    return json.loads(json.dumps({f"{s[0]}|{p}": hub_ideas(s, p, flag=flag) for s in specs for p in postures}, default=repr))
