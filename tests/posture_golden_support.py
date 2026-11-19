"""Snapshot builders for the shared-posture-model golden (tests/fixtures/posture_golden.json).

``tables_snapshot`` and ``grade_snapshot`` are cheap and run under both starter-floor flag states (the flag is read
at import, so the floor-OFF side runs in a subprocess). ``engine_snapshot`` and ``multi_team_snapshot`` run
Hub / Finder / GM Plan / 3-team search on fixture leagues. Nothing here imports a posture table by name: it reads only
public behaviour, so the same code captures the golden before the refactor and checks it after.
"""

from __future__ import annotations

import hashlib
import json
import os
from unittest.mock import patch

import pandas as pd

POSTURES = ("contender", "fringe_contender", "retool", "rebuild", "tank")
STANCE = {
    "contender": "contending", "fringe_contender": "contending", "retool": "balanced",
    "rebuild": "rebuilding", "tank": "rebuilding",
}


def _json(obj):
    return json.loads(json.dumps(obj, sort_keys=True, default=repr))


def _digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=repr).encode()).hexdigest()[:16]


def tables_snapshot():
    """Behavioural dump of every posture-keyed number reachable through the public surface."""

    from modules import drop_candidates, multi_team_trade_finder, trade_grade, trade_hub_engine, trade_ideas
    from modules import trade_lineup_model, trade_posture

    out = {
        "starter_weight": {p: trade_grade.starter_strength_weight(p) for p in POSTURES},
        "injury_weight": {p: trade_grade.INJURY_POSTURE_WEIGHTS.get(p) for p in POSTURES},
        "posture_weights": {p: list(trade_lineup_model.POSTURE_WEIGHTS[p]) for p in POSTURES},
        "present_adjust": dict(trade_posture.PRESENT_ADJUST),
        "orientation": dict(trade_posture.ORIENTATION),
        "window_win": dict(trade_posture.WINDOW_WIN_WEIGHT),
        "pick_multiplier": {p: trade_hub_engine.strategy_adjusted_pick_score_multiplier(1.0, p) for p in POSTURES},
        "drop_youth_protection": {p: list(drop_candidates.YOUTH_PROTECTION[p]) for p in POSTURES},
        "pick_want": dict(multi_team_trade_finder.PICK_WANT_BY_GROUP),
    }
    ages = [float(a) for a in range(20, 38)] + [24.5, 26.5, 29.5]
    rows = [
        {"player_id": f"{pos}{int(a * 10)}", "position": pos, "age": a, "dynasty_score": 5000, "value_score": 5000,
         "base_score": 5000, "name": f"{pos}{a}"}
        for pos in ("QB", "RB", "WR", "TE") for a in ages
    ]
    frame = pd.DataFrame(rows)
    curve = {}
    for p in POSTURES:
        got = trade_hub_engine.apply_strategy_age_curve(frame, p, "dynasty_score")
        curve[p] = [[r["player_id"], r["strategy_preference_multiplier"], int(r["strategy_score"])] for r in got.to_dict("records")]
    out["age_curve"] = curve
    send = {"asset_type": "pick"}
    out["pick_send_terms"] = {
        f"{p}|{n}": list(trade_ideas._pick_send_posture_terms([send] * n, {"strategy": p})) for p in POSTURES for n in (1, 2)
    }
    return _json(out)


