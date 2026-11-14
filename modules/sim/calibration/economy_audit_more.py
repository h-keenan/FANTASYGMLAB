"""Draft, market, wire and long-run sections of the economy audit (see ``economy_audit``)."""

from __future__ import annotations

from collections import Counter, defaultdict
from multiprocessing import Pool
from typing import Any

import numpy as np

from modules.sim import aging
from modules.sim import game_actions as act
from modules.sim.calibration.economy_audit import BOTS, CORE, Bot, Ctx, play, pool_byes, se, start_game
from modules.sim.game_ai import TradeDesk
from modules.sim.game_eval import Evaluator
from modules.sim.picks import pick_market_value
from modules.sim.types import is_pick_id


def _ppg(state, snap, games: int) -> dict[str, float]:
    return {p: float(np.mean([x for x in h[:games] if x is not None])) for p, h in state.points.items()
            if len([x for x in h[:games] if x is not None]) >= 8 and p in snap.players}


# ------------------------------------------------------------------------------------------ draft


def _startup_job(args):
    shape, seed, econ = args
    root, state, em = start_game(shape, seed, 1, econ)
    snap = root
    rank = {p: i + 1 for i, p in enumerate(sorted(snap.pids, key=lambda p: (snap.players[p].adp, p)))}
    n_teams = len(snap.tids)
    rows = []
    for pk in state.picks:
        pid = pk["pid"]
        rows.append({"n": pk["n"] + 1, "round": pk["round"], "pos": snap.players[pid].pos, "adp_rank": rank[pid], "adp": snap.players[pid].adp, "team": pk["team"]})
    # roster composition after the draft
    comp = []
    for t in snap.tids:
        c = Counter(snap.players[p].pos for p in state.rosters[t])
        comp.append(dict(c))
    return {"picks": rows, "teams": n_teams, "comp": comp}


def _rookie_job(args):
    seed, n_seasons, econ = args
    games = 14
    rows: list[dict[str, Any]] = []
    classes: list[dict[str, Any]] = []
    season_ppg: dict[int, dict[str, float]] = {}

    def observe(c: Ctx, phase, rec):
        if phase == "season_end":
            season_ppg[c.state.season_no] = _ppg(c.state, c.snap, games)
            # starter bar for the season: rank-N ppg by position (N = teams x starters, flex share added for RB/WR)
            n = len(c.snap.tids)
            bars = {}
            for pos, k in (("QB", n), ("RB", int(n * 2.5)), ("WR", int(n * 2.5)), ("TE", n)):
                v = sorted((x for p, x in season_ppg[c.state.season_no].items() if c.snap.players[p].pos == pos), reverse=True)
                bars[pos] = v[k - 1] if len(v) >= k else (v[-1] if v else 0.0)
            season_ppg[-c.state.season_no] = bars  # type: ignore[assignment]
        return None

    r = play({"teams": 12}, seed, Bot(), n_seasons, econ, observe)
    state, root = r["state"], r["root"]
    log = state.rookie_log
    for k, d in enumerate(log):
        season_after = k + 2  # the rookie draft after season k+1 feeds season k+2
        picks = d["picks"]
        v = root.season_view(season_after) if season_after <= n_seasons else None
        if v is None:
            continue
        class_players = [p for p in v.players.values() if p.extra.get("is_rookie") and p.extra.get("draft_year")]
        classes.append({"season": season_after, "n": len(class_players), "age": float(np.mean([p.age for p in class_players])),
                        "mix": dict(Counter(p.pos for p in class_players)), "top12_mean": float(np.mean(sorted([p.mean for p in class_players], reverse=True)[:12])),
                        "undrafted": len(class_players) - len(picks)})
        picked = {x["pid"]: x["n"] + 1 for x in picks}
        for p in class_players:
            row = {"season": season_after, "pid": p.pid, "pos": p.pos, "age": p.age, "mean": p.mean, "market": p.market,
                   "base": aging.horizon_value(p.pos, p.age, p.market), "class_rank": p.extra.get("class_rank"), "overall": picked.get(p.pid),
                   "slot_n": len(picks)}
            for y in (0, 1, 2):
                row[f"ppg{y + 1}"] = season_ppg.get(season_after + y, {}).get(p.pid)
                row[f"bar{y + 1}"] = season_ppg.get(-(season_after + y), {}).get(p.pos)
            rows.append(row)
    return {"rows": rows, "classes": classes}


