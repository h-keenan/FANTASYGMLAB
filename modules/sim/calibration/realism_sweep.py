"""Realism sweep: many whole GM games across league shapes, measured against real fantasy football.

    python -m modules.sim.calibration.realism_sweep seasons [--seeds 4] [--json out.json]   # redraft shapes: scoring, standings, parity, injuries, ADP
    python -m modules.sim.calibration.realism_sweep dynasty [--seeds 3]                        # rookies, aging, retirements, 5-season drift
    python -m modules.sim.calibration.realism_sweep real                                        # the real-data yardsticks these are compared with
    python -m modules.sim.calibration.realism_sweep exploit [--seeds 3]                        # a greedy trader against the AI trade desk
    (API latency and payload sizes live in tests/test_sim_latency_probe.py: they need the web framework)

Pure stdlib + numpy + modules.sim. Never touches data/players.db.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import replace
from typing import Any

import numpy as np

from modules.sim import game_dynasty as dyn
from modules.sim import game_scoring
from modules.sim.calibration import dataset, tail_report
from modules.sim.game_draft import DraftContext, auto_for_user, run_ai_picks
from modules.sim.game_engine import advance, finish_draft
from modules.sim.game_eval import Evaluator
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import GameSettings, slot_positions

CORE = ("QB", "RB", "WR", "TE")

SHAPES: dict[str, dict[str, Any]] = {
    "12t ppr": {"teams": 12, "scoring": "ppr"},
    "12t half": {"teams": 12, "scoring": "half"},
    "12t std": {"teams": 12, "scoring": "std"},
    "8t ppr": {"teams": 8, "scoring": "ppr"},
    "10t ppr": {"teams": 10, "scoring": "ppr"},
    "14t ppr": {"teams": 14, "scoring": "ppr"},
    "12t superflex": {"teams": 12, "scoring": "ppr", "superflex": True},
    "12t def+k": {"teams": 12, "scoring": "ppr", "include_def": True},
    "12t no-k": {"teams": 12, "scoring": "ppr", "include_k": False},
    "12t te-premium": {"teams": 12, "scoring": "ppr", "te_premium": 0.5},
}


def spearman(a, b) -> float:
    ra = np.argsort(np.argsort(a))
    rb = np.argsort(np.argsort(b))
    if len(ra) < 3:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


# --------------------------------------------------------------------------- real yardsticks


def real_yardsticks() -> dict[str, Any]:
    rows = dataset.load_panel()
    out: dict[str, Any] = {}
    by = defaultdict(list)
    for r in rows:
        by[(r["season"], r["pos"])].append(r)
    slot = {}
    for pos, ranks in (("QB", 12), ("RB", 24), ("WR", 24), ("TE", 12), ("K", 12)):
        vals = []
        for (season, p), rs in by.items():
            if p != pos:
                continue
            rs = sorted(rs, key=lambda r: (r["adp"] if r["adp"] is not None else 999, -(r["proj_ppg"] or 0)))[:ranks]
            for r in rs:
                pts = [w[1] for w in r["weeks"] if w and w[0]]
                if len(pts) >= 6:
                    vals.append(np.mean(pts))
        slot[pos] = round(float(np.mean(vals)), 2) if vals else None
    out["top_by_adp_ppg"] = slot
    # ADP rank vs season finish (PPR points per game), per position: Spearman and top-12 hit rate
    sp, hit = {}, {}
    for pos in CORE:
        cs, hs = [], []
        for (season, p), rs in by.items():
            if p != pos:
                continue
            rs = [r for r in rs if r["adp"] is not None and sum(1 for w in r["weeks"] if w and w[0]) >= 8]
            if len(rs) < 20:
                continue
            adp = [r["adp"] for r in rs]
            ppg = [-np.mean([w[1] for w in r["weeks"] if w and w[0]]) for r in rs]
            cs.append(spearman(adp, ppg))
            top = sorted(range(len(rs)), key=lambda i: adp[i])[:12]
            fin = set(sorted(range(len(rs)), key=lambda i: ppg[i])[:12])
            hs.append(len(fin & set(top)) / 12)
        sp[pos], hit[pos] = round(float(np.mean(cs)), 3), round(float(np.mean(hs)), 3)
    out["adp_vs_finish_spearman"], out["adp_top12_finish_top12"] = sp, hit
    # games missed per player-season of drafted skill players and the share with >= 3 missed
    miss, miss3 = [], []
    for r in rows:
        if r["pos"] in CORE and r["adp"] is not None and r["adp"] <= 120:
            played = sum(1 for w in r["weeks"] if w and w[0])
            avail = sum(1 for w in r["weeks"] if w is not None)
            miss.append(avail - played)
            miss3.append(avail - played >= 3)
    out["games_missed_per_season_adp120"] = round(float(np.mean(miss)), 2)
    out["share_missing_3plus"] = round(float(np.mean(miss3)), 3)
    return out


# ----------------------------------------------------------------------------- redraft sweep


def play_redraft(pool, byes, shape: dict, seed: int, model_id: str, ai_v: int | None = None) -> dict[str, Any]:
    settings = GameSettings.parse({"user_slot": 1 + seed % shape.get("teams", 12), **shape})
    if ai_v is not None:
        settings = replace(settings, ai_v=ai_v)
    snap = build_snapshot(pool, byes, settings, seed, scoring_model=model_id)
    state = GameState(snap)
    em = Emitter(state, snap)
    run_ai_picks(DraftContext(snap, state), em, seed)
    auto_for_user(DraftContext(snap, state), em, seed)
    finish_draft(em, snap, state, seed)
    slot_pts: dict[str, list[float]] = defaultdict(list)
    week_scores: dict[int, list[float]] = defaultdict(list)
    all_events: list[dict] = list(em.events)
    while state.status in ("in_season", "playoffs"):
        w = state.week
        em = Emitter(state, snap)
        advance(em, snap, state, seed)
        all_events.extend(em.events)
        if state.week == w + 1 and w <= settings.regular_weeks:
            for tid in snap.tids:
                tot = 0.0
                for slot, pid in state.lineups[tid]:
                    pts = state.points.get(pid, [])
                    v = pts[w - 1] if pid and len(pts) >= w and pts[w - 1] is not None else 0.0
                    slot_pts[slot].append(v)
                    tot += v
                week_scores[w].append(tot)
    return {"snap": snap, "state": state, "events": all_events, "slot_pts": slot_pts, "week_scores": week_scores}


def season_metrics(g: dict[str, Any]) -> dict[str, Any]:
    snap, state = g["snap"], g["state"]
    S = snap.settings
    games = S.regular_weeks
    teams = snap.tids
    win = np.array([(state.stand[t]["w"] + 0.5 * state.stand[t]["t"]) / games for t in teams])
    pf = np.array([state.stand[t]["pf"] for t in teams])
    ties = sum(state.stand[t]["t"] for t in teams) / 2
    out: dict[str, Any] = {
        "win_pct_sd": float(win.std()), "pf_cv": float(pf.std() / pf.mean()), "ties": ties,
        "pf_rank_vs_wins": spearman(pf, win), "best_wins": float(win.max() * games), "worst_wins": float(win.min() * games),
    }
    pl = state.playoff or {}
    seeds = pl.get("seeds") or []
    champ = state.champion
    out["champ_seed"] = seeds.index(champ) + 1 if champ in seeds else None
    out["n_seeds"] = len(seeds)
    from modules.sim.game_engine import rank_teams
    out["seed_order_matches_rank"] = bool(seeds == rank_teams(snap, state)[: len(seeds)]) if seeds else True
    # per-slot means
    sp = g["slot_pts"]
    out["slot_mean"] = {s: float(np.mean(v)) for s, v in sp.items()}
    out["team_week_mean"] = float(np.mean([x for v in g["week_scores"].values() for x in v]))
    out["team_week_sd"] = float(np.std([x for v in g["week_scores"].values() for x in v]))
    out["week_means"] = [float(np.mean(g["week_scores"][w])) for w in sorted(g["week_scores"])]
    # injuries from the events
    inj = Counter()
    dur = defaultdict(list)
    games_by_pos = Counter()
    for pid, hist in state.points.items():
        pos = snap.players[pid].pos
        games_by_pos[pos] += sum(1 for x in hist[:games] if x is not None)
    for e in g["events"]:
        if e["type"] == "injury":
            for pid, wk in e["payload"]["items"]:
                pos = snap.players[pid].pos
                inj[pos] += 1
                dur[pos].append(wk)
    miss, miss3 = [], []
    for pid in snap.pids:
        p = snap.players[pid]
        if p.pos in CORE and p.adp <= 120:
            hist = state.points.get(pid, [])[:games]
            sched = games - (1 if 1 <= snap.bye_of(pid) <= games else 0)
            played = sum(1 for x in hist if x is not None)
            miss.append(max(0, sched - played))
            miss3.append(sched - played >= 3)
    out["missed_per_season_adp120"] = float(np.mean(miss)) if miss else None
    out["missed_3plus_share"] = float(np.mean(miss3)) if miss3 else None
    out["injury_per_100_games"] = {p: round(100 * inj[p] / max(1, games_by_pos[p]), 2) for p in CORE + ("K",)}
    out["injury_mean_weeks"] = {p: round(float(np.mean(v)), 2) for p, v in dur.items() if v}
    out["injury_p_long"] = {p: round(float(np.mean([x >= 9 for x in v])), 3) for p, v in dur.items() if v}
    # ADP vs outcome (drafted players, by position): spearman of ADP and season points; top-12 hit rate
    sp_adp, hit = {}, {}
    for pos in CORE:
        ids = [p for p in snap.pids if snap.players[p].pos == pos and len([x for x in state.points.get(p, []) if x is not None]) >= 8]
        if len(ids) < 20:
            continue
        adp = [snap.players[p].adp for p in ids]
        ppg = [-np.mean([x for x in state.points[p] if x is not None]) for p in ids]
        sp_adp[pos] = spearman(adp, ppg)
        top = set(sorted(range(len(ids)), key=lambda i: adp[i])[:12])
        fin = set(sorted(range(len(ids)), key=lambda i: ppg[i])[:12])
        hit[pos] = len(top & fin) / 12
    out["adp_vs_finish_spearman"], out["adp_top12_finish_top12"] = sp_adp, hit
    # transactions
    ai = [t for t in state.transactions]
    out["tx"] = Counter(t["type"] for t in ai)
    out["trades_ai_ai"] = sum(1 for e in g["events"] if e["type"] == "trade" and e["payload"].get("source") == "ai_ai")
    out["waiver_adds_ai"] = sum(1 for e in g["events"] if e["type"] == "waiver_result" and e["payload"].get("ok") and not snap.team(e["payload"]["team"]).is_user)
    out["offers"] = sum(1 for e in g["events"] if e["type"] == "inbox_offer")
    gaps = []
    for e in g["events"]:
        if e["type"] == "trade" and e["payload"].get("source") == "ai_ai":
            give = sum(snap.players[x].market for x in e["payload"]["give"] if x in snap.players)
            get = sum(snap.players[x].market for x in e["payload"]["get"] if x in snap.players)
            if max(give, get) > 0:
                gaps.append(abs(give - get) / max(give, get))
    out["trade_market_gap"] = float(np.mean(gaps)) if gaps else None
    return out


def agg(vals: list) -> dict[str, float]:
    a = np.array([v for v in vals if v is not None], dtype=float)
    return {"mean": round(float(a.mean()), 3), "sd": round(float(a.std()), 3), "min": round(float(a.min()), 3), "max": round(float(a.max()), 3)} if len(a) else {}


def seasons(seeds: int, shapes: list[str] | None = None) -> dict[str, Any]:
    model_id = game_scoring.default_model().model_id
    pool, byes = tail_report.pool_from_panel(dataset.load_panel())
    out: dict[str, Any] = {"model": model_id}
    champ_by_seed: dict[str, Counter] = {}
    for name in shapes or list(SHAPES):
        shape = SHAPES[name]
        ms = [season_metrics(play_redraft(pool, byes, shape, s, model_id)) for s in range(1, seeds + 1)]
        slot_keys = sorted({k for m in ms for k in m["slot_mean"]})
        out[name] = {
            "win_pct_sd": agg([m["win_pct_sd"] for m in ms]), "pf_cv": agg([m["pf_cv"] for m in ms]),
            "pf_rank_vs_wins": agg([m["pf_rank_vs_wins"] for m in ms]), "ties_per_season": agg([m["ties"] for m in ms]),
            "best_wins": agg([m["best_wins"] for m in ms]), "worst_wins": agg([m["worst_wins"] for m in ms]),
            "team_week_mean": agg([m["team_week_mean"] for m in ms]), "team_week_sd": agg([m["team_week_sd"] for m in ms]),
            "slot_mean": {k: round(float(np.mean([m["slot_mean"].get(k, np.nan) for m in ms])), 2) for k in slot_keys},
            "week_means": [round(float(np.mean([m["week_means"][i] for m in ms if i < len(m["week_means"])])), 1) for i in range(max(len(m["week_means"]) for m in ms))],
            "champ_seed": dict(Counter(m["champ_seed"] for m in ms)), "n_seeds": ms[0]["n_seeds"],
            "seed_order_matches_rank": all(m["seed_order_matches_rank"] for m in ms),
            "missed_per_season_adp120": agg([m["missed_per_season_adp120"] for m in ms]), "missed_3plus_share": agg([m["missed_3plus_share"] for m in ms]),
            "injury_per_100_games": {p: round(float(np.mean([m["injury_per_100_games"].get(p, 0) for m in ms])), 2) for p in CORE + ("K",)},
            "injury_mean_weeks": {p: round(float(np.mean([m["injury_mean_weeks"].get(p, np.nan) for m in ms])), 2) for p in CORE},
            "injury_p_long": {p: round(float(np.mean([m["injury_p_long"].get(p, np.nan) for m in ms])), 3) for p in CORE},
            "adp_vs_finish_spearman": {p: round(float(np.mean([m["adp_vs_finish_spearman"].get(p, np.nan) for m in ms])), 3) for p in CORE},
            "adp_top12_finish_top12": {p: round(float(np.mean([m["adp_top12_finish_top12"].get(p, np.nan) for m in ms])), 3) for p in CORE},
            "ai_trade_market_gap": agg([m["trade_market_gap"] for m in ms]), "ai_trades": agg([m["trades_ai_ai"] for m in ms]), "ai_waiver_adds": agg([m["waiver_adds_ai"] for m in ms]), "offers": agg([m["offers"] for m in ms]),
        }
    return out


# ----------------------------------------------------------------------------------- dynasty


AGING_V: int | None = None


def dynasty(seeds: int, n_seasons: int = 5) -> dict[str, Any]:
    from modules.sim.game_actions import cut_player
    from modules.sim.game_eval import USER_PARAMS
    from modules.sim.synthetic import build_synthetic_pool

    model_id = game_scoring.default_model().model_id
    pool, byes = tail_report.pool_from_panel(dataset.load_panel())
    ret_age: list[tuple[str, float]] = []
    ratios: dict[str, dict[int, list[float]]] = {p: defaultdict(list) for p in CORE}
    est: dict[tuple[str, int], list[float]] = defaultdict(list)  # the calibration estimator (age_curve.py): ppg > 3, 8+ games both years, 2-year age buckets
    est_vet: dict[tuple[str, int], list[float]] = defaultdict(list)  # the same, original-pool veterans only
    est_sel: dict[tuple[str, int], list[float]] = defaultdict(list)  # the same, and only players still in the draftable pool (ADP top 200) next year: the real panel's survivorship
    rookies: list[dict[str, Any]] = []
    for seed in range(1, seeds + 1):
        base = GameSettings.parse({"mode": "dynasty", "teams": 12, "user_slot": 3, "start_year": 2026, "seasons": n_seasons, "rookie_rounds": 3, "scoring": "ppr"})
        if AGING_V is not None:  # --aging-v: before/after runs of the retirement curves
            base = replace(base, aging_v=AGING_V)
        root = build_snapshot(pool, byes, base, seed, scoring_model=model_id)
        state = GameState(root)
        em = Emitter(state, root)
        auto_for_user(DraftContext(root, state), em, seed)
        finish_draft(em, root, state, seed)
        season_ppg: dict[int, dict[str, float]] = {}
        while True:
            snap = root.season_view(state.view_no)
            sd = dyn.season_seed(seed, state.view_no)
            em.snap = snap
            while state.status in ("in_season", "playoffs"):
                advance(em, snap, state, sd)
            snap = root.season_view(state.view_no) if state.status == "offseason" else snap
            season_ppg[state.season_no] = {p: float(np.mean([x for x in h[:14] if x is not None])) for p, h in state.points.items() if len([x for x in h[:14] if x is not None]) >= 8}
            if state.status != "offseason":
                break
            sd = dyn.season_seed(seed, state.view_no)
            em.snap = snap
            dyn.start_rookie_draft(em)
            dyn.run_ai_rookie_picks(em, sd)
            dyn.auto_rookie_draft(em, sd)
            user = snap.user_team.tid
            while len(state.rosters[user]) > snap.settings.roster_limit:
                ev = Evaluator(snap, state)
                cut_player(em, min(state.rosters[user], key=lambda p: (ev.worth(USER_PARAMS, p), p)))
            dyn.start_next_season(em, sd)
        views = {n: root.season_view(n) for n in range(1, n_seasons + 1)}
        for n in range(1, n_seasons):
            a, b = views[n], views[n + 1]
            for pid, p in a.players.items():
                if pid not in b.players:
                    ret_age.append((p.pos, p.age + 1))
                elif p.pos in CORE and pid in season_ppg.get(n, {}) and pid in season_ppg.get(n + 1, {}) and not p.extra.get("is_rookie"):
                    if season_ppg[n][pid] >= 6:
                        ratios[p.pos][int(p.age)].append(season_ppg[n + 1][pid] / season_ppg[n][pid])
                    if season_ppg[n][pid] > 3:
                        est[(p.pos, int(p.age // 2) * 2)].append(season_ppg[n + 1][pid] / season_ppg[n][pid])
                        if not p.extra.get("dev_arch"):
                            est_vet[(p.pos, int(p.age // 2) * 2)].append(season_ppg[n + 1][pid] / season_ppg[n][pid])
                            if b.players[pid].adp <= 200:
                                est_sel[(p.pos, int(p.age // 2) * 2)].append(season_ppg[n + 1][pid] / season_ppg[n][pid])
        for n in range(2, n_seasons + 1):
            v = views[n]
            cls = [p for p in v.players.values() if p.extra.get("is_rookie") and p.extra.get("draft_year")]
            for p in cls:
                rookies.append({"season": n, "pid": p.pid, "pos": p.pos, "rank": p.extra.get("class_rank"), "mean": p.mean, "ppg1": season_ppg.get(n, {}).get(p.pid),
                                "ppg3": season_ppg.get(n + 2, {}).get(p.pid), "proj_rank_in_pos": None})
    out: dict[str, Any] = {}
    out["retire_age_by_pos"] = {p: {"mean": round(float(np.mean([a for q, a in ret_age if q == p])), 1), "n": sum(1 for q, _ in ret_age if q == p)} for p in (*CORE, "K")}
    out["aging_ratio_by_age"] = {
        p: {str(a): round(float(np.median(v)), 3) for a, v in sorted(d.items()) if len(v) >= 6} for p, d in ratios.items()
    }
    from modules.sim.calibration import age_curve

    real = age_curve.curve_table()
    out["aging_vs_real_median_ratio"] = {
        f"{pos} {age}-{age + 1}": {"real": round(real[(pos, age)][1], 3), "real_n": real[(pos, age)][0],
                                    "sim_all": round(float(np.median(est[(pos, age)])), 3) if len(est.get((pos, age), ())) >= 8 else None,
                                    "sim_vets": round(float(np.median(est_vet[(pos, age)])), 3) if len(est_vet.get((pos, age), ())) >= 8 else None,
                                    "sim_vets_still_in_pool": round(float(np.median(est_sel[(pos, age)])), 3) if len(est_sel.get((pos, age), ())) >= 8 else None,
                                    "sim_n": len(est.get((pos, age), ()))}
        for (pos, age) in sorted(real) if pos in CORE
    }
    # rookie draft capital -> outcomes
    done = [r for r in rookies if r["ppg1"] is not None and r["rank"]]
    out["rookies"] = {"n": len(rookies), "with_year1_ppg": len(done)}
    if done:
        ranks = np.array([r["rank"] for r in done])
        ppg1 = np.array([r["ppg1"] for r in done])
        out["rookies"]["rank_vs_year1_ppg_spearman"] = round(spearman(ranks, -ppg1), 3)
        bins = {"1-12": (1, 12), "13-24": (13, 24), "25-48": (25, 48), "49+": (49, 999)}
        out["rookies"]["year1_ppg_by_class_rank"] = {k: round(float(np.mean([r["ppg1"] for r in done if lo <= r["rank"] <= hi])), 2) for k, (lo, hi) in bins.items() if any(lo <= r["rank"] <= hi for r in done)}
        out["rookies"]["share_year1_over_8ppg_by_class_rank"] = {k: round(float(np.mean([r["ppg1"] >= 8 for r in done if lo <= r["rank"] <= hi])), 3) for k, (lo, hi) in bins.items() if any(lo <= r["rank"] <= hi for r in done)}
    return out


# ------------------------------------------------------------------------------------ exploits


def exploit_probe(seeds: int = 3, mode: str = "dynasty", objective: str = "assets") -> dict[str, Any]:
    """A greedy trader that only sends 1-for-1 trades the AI accepts. ``objective`` picks what it maximizes each time: the user's
    neutral asset value (``assets``: market / long-horizon value of players plus pick value), or the lineup (``lineup``). Reports what
    that buys: asset value and lineup after the trades, and the realised season (points for and wins) against the same game with no
    trades. If the AI can be farmed this finds it; a modest gain in the objective that does not turn into wins is persona disagreement,
    not an exploit."""

    from modules.sim import game_actions as act
    from modules.sim.game_ai import TradeDesk
    from modules.sim.game_types import GameError

    model_id = game_scoring.default_model().model_id
    pool, byes = tail_report.pool_from_panel(dataset.load_panel())
    out: list[dict[str, Any]] = []
    for seed in range(1, seeds + 1):
        res = {}
        for variant in ("baseline", "trader"):
            raw = {"teams": 12, "user_slot": 4, "scoring": "ppr"}
            if mode == "dynasty":
                raw.update(mode="dynasty", seasons=5, rookie_rounds=3, start_year=2026)
            snap = build_snapshot(pool, byes, GameSettings.parse(raw), seed, scoring_model=model_id)
            state = GameState(snap)
            em = Emitter(state, snap)
            run_ai_picks(DraftContext(snap, state), em, seed)
            auto_for_user(DraftContext(snap, state), em, seed)
            finish_draft(em, snap, state, seed)
            user = snap.user_team.tid

            def value_of(ev: Evaluator, pid: str) -> float:
                return ev.base_value(pid) if pid in snap.players else ev.pick_value(pid)

            def assets_value(ev: Evaluator) -> float:
                return sum(value_of(ev, p) for p in [*state.holdings(user), *(state.picks_of(user) if snap.settings.dynasty else [])])

            ev0 = Evaluator(snap, state)
            v0, l0 = assets_value(ev0), ev0.lineup_total(state.rosters[user])
            sent = 0
            while state.status == "in_season" and variant == "trader" and state.week < snap.settings.trade_deadline_week:
                for _ in range(8):
                    ev = Evaluator(snap, state)
                    desk = TradeDesk(ev, seed, state.week)
                    base_assets, base_lineup = assets_value(ev), ev.lineup_total(state.rosters[user])
                    best = None
                    mine = desk.tradable(user)
                    for tid in snap.tids:
                        if tid == user:
                            continue
                        theirs = sorted(desk.tradable(tid), key=lambda p: -value_of(ev, p))[:10]
                        for give in sorted(mine, key=lambda p: value_of(ev, p))[:12]:
                            for get in theirs:
                                if not desk.ai_accepts(tid, [give], [get])[0]:
                                    continue
                                if objective == "assets":
                                    gain = value_of(ev, get) - value_of(ev, give)
                                else:
                                    gain = ev.lineup_total([p for p in state.rosters[user] if p != give] + ([get] if get in snap.players else [])) - base_lineup
                                if best is None or gain > best[0]:
                                    best = (gain, tid, give, get)
                    if best is None or best[0] <= (0.5 if objective == "assets" else 0.2):
                        break
                    try:
                        _, trade = act.send_trade(em, TradeDesk(Evaluator(snap, state), seed, state.week), best[1], [best[2]], [best[3]])
                    except (GameError, ValueError):
                        break
                    if trade is None:
                        break
                    sent += 1
                em = Emitter(state, snap)
                advance(em, snap, state, seed)
            while state.status in ("in_season", "playoffs"):
                em = Emitter(state, snap)
                advance(em, snap, state, seed)
            ev1 = Evaluator(snap, state)
            rec = state.stand[user]
            res[variant] = {"trades": sent, "wins": rec["w"], "pf": round(rec["pf"], 1), "assets_before": round(v0, 1), "assets_after": round(assets_value(ev1), 1),
                            "lineup_before": round(l0, 1), "lineup_after_season": round(ev1.lineup_total(state.rosters[user]), 1)}
        out.append({"seed": seed, **res})
    return {"mode": mode, "objective": objective, "runs": out}


# ----------------------------------------------------------------- 20-season exploit bots


def exploit_long(strategy: str, seed: int, n_seasons: int = 20, trade_weeks: int = 4, per_week: int = 2) -> dict[str, Any]:
    """One user bot against the AI league for a whole dynasty (12 teams, 3 rookie rounds, player-model default, ai_v default).

    ``balanced``: auto lineup, auto rookie draft, nothing else. ``stacker``: every early week, up to ``per_week`` AI-accepted 1-for-1 trades that raise
    its asset value (market / long-horizon value of players plus pick value). ``hoarder``: the same but only trades that bring back a pick.
    ``churn``: waiver claims every week (best free agent by dynasty value for the weakest bench player), no trades. ``lineup``: AI-accepted trades that
    raise its lineup. Reports per season: wins, rank, title, asset value and its share of the league's, pick count, plus league-wide asset totals."""

    from modules.sim import game_actions as act
    from modules.sim.game_ai import TradeDesk
    from modules.sim.game_eval import USER_PARAMS
    from modules.sim.game_types import GameError

    model_id = game_scoring.default_model().model_id
    pool, byes = tail_report.pool_from_panel(dataset.load_panel())
    base = GameSettings.parse({"mode": "dynasty", "teams": 12, "user_slot": 4, "start_year": 2026, "seasons": 5, "rookie_rounds": 3, "scoring": "ppr"})
    settings = replace(base, seasons=n_seasons)
    root = build_snapshot(pool, byes, settings, seed, scoring_model=model_id)
    state = GameState(root)
    em = Emitter(state, root)
    auto_for_user(DraftContext(root, state), em, seed)
    finish_draft(em, root, state, seed)
    user = root.user_team.tid
    rows: list[dict[str, Any]] = []

    def value_of(ev, snap, pid):
        return ev.base_value(pid) if pid in snap.players else ev.pick_value(pid)

    def team_assets(ev, snap, tid):
        return sum(value_of(ev, snap, p) for p in [*state.holdings(tid), *state.picks_of(tid)])

    def trade_loop(snap, sd):
        for _ in range(per_week):
            ev = Evaluator(snap, state)
            desk = TradeDesk(ev, sd, state.week)
            best = None
            lineup0 = ev.lineup_total(state.rosters[user])
            mine = sorted(desk.tradable(user), key=lambda p: value_of(ev, snap, p))[:8]
            for tid in snap.tids:
                if tid == user:
                    continue
                theirs = sorted(desk.tradable(tid), key=lambda p: -value_of(ev, snap, p))[:8]
                if strategy == "farmer":  # consolidation and spreading: two for one, one for two, judged on the sum of neutral values
                    for i in range(len(mine)):
                        for j in range(i + 1, len(mine)):
                            for get in theirs[:5]:
                                give2 = [mine[i], mine[j]]
                                if desk.ai_accepts(tid, give2, [get])[0]:
                                    gain = value_of(ev, snap, get) - sum(value_of(ev, snap, g) for g in give2)
                                    if best is None or gain > best[0]:
                                        best = (gain, tid, give2, [get])
                    for give in mine[:4]:
                        for a2 in range(min(5, len(theirs))):
                            for b2 in range(a2 + 1, min(5, len(theirs))):
                                get2 = [theirs[a2], theirs[b2]]
                                if desk.ai_accepts(tid, [give], get2)[0]:
                                    gain = sum(value_of(ev, snap, g) for g in get2) - value_of(ev, snap, give)
                                    if best is None or gain > best[0]:
                                        best = (gain, tid, [give], get2)
                for give in mine:
                    for get in theirs:
                        if strategy == "hoarder" and get in snap.players:
                            continue
                        if not desk.ai_accepts(tid, [give], [get])[0]:
                            continue
                        if strategy == "lineup":
                            gain = ev.lineup_total([p for p in state.rosters[user] if p != give] + ([get] if get in snap.players else [])) - lineup0
                        else:
                            gain = value_of(ev, snap, get) - value_of(ev, snap, give)
                        if best is None or gain > best[0]:
                            best = (gain, tid, [give], [get])
            if best is None or best[0] <= (0.2 if strategy == "lineup" else 0.5):
                return
            try:
                _, trade = act.send_trade(em, TradeDesk(Evaluator(snap, state), sd, state.week), best[1], best[2], best[3])
            except (GameError, ValueError):
                return
            if trade is None:
                return

    def churn(snap):
        ev = Evaluator(snap, state)
        owned = state.owner_map()
        free = sorted((p for p in snap.pids if p not in owned and snap.players[p].pos in CORE and state.out.get(p, 0) == 0), key=lambda p: -ev.base_value(p))[:6]
        lineup_ids = {pid for _, pid in ev.best_lineup(state.rosters[user], state.week)[0] if pid}
        bench = sorted((p for p in state.rosters[user] if p not in lineup_ids), key=lambda p: ev.base_value(p))
        for add, drop in zip(free[:3], bench[:3]):
            if ev.base_value(add) > ev.base_value(drop):
                try:
                    act.queue_claim(em, add, drop, None)
                except (GameError, ValueError):
                    pass

    t0 = __import__("time").time()
    while True:
        snap = root.season_view(state.view_no)
        sd = dyn.season_seed(seed, state.view_no)
        em.snap = snap
        ev = Evaluator(snap, state)
        a0 = team_assets(ev, snap, user)
        league0 = float(np.mean([team_assets(ev, snap, t) for t in snap.tids]))
        while state.status in ("in_season", "playoffs"):
            if state.status == "in_season":
                if strategy in ("stacker", "hoarder", "lineup", "farmer") and state.week <= trade_weeks and state.week < snap.settings.trade_deadline_week:
                    trade_loop(snap, sd)
                if strategy == "churn":
                    churn(snap)
                over = len(state.rosters[user]) - snap.settings.roster_limit
                for _ in range(max(0, over)):
                    ev = Evaluator(snap, state)
                    act.cut_player(em, min(state.rosters[user], key=lambda p: (ev.worth(USER_PARAMS, p), p)))
                act.auto_lineup(em)
            advance(em, snap, state, sd)
        archive = state.seasons[-1] if state.seasons else None
        you = archive["you"] if archive else {}
        ev = Evaluator(snap, state)
        rows.append({
            "season": state.season_no, "wins": you.get("wins"), "rank": you.get("rank"), "title": bool(archive and archive["champion"] and archive["champion"]["is_you"]),
            "assets_start": round(a0, 1), "assets_end": round(team_assets(ev, snap, user), 1), "league_mean_start": round(league0, 1),
            "league_mean_end": round(float(np.mean([team_assets(ev, snap, t) for t in snap.tids])), 1),
            "picks": len(state.picks_of(user)),
        })
        if state.status != "offseason":
            break
        snap = root.season_view(state.view_no)
        sd = dyn.season_seed(seed, state.view_no)
        em.snap = snap
        dyn.start_rookie_draft(em)
        dyn.run_ai_rookie_picks(em, sd)
        dyn.auto_rookie_draft(em, sd)
        while len(state.rosters[user]) > snap.settings.roster_limit:
            ev = Evaluator(snap, state)
            act.cut_player(em, min(state.rosters[user], key=lambda p: (ev.worth(USER_PARAMS, p), p)))
        dyn.start_next_season(em, sd)
    return {"strategy": strategy, "seed": seed, "seasons": rows, "wall_s": round(__import__("time").time() - t0, 1)}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=["seasons", "dynasty", "real", "exploit", "exploit20"])
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--shapes", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--aging-v", type=int, default=None, help="dynasty command: force the aging generation (0 = before position hazard curves)")
    args = ap.parse_args(argv)
    global AGING_V
    AGING_V = args.aging_v
    if args.cmd == "real":
        res = real_yardsticks()
    elif args.cmd == "exploit20":
        res = exploit_long(args.shapes or "balanced", args.seeds, 20)
    elif args.cmd == "exploit":
        res = {f"{m}/{o}": exploit_probe(args.seeds, m, o) for m in ("redraft", "dynasty") for o in ("assets", "lineup")}
    elif args.cmd == "seasons":
        res = seasons(args.seeds, [s for s in args.shapes.split(",") if s] or None)
    else:
        res = dynasty(args.seeds)
    text = json.dumps(res, indent=1, default=str)
    if args.json:
        open(args.json, "w").write(text)
    print(text)



if __name__ == "__main__":
    main()
