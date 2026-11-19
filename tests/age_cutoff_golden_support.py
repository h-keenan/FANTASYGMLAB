"""Snapshot builder for the age-cutoff golden (tests/fixtures/age_cutoff_golden.json).

Sweeps every age-cutoff site that was migrated into ``modules/age_profile.py`` over a grid of ages (including the
exact boundary values and missing/NaN ages), scores, tiers, strategies and positions, and records the outputs. It
reads only public behaviour, so the same code captured the golden BEFORE the refactor and checks it after.
"""

from __future__ import annotations

import hashlib
import json
import os
from unittest import mock

import pandas as pd

AGES = [None, float("nan"), 0, -1] + [a / 2 for a in range(36, 82)] + [99]  # 18.0 .. 40.5 in half steps, plus 99
SCORES = [0, 1800, 1801, 2600, 3200, 3201, 4200, 5000, 5200, 5201, 5400, 6000, 6500, 7600, 7601, 9800]
TIERS = ["", "depth", "contributor", "starter", "core starter", "star", "elite"]
POSITIONS = ["QB", "RB", "WR", "TE"]
STRATEGIES = ["tank", "rebuild", "retool", "fringe_contender", "contender"]
ARCHETYPES = ["", "Juggernaut", "Young Competitive Team", "Asset Consolidator", "Aging Contender"]
CURVE_ENV = "DYNASTYGM_CANONICAL_AGE_CURVE"


def _json_safe(obj):
    return json.loads(json.dumps(obj, default=repr, sort_keys=True))


def _digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=repr).encode()).hexdigest()[:16]


def _pack(results: list) -> dict:
    results = _json_safe(results)
    return {"n": len(results), "digest": _digest(results), "head": results[:40]}


def _asset(pos, age, score, tier, opp="", **extra):
    a = {"asset_type": "player", "position": pos, "age": age, "score": score, "player_tier": tier,
         "opportunity_label": opp}
    a.update(extra)
    return a


def trade_ideas_snapshot():
    from modules import trade_ideas as ti

    out = {}
    opps = ["", "Buried Depth", "Elite Opportunity"]
    fmts = [{"qb_format": "1QB"}, {"qb_format": "Superflex", "te_premium": True}]
    for name, fn in (
        ("throw_in", ti._is_throw_in_asset),
        ("core_protected", ti._is_core_or_protected_starter),
        ("long_term", ti._is_long_term_starter_asset),
    ):
        res = [fn(_asset(p, a, s, t, o)) for p in POSITIONS[:2] for a in AGES for s in SCORES for t in TIERS[:5:2] for o in opps]
        out[name] = _pack(res)
    for name, fn in (("premium", ti._is_premium_market_asset), ("cornerstone", ti._is_cornerstone_asset)):
        res = [fn(_asset(p, a, s, t, o), f) for p in POSITIONS for a in AGES for s in SCORES for t in TIERS for o in opps for f in fmts]
        out[name] = _pack(res)
    shapes = [{"strategy": st, "archetype_label": ar, "needs": ["RB"], "surplus": []} for st in STRATEGIES for ar in ARCHETYPES]
    res = []
    for sh in shapes:
        for a in AGES:
            for s in (0, 5000, 6000):
                for t in ("", "core starter", "star"):
                    asset = _asset("WR", a, s, t)
                    res.append([ti._player_trade_fit(asset, "Core", sh, {}), ti._player_trade_fit(asset, "Bench", sh, None),
                                ti._target_trade_fit(asset, sh, {}), ti._my_player_candidate_reason(dict(asset, label="X"), sh),
                                ti._target_fit_reason(dict(asset, label="X"), sh)])
    out["fits_and_reasons"] = _pack(res)
    ctx = []
    for env in ("1", "0"):
        with mock.patch.dict(os.environ, {CURVE_ENV: env}):
            for st in STRATEGIES:
                for ra in (21, 24, 25.5, 26, 27.5, 30, 30.5, 33):
                    for sa in (23, 27, 31):
                        sh = {"strategy": st, "needs": [], "surplus": [], "archetype_label": ""}
                        ps = {"strategy": "contender", "needs": [], "surplus": []}
                        send = [_asset("WR", sa, 4000, "starter", label="S", player_id="s")]
                        recv = [_asset("WR", ra, 4000, "starter", label="R", player_id="r")]
                        try:
                            r = ti._trade_reasoning_context(sh, ps, send, recv, "P")
                        except Exception as exc:  # recorded so a refactor cannot change what raises
                            r = {"error": type(exc).__name__}
                        ctx.append([env, st, ra, sa, r])
            for st in STRATEGIES:
                for ia in (21, 24, 25, 25.5, 28, 30, 30.5, 33):
                    sh = {"strategy": st, "needs": [], "surplus": [], "archetype_label": ""}
                    ps = {"strategy": "rebuild", "needs": [], "surplus": []}
                    try:
                        r = ti.partner_acceptance_context(
                            send_assets=[_asset("WR", 25, 4000, "starter", label="S", player_id="s")],
                            receive_assets=[_asset("WR", ia, 4000, "starter", label="R", player_id="r")],
                            partner_shape=ps, send_score=4000, receive_score=4000)
                    except Exception as exc:
                        r = {"error": type(exc).__name__}
                    ctx.append([env, "partner", st, ia, r])
    out["reasoning_context"] = _pack(ctx)
    return out


