"""Weekly TEAM score distribution (low tail) in the Sim vs real 12-team leagues, and what makes the Sim's low weeks.

    python -m modules.sim.calibration.team_score_report sim  [--seeds 16] [--seasons 2] [--flags '{"lineup_v": 0}'] [--json out.json]
    python -m modules.sim.calibration.team_score_report real --cache DIR [--leagues 12] [--json out.json]
    python -m modules.sim.calibration.team_score_report decompose [--seeds 16] [--flags ...]

``sim``        whole redraft games on the committed 2025 panel pool (never ``data/players.db``), regular season only, by format
               (PPR / half / standard, 1QB / superflex, bench size, K+DEF).
``real``       real weekly team scores rebuilt from Sleeper public weekly stats + projections 2021-25 (``--cache`` holds the
               ``stats_{season}_{week}.json`` / ``proj_{season}_{week}.json`` files ``scripts/projection_calibration_backtest.py fetch``
               writes, with ``position[]=DEF`` added). Per season, ``--leagues`` independent 12-team leagues: a snake draft by the real
               preseason ADP (Sleeper ``adp_dd_ppr`` in the week-1 projection, with noise), a waiver wire, and every week each manager
               starts the best lineup by that week's published Sleeper projection (healthy-looking players only), with an optional share of
               stale lineups (a manager who did not touch his lineup). Scores are the real week's Sleeper points.
``decompose``  the Sim's low team weeks (< 70) split by cause: an empty slot, a started player who was out / on bye, a healthy starter
               who did not play (inactive), a K / DEF dud, and a bust by a player who did play (independent vs team-correlated).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

QS = (1, 5, 10, 50, 90, 99)
CUTS_LOW = (50, 60, 70, 80)
CUTS_HIGH = (170, 200)


def summarize(vals) -> dict[str, float]:
    v = np.asarray(list(vals), dtype=float)
    out: dict[str, float] = {"n": int(v.size), "mean": float(v.mean()), "sd": float(v.std())}
    for q, x in zip(QS, np.percentile(v, QS)):
        out[f"p{q}"] = float(x)
    for c in CUTS_LOW:
        out[f"lt{c}"] = float((v < c).mean())
    for c in CUTS_HIGH:
        out[f"gt{c}"] = float((v > c).mean())
    out["min"] = float(v.min())
    return out


def fmt_row(name: str, s: dict[str, float]) -> str:
    return (f"{name:<34}{s['n']:>7}{s['mean']:>7.1f}{s['sd']:>6.1f}" + "".join(f"{s[f'p{q}']:>7.1f}" for q in QS)
            + "".join(f"{100 * s[f'lt{c}']:>6.2f}" for c in CUTS_LOW) + "".join(f"{100 * s[f'gt{c}']:>6.2f}" for c in CUTS_HIGH))


HEADER = (f"{'':<34}{'n':>7}{'mean':>7}{'sd':>6}" + "".join(f"{'p' + str(q):>7}" for q in QS)
          + "".join(f"{'<' + str(c) + '%':>6}" for c in CUTS_LOW) + "".join(f"{'>' + str(c) + '%':>6}" for c in CUTS_HIGH))


# ------------------------------------------------------------------------------------------------ sim side

FORMATS: dict[str, dict[str, Any]] = {
    "ppr 1QB K+DEF": {"scoring": "ppr", "include_def": True},
    "half 1QB K+DEF": {"scoring": "half", "include_def": True},
    "std 1QB K+DEF": {"scoring": "std", "include_def": True},
    "ppr superflex K+DEF": {"scoring": "ppr", "include_def": True, "superflex": True},
    "ppr 1QB K only (game default)": {"scoring": "ppr"},
    "ppr 1QB no K/DEF": {"scoring": "ppr", "include_k": False},
    "ppr 1QB K+DEF bench 4": {"scoring": "ppr", "include_def": True, "bench": 4},
    "ppr 1QB K+DEF bench 10": {"scoring": "ppr", "include_def": True, "bench": 10},
}


# what a typical starter at the slot is worth (only used to price an empty slot's shortfall)
SLOT_EXP = {"QB": 18.0, "SUPER_FLEX": 16.0, "RB": 11.0, "WR": 11.0, "TE": 8.0, "FLEX": 10.0, "WRRB_FLEX": 10.0, "K": 8.0, "DEF": 7.0}


class _Tap:
    """Records every team-week's started lineup with the facts the decomposition needs, by wrapping ``game_engine._team_score``
    (called from ``run_week`` with the lineups and the week's points in scope)."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def __enter__(self):
        from modules.sim import game_engine

        self._eng = game_engine
        self._orig = game_engine._team_score
        tap = self

        def wrapped(lineup, pts):
            frame = sys._getframe(1)
            while frame is not None and frame.f_code.co_name != "run_week":
                frame = frame.f_back
            score = tap._orig(lineup, pts)
            if frame is not None:
                loc = frame.f_locals
                ev, played, W, snap = loc["ev"], loc["played"], loc["W"], loc["snap"]
                user = snap.user_team.tid
                tid = next((t for t, lu in loc["lineups"].items() if lu is lineup), None)
                if loc["kind"] == "regular":  # rows carry ``user``: the user's lineup is whatever the human (or this harness) left
                    starters = []
                    for slot, pid in lineup:
                        if not pid:
                            starters.append(dict(slot=slot, pid=None, pos=None, cat="empty", pts=0.0, exp=SLOT_EXP.get(slot, 10.0)))
                            continue
                        pos = snap.players[pid].pos
                        status = ev.status(pid, W)
                        exp = float(ev.ros_mean(pid))
                        cat = "played" if pid in played else ("out" if status == "out" else "bye" if status == "bye" else "inactive")
                        hurt = bool(played[pid].newly_injured) if pid in played else False
                        starters.append(dict(slot=slot, pid=pid, pos=pos, cat=cat, pts=float(pts.get(pid, 0.0)), exp=exp, hurt=hurt))
                    tap.rows.append(dict(score=score, week=W, starters=starters, user=tid == user))
            return score

        game_engine._team_score = wrapped
        return self

    def __exit__(self, *exc):
        self._eng._team_score = self._orig


def run_games(seeds: int, seasons: int, fmt: dict[str, Any], flags: dict[str, int], who: str = "ai", seed0: int = 1):
    """Team-week rows for ``seeds`` games x ``seasons`` back-to-back seeds on the 2025 panel pool."""

    from modules.sim.calibration import realism_p1_report as rp
    from modules.sim.game_engine import advance
    from modules.sim.game_state import Emitter

    rows: list[dict[str, Any]] = []
    with _Tap() as tap:
        for s in range(seeds * seasons):
            seed = seed0 + s
            snap, state = rp._new_game(seed, flags, fmt)
            while state.status == "in_season" and state.week <= snap.settings.regular_weeks:
                advance(Emitter(state, snap), snap, state, seed)
        rows = [r for r in tap.rows if who == "all" or r["user"] == (who == "user")]
    return rows


def cmd_sim(args) -> dict[str, Any]:
    flags = json.loads(args.flags or "{}")
    out: dict[str, Any] = {}
    print(HEADER)
    for name, fmt in FORMATS.items():
        if args.only and args.only not in name:
            continue
        rows = run_games(args.seeds, args.seasons, fmt, flags, args.who)
        out[name] = summarize([r["score"] for r in rows])
        print(fmt_row(name, out[name]))
    return out


def decompose(rows: list[dict[str, Any]], cut: float = 70.0) -> dict[str, Any]:
    """Split the shortfall (expected - scored, summed over the starters) of team-weeks under ``cut`` by cause."""

    low = [r for r in rows if r["score"] < cut]
    parts: dict[str, float] = defaultdict(float)
    weeks_with: dict[str, int] = defaultdict(int)
    for r in low:
        seen = set()
        for s in r["starters"]:
            short = s["exp"] - s["pts"]
            if s["cat"] == "empty":
                key = "empty slot"
            elif s["cat"] in ("out", "bye"):
                key = f"started a player who was {s['cat']}"
            elif s["cat"] == "inactive":
                key = "healthy starter did not play"
            elif s["pos"] in ("K", "DEF"):
                key = "K / DEF below mean"
            elif s.get("hurt"):
                key = "hurt in the game (partial)"
            elif s["pts"] < 0.4 * s["exp"] and s["exp"] > 4:
                key = "bust game (< 40% of mean)"
            else:
                key = "ordinary below-mean games"
            parts[key] += short
            if key != "ordinary below-mean games":
                seen.add(key)
        for k in seen:
            weeks_with[k] += 1
    total = sum(parts.values()) or 1.0
    return dict(n_low=len(low), n=len(rows), share_low=len(low) / max(1, len(rows)),
                parts={k: dict(points=v, share=v / total) for k, v in sorted(parts.items(), key=lambda kv: -kv[1])},
                weeks_with={k: v / max(1, len(low)) for k, v in weeks_with.items()})


def cmd_decompose(args) -> dict[str, Any]:
    flags = json.loads(args.flags or "{}")
    rows = run_games(args.seeds, args.seasons, FORMATS["ppr 1QB K+DEF"], flags, args.who)
    out = {}
    for cut in (60, 70, 80):
        d = decompose(rows, cut)
        out[str(cut)] = d
        print(f"\nteam weeks under {cut}: {d['n_low']} of {d['n']} ({100 * d['share_low']:.2f}%)")
        for k, v in d["parts"].items():
            print(f"  {k:<42} {100 * v['share']:>6.1f}% of shortfall   in {100 * d['weeks_with'].get(k, 0):>5.1f}% of those weeks")
    return out


# ------------------------------------------------------------------------------------------------ real side

LINEUP = ("QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DEF")
FLEX_POS = ("RB", "WR", "TE")
POS_CAP = {"QB": 3, "RB": 7, "WR": 7, "TE": 3, "K": 1, "DEF": 1}


def _load(cache: Path, season: int):
    stats: dict[int, dict[str, dict]] = {}
    proj: dict[int, dict[str, dict]] = {}
    pos: dict[str, str] = {}
    for w in range(1, 18):
        for pre, dest in (("stats", stats), ("proj", proj)):
            f = cache / f"{pre}_{season}_{w}.json"
            if not f.exists():
                continue
            d: dict[str, dict] = {}
            for r in json.loads(f.read_text()):
                p = (r.get("player") or {}).get("position")
                if p in ("QB", "RB", "WR", "TE", "K", "DEF"):
                    d[str(r["player_id"])] = r.get("stats") or {}
                    pos[str(r["player_id"])] = p
            dest[w] = d
    return stats, proj, pos


def _lineup(roster: list[str], pos: dict, proj: dict[str, float], slots: tuple[str, ...]) -> list[str]:
    """Best lineup by ``proj`` (greedy per position, then flex-type slots from what is left)."""

    chosen: list[str] = []
    left = sorted(roster, key=lambda p: -proj.get(p, 0.0))
    for slot in slots:
        if slot in FLEX_POS + ("QB", "K", "DEF") and slot != "FLEX":
            for p in left:
                if pos[p] == slot and proj.get(p, 0.0) > 0.5:
                    chosen.append(p)
                    left.remove(p)
                    break
    for slot in slots:
        if slot in ("FLEX", "SUPER_FLEX"):
            ok = FLEX_POS if slot == "FLEX" else ("QB",) + FLEX_POS
            for p in left:
                if pos[p] in ok and proj.get(p, 0.0) > 0.5:
                    chosen.append(p)
                    left.remove(p)
                    break
    return chosen


def real_scores(cache: Path, leagues: int, stale: float, rng: np.random.Generator, key: str, superflex: bool, seasons=range(2021, 2026), weeks=range(1, 15), log: list | None = None) -> list[float]:
    slots = LINEUP + (("SUPER_FLEX",) if superflex else ())
    out: list[float] = []
    for season in seasons:
        stats, proj, pos = _load(cache, season)
        if not stats or not proj or 1 not in proj:
            continue
        adp = {pid: float(s.get("adp_dd_ppr") or 400.0) for pid, s in proj[1].items()}
        for pid, p in pos.items():
            adp.setdefault(pid, 400.0)
        for _ in range(leagues):
            noisy = {pid: a * float(np.exp(rng.normal(0, 0.18))) for pid, a in adp.items() if pos[pid] in POS_CAP}
            # K / DEF go in the last two rounds like real drafts: push them past every skill player
            for pid in noisy:
                if pos[pid] in ("K", "DEF"):
                    noisy[pid] += 300.0
            order = sorted(noisy, key=lambda p: noisy[p])
            rosters = [[] for _ in range(12)]
            taken: set[str] = set()
            rounds = len(slots) + 6
            for rd in range(rounds):
                for i in (range(12) if rd % 2 == 0 else range(11, -1, -1)):
                    need_k = rd >= rounds - 2
                    for pid in order:
                        if pid in taken:
                            continue
                        r = rosters[i]
                        cnt = sum(1 for q in r if pos[q] == pos[pid])
                        cap = POS_CAP[pos[pid]] + (1 if superflex and pos[pid] == "QB" else 0)
                        if cnt >= cap:
                            continue
                        if pos[pid] in ("K", "DEF") and not need_k:
                            continue
                        r.append(pid)
                        taken.add(pid)
                        break
            prev: dict[int, list[str]] = {}
            for w in weeks:
                if w not in stats or w not in proj:
                    continue
                key_proj = {pid: float(s.get(key) or 0.0) for pid, s in proj[w].items()}
                free = sorted((p for p in key_proj if p not in taken and key_proj[p] > 0.5), key=lambda p: -key_proj[p])
                for i in rng.permutation(12):
                    r = rosters[i]
                    # waiver wire: fill each unfillable starting slot with the best free agent at the position (one claim per slot)
                    for slot in LINEUP:
                        have = [p for p in r if pos[p] == slot and key_proj.get(p, 0.0) > 0.5]
                        if slot in ("K", "DEF", "QB", "TE") and not have:
                            for p in free:
                                if pos.get(p) == slot:
                                    r.append(p)
                                    taken.add(p)
                                    free.remove(p)
                                    break
                    lu = _lineup(r, pos, key_proj, slots)
                    for _fill in range(3):  # any slot still vacant (bye / injury / scratch): the best free agent who fills it
                        if len(lu) >= len(slots):
                            break
                        for p in free:
                            if p in taken:
                                continue
                            if len(_lineup(r + [p], pos, key_proj, slots)) > len(lu):
                                r.append(p)
                                taken.add(p)
                                free.remove(p)
                                break
                        lu = _lineup(r, pos, key_proj, slots)
                    if i in prev and rng.random() < stale:
                        keep = [p for p in prev[i] if p in r and key_proj.get(p, 0.0) > 0.5]
                        lu = keep + [p for p in lu if p not in keep][: len(slots) - len(keep)]
                    prev[i] = lu
                    got = [float((stats[w].get(p) or {}).get(key) or 0.0) for p in lu]
                    out.append(sum(got))
                    if log is not None:
                        log.append(dict(score=sum(got), n=len(lu), pos=[pos[p] for p in lu], pts=got, proj=[key_proj.get(p, 0.0) for p in lu], season=season, week=w))
    return out


REAL_FORMATS = {
    "ppr 1QB K+DEF": ("pts_ppr", False), "half 1QB K+DEF": ("pts_half_ppr", False), "std 1QB K+DEF": ("pts_std", False),
    "ppr superflex K+DEF": ("pts_ppr", True),
}


def cmd_real(args) -> dict[str, Any]:
    out: dict[str, Any] = {}
    print(HEADER)
    for stale in (0.0, 0.1):
        for name, (key, sf) in REAL_FORMATS.items():
            rng = np.random.default_rng(7)
            vals = real_scores(Path(args.cache), args.leagues, stale, rng, key, sf)
            label = f"{name}" + (f" (+{int(stale * 100)}% stale lineups)" if stale else "")
            out[label] = summarize(vals)
            print(fmt_row(label, out[label]))
    return out


def cmd_starters(args) -> dict[str, Any]:
    """Starter-level bust rates, sim (AI teams) against the rebuilt real leagues: share of started player-weeks that score <= 2 points and
    that score under 40% of the pre-game expectation (real: that week's Sleeper projection; sim: the player's rest-of-season mean)."""

    flags = json.loads(args.flags or "{}")
    real_log: list = []
    real_scores(Path(args.cache), args.leagues, 0.0, np.random.default_rng(7), "pts_ppr", False, log=real_log)
    rows = run_games(args.seeds, args.seasons, FORMATS["ppr 1QB K+DEF"], flags)
    out: dict[str, Any] = {}
    cnt: dict[str, dict[str, list[int]]] = {"real": defaultdict(lambda: [0, 0, 0]), "sim": defaultdict(lambda: [0, 0, 0])}
    for r in real_log:
        for ps, pt, pj in zip(r["pos"], r["pts"], r["proj"]):
            c = cnt["real"][ps]
            c[0] += 1
            c[1] += pt <= 2.0
            c[2] += pj > 4 and pt < 0.4 * pj
    for r in rows:
        for st in r["starters"]:
            if st["pos"] is None:
                continue
            c = cnt["sim"][st["pos"]]
            c[0] += 1
            c[1] += st["pts"] <= 2.0
            c[2] += st["exp"] > 4 and st["pts"] < 0.4 * st["exp"]
    print(f"{'pos':<5}{'real n':>8}{'<=2pt %':>9}{'<40% %':>8}   {'sim n':>8}{'<=2pt %':>9}{'<40% %':>8}")
    for ps in ("QB", "RB", "WR", "TE", "K", "DEF"):
        a, b = cnt["real"][ps], cnt["sim"][ps]
        out[ps] = dict(real=a, sim=b)
        print(f"{ps:<5}{a[0]:>8}{100 * a[1] / max(1, a[0]):>9.1f}{100 * a[2] / max(1, a[0]):>8.1f}   {b[0]:>8}{100 * b[1] / max(1, b[0]):>9.1f}{100 * b[2] / max(1, b[0]):>8.1f}")
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("sim", "decompose"):
        p = sub.add_parser(n)
        p.add_argument("--seeds", type=int, default=16)
        p.add_argument("--seasons", type=int, default=2)
        p.add_argument("--flags", default="")
        p.add_argument("--only", default="")
        p.add_argument("--who", default="ai", choices=("ai", "user", "all"), help="AI-managed teams (default), the user's team (lineup never touched after the draft), or all")
        p.add_argument("--json", default="")
    p = sub.add_parser("starters")
    p.add_argument("--cache", required=True)
    p.add_argument("--leagues", type=int, default=12)
    p.add_argument("--seeds", type=int, default=16)
    p.add_argument("--seasons", type=int, default=2)
    p.add_argument("--flags", default="")
    p.add_argument("--json", default="")
    p = sub.add_parser("real")
    p.add_argument("--cache", required=True)
    p.add_argument("--leagues", type=int, default=12)
    p.add_argument("--json", default="")
    args = ap.parse_args(argv)
    res = {"sim": cmd_sim, "decompose": cmd_decompose, "real": cmd_real, "starters": cmd_starters}[args.cmd](args)
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