def grade_snapshot():
    from modules import nfl_schedule, trade_analyzer_fit, trade_offer_analyzer
    from tests import test_trade_lineup_model as T
    from tests import test_trade_posture as TP

    nfl_schedule.team_bye_week = lambda team, season, **kw: 99
    r = T._row
    settings_variants = {
        "1qb_12": dict(T.SETTINGS, league_size=12),
        "sf_10": dict(T.SETTINGS, qb_format="Superflex", superflex_count=1, league_size=10),
        "tep_14": dict(T.SETTINGS, te_premium=True, league_size=14),
    }
    roster = TP._contender_roster()
    noel = TP._noel()
    old_vets = [r("OV1", "RB", 4200, ppg=12, age=31), r("OV2", "WR", 3800, ppg=11, age=32)]
    inj = r("InjWR", "WR", 5200, ppg=15, age=26, injury="Out", status="Injured Reserve")
    young = r("YngWR", "WR", 3600, ppg=7, age=21)
    trades = {
        "higgins_for_ir_plus_r1": (["Higgins"], [noel], [], [TP._pick(7400)]),
        "stud_for_depth": (["RB1"], [r("D1", "RB", 3500, ppg=11, age=26), r("D2", "WR", 3300, ppg=10, age=27)], [], []),
        "firsts_for_old_vets": ([], old_vets, [TP._pick(5200), TP._pick(4800, season=2027)], []),
        "buy_injured": (["WR2"], [inj], [], []),
        "sell_vet_for_youth": (["WR4"], [young], [], [TP._pick(2500, 2)]),
        "pick_sale": ([], [r("U1", "WR", 5000, ppg=15, age=24)], [TP._pick(6000)], []),
    }
    out = {}
    for sname, settings in settings_variants.items():
        for tname, (send_ids, recv, send_picks, recv_picks) in trades.items():
            for p in POSTURES:
                rost = pd.DataFrame(roster)
                by_id = rost.set_index("player_id", drop=False)
                send = [T._asset(by_id.loc[i].to_dict()) for i in send_ids] + list(send_picks)
                receive = [T._asset(x) for x in recv] + list(recv_picks)
                universe = pd.concat([rost, T._universe(), pd.DataFrame(recv or [])], ignore_index=True)
                fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
                    rost, universe, send, receive, None, p, settings, "dynasty_score",
                    waiver_df=T._fas(("RB", 3.5), ("WR", 5), ("TE", 3)), posture=None,
                )
                v = trade_offer_analyzer.decide_offer_verdict(fit, send_assets=send, receive_assets=receive)
                lm = (fit or {}).get("lineup_model") or {}
                out[f"{sname}|{tname}|{p}"] = {
                    "score": v.trade_score, "band": v.band, "ui": v.ui_verdict, "tone": v.tone,
                    "note": getattr(v, "posture_note", ""),
                    "weights": lm.get("weights"), "components": lm.get("components"),
                    "posture_now": lm.get("posture_now"), "posture_future": lm.get("posture_future"),
                    "lm_score": lm.get("trade_score"),
                }
    return _json(out)


SPECS = (
    ("10t-1qb", 10, 22, "1QB", False),
    ("12t-sf-tep", 12, 24, "Superflex", True),
    ("14t-1qb-tep", 14, 22, "1QB", True),
    ("10t-sf", 10, 24, "Superflex", False),
    ("12t-1qb", 12, 22, "1QB", False),
    ("14t-sf", 14, 24, "Superflex", False),
)


def _idea_row(i, idea):
    return {
        "i": i, "my": str(idea.get("my_player") or ""), "their": str(idea.get("their_player") or ""),
        "send": [str(a.get("player_id") or a.get("label") or "") for a in idea.get("send_assets") or ()],
        "receive": [str(a.get("player_id") or a.get("label") or "") for a in idea.get("receive_assets") or ()],
        "my_score": idea.get("my_score"), "their_score": idea.get("their_score"), "gain": idea.get("trade_gain"),
        "idea_score": idea.get("trade_idea_score"), "verdict": idea.get("analyzer_verdict"),
        "an_score": idea.get("analyzer_trade_score"), "label": idea.get("analyzer_label"),
        "posture_label": idea.get("posture_label"),
    }


