"""stability_v: the fast (no games played) measurements behind docs/audits/2026-11-sim-desk-logic-realism-audit.md, "Implemented".

Builds whole dynasties' season pools from the real 2025 panel (a dynasty's offseason is a pure function of the seed, so nothing is simulated) and
reports, per ``stability_v`` and player model:

* ``levels``: the hidden projection at the ranks that matter (top of a position, its flex tier, its bench tier) by season, the pool's mean age;
* ``ratios``: the REALIZED next / this points-per-game ratio of players at 6+ ppg and 8+ games both years, by position and age (read from the same season
  profile the engine plays), the shape the real panel gives (WR 22 = 1.05, RB 22 = 1.07, TE 23 = 1.14);
* ``rookies``: the share of each class-rank band that finishes under 0.6 of its projection (a bust) and over 8 ppg in year 1.

    python -m modules.sim.calibration.stability_report [--seeds 8] [--seasons 10]

The full-league numbers (team scores, parity, week-by-week decay) come from ``dynasty_run.py`` + ``dynasty_distributions.py``. Pure stdlib + numpy;
never touches data/players.db (the panel is a committed file).
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import replace
from typing import Any

import numpy as np

from modules.sim import game_dynasty as dyn
from modules.sim.calibration import dataset, tail_report
from modules.sim.game_engine import session_for
from modules.sim.game_setup import build_snapshot
from modules.sim.game_types import GameSettings

SKILL = ("QB", "RB", "WR", "TE")
LEVEL_RANKS = {"QB": (12, 24), "RB": (12, 24, 36), "WR": (12, 24, 36), "TE": (12, 24)}
BANDS = {"21-22": (21, 22), "23-24": (23, 24), "25-26": (25, 26), "27-28": (27, 28), "29-30": (29, 30)}
OLD_MODEL = "player_model-player-model-6"  # the player model of every game made before stability_v


def pool_stats(seeds: int = 8, seasons: int = 10, *, stability_v: int = 1, model_id: str | None = None, teams: int = 12) -> dict[str, Any]:
    rows, byes = tail_report.pool_from_panel(dataset.load_panel())
    if model_id is None:
        from modules.sim import game_scoring

        model_id = game_scoring.default_model().model_id
    levels: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    ratios: dict[tuple[str, int], list[float]] = defaultdict(list)
    rookies: list[tuple[float, float, float]] = []  # (class rank, realized / projection, realized ppg)
    for seed in range(1, seeds + 1):
        base = GameSettings.parse({"mode": "dynasty", "teams": teams, "user_slot": 3, "start_year": 2026, "seasons": seasons, "rookie_rounds": 3, "scoring": "ppr"})
        root = build_snapshot(rows, byes, replace(base, stability_v=stability_v), seed, scoring_model=model_id)
        prev: dict[str, tuple[str, float, float]] = {}
        for n in range(1, seasons + 1):
            snap = root.season_view(n)
            session = session_for(snap, dyn.season_seed(seed, n))
            cur: dict[str, tuple[str, float, float]] = {}
            for pos in SKILL:
                ps = sorted((p for p in snap.players.values() if p.pos == pos), key=lambda p: -p.mean)
                for r in LEVEL_RANKS[pos]:
                    levels[n][f"{pos}{r}"].append(float(np.mean([p.mean for p in ps[:r]])))
            valued = sorted(snap.players.values(), key=lambda p: -p.value)[: teams * 16]
            levels[n]["age"].append(float(np.mean([p.age for p in valued])))
            for pid, p in snap.players.items():
                if p.pos not in SKILL:
                    continue
                profile = session.profile(pid)
                if sum(1 for m in profile.games_available_mask if m) >= 8:
                    cur[pid] = (p.pos, p.age, float(profile.season_mean_ppg))
                if p.extra.get("is_rookie") and "class_rank" in p.extra:
                    rookies.append((float(p.extra["class_rank"]), float(profile.season_multiplier), float(profile.season_mean_ppg)))
            for pid, (pos, age, ppg) in prev.items():
                if pid in cur and ppg >= 6.0:
                    ratios[(pos, int(age))].append(cur[pid][2] / ppg)
            prev = cur
    return {"levels": levels, "ratios": ratios, "rookies": rookies, "seasons": seasons}


def mean_level(stats: dict[str, Any], key: str, seasons: range) -> float:
    return float(np.mean([np.mean(stats["levels"][n][key]) for n in seasons]))


def ratio(stats: dict[str, Any], pos: str, ages: tuple[int, ...]) -> float:
    xs = [x for a in ages for x in stats["ratios"].get((pos, a), [])]
    return float(np.mean(xs)) if xs else float("nan")


def bust_rate(stats: dict[str, Any], lo: int, hi: int) -> tuple[float, float, float]:
    """(share under 0.6 of the projection, share over 8 ppg, mean realized / projection) for class ranks ``lo``..``hi``."""

    sel = [r for r in stats["rookies"] if lo <= r[0] <= hi]
    if not sel:
        return (float("nan"),) * 3
    return float(np.mean([r[1] < 0.6 for r in sel])), float(np.mean([r[2] > 8.0 for r in sel])), float(np.mean([r[1] for r in sel]))


def report(seeds: int, seasons: int) -> str:
    old = pool_stats(seeds, seasons, stability_v=0, model_id=OLD_MODEL)
    new = pool_stats(seeds, seasons, stability_v=1)
    out = ["metric | before (stability_v 0) | after (stability_v 1) | real panel"]
    for label, pos, ages, real in (("WR 22 realized next/this ppg", "WR", (22,), 1.05), ("WR 23", "WR", (23,), 0.97), ("RB 22", "RB", (22,), 1.07), ("TE 23", "TE", (23,), 1.14), ("TE 24", "TE", (24,), 1.04)):
        out.append(f"{label} | {ratio(old, pos, ages):.2f} | {ratio(new, pos, ages):.2f} | {real:.2f}")
    for pos in SKILL:
        for name, ages in BANDS.items():
            out.append(f"{pos} age {name} | {ratio(old, pos, ages_range(ages)):.2f} | {ratio(new, pos, ages_range(ages)):.2f} |")
    for lo, hi in ((1, 12), (13, 24), (25, 48)):
        o, n = bust_rate(old, lo, hi), bust_rate(new, lo, hi)
        out.append(f"rookie class rank {lo}-{hi}: bust (< 0.6 of projection) | {o[0]:.2f} | {n[0]:.2f} | about 0.20 (top 12)")
        out.append(f"rookie class rank {lo}-{hi}: over 8 ppg in year 1 | {o[1]:.2f} | {n[1]:.2f} |")
    for key in ("RB24", "RB36", "WR24", "WR36", "QB24", "TE12"):
        for label, rng in (("season 1", range(1, 2)), ("seasons 6-10", range(6, seasons + 1))):
            out.append(f"pool {key} projection, {label} | {mean_level(old, key, rng):.1f} | {mean_level(new, key, rng):.1f} |")
    for label, rng in (("season 1", range(1, 2)), ("seasons 6-10", range(6, seasons + 1))):
        out.append(f"pool mean age of the {12 * 16} most valuable players, {label} | {mean_level(old, 'age', rng):.2f} | {mean_level(new, 'age', rng):.2f} |")
    return "\n".join(out)


def ages_range(ages: tuple[int, int]) -> tuple[int, ...]:
    return tuple(range(ages[0], ages[1] + 1))


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - a reporting tool
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--seasons", type=int, default=10)
    args = ap.parse_args(argv)
    print(report(args.seeds, args.seasons))


if __name__ == "__main__":  # pragma: no cover
    main()
