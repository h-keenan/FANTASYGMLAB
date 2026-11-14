"""Letter-grade calibration: how the shown grades are distributed, how well they track real outcomes, and whether
"draft the highest grade" is an exploit.

    python -m modules.sim.calibration.grade_report dist     [--seeds 4]            # grade histogram per position
    python -m modules.sim.calibration.grade_report corr     [--seeds 6]            # Spearman: grade vs season ppg, vs hidden rating, vs projection
    python -m modules.sim.calibration.grade_report bots     [--seeds 12] [--only hint_new,value_only]  # draft bots: grade vs ADP+need vs hint vs oracle
    python -m modules.sim.calibration.grade_report all      [--seeds 8] [--json out.json]

Pure stdlib + numpy + modules.sim. Never touches data/players.db (pool from the committed calibration panel).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from typing import Any, Callable

import numpy as np

from modules.sim import game_grades as gg
from modules.sim import game_scoring
from modules.sim.calibration import dataset, tail_report
from modules.sim.calibration.realism_sweep import spearman
from modules.sim.game_draft import DraftContext, _candidates, choose_pick, choose_public, run_ai_picks, user_pick
from modules.sim.game_engine import advance, finish_draft, rank_teams
from modules.sim.game_setup import build_snapshot
from modules.sim.game_state import Emitter, GameState
from modules.sim.game_types import GameSettings

CORE = ("QB", "RB", "WR", "TE")
SHAPE = {"teams": 12, "scoring": "ppr", "auto_lineup": True}


def _pool():
    return tail_report.pool_from_panel(dataset.load_panel())


def _settings(seed: int) -> GameSettings:
    return GameSettings.parse({"user_slot": 1 + seed % SHAPE["teams"], **SHAPE})


# ---------------------------------------------------------------------------------- bots

Bot = Callable[[DraftContext, str, int], str]


def bot_grade(ctx: DraftContext, tid: str, n: int) -> str:
    """Highest SHOWN grade among the legal candidates (ties: ADP). The exploit a player would try."""
    snap = ctx.snap
    cands = _candidates(ctx, tid, n)
    return max(cands, key=lambda p: (gg.sort_key(snap, p, 1), -snap.players[p].adp, p))


def bot_adp_need(ctx: DraftContext, tid: str, n: int) -> str:
    """Public information only: the best ADP among the legal candidates (the legality filter is the roster-need rule)."""
    return _candidates(ctx, tid, n)[0]


def bot_grade_near_adp(ctx: DraftContext, tid: str, n: int) -> str:
    """The smarter exploit: stay near the ADP board (so positions stay balanced) and break ties by the SHOWN grade."""
    snap = ctx.snap
    cands = _candidates(ctx, tid, n)
    best = snap.players[cands[0]].adp
    near = [p for p in cands if snap.players[p].adp <= best + 12.0]
    return max(near, key=lambda p: (gg.sort_key(snap, p, 1), -snap.players[p].adp, p))


def bot_oracle(ctx: DraftContext, tid: str, n: int) -> str:
    """The engine's own auto-pick: hidden value + need. An upper bound no real player can see."""
    return choose_pick(ctx, tid, n, 0, human=True)


def bot_hint(ctx: DraftContext, tid: str, n: int) -> str:
    """hint_v 1: always take the hint / Auto-pick (public ADP + need + bye overlap, shown grade breaking ties)."""
    return choose_public(ctx, tid, n)


def bot_value_only(ctx: DraftContext, tid: str, n: int) -> str:
    """Hidden value alone among the legal candidates, no need bonus: isolates what the hidden number adds."""
    snap = ctx.snap
    return max(_candidates(ctx, tid, n), key=lambda p: (snap.players[p].value, p))


def _with_spots(need: float, bye: float) -> Bot:
    from modules.sim import game_draft as gd

    def bot(ctx: DraftContext, tid: str, n: int) -> str:
        old = gd.NEED_SPOTS, gd.BYE_SPOTS
        gd.NEED_SPOTS, gd.BYE_SPOTS = need, bye
        try:
            return choose_public(ctx, tid, n)
        finally:
            gd.NEED_SPOTS, gd.BYE_SPOTS = old
    return bot