def engine_snapshot(specs=SPECS):
    from modules import gm_plan, trade_hub_engine, trade_ideas, trade_posture
    from scripts.profile_trade_hub import FixtureSpec, build_fixture

    out = {}
    for label, teams, size, qbf, tep in specs:
        fx = build_fixture(FixtureSpec(label, teams, size, qbf, te_premium=tep, strategy="contender"))
        fx["settings"] = dict(fx["settings"], current_week=8)
        for p in POSTURES:
            pool = trade_hub_engine.apply_strategy_age_curve(fx["players"], p, "value_score")
            kw = dict(
                max_ideas=8, score_field="value_score",
                pick_score_multiplier=trade_hub_engine.strategy_adjusted_pick_score_multiplier(1.0, p),
                team_strategy=p, league_settings=fx["settings"],
                draft_status={"draft_year": 2026, "current_year_picks_active": True}, adapter=fx["adapter"],
            )
            hub = trade_ideas._build_trade_ideas_impl(pool, "fixture-league", fx["summary"], 1, [], [], {}, **kw)
            shopped = [hub[0]["my_player"]] if hub and hub[0].get("my_player") else []
            fin = (
                trade_ideas._build_trade_ideas_impl(pool, "fixture-league", fx["summary"], 1, shopped, [], {}, **kw)
                if shopped else []
            )
            posture = trade_posture.resolve_posture(
                declared_strategy=p, power_rank=3, league_size=teams, record={"wins": 5, "losses": 2}
            )
            stamped = trade_posture.stamp_records(hub, posture)
            plan = gm_plan.build_gm_plan(
                team_stance=STANCE[p], season_phase=gm_plan.PHASE_EARLY_SEASON, total_teams=teams, trade_ideas=stamped
            )
            out[f"{label}|{p}"] = {
                "hub": [_idea_row(i, x) for i, x in enumerate(hub)],
                "finder": [_idea_row(i, x) for i, x in enumerate(fin)],
                "stamped": [[x.get("posture_note"), x.get("posture_alignment"), x.get("posture_label")] for x in stamped],
                "gm_plan_sha": _digest(plan),
                "gm_plan_trade_items": [str(i)[:200] for fa in plan.get("focus_areas", []) for i in fa.get("items", [])][:6],
            }
    return _json(out)


MULTI_SPECS = (("8t-1qb", 8, 22, "1QB"), ("10t-sf", 10, 24, "Superflex"), ("12t-1qb", 12, 22, "1QB"))