def draft(a, econ):
    out: dict[str, Any] = {}
    pool = Pool(6)
    for name, shape in (("12t", {"teams": 12}), ("12t sf", {"teams": 12, "superflex": True}), ("10t", {"teams": 10})):
        res = pool.map(_startup_job, [(shape, s, econ) for s in range(1, a.seeds + 1)])
        picks = [p for r in res for p in r["picks"]]
        n = res[0]["teams"]
        dev = np.array([p["n"] - p["adp_rank"] for p in picks])
        by_round = {}
        for rd in range(1, 15):
            ps = [p for p in picks if p["round"] == rd]
            if not ps:
                continue
            d = np.array([p["n"] - p["adp_rank"] for p in ps])
            by_round[rd] = {"mean_abs_dev": round(float(np.abs(d).mean()), 1), "reach_gt_1rd": round(float(np.mean(d < -n)), 3),
                            "fall_gt_1rd": round(float(np.mean(d > n)), 3)}
        pos_by_round = {rd: {pos: round(float(np.mean([p["pos"] == pos for p in picks if p["round"] == rd])), 2) for pos in (*CORE, "K", "DEF")}
                        for rd in (1, 2, 3, 4, 6, 8, 10, 12, 14) if any(p["round"] == rd for p in picks)}
        first_qb = [min((p["n"] for p in r["picks"] if p["pos"] == "QB"), default=None) for r in res]
        te_first = [min((p["n"] for p in r["picks"] if p["pos"] == "TE"), default=None) for r in res]
        k_round = [np.mean([p["round"] for p in r["picks"] if p["pos"] == "K"]) for r in res if any(p["pos"] == "K" for p in r["picks"])]
        # runs: longest streak of the same position in a row (non-K) and the share of picks that continue the previous pick's position
        runs, cont = [], []
        for r in res:
            seq = [p["pos"] for p in sorted(r["picks"], key=lambda x: x["n"])]
            best = cur = 1
            c = 0
            for i in range(1, len(seq)):
                if seq[i] == seq[i - 1]:
                    cur += 1
                    c += 1
                else:
                    best, cur = max(best, cur), 1
            runs.append(max(best, cur))
            cont.append(c / (len(seq) - 1))
        top12 = [p for p in picks if p["adp_rank"] <= n]
        comp_ok = {pos: round(float(np.mean([c.get(pos, 0) for r in res for c in r["comp"]])), 2) for pos in (*CORE, "K", "DEF")}
        out[name] = {"picks": len(picks), "mean_abs_dev": round(float(np.abs(dev).mean()), 1), "by_round": by_round, "pos_share_by_round": pos_by_round,
                     "first_qb_pick_mean": round(float(np.mean([x for x in first_qb if x])), 1), "first_te_pick_mean": round(float(np.mean([x for x in te_first if x])), 1),
                     "kicker_round_mean": round(float(np.mean(k_round)), 1) if k_round else None, "longest_run_mean": round(float(np.mean(runs)), 1),
                     "same_pos_as_prev_pick": round(float(np.mean(cont)), 3), "top_n_adp_taken_in_round1": round(float(np.mean([p["round"] == 1 for p in top12])), 3),
                     "roster_mix_mean": comp_ok}
    # rookie classes
    seeds = max(4, a.seeds // 2)
    res = pool.map(_rookie_job, [(s, 5, econ) for s in range(1, seeds + 1)])
    rows = [r for x in res for r in x["rows"]]
    classes = [c for x in res for c in x["classes"]]
    done = [r for r in rows if r["ppg1"] is not None]
    bins = {"1-6": (1, 6), "7-12": (7, 12), "13-24": (13, 24), "25-36": (25, 36), "37+": (37, 999)}

    def hit(r, level):  # best of the first three seasons clears the starter bar (QB/TE rank 12, RB/WR rank 30)
        best = [(r[f"ppg{y}"] or 0.0) >= (r[f"bar{y}"] or 99) for y in (1, 2, 3) if r[f"ppg{y}"] is not None]
        return any(best)

    drafted = [r for r in rows if r["overall"]]
    rk = {}
    for k, (lo, hi) in bins.items():
        sel = [r for r in rows if r["overall"] and lo <= r["overall"] <= hi]
        sel1 = [r for r in sel if r["ppg1"] is not None]
        rk[k] = {"n": len(sel), "played_year1": round(len(sel1) / max(1, len(sel)), 2), "ppg1_mean": round(float(np.mean([r["ppg1"] for r in sel1])), 2) if sel1 else None,
                 "starter_hit_3y": round(float(np.mean([hit(r, 0) for r in sel if any(r[f"ppg{y}"] is not None for y in (1, 2, 3))])), 3)
                 if any(any(r[f"ppg{y}"] is not None for y in (1, 2, 3)) for r in sel) else None,
                 "mean_projection": round(float(np.mean([r["mean"] for r in sel])), 2), "base_value": round(float(np.mean([r["base"] for r in sel])), 1)}
    und = [r for r in rows if not r["overall"]]
    und1 = [r for r in und if r["ppg1"] is not None]
    # pick value vs the rookie it becomes: pick_market_value at the final slot (years_out 0) vs base value of the player taken there
    by_slot = defaultdict(list)
    for r in drafted:
        by_slot[r["overall"]].append(r["base"])
    ratio = []
    for slot, vals in sorted(by_slot.items()):
        rnd = (slot - 1) // 12 + 1
        frac = ((slot - 1) % 12) / 11.0
        ratio.append((slot, pick_market_value(rnd, frac, 0, 12), float(np.mean(vals)), float(np.mean([r["mean"] for r in drafted if r["overall"] == slot]))))
    out["rookie_classes"] = {
        "classes": len(classes), "size_mean": round(float(np.mean([c["n"] for c in classes])), 1), "age_mean": round(float(np.mean([c["age"] for c in classes])), 2),
        "pos_mix": {pos: round(float(np.mean([c["mix"].get(pos, 0) for c in classes]) / np.mean([c["n"] for c in classes])), 3) for pos in (*CORE, "K")},
        "top12_mean_cv": round(float(np.std([c["top12_mean"] for c in classes]) / np.mean([c["top12_mean"] for c in classes])), 3),
        "undrafted_per_class": round(float(np.mean([c["undrafted"] for c in classes])), 1),
        "by_overall_pick": rk,
        "undrafted": {"n": len(und), "played_year1": round(len(und1) / max(1, len(und)), 2), "ppg1_mean": round(float(np.mean([r["ppg1"] for r in und1])), 2) if und1 else None,
                      "over_8ppg_share": round(float(np.mean([r["ppg1"] >= 8 for r in und1])), 3) if und1 else None},
        "pick_value_vs_rookie_base_value": {str(s): [round(pv, 1), round(bv, 1), round(m, 1)] for s, pv, bv, m in ratio if s in (1, 2, 3, 6, 12, 13, 18, 24, 25, 30, 36)},
        "pick_to_base_ratio_by_round": {str(rd): round(float(np.sum([pv for s, pv, bv, m in ratio if (s - 1) // 12 + 1 == rd]) / max(1e-9, np.sum([bv for s, pv, bv, m in ratio if (s - 1) // 12 + 1 == rd]))), 3) for rd in (1, 2, 3)},
    }
    pool.close()
    return out


# ---------------------------------------------------------------------------------------- market


def _market_job(args):
    seed, mode, econ = args
    shape = {"teams": 12}
    n_seasons = 5 if mode == "dynasty" else 1
    stats: dict[str, Any] = {"trades": [], "offers": 0, "ai_trades_by_season": [], "probes": []}
    inj_ratio: list[float] = []
    K_probe: list[tuple] = []

    def observe(c: Ctx, phase, rec):
        st, snap = c.state, c.snap
        if phase == "season_end":
            return {"trades_made": sum(st.trades_made.values()) / 2}
        if phase == "week" and st.status == "in_season" and st.week in (2, 6, 9) and mode == "dynasty" or phase == "week" and st.status == "in_season" and st.week in (2, 6):
            ev = Evaluator(snap, st)
            desk = TradeDesk(ev, c.sd, st.week)
            probe_age(desk, c, stats)
            probe_injured(desk, c, inj_ratio)
            probe_kicker(desk, c, K_probe)
        return None

    r = play(shape, seed, Bot(), n_seasons, econ, observe)
    ev_types = Counter()
    state = r["state"]
    gap_ai, age_move = [], []
    trade_rows = []
    for t in state.transactions:
        if t.get("type") == "trade":
            trade_rows.append(t)
    stats["tx_types"] = dict(Counter(t.get("type") for t in state.transactions))
    stats["n_seasons"] = n_seasons
    stats["season_trades"] = r["extra"]
    stats["inj_ratio"] = inj_ratio
    stats["K_probe"] = K_probe
    return stats


def probe_age(desk: TradeDesk, c: Ctx, stats: dict) -> None:
    """Equal-base-value 1-for-1 swaps between a young and an old player (user gives X gets Y): which direction does an AI accept?"""

    snap, st = c.snap, c.state
    ev = desk.ev
    user = c.user
    mine = [p for p in st.holdings(user) if snap.players[p].pos in CORE]
    for tid in snap.tids:
        if tid == user:
            continue
        for g in mine:
            for t in desk.tradable(tid):
                if is_pick_id(t) or snap.players[t].pos != snap.players[g].pos:
                    continue
                bg, bt = ev.base_value(g), ev.base_value(t)
                if bg < 15 or abs(bg - bt) > 3:
                    continue
                ag, at = snap.players[g].age, snap.players[t].age
                if abs(ag - at) < 4:
                    continue
                ok = desk.ai_accepts(tid, [g], [t])[0]
                stats["probes"].append(("old_for_young" if ag > at else "young_for_old", ok, desk.params(tid).horizon, round(bg, 1), round(abs(ag - at), 1)))


def probe_injured(desk: TradeDesk, c: Ctx, out: list) -> None:
    """Worth of an injured player to a mid-horizon team vs the same player healthy (the discount the AI applies for an injury)."""

    st, snap = c.state, c.snap
    ev = desk.ev
    params = desk.params(c.snap.tids[0])
    for pid, wk in list(st.out.items()):
        if wk >= 4 and pid in snap.players and snap.players[pid].pos in CORE and ev.base_value(pid) >= 25:
            w_now = ev.worth(params, pid)
            saved = st.out[pid]
            st.out[pid] = 0
            try:
                ev2 = Evaluator(snap, st)
                w_h = ev2.worth(params, pid)
            finally:
                st.out[pid] = saved
            out.append((wk, round(ev.base_value(pid), 1), round(w_now, 1), round(w_h, 1), round(ev.ros_mean(pid), 2), round(ev2.ros_mean(pid), 2)))


def probe_kicker(desk: TradeDesk, c: Ctx, out: list) -> None:
    """How much does the AI pay for a kicker / defense the user hands over (kd_v 1)? Its worth and the margin it adds to an offer."""

    st, snap = c.state, c.snap
    ev = desk.ev
    user = c.user
    kd = [p for p in st.holdings(user) if snap.players[p].pos in ("K", "DEF")]
    mine = sorted((p for p in st.holdings(user) if snap.players[p].pos in CORE), key=lambda p: ev.base_value(p))[:6]
    for tid in snap.tids:
        if tid == user or not kd:
            continue
        for k in kd:
            theirs = [p for p in desk.tradable(tid) if not is_pick_id(p) and snap.players[p].pos in CORE and 15 <= ev.base_value(p) <= 45]
            for t in theirs[:4]:
                m0 = desk.ai_accepts(tid, [mine[0]], [t])[1]
                m1 = desk.ai_accepts(tid, [mine[0], k], [t])[1]
                out.append((snap.players[k].pos, round(ev.base_value(k), 1), round(ev.ros_mean(k), 2), round(m1 - m0, 2), round(desk.params(tid).accept_threshold, 1)))


def market(a, econ):
    out: dict[str, Any] = {}
    with Pool(6) as pool:
        for mode in ("dynasty", "redraft"):
            res = pool.map(_market_job, [(s, mode, econ) for s in range(1, a.seeds + 1)])
            pr = [p for r in res for p in r["probes"]]
            agg = {}
            for kind in ("old_for_young", "young_for_old"):
                ps = [p for p in pr if p[0] == kind]
                agg[kind] = {"n": len(ps), "accept_rate": round(float(np.mean([p[1] for p in ps])), 3) if ps else None}
                for lo, hi, label in ((0, 0.4, "rebuilders(h<.4)"), (0.4, 0.7, "mid"), (0.7, 2, "contenders(h>.7)")):
                    sub = [p for p in ps if lo <= p[2] < hi]
                    agg[kind][label] = [round(float(np.mean([p[1] for p in sub])), 3), len(sub)] if sub else None
            inj = [i for r in res for i in r["inj_ratio"]]
            kp = [k for r in res for k in r["K_probe"]]
            out[mode] = {
                "ai_ai_trades_per_league_season": round(float(np.mean([s["trades_made"] for r in res for s in r["season_trades"] if s])), 2),
                "tx_types_per_league_season": {k: round(sum(r["tx_types"].get(k, 0) for r in res) / (len(res) * res[0]["n_seasons"]), 1) for k in sorted({k for r in res for k in r["tx_types"]})},
                "equal_value_age_swaps": agg,
                "injured_players_probed": len(inj),
                "injured_worth_ratio_by_weeks_out": {str(k): [round(float(np.mean([i[2] / max(1e-9, i[3]) for i in inj if lo <= i[0] <= hi])), 3), sum(1 for i in inj if lo <= i[0] <= hi)]
                                                     for k, (lo, hi) in {"4-5": (4, 5), "6-8": (6, 8), "9+": (9, 99)}.items() if any(lo <= i[0] <= hi for i in inj)},
                "kicker_def_in_offer": {pos: {"n": len([k for k in kp if k[0] == pos]), "mean_base_value": round(float(np.mean([k[1] for k in kp if k[0] == pos])), 1),
                                              "mean_margin_added": round(float(np.mean([k[3] for k in kp if k[0] == pos])), 2),
                                              "mean_accept_threshold": round(float(np.mean([k[4] for k in kp if k[0] == pos])), 1)}
                                        for pos in ("K", "DEF") if any(k[0] == pos for k in kp)},
            }
    return out


# ------------------------------------------------------------------------------------------ wire


def _wire_job(args):
    seed, econ = args
    weekly: list[dict[str, Any]] = []

    def observe(c: Ctx, phase, rec):
        st, snap = c.state, c.snap
        if phase == "week" and st.status == "in_season":
            ev = Evaluator(snap, st)
            owned = st.owner_map()
            fa = [p for p in snap.pids if p not in owned and st.out.get(p, 0) == 0]
            row = {"week": st.week}
            for pos in (*CORE, "K"):
                v = sorted((ev.ros_mean(p) for p in fa if snap.players[p].pos == pos), reverse=True)
                row[pos] = [round(v[0], 2) if v else 0.0, round(v[2], 2) if len(v) > 2 else 0.0, len(v)]
            # starter level for context: the rank-N rostered player at the position
            for pos, k in (("RB", 30), ("WR", 30), ("QB", 12), ("TE", 12)):
                v = sorted((ev.ros_mean(p) for p in owned if snap.players[p].pos == pos and owned[p] in snap.tids), reverse=True)
                row[f"starter_{pos}"] = round(v[k - 1], 2) if len(v) >= k else 0.0
            row["fa_over_8"] = sum(1 for p in fa if snap.players[p].pos in CORE and ev.ros_mean(p) >= 8)
            weekly.append(row)
        return None

    r = play({"teams": 12}, seed, Bot(), 1, econ, observe)
    state = r["state"]
    adds = Counter()
    drops = 0
    by_week_adds = Counter()
    churn = []  # (pid, week added) -> dropped within 3 weeks
    added_at: dict[tuple[str, str], int] = {}
    for tx in state.transactions:
        if tx.get("type") == "waiver" and tx.get("ok", True):
            pass
    return {"weekly": weekly, "tx": dict(Counter(t.get("type") for t in state.transactions))}


def wire(a, econ):
    with Pool(6) as pool:
        res = pool.map(_wire_job, [(s, econ) for s in range(1, a.seeds + 1)])
    out: dict[str, Any] = {"tx_per_season": {k: round(float(np.mean([r["tx"].get(k, 0) for r in res])), 1) for k in sorted({k for r in res for k in r["tx"]})}}
    weeks = sorted({w["week"] for r in res for w in r["weekly"]})
    tab = {}
    for wk in weeks:
        rows = [w for r in res for w in r["weekly"] if w["week"] == wk]
        tab[wk] = {pos: [round(float(np.mean([x[pos][0] for x in rows])), 1), round(float(np.mean([x[pos][1] for x in rows])), 1), round(float(np.mean([x[pos][2] for x in rows])), 0)]
                   for pos in (*CORE, "K")}
        tab[wk]["starter_rb30"] = round(float(np.mean([x["starter_RB"] for x in rows])), 1)
        tab[wk]["starter_wr30"] = round(float(np.mean([x["starter_WR"] for x in rows])), 1)
        tab[wk]["fa_core_over_8ppg"] = round(float(np.mean([x["fa_over_8"] for x in rows])), 1)
    out["free_agents_best_third_count_by_week"] = tab
    return out


# ------------------------------------------------------------------------------------------- long


def _long_job(args):
    seed, n_seasons, econ = args
    rows: list[dict[str, Any]] = []

    def observe(c: Ctx, phase, rec):
        if phase != "season_end":
            return None
        st, snap = c.state, c.snap
        ppg = _ppg(st, snap, snap.settings.regular_weeks)
        row: dict[str, Any] = {"season": st.season_no}
        for pos, bars in (("QB", (12, 24)), ("RB", (12, 24, 36)), ("WR", (12, 24, 36)), ("TE", (6, 12))):
            v = sorted((x for p, x in ppg.items() if snap.players[p].pos == pos), reverse=True)
            row[pos] = {"relevant_ge_10ppg": sum(1 for x in v if x >= 10), "rank": {str(b): round(v[b - 1], 1) if len(v) >= b else None for b in bars}}
            ages = [snap.players[p].age for p in sorted((p for p in ppg if snap.players[p].pos == pos), key=lambda p: -ppg[p])[:24]]
            row[pos]["age_top24"] = round(float(np.mean(ages)), 1) if ages else None
        ev = Evaluator(snap, st)
        # pick economy: total pick value outstanding and the concentration of picks
        picks = [p for t in snap.tids for p in st.picks_of(t)]
        vals = [ev.pick_value(p) for p in picks]
        per_team = [sum(ev.pick_value(p) for p in st.picks_of(t)) for t in snap.tids]
        row["picks"] = {"n": len(picks), "total_value": round(sum(vals), 0), "team_value_cv": round(float(np.std(per_team) / np.mean(per_team)), 3),
                        "max_team_share": round(max(per_team) / max(1e-9, sum(per_team)), 3)}
        assets = [sum(ev.base_value(p) for p in st.holdings(t)) for t in snap.tids]
        row["player_assets_mean"] = round(float(np.mean(assets)), 0)
        row["trades"] = sum(st.trades_made.values()) / 2
        return row

    r = play({"teams": 12}, seed, Bot(), n_seasons, econ, observe)
    return {"rows": [x for x in r["extra"] if x], "seasons": r["rows"]}


def long(a, econ):
    n = a.seasons if a.seasons > 1 else 20
    with Pool(6) as pool:
        res = pool.map(_long_job, [(s, n, econ) for s in range(1, a.seeds + 1)])
    out: dict[str, Any] = {}
    checkpoints = [s for s in (1, 2, 5, 10, 15, 20) if s <= n]
    for s in checkpoints:
        rows = [x for r in res for x in r["rows"] if x["season"] == s]
        out[f"s{s}"] = {
            "relevant_ge_10ppg": {pos: round(float(np.mean([x[pos]["relevant_ge_10ppg"] for x in rows])), 1) for pos in CORE},
            "rank24_rb_wr": [round(float(np.mean([x["RB"]["rank"]["24"] for x in rows])), 1), round(float(np.mean([x["WR"]["rank"]["24"] for x in rows])), 1)],
            "top12_qb_rb_wr_te": [round(float(np.mean([x[p]["rank"]["12" if p != "TE" else "12"] for x in rows])), 1) for p in CORE],
            "age_top24": {pos: round(float(np.mean([x[pos]["age_top24"] for x in rows])), 1) for pos in CORE},
            "picks": {k: round(float(np.mean([x["picks"][k] for x in rows])), 3) for k in ("n", "total_value", "team_value_cv", "max_team_share")},
            "player_assets_mean": round(float(np.mean([x["player_assets_mean"] for x in rows])), 0),
            "trades_per_league_season": round(float(np.mean([x["trades"] for x in rows])), 1),
        }
    return out