BOTS: dict[str, Bot] = {"grade": bot_grade, "grade_near_adp": bot_grade_near_adp, "adp_need": bot_adp_need, "hint_new": bot_hint, "oracle": bot_oracle,
    "value_only": bot_value_only, "hint_need_only": _with_spots(0.8, 0.0), "hint_bye_only": _with_spots(0.0, 2.0)}


def play(pool, byes, seed: int, bot: Bot | None, model_id: str) -> dict[str, Any]:
    settings = _settings(seed)
    snap = build_snapshot(pool, byes, settings, seed, scoring_model=model_id)
    state = GameState(snap)
    em = Emitter(state, snap)
    ctx = DraftContext(snap, state)
    run_ai_picks(ctx, em, seed)
    user = snap.user_team.tid
    while state.pick_index < ctx.total:
        pid = bot(ctx, user, state.pick_index) if bot else choose_pick(ctx, user, state.pick_index, seed, human=True)
        user_pick(ctx, em, pid, seed)
    finish_draft(em, snap, state, seed)
    while state.status in ("in_season", "playoffs"):
        em = Emitter(state, snap)
        advance(em, snap, state, seed)
    ranks = rank_teams(snap, state)
    st = state.stand[user]
    mine = [p for p in state.picks if p["team"] == user]
    shape = {
        "reach": float(np.mean([snap.players[p["pid"]].adp - (p["n"] + 1) for p in mine])),  # > 0: took players before their ADP
        "max_reach": float(max(snap.players[p["pid"]].adp - (p["n"] + 1) for p in mine)),
        "pos": dict(Counter(snap.players[p["pid"]].pos for p in mine)),
        "first_k": min((p["round"] for p in mine if snap.players[p["pid"]].pos == "K"), default=None),
        "first_def": min((p["round"] for p in mine if snap.players[p["pid"]].pos == "DEF"), default=None),
        "top_adp_hits": sum(1 for p in mine if p["round"] <= 4 and snap.players[p["pid"]].pos in ("RB", "WR")),
    }
    return {"shape": shape, "snap": snap, "state": state, "wins": st["w"] + 0.5 * st["t"], "pf": st["pf"], "rank": ranks.index(user) + 1 if user in ranks else None,
            "champion": state.champion == user}


# ------------------------------------------------------------------------------ correlation


def outcomes(g: dict[str, Any]) -> list[dict[str, Any]]:
    snap, state = g["snap"], g["state"]
    rows = []
    for pid in snap.pids:
        p = snap.players[pid]
        pts = [x for x in state.points.get(pid, [])[: snap.settings.regular_weeks] if x is not None]
        if p.pos not in CORE or len(pts) < 8:
            continue
        info = gg.grade_of(snap, pid, 1)
        if info is None:
            continue
        rows.append({"pid": pid, "pos": p.pos, "ppg": float(np.mean(pts)), "grade": info["index"], "hidden": p.value, "proj": p.mean})
    return rows


def correlations(seeds: int) -> dict[str, Any]:
    pool, byes = _pool()
    model_id = game_scoring.default_model().model_id
    per = defaultdict(lambda: defaultdict(list))
    hist = Counter()
    for seed in range(1, seeds + 1):
        rows = outcomes(play(pool, byes, seed, None, model_id))
        for pos in CORE:
            r = [x for x in rows if x["pos"] == pos]
            if len(r) < 20:
                continue
            ppg = [x["ppg"] for x in r]
            per[pos]["grade_vs_ppg"].append(spearman([x["grade"] for x in r], ppg))
            per[pos]["hidden_vs_grade"].append(spearman([x["grade"] for x in r], [x["hidden"] for x in r]))
            per[pos]["hidden_vs_ppg"].append(spearman([x["hidden"] for x in r], ppg))
            per[pos]["proj_vs_ppg"].append(spearman([x["proj"] for x in r], ppg))
            # top-12 at the position by ppg: how many a top-12 grade sort catches
            top = set(sorted(range(len(r)), key=lambda i: -ppg[i])[:12])
            byg = set(sorted(range(len(r)), key=lambda i: (-r[i]["grade"], -r[i]["proj"]))[:12])
            byh = set(sorted(range(len(r)), key=lambda i: -r[i]["hidden"])[:12])
            per[pos]["grade_top12_hit"].append(len(top & byg) / 12)
            per[pos]["hidden_top12_hit"].append(len(top & byh) / 12)
    return {pos: {k: round(float(np.mean(v)), 3) for k, v in d.items()} for pos, d in per.items()}