def rankings_snapshot():
    from modules import rankings as rk

    out = {}
    res = []
    for a in AGES:
        for ye in (None, 0, 1, 2, 3, 12):
            res.append(rk.opportunity_profile("RB", "RB", 3000.0, 1, ye, a))
    out["opportunity_profile"] = _pack(res)
    res = []
    for a in AGES:
        for ye in (None, 0, 1, 2, 3):
            res.append(rk._injury_future_asset_profile({"age": a, "years_exp": ye, "depth_chart_order": 3,
                                                        "status": "Active", "depth_chart_position": "RB"}))
            res.append(rk._injury_future_asset_profile({"age": a, "years_exp": ye}))
    out["injury_future"] = _pack(res)
    res = []
    for a in AGES:
        for ye in (None, 5, 11, 12, 15):
            for sr in (None, 50, 100, 120, 150, 200):
                for nu in (None, 1.0, 1.0e12):
                    row = {"position": "WR", "age": a, "years_exp": ye, "search_rank": sr, "status": "Active",
                           "news_updated": nu, "depth_chart_position": "", "full_name": "A B", "team": "KC"}
                    with mock.patch.object(rk, "player_eligibility", lambda r: {"eligible": True}):
                        res.append(bool(rk.is_probably_stale_free_agent(row)))
    out["stale_fa"] = _pack(res)
    return out


def frames_snapshot():
    from modules import draft_assistant
    from services import mobile_api_service as m

    out = {}
    combos = [(pos, a, opp) for pos in ("WR", "K") for a in (21, 23.9, 24, 24.1, 25, None) for opp in ("", "Committee Back")]
    fa = pd.DataFrame([{"player_id": f"p{i}", "position": pos, "age": a, "dynasty_score": 1000 + i,
                        "opportunity_label": opp, "stale_free_agent": False} for i, (pos, a, opp) in enumerate(combos)])
    stash, watch, faab = m._secondary_waiver_sections(fa, set(), "dynasty_score")
    out["waiver_sections"] = [stash["player_id"].tolist(), watch["player_id"].tolist(), faab["player_id"].tolist()]
    combos = [(a, ye) for a in (21, 23, 24, 24.5, 26, 30, None) for ye in (0, 1, 2, 3, 6) for _ in range(2)]
    pool = pd.DataFrame([{"player_id": f"d{i}", "full_name": f"N{i}", "position": "WR", "team": "KC", "age": a,
                          "years_exp": ye, "status": "Active", "dynasty_score": 100 + i}
                         for i, (a, ye) in enumerate(combos)])
    with mock.patch.object(draft_assistant, "filter_current_fantasy_players", lambda df, **kw: df):
        got = draft_assistant.apply_draft_pool_filter(pool, {"draft_rounds": 3, "draft_status": "pre"})
    out["draft_pool"] = got["player_id"].tolist()
    return out


def drop_candidates_snapshot():
    from modules import age_profile, drop_candidates, posture_model

    out = {"youth_protection": {k: list(v) for k, v in posture_model.YOUTH_PROTECTION.items()}}
    res = []
    for env in ("1", "0"):
        with mock.patch.dict(os.environ, {CURVE_ENV: env}):
            for st in STRATEGIES:
                max_age, bump, _share = posture_model.YOUTH_PROTECTION[st]
                for pos in POSITIONS:
                    for a in (20, 22, 23, 23.5, 24, 25, 26, 27, 28, 29, 31):
                        runway = max_age - drop_candidates.YOUTH_RUNWAY_BASE_AGE
                        cut = max_age + (bump if pos == "QB" else 0.0)
                        res.append([env, st, pos, a, age_profile.runway_ok(pos, a, years_past_start=runway, legacy_max=cut)])
    out["runway"] = _pack(res)
    return out