def multi_team_snapshot(specs=MULTI_SPECS):
    from freezegun import freeze_time

    from modules import league_rankings, league_value_settings, nfl_schedule, sleeper, trade_ideas
    from modules import multi_team_trade_engine as engine
    from modules import multi_team_trade_finder as finder
    from modules import roster_value_model as rvm
    from scripts.profile_trade_hub import FixtureSpec, build_fixture

    out = {}
    for label, teams, size, qbf in specs:
        for p in POSTURES:
            fx = build_fixture(FixtureSpec(label, teams, size, qbf, strategy=p))
            fx["settings"] = dict(fx["settings"], current_week=8, max_roster_size=size + 4, bench_count=size - 9)
            players = fx["players"].copy()
            pid = players["player_id"].astype(str)
            for col in ("dynasty_score", "value_score"):
                # one RB / QB / WR per team priced equally (a fair cycle can exist); every third team's QBs are weak
                # distinct per-player offsets: exact ties would let float noise (platform, BLAS) reorder the search
                balanced = pid.str.endswith(("-17", "-14", "-10"))
                owner = pid.str.slice(1, 3).astype(int)
                slot = pid.str.slice(4, 6).astype(int)
                players.loc[balanced, col] = 4000.0 + ((owner * 13 + slot * 7) % 29 * 3)[balanced]
                weak = pid.str.slice(1, 3).astype(int).mod(3).eq(0) & pid.str.endswith(("-00", "-01", "-15"))
                players.loc[weak, col] = 3200.0
            fx["players"] = players
            trade_ideas.clear_team_shape_memos()
            nfl_schedule.clear_load_games_cache()
            with patch.object(nfl_schedule, "load_games", lambda *a, **k: pd.DataFrame()), \
                 patch.object(nfl_schedule, "team_bye_week", lambda team, season, **kw: 99), \
                 patch.object(sleeper, "get_league", lambda lid: {"league_id": lid, "total_rosters": len(fx["rosters"])}), \
                 patch.object(sleeper, "get_rosters", lambda lid: fx["rosters"]), \
                 patch.object(sleeper, "get_league_roster_profiles", lambda lid: {}), \
                 patch.object(league_value_settings, "detect_league_value_settings_from_payload", lambda league: fx["settings"]), \
                 patch.object(league_value_settings, "build_valued_players_frame_cached", lambda **k: fx["players"]), \
                 patch.object(league_rankings, "build_league_summary_and_draft_capital_cached", lambda **k: (fx["summary"], None)), \
                 patch.object(league_rankings, "build_league_rankings_frame_cached", lambda **k: pd.DataFrame()), \
                 patch.object(trade_ideas, "get_sleeper_adapter", lambda *a, **k: fx["adapter"]), \
                 freeze_time("2026-10-28T12:00:00"):
                ctx = engine.build_context(league_id="fixture-league", lens="Dynasty", players_db_path=":memory:")
                if isinstance(ctx, dict):
                    out[f"{label}|{p}"] = {"ctx": ctx}
                    continue
                needs = {}
                for rid in ctx.by_rid:
                    wants = (("WR",), ("RB",), ("QB",))[(int(rid) - 1) % 3]
                    needs[rid] = {"positions": [
                        {"position": pos, "tier": "primary" if pos in wants else "covered", "score": 1.0,
                         "starters": {"QB": 1, "RB": 4, "WR": 3, "TE": 1}[pos], "surplus_player_ids": []}
                        for pos in ("QB", "RB", "WR", "TE")]}
                ctx._needs = rvm.LeagueNeeds(by_roster=needs, status={})
                res = finder.find_three_team_ideas(ctx, "1", time_budget=1e9)
            res = _json(res)
            out[f"{label}|{p}"] = {
                "sha": _digest(res),
                "reason": (res.get("search") or {}).get("reason"),
                "ideas": [
                    [sorted((f["id"], f["to_roster_id"]) for f in i["flows"]), [t["tone"] for t in i["teams"]]]
                    for i in res.get("ideas") or ()
                ],
            }
    return _json(out)


def coherence_snapshot():
    """Everything the posture-coherence flag (DYNASTYGM_POSTURE_COHERENCE_V1) can move, captured with it ON."""

    from modules import posture_model, trade_grade, trade_ideas

    send = {"asset_type": "pick"}
    return _json({
        "injury_weight": {p: trade_grade.INJURY_POSTURE_WEIGHTS.get(p) for p in POSTURES},
        "pick_sale_priority": {
            f"{p}|{n}": list(trade_ideas._pick_send_posture_terms([send] * n, {"strategy": p})) for p in POSTURES for n in (1, 2)
        },
        "pick_want": {f"{g}|{p}": posture_model.pick_want(g, p) for g, p in (
            ("contender", "contender"), ("contender", "fringe_contender"), ("retool", "retool"),
            ("rebuild", "rebuild"), ("rebuild", "tank"))},
        "tables": tables_snapshot(),
        "grade": grade_snapshot(),
        "engine": engine_snapshot(),
        "multi": multi_team_snapshot(),
    })


if __name__ == "__main__" and os.environ.get("POSTURE_GOLDEN_MODE") == "coherence":  # subprocess entry, flag ON
    print("GOLDEN_JSON=" + json.dumps(coherence_snapshot(), sort_keys=True))
elif __name__ == "__main__":  # subprocess entry: cheap snapshots under the caller's env flags
    print("GOLDEN_JSON=" + json.dumps({"tables": tables_snapshot(), "grade": grade_snapshot()}, sort_keys=True))
