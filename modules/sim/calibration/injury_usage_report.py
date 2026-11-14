"""Injury and team-usage realism harness (2026-11 audit, docs/audits/2026-11-sim-injuries-and-usage.md).

Plays whole dynasty GM games (pool from the real 2025 panel, 12 teams) for many seeds x a few seasons, records one row per
player-week and one per player-season through the engine's own scoring session (nothing is re-simulated), and compares the
aggregates with the same quantities measured on the real 2021-25 panel (``modules/sim/calibration/data/panel.json.gz``).

    python -m modules.sim.calibration.injury_usage_report [--seeds 40] [--seasons 3] [--procs 6] [--model ID] [--dynasty-v N]
        [--world-v N] [--json out.json] [--real]

Only the ``panel.json.gz`` file is read (never ``data/players.db``). Real yardsticks that the panel cannot give (injury-report
status shares, practice participation) are NFL published figures, quoted in the audit document and not computed here.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from collections import Counter, defaultdict
from dataclasses import replace
from typing import Any

import numpy as np

from modules.sim.calibration import dataset, tail_report

CORE = ("QB", "RB", "WR", "TE")
STARTER_SLOTS = {"QB": 1, "RB": 2, "WR": 3, "TE": 1}


# ------------------------------------------------------------------------------------------------ real panel


def real_metrics(rows: list[dict] | None = None) -> dict[str, Any]:
    """The same quantities the simulated side reports, measured on the real 2021-25 panel (pool players only)."""

    rows = rows if rows is not None else dataset.load_panel()
    out: dict[str, Any] = {}
    # --- absences: run lengths of consecutive missed (non-bye) games between played games, relevant players
    runs = Counter()
    miss_per_season = defaultdict(list)
    pos_wk = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["pos"] not in CORE:
            continue
        rel = (r["adp"] is not None and r["adp"] <= 150) or (r["proj_ppg"] or 0) >= 8
        if not rel:
            continue
        seq = [bool(w[0]) for w in r["weeks"] if w is not None]
        first = next((i for i, v in enumerate(seq) if v), None)
        if first is None:
            continue
        last = max(i for i, v in enumerate(seq) if v)
        m = 0
        for v in seq[first:last + 1]:
            if v:
                if m:
                    runs[min(m, 10)] += 1
                m = 0
            else:
                m += 1
        miss_per_season[r["pos"]].append(sum(1 for v in seq if not v))
        pos_wk[r["pos"]][0] += sum(1 for v in seq if not v)
        pos_wk[r["pos"]][1] += len(seq)
    tot = sum(runs.values()) or 1
    out["gap_len_share"] = {str(k): round(v / tot, 3) for k, v in sorted(runs.items())}
    out["gap_episodes_per_100_player_games"] = round(100.0 * tot / max(1, sum(v[1] for v in pos_wk.values())), 2)
    out["games_missed_per_season"] = {p: round(float(np.mean(v)), 2) for p, v in miss_per_season.items()}
    out["missed_share_by_pos"] = {p: round(v[0] / max(1, v[1]), 3) for p, v in pos_wk.items()}
    out["missed_games_bucket_share"], out["episodes_per_100_games_by_age"], out["episodes_per_100_games_by_tier"] = _real_missed_dist(rows)
    out["cohort_missed_share_by_age_and_pos"] = _real_missed_dist.share
    # --- QBs per week with a real passing workload
    qb10, qb20, qbany = [], [], []
    for season in sorted({r["season"] for r in rows}):
        qbs = [r for r in rows if r["season"] == season and r["pos"] == "QB"]
        for wk in range(17):
            n_any = sum(1 for r in qbs if r["weeks"][wk] and r["weeks"][wk][0])
            if n_any:
                qbany.append(n_any)
            n10 = sum(1 for r in qbs if r["weeks"][wk] and r["weeks"][wk][2] >= 10)
            n20 = sum(1 for r in qbs if r["weeks"][wk] and r["weeks"][wk][2] >= 20)
            if n10:
                qb10.append(n10)
                qb20.append(n20)
    out["qbs_att10_per_week"] = {"mean": round(float(np.mean(qb10)), 1), "max": int(max(qb10))}
    out["qbs_att20_per_week"] = {"mean": round(float(np.mean(qb20)), 1), "max": int(max(qb20))}
    out["qbs_with_a_game_per_week"] = {"mean": round(float(np.mean(qbany)), 1), "max": int(max(qbany))}
    # --- team usage: pool-player sums per team-week
    tt = []
    share = {k: [] for k in ("WR1", "WR2", "WR3", "WR4", "TE1", "RB1", "RB2")}
    for season in sorted({r["season"] for r in rows}):
        by_team = defaultdict(list)
        for r in rows:
            if r["season"] == season and r["team"] and r["pos"] in CORE:
                by_team[r["team"]].append(r)
        for team, rs in by_team.items():
            for wk in range(17):
                att = rush = tgt = 0.0
                wr, te, rb = [], [], []
                for r in rs:
                    w = r["weeks"][wk]
                    if not w or not w[0]:
                        continue
                    att += w[2]
                    rush += w[7]
                    if r["pos"] != "QB":
                        tgt += w[10]
                        {"WR": wr, "TE": te, "RB": rb}[r["pos"]].append(w[10])
                if att < 10:
                    continue
                tt.append([att, rush, tgt])
                total_t = sum(wr) + sum(te) + sum(rb)
                if total_t > 0:
                    wr.sort(reverse=True)
                    te.sort(reverse=True)
                    rb.sort(reverse=True)
                    for i in range(4):
                        share[f"WR{i + 1}"].append((wr[i] if i < len(wr) else 0.0) / total_t)
                    share["TE1"].append((te[0] if te else 0.0) / total_t)
                    share["RB1"].append((rb[0] if rb else 0.0) / total_t)
                    share["RB2"].append((rb[1] if len(rb) > 1 else 0.0) / total_t)
    arr = np.array(tt)
    out["team_week_pool_totals_mean"] = {"pass_att": round(float(arr[:, 0].mean()), 1), "rush_att": round(float(arr[:, 1].mean()), 1), "targets": round(float(arr[:, 2].mean()), 1)}
    out["team_week_pool_totals_sd"] = {"pass_att": round(float(arr[:, 0].std()), 1), "rush_att": round(float(arr[:, 1].std()), 1), "targets": round(float(arr[:, 2].std()), 1)}
    out["target_share_ranked_in_team_week"] = {k: round(float(np.mean(v)), 3) for k, v in share.items() if v}
    # --- fantasy-relevant players per team per season (top-N of the position by ppg, 8+ games)
    rel = defaultdict(list)
    for season in sorted({r["season"] for r in rows}):
        teams = {r["team"] for r in rows if r["season"] == season and r["team"]}
        for pos, n in (("QB", 24), ("RB", 36), ("WR", 36), ("TE", 18)):
            pts = []
            for r in rows:
                if r["season"] == season and r["pos"] == pos and r["team"]:
                    gp = [w for w in r["weeks"] if w and w[0]]
                    if len(gp) >= 8:
                        pts.append((float(np.mean([w[1] for w in gp])), r["team"]))
            pts.sort(reverse=True)
            c = Counter(t for _, t in pts[:n])
            for t in teams:
                rel[pos].append(c.get(t, 0))
    out["relevant_per_team"] = {p: _rel_summary(v) for p, v in rel.items()}
    # --- team-position group points vs the preseason projection sum (usage conservation: how far can a group run over its baseline?)
    ratios = {}
    for pos in CORE:
        g = defaultdict(lambda: [0.0, 0.0])
        for r in rows:
            if r["pos"] == pos and r["team"]:
                key = (r["season"], r["team"])
                g[key][0] += sum(w[1] for w in r["weeks"] if w and w[0])
                g[key][1] += (r["proj_ppg"] or 0) * sum(1 for w in r["weeks"] if w is not None)
        ratios[pos] = _ratio_summary([a / b for a, b in g.values() if b > 20])
    out["group_points_over_projection_sum"] = ratios
    pairs = []
    for r in rows:
        if r["pos"] in ("RB", "WR", "TE") and r["proj_ppg"] is not None:
            g = [w[1] for w in r["weeks"] if w and w[0]]
            if len(g) >= 8:
                pairs.append((r["proj_ppg"], float(np.mean(g))))
    out["season_ppg_by_projection_tier"] = _tier_table(pairs)
    out["breakouts"] = breakout_table_real(rows)
    return out


TOP_N = {"QB": 24, "RB": 48, "WR": 60, "TE": 24}
BUCKETS = (("0", 0, 0), ("1-2", 1, 2), ("3-5", 3, 5), ("6-9", 6, 9), ("10+", 10, 99))


def _bucket_share(vals) -> dict[str, float]:
    n = max(1, len(vals))
    return {name: round(sum(1 for v in vals if lo <= v <= hi) / n, 3) for name, lo, hi in BUCKETS}


def _age_band(a: float) -> str:
    return "<=24" if a <= 24 else "25-27" if a <= 27 else "28-30" if a <= 30 else "31+"


def _real_missed_dist(rows):
    miss, age_e, age_n, tier_e, tier_n = [], Counter(), Counter(), Counter(), Counter()
    ms = defaultdict(lambda: [0, 0])
    for pos, n in TOP_N.items():
        for season in sorted({r["season"] for r in rows}):
            rs = sorted((r for r in rows if r["season"] == season and r["pos"] == pos), key=lambda r: -(r["proj_ppg"] or 0))[:n]
            for rank, r in enumerate(rs, 1):
                seq = [bool(w[0]) for w in r["weeks"] if w is not None]
                if not any(seq):
                    continue
                miss.append(sum(1 for v in seq if not v))
                tier = "top12" if rank <= 12 else "13-36" if rank <= 36 else "37+"
                first = seq.index(True)
                last = max(i for i, v in enumerate(seq) if v)
                m = 0
                eps = 0
                for v in seq[first:last + 1]:
                    if v:
                        eps += 1 if m else 0
                        m = 0
                    else:
                        m += 1
                ab = _age_band(float(r["age"] or 26))
                if sum(seq) >= 4:
                    for k in ("age " + ab, "pos " + pos):
                        ms[k][0] += len(seq) - sum(seq)
                        ms[k][1] += len(seq)
                age_e[ab] += eps
                age_n[ab] += len(seq)
                tier_e[tier] += eps
                tier_n[tier] += len(seq)
    _real_missed_dist.share = {k: round(v[0] / v[1], 3) for k, v in sorted(ms.items())}
    return (_bucket_share(miss), {k: round(100.0 * age_e[k] / age_n[k], 2) for k in age_n}, {k: round(100.0 * tier_e[k] / tier_n[k], 2) for k in tier_n})


TIERS = ((0.0, 1.5), (1.5, 3.0), (3.0, 4.5), (4.5, 6.0))


def _tier_table(pairs) -> dict[str, Any]:
    """(projection ppg, season ppg over 8+ games) of RB/WR/TE -> the upper tail of season ppg by projection tier."""

    out = {}
    for lo, hi in TIERS:
        v = np.array([m for p, m in pairs if lo <= p < hi])
        if len(v) < 20:
            continue
        p50, p90, p97, p99 = np.percentile(v, [50, 90, 97, 99])
        out[f"proj {lo}-{hi}"] = {"n": int(len(v)), "p50": round(float(p50), 1), "p90": round(float(p90), 1), "p97": round(float(p97), 1), "p99": round(float(p99), 1),
                                  "max": round(float(v.max()), 1), "share_ge8": round(float((v >= 8).mean()), 3), "share_ge10": round(float((v >= 10).mean()), 3)}
    return out


def _ratio_summary(vals) -> dict[str, float]:
    a = np.array(vals)
    p10, p50, p90 = np.percentile(a, [10, 50, 90])
    return {"mean": round(float(a.mean()), 3), "cv": round(float(a.std() / a.mean()), 3), "p10": round(float(p10), 3), "p50": round(float(p50), 3),
            "p90": round(float(p90), 3), "p90_over_p50": round(float(p90 / p50), 3), "n": int(len(a))}


def _rel_summary(v) -> dict[str, float]:
    a = np.array(v)
    return {"mean": round(float(a.mean()), 2), "max": int(a.max()), "share_ge3": round(float((a >= 3).mean()), 3),
            "share_ge4": round(float((a >= 4).mean()), 3), "share_0": round(float((a == 0).mean()), 3)}


def breakout_table_real(rows: list[dict]) -> dict[str, Any]:
    """Finishing top-N by total PPR points with a preseason projection rank beyond ``deep``, per season."""

    out: dict[str, Any] = {}
    for pos, deep, top in (("RB", 50, 24), ("WR", 60, 24), ("TE", 20, 12), ("QB", 24, 12)):
        n_deep, jump30 = [], []
        for season in sorted({r["season"] for r in rows}):
            rs = [r for r in rows if r["season"] == season and r["pos"] == pos]
            pre = sorted(rs, key=lambda r: -(r["proj_ppg"] or 0))
            pre_rank = {id(r): i + 1 for i, r in enumerate(pre)}
            tot = {id(r): sum(w[1] for w in r["weeks"] if w and w[0]) for r in rs}
            fin = sorted(rs, key=lambda r: -tot[id(r)])
            fin_rank = {id(r): i + 1 for i, r in enumerate(fin)}
            n_deep.append(sum(1 for r in rs if fin_rank[id(r)] <= top and pre_rank[id(r)] > deep))
            jump30.append(sum(1 for r in rs if pre_rank[id(r)] - fin_rank[id(r)] >= 30 and fin_rank[id(r)] <= 36))
        out[pos] = {f"top{top}_from_pre_rank_gt{deep}_per_season": round(float(np.mean(n_deep)), 2),
                    "finish_ge30_places_better_in_top36_per_season": round(float(np.mean(jump30)), 2)}
    return out


# ------------------------------------------------------------------------------------------------ sim side


def play_game(seed: int, seasons: int, model_id: str, pool, byes, dynasty_v: int | None = None, world_v: int | None = None) -> dict[str, Any]:
    from modules.sim import game_dynasty as dyn
    from modules.sim import game_engine
    from modules.sim.game_actions import cut_player
    from modules.sim.game_draft import DraftContext, auto_for_user
    from modules.sim.game_engine import advance, finish_draft
    from modules.sim.game_eval import USER_PARAMS, Evaluator
    from modules.sim.game_setup import build_snapshot
    from modules.sim.game_state import Emitter, GameState
    from modules.sim.game_types import GameSettings

    extra: dict[str, Any] = {}
    if dynasty_v is not None:
        extra["dynasty_v"] = dynasty_v
    if world_v is not None:
        extra["world_v"] = world_v
    base = GameSettings.parse({"mode": "dynasty", "teams": 12, "user_slot": 3, "start_year": 2026, "seasons": 5, "rookie_rounds": 3, "scoring": "ppr"})
    settings = replace(base, seasons=seasons, **extra)
    root = build_snapshot(pool, byes, settings, seed, scoring_model=model_id)
    state = GameState(root)
    em = Emitter(state, root)
    auto_for_user(DraftContext(root, state), em, seed)
    finish_draft(em, root, state, seed)

    captured: dict[str, tuple] = {}
    orig = game_engine.ScoringSession.week

    def wrapped(self, pid, week, role_mult=None):
        res = orig(self, pid, week, role_mult)
        captured[pid, week] = (res.points, res.stats, res.active, res.newly_injured)  # keyed by week: the last regular week's advance may also play the playoff weeks
        return res

    game_engine.ScoringSession.week = wrapped
    weekrows: list[tuple] = []
    seasonrows: list[tuple] = []
    try:
        while True:
            snap = root.season_view(state.view_no)
            sd = dyn.season_seed(seed, state.view_no)
            em.snap = snap
            season_no = state.season_no
            while state.status in ("in_season", "playoffs"):
                w = state.week
                if w > snap.settings.regular_weeks:
                    advance(em, snap, state, sd)
                    continue
                ev = Evaluator(snap, state)
                captured.clear()
                pre = {}
                for pid in snap.pids:
                    p = snap.players[pid]
                    if p.pos not in CORE:
                        continue
                    r = ev.role(pid, w) if ev.roles_on else None
                    key = ev.book.key(pid) if ev.roles_on else None
                    rank = [m.pid for m in ev.book.groups[key]].index(pid) + 1 if key else 99
                    pre[pid] = (ev.status(pid, w), r.kind if r else "", float(r.add) if r else 0.0, float(r.mult) if r else 1.0, rank)
                nev = len(em.events)
                advance(em, snap, state, sd)
                hurt = {}
                for e in em.events[nev:]:
                    if e["type"] == "injury" and e["week"] == w:
                        for pid, weeks in e["payload"]["items"]:
                            hurt[pid] = weeks
                for pid, (st, kind, add, mult, rank) in pre.items():
                    p = snap.players[pid]
                    c = captured.get((pid, w))
                    if c is None:
                        weekrows.append((season_no, w, pid, p.pos, p.nfl_team, st, kind, add, mult, 0, 0.0, 0.0, 0.0, 0.0, 0, rank))
                    else:
                        s = c[1]
                        weekrows.append((season_no, w, pid, p.pos, p.nfl_team, st, kind, add, mult, 1 if c[2] else 0, float(c[0]),
                                         float(s.get("pass_att", 0.0)), float(s.get("rush_att", 0.0)), float(s.get("rec_tgt", 0.0)), int(hurt.get(pid, 0)), rank))
            session = game_engine.session_for(snap, sd)
            for pid in snap.pids:
                p = snap.players[pid]
                if p.pos not in CORE:
                    continue
                prof = session.profile(pid)
                cum = 1.0
                for rc in getattr(prof, "role_changes", ()):
                    if rc.kind == "promotion" and not rc.end_week:
                        cum *= rc.multiplier
                seasonrows.append((season_no, pid, p.pos, p.nfl_team, float(p.age), float(p.mean), float(p.market), str(getattr(prof, "archetype", "")),
                                   float(getattr(prof, "season_mean_ppg", 0.0)), round(cum, 3), len(getattr(prof, "injury_events", ())), bool(p.extra.get("is_rookie"))))
            if state.status != "offseason":
                break
            snap = root.season_view(state.view_no)
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
    finally:
        game_engine.ScoringSession.week = orig
    return {"seed": seed, "week_rows": weekrows, "season_rows": seasonrows}


def _worker(args):
    seed, seasons, model_id, pool, byes, dynasty_v, world_v = args
    return play_game(seed, seasons, model_id, pool, byes, dynasty_v, world_v)


# ------------------------------------------------------------------------------------------------ aggregation (sim)


def aggregate(games: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"games": len(games)}
    exp = defaultdict(float)
    inj = defaultdict(float)
    outlen = defaultdict(Counter)
    team_out = []
    starters_missing = defaultdict(lambda: [0, 0])
    qb_att10, qb_att20, qb_team, qb_any = [], [], [], []
    team_tot = []
    share = {k: [] for k in ("WR1", "WR2", "WR3", "WR4", "TE1", "RB1", "RB2")}
    reinj = [0, 0]
    fill_in_n = Counter()
    fill_in_pts = defaultdict(list)
    starter_pts = defaultdict(list)
    relevant = defaultdict(list)
    breakout_rows = []
    seasons_seen = set()
    missed = []
    group_ratio = defaultdict(list)
    tier_pairs = []
    out_n, wk_n = defaultdict(int), defaultdict(int)
    age_i, age_n, tier_i, tier_n = Counter(), Counter(), Counter(), Counter()
    cms = defaultdict(lambda: [0, 0])
    for g in games:
        W = g["week_rows"]
        bypk = defaultdict(list)
        for row in W:
            bypk[row[0], row[1]].append(row)
            season, wk, pid, pos, team, st, kind, add, mult, played, pts, att, rush, tgt, hurt, rank = row
            seasons_seen.add(season)
            if st == "healthy":
                cls = "starter" if kind in ("starter", "fill_in") else "bench"
                exp[pos, cls] += 1
                inj[pos, cls] += 1 if hurt else 0
                if hurt:
                    outlen[pos][min(hurt, 10)] += 1
            if played and kind == "fill_in":
                fill_in_pts[pos].append(pts)
                fill_in_n[pos] += 1
            elif played and kind == "starter":
                starter_pts[pos].append(pts)
        for (season, wk), rows_ in bypk.items():
            by_team = defaultdict(list)
            for r in rows_:
                if r[4]:
                    by_team[r[4]].append(r)
            qa10 = qa20 = 0
            qb_any.append(sum(1 for r in rows_ if r[3] == "QB" and r[9]))
            for team, rs in by_team.items():
                if all(r[5] == "bye" for r in rs):
                    continue
                for pos in CORE:
                    st = [r for r in rs if r[3] == pos and r[5] != "bye" and r[15] <= STARTER_SLOTS[pos]]
                    starters_missing[pos][0] += sum(1 for r in st if r[5] == "out")
                    starters_missing[pos][1] += len(st)
                team_out.append(sum(1 for r in rs if r[5] == "out"))
                att = sum(r[11] for r in rs if r[9] and r[3] == "QB")
                rush = sum(r[12] for r in rs if r[9])
                tgt = sum(r[13] for r in rs if r[9] and r[3] != "QB")
                nq = sum(1 for r in rs if r[3] == "QB" and r[9] and r[11] >= 10)
                qb_team.append(nq)
                qa10 += nq
                qa20 += sum(1 for r in rs if r[3] == "QB" and r[9] and r[11] >= 20)
                if att >= 10:
                    team_tot.append((att, rush, tgt))
                    wr = sorted((r[13] for r in rs if r[3] == "WR" and r[9]), reverse=True)
                    te = sorted((r[13] for r in rs if r[3] == "TE" and r[9]), reverse=True)
                    rb = sorted((r[13] for r in rs if r[3] == "RB" and r[9]), reverse=True)
                    tt = sum(wr) + sum(te) + sum(rb)
                    if tt > 0:
                        for i in range(4):
                            share[f"WR{i + 1}"].append((wr[i] if i < len(wr) else 0.0) / tt)
                        share["TE1"].append((te[0] if te else 0.0) / tt)
                        share["RB1"].append((rb[0] if rb else 0.0) / tt)
                        share["RB2"].append((rb[1] if len(rb) > 1 else 0.0) / tt)
            qb_att10.append(qa10)
            qb_att20.append(qa20)
        byp = defaultdict(list)
        for row in W:
            byp[row[0], row[2]].append(row)
        for rs in byp.values():
            rs.sort(key=lambda r: r[1])
            for r in rs:
                if r[14]:
                    ret_w = r[1] + r[14] + 1
                    follow = [x for x in rs if ret_w <= x[1] <= ret_w + 7 and x[5] == "healthy"]
                    reinj[1] += len(follow)
                    reinj[0] += sum(1 for x in follow if x[14])
        pts_by = defaultdict(float)
        gp_by = Counter()
        fill_pts = defaultdict(float)
        fill_n = Counter()
        for row in W:
            if row[9]:
                pts_by[row[0], row[2]] += row[10]
                gp_by[row[0], row[2]] += 1
                if row[6] == "fill_in":
                    fill_pts[row[0], row[2]] += row[10]
                    fill_n[row[0], row[2]] += 1
        miss_by = Counter()
        avail_by = Counter()
        for row in W:
            if row[5] != "bye":
                avail_by[row[0], row[2]] += 1
                if row[5] == "out":
                    miss_by[row[0], row[2]] += 1
                    out_n[row[3]] += 1
                wk_n[row[3]] += 1
        bypos = defaultdict(list)
        for sr in g["season_rows"]:
            bypos[sr[0], sr[2]].append(sr)
        gsum = defaultdict(lambda: [0.0, 0.0])
        for sr in g["season_rows"]:
            if sr[3]:
                k = (sr[0], sr[2], sr[3])
                gsum[k][0] += pts_by[sr[0], sr[1]]
                gsum[k][1] += sr[5] * avail_by[sr[0], sr[1]]
        for (season, pos, team), (a, b) in gsum.items():
            if b > 20:
                group_ratio[pos].append(a / b)
        hurt_by = Counter()
        for row in W:
            if row[14] and row[5] == "healthy":
                hurt_by[row[0], row[2]] += 1
        for (season, pos), srs in bypos.items():
            pre = sorted(srs, key=lambda r: (-r[5], r[1]))
            pre_rank = {r[1]: i + 1 for i, r in enumerate(pre)}
            fin = sorted(srs, key=lambda r: (-pts_by[season, r[1]], r[1]))
            fin_rank = {r[1]: i + 1 for i, r in enumerate(fin)}
            top_n = {"QB": 24, "RB": 36, "WR": 36, "TE": 18}[pos]
            c = Counter(r[3] for r in fin[:top_n] if gp_by[season, r[1]] >= 8)
            for t in sorted({r[3] for r in srs if r[3]}):
                relevant[pos].append(c.get(t, 0))
            for r in srs:
                pid = r[1]
                if pos != "QB" and gp_by[season, pid] >= 8:
                    tier_pairs.append((r[5], pts_by[season, pid] / gp_by[season, pid]))
                if pre_rank[pid] <= TOP_N[pos]:
                    missed.append(miss_by[season, pid])
                    ab = _age_band(r[4])
                    if gp_by[season, pid] >= 4:
                        for k in ("age " + ab, "pos " + pos):
                            cms[k][0] += miss_by[season, pid]
                            cms[k][1] += avail_by[season, pid]
                    tier = "top12" if pre_rank[pid] <= 12 else "13-36" if pre_rank[pid] <= 36 else "37+"
                    age_i[ab] += hurt_by[season, pid]
                    age_n[ab] += avail_by[season, pid]
                    tier_i[tier] += hurt_by[season, pid]
                    tier_n[tier] += avail_by[season, pid]
                breakout_rows.append((pos, pre_rank[pid], fin_rank[pid], r[5], r[7], r[8], r[9], pts_by[season, pid], gp_by[season, pid],
                                      fill_pts[season, pid], fill_n[season, pid], r[11], season))
    out["group_points_over_projection_sum"] = {p: _ratio_summary(v) for p, v in sorted(group_ratio.items())}
    out["season_ppg_by_projection_tier"] = _tier_table(tier_pairs)
    out["cohort_missed_share_by_age_and_pos"] = {k: round(v[0] / v[1], 3) for k, v in sorted(cms.items())}
    out["missed_games_bucket_share"] = _bucket_share(missed)
    out["episodes_per_100_games_by_age"] = {k: round(100.0 * age_i[k] / age_n[k], 2) for k in age_n}
    out["episodes_per_100_games_by_tier"] = {k: round(100.0 * tier_i[k] / tier_n[k], 2) for k in tier_n}
    out["missed_share_by_pos"] = {p: round(out_n[p] / wk_n[p], 3) for p in sorted(wk_n)}
    out["injury_rate_per_100_player_games"] = {f"{p}/{c}": round(100.0 * inj[p, c] / exp[p, c], 2) for (p, c) in sorted(exp) if exp[p, c] > 200}
    byp = defaultdict(lambda: [0.0, 0.0])
    for (p, c), v in exp.items():
        byp[p][0] += inj[p, c]
        byp[p][1] += v
    out["injury_rate_per_100_by_pos"] = {p: round(100.0 * a / b, 2) for p, (a, b) in sorted(byp.items())}
    out["weeks_out_share"] = {p: {str(k): round(v / sum(c.values()), 3) for k, v in sorted(c.items())} for p, c in sorted(outlen.items())}
    out["injured_out_per_team_week"] = {"mean": round(float(np.mean(team_out)), 2), "p90": float(np.percentile(team_out, 90))}
    out["starters_out_share"] = {p: round(a / max(1, b), 3) for p, (a, b) in sorted(starters_missing.items())}
    out["qbs_att10_per_week"] = {"mean": round(float(np.mean(qb_att10)), 1), "p95": float(np.percentile(qb_att10, 95)), "max": int(max(qb_att10))}
    out["qbs_att20_per_week"] = {"mean": round(float(np.mean(qb_att20)), 1), "max": int(max(qb_att20))}
    out["qbs_with_a_game_per_week"] = {"mean": round(float(np.mean(qb_any)), 1), "p95": float(np.percentile(qb_any, 95)), "max": int(max(qb_any))}
    out["team_week_two_qbs_att10_share"] = round(float(np.mean(np.array(qb_team) >= 2)), 4)
    arr = np.array(team_tot)
    out["team_week_pool_totals_mean"] = {"pass_att": round(float(arr[:, 0].mean()), 1), "rush_att": round(float(arr[:, 1].mean()), 1), "targets": round(float(arr[:, 2].mean()), 1)}
    out["team_week_pool_totals_sd"] = {"pass_att": round(float(arr[:, 0].std()), 1), "rush_att": round(float(arr[:, 1].std()), 1), "targets": round(float(arr[:, 2].std()), 1)}
    out["target_share_ranked_in_team_week"] = {k: round(float(np.mean(v)), 3) for k, v in share.items() if v}
    out["reinjury_within_8_weeks_of_return_per_100_games"] = round(100.0 * reinj[0] / max(1, reinj[1]), 2)
    out["fill_in_games_per_100_starter_games"] = {p: round(100.0 * fill_in_n[p] / max(1, len(starter_pts[p])), 2) for p in CORE}
    out["fill_in_vs_starter_mean_pts"] = {p: [round(float(np.mean(fill_in_pts[p])), 2) if fill_in_pts[p] else None, round(float(np.mean(starter_pts[p])), 2) if starter_pts[p] else None] for p in CORE}
    out["relevant_per_team"] = {p: _rel_summary(v) for p, v in relevant.items()}
    out["breakouts"] = breakout_summary(breakout_rows, len(games), len(seasons_seen))
    return out


def breakout_summary(rows: list[tuple], n_games: int, n_seasons: int) -> dict[str, Any]:
    """rows: (pos, pre_rank, fin_rank, proj, archetype, season_mean, cum_promo, points, games, fill_pts, fill_n, rookie, season)."""

    out: dict[str, Any] = {}
    per = max(1, n_games * n_seasons)
    for pos, deep, top in (("RB", 50, 24), ("WR", 60, 24), ("TE", 20, 12), ("QB", 24, 12)):
        rs = [r for r in rows if r[0] == pos]
        deep_top = [r for r in rs if r[2] <= top and r[1] > deep]
        jumps = [r for r in rs if r[1] - r[2] >= 30 and r[2] <= 36]
        causes = Counter()
        for r in jumps:
            if r[10] >= 3 and r[7] > 0 and r[9] / r[7] >= 0.3:
                causes["injury cover (fill-in weeks >= 30% of points)"] += 1
            elif r[4] == "breakout":
                causes["breakout season story"] += 1
            elif r[6] >= 1.5:
                causes["natural role promotion (no injury ahead)"] += 1
            else:
                causes["solid-season draw / luck"] += 1
        out[pos] = {f"top{top}_from_pre_rank_gt{deep}_per_season": round(len(deep_top) / per, 2),
                    "finish_ge30_places_better_in_top36_per_season": round(len(jumps) / per, 2),
                    "causes_share": {k: round(v / max(1, len(jumps)), 3) for k, v in causes.most_common()}}
    return out


# ------------------------------------------------------------------------------------------------ cli


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--seed-start", type=int, default=1)
    ap.add_argument("--seasons", type=int, default=3)
    ap.add_argument("--procs", type=int, default=6)
    ap.add_argument("--model", default="")
    ap.add_argument("--dynasty-v", type=int, default=None)
    ap.add_argument("--world-v", type=int, default=None)
    ap.add_argument("--cap", default="", help="override game_usage.USAGE_CAP for a tuning run, e.g. RB=1.15,WR=1.15")
    ap.add_argument("--tier", default="", help="override game_usage TIER_A,TIER_B for a tuning run, e.g. 6.0,1.5")
    ap.add_argument("--json", default="")
    ap.add_argument("--real", action="store_true", help="print the real-panel yardsticks and exit")
    args = ap.parse_args(argv)
    if args.real:
        text = json.dumps(real_metrics(), indent=1)
        if args.json:
            open(args.json, "w").write(text)
        print(text)
        return
    from modules.sim import game_scoring, game_usage

    for part in filter(None, args.cap.split(",")):
        k, v = part.split("=")
        game_usage.USAGE_CAP[k] = float(v)
    if args.tier:
        game_usage.TIER_A, game_usage.TIER_B = (float(x) for x in args.tier.split(","))
    model_id = args.model or game_scoring.default_model().model_id
    pool, byes = tail_report.pool_from_panel(dataset.load_panel())
    jobs = [(s, args.seasons, model_id, pool, byes, args.dynasty_v, args.world_v) for s in range(args.seed_start, args.seed_start + args.seeds)]
    if args.procs > 1:
        with mp.get_context("fork").Pool(args.procs) as pl:
            games = pl.map(_worker, jobs, chunksize=1)
    else:
        games = [_worker(j) for j in jobs]
    res = {"model": model_id, "seeds": args.seeds, "seasons": args.seasons, "sim": aggregate(games)}
    text = json.dumps(res, indent=1)
    if args.json:
        open(args.json, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