def team_level_snapshot():
    """Team-level age deltas (posture classification, analyzer fit) and the remaining per-asset age sites."""

    from modules import team_eval, trade_analyzer_fit, trade_ideas as ti, usage_roles_targets
    from services import mobile_api_service as m

    out = {}
    res = []
    for pct in (0.9, 0.7, 0.62, 0.5, 0.38, 0.3, 0.18, 0.1):
        for delta in (-3.0, -1.0, 0.0, 0.99, 1.0, 1.01, 1.24, 1.25, 1.26, 3.0):
            res.append([pct, delta, team_eval._classify_team_strategy(pct, 25.0 + delta, 25.0)])
    out["classify_team_strategy"] = _pack(res)

    res = []
    for st in STRATEGIES + ["competitive", ""]:
        for ra in (None, 0, 21, 24, 25, 26, 27.5, 28.4, 28.5, 29, 33):
            for sa in (None, 0, 22, 25, 26, 30):
                sh = {"strategy": st, "needs": [], "surplus": [], "archetype_label": ""}
                for arch in ("", "Juggernaut", "Aging Contender"):
                    sh["archetype_label"] = arch
                    send = [_asset("WR", sa, 6500 if sa == 25 else 4000, "star" if sa == 22 else "starter", label="S", player_id="s", role="Core")]
                    recv = [_asset("WR", ra, 4000, "starter", label="R", player_id="r")] + [_asset("", None, 1500, "", asset_type="pick")]
                    res.append(ti.trade_strategy_fit_context(sh, send, recv))
    out["strategy_fit_context"] = _pack(res)

    res = []
    for beh in ("Prospect Chaser", "Pick Hoarder", "Consolidator", ""):
        for a in (None, 0, 21, 23.9, 24, 24.5, 27):
            for sa in (22, 30):
                mine = {"strategy": "contender", "needs": ["RB"], "surplus": [], "archetype_label": ""}
                partner = {"strategy": "rebuild", "needs": ["WR"], "surplus": [], "archetype_label": ""}
                send = [_asset("WR", a, 4000, "starter", label="S", player_id="s")]
                recv = [_asset("RB", sa, 4200, "starter", label="R", player_id="r")]
                try:
                    r = ti.evaluate_trade_market_realism(send_assets=send, receive_assets=recv, my_shape=mine,
                                                          partner_shape=partner, partner_name="P",
                                                          partner_profile={"asset_behavior": beh})
                except Exception as exc:
                    r = {"error": type(exc).__name__}
                res.append(r)
    out["market_realism"] = _pack(res)

    res = []
    roles = {"r": {"key": "role_expanding", "explanation": "His role is growing."},
             "s": {"key": "role_shrinking", "explanation": "His role is shrinking."}}
    with mock.patch.object(usage_roles_targets, "enabled", lambda *a, **k: True):
        for st in STRATEGIES:
            for a in (None, 0, 22, 24.9, 25, 25.1, 30):
                try:
                    res.append(usage_roles_targets.adjustment(
                        roles=roles, my_strategy=st, my_needs=[],
                        send_assets=[{"asset_type": "player", "player_id": "s", "position": "WR", "age": a}],
                        receive_assets=[{"asset_type": "player", "player_id": "r", "position": "WR", "age": a}]))
                except Exception as exc:
                    res.append(type(exc).__name__)
    out["usage_roles"] = _pack(res)

    res = []
    for ra in (None, 0, -1, 20, 98.9, 99, 99.5, 120, "x"):
        for da in (None, 0, 25, 98, 99, 100):
            row = pd.Series({"age": ra, "name": "N", "team": "KC", "position": "WR"})
            with mock.patch.object(m.sleeper, "get_players", lambda: {"1": {"age": da, "full_name": "D", "team": "KC", "position": "WR"}}):
                res.append(m._quick_view_identity("1", row).get("age"))
    out["quick_view_age"] = _pack(res)

    from tests import test_trade_lineup_model as T
    from tests import test_trade_posture as TP

    r = T._row
    roster = TP._contender_roster()
    res = []
    with mock.patch("modules.nfl_schedule.team_bye_week", lambda team, season, **kw: 99):
        for p in POSTURES_ALL:
            for age in (21, 24, 26, 28, 30, 33):
                for send_id in ("WR4", "RB1"):
                    rost = pd.DataFrame(roster)
                    by_id = rost.set_index("player_id", drop=False)
                    send = [T._asset(by_id.loc[send_id].to_dict())]
                    recv_row = r("AgeX", "WR", 4200, ppg=11, age=age)
                    receive = [T._asset(recv_row)]
                    universe = pd.concat([rost, T._universe(), pd.DataFrame([recv_row])], ignore_index=True)
                    fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
                        rost, universe, send, receive, None, p, T.SETTINGS, "dynasty_score",
                        waiver_df=T._fas(("RB", 3.5), ("WR", 5), ("TE", 3)), posture=None)
                    res.append([p, age, send_id, fit])
    out["analyzer_fit"] = _pack(res)
    return out


POSTURES_ALL = STRATEGIES


def snapshot():
    return _json_safe({
        "trade_ideas": trade_ideas_snapshot(),
        "rankings": rankings_snapshot(),
        "frames": frames_snapshot(),
        "drop_candidates": drop_candidates_snapshot(),
        "team_level": team_level_snapshot(),
    })