def distribution(seeds: int) -> dict[str, Any]:
    pool, byes = _pool()
    model_id = game_scoring.default_model().model_id
    out: dict[str, Any] = {}
    for scope in ("pool", "drafted"):
        out[scope] = {}
    for seed in range(1, seeds + 1):
        g = play(pool, byes, seed, None, model_id)
        snap, state = g["snap"], g["state"]
        drafted = {p for roster in state.rosters.values() for p in roster}
        for pid in snap.pids:
            info = gg.grade_of(snap, pid, 1)
            if info is None:
                continue
            pos = snap.players[pid].pos
            out["pool"].setdefault(pos, Counter())[info["letter"]] += 1
            out["pool"].setdefault("ALL", Counter())[info["letter"]] += 1
            if pid in drafted:
                out["drafted"].setdefault(pos, Counter())[info["letter"]] += 1
                out["drafted"].setdefault("ALL", Counter())[info["letter"]] += 1
    res: dict[str, Any] = {}
    for scope, by_pos in out.items():
        res[scope] = {}
        for pos, c in by_pos.items():
            n = sum(c.values())
            res[scope][pos] = {letter: round(100.0 * c[letter] / n, 1) for letter in reversed(gg.LETTERS)}
    return res


# ------------------------------------------------------------------------------------ bots


def bot_compare(seeds: int, only: tuple[str, ...] = ()) -> dict[str, Any]:
    pool, byes = _pool()
    model_id = game_scoring.default_model().model_id
    res: dict[str, Any] = {}
    for name, bot in BOTS.items():
        if only and name not in only and name != "adp_need":
            continue
        runs = [play(pool, byes, s, bot, model_id) for s in range(1, seeds + 1)]
        res[name] = {
            "wins": [r["wins"] for r in runs], "pf": [round(r["pf"], 1) for r in runs], "rank": [r["rank"] for r in runs],
            "champs": sum(1 for r in runs if r["champion"]),
            "shape": {k: (round(float(np.mean([r["shape"][k] for r in runs])), 2)) for k in ("reach", "max_reach", "top_adp_hits")}
            | {"pos": {pos: round(float(np.mean([r["shape"]["pos"].get(pos, 0) for r in runs])), 2) for pos in ("QB", "RB", "WR", "TE", "K", "DEF")},
               "first_k_round": round(float(np.mean([r["shape"]["first_k"] or 0 for r in runs])), 1)},
        }
    summary = {}
    for name, r in res.items():
        w, pf, rk = np.array(r["wins"], float), np.array(r["pf"], float), np.array(r["rank"], float)
        summary[name] = {"mean_wins": round(float(w.mean()), 2), "mean_pf": round(float(pf.mean()), 1), "mean_rank": round(float(rk.mean()), 2), "champs": r["champs"], "n": len(w)}
    base = np.array(res["adp_need"]["wins"], float)
    for name, r in res.items():
        summary[name]["draft_shape"] = r["shape"]
    for name in ("grade", "grade_near_adp", "hint_new", "oracle", "value_only", "hint_need_only", "hint_bye_only"):
        if name not in res:
            continue
        d = np.array(res[name]["wins"], float) - base
        se = float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else 0.0
        summary[name]["wins_vs_adp_need"] = {"diff": round(float(d.mean()), 2), "se": round(se, 2)}
        dpf = np.array(res[name]["pf"], float) - np.array(res["adp_need"]["pf"], float)
        summary[name]["pf_vs_adp_need"] = {"diff": round(float(dpf.mean()), 1), "se": round(float(dpf.std(ddof=1) / np.sqrt(len(dpf))), 1) if len(dpf) > 1 else 0.0}
    return summary


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=["dist", "corr", "bots", "all"])
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--json", default="")
    ap.add_argument("--only", default="", help="bots: comma list of bot names to run besides the adp_need baseline")
    a = ap.parse_args(argv)
    res: dict[str, Any] = {}
    if a.cmd in ("dist", "all"):
        res["distribution"] = distribution(max(1, a.seeds // 2))
    if a.cmd in ("corr", "all"):
        res["correlations"] = correlations(a.seeds)
    if a.cmd in ("bots", "all"):
        res["bots"] = bot_compare(a.seeds, tuple(x for x in a.only.split(",") if x))
    text = json.dumps(res, indent=1)
    if a.json:
        open(a.json, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()
