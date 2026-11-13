"""Generated rookie classes vs the real ones in the calibration panel.

``python -m modules.sim.calibration.rookie_audit`` prints the comparison tables
(the report in ``docs/audits/2026-11-generated-rookie-classes.md`` is this output
plus commentary). Real side: rookies in ``calibration/data/panel.json.gz``
(2021-2025, QB/RB/WR/TE with a preseason projection; the panel has no draft round
or pick, so class rank by preseason projection stands in for draft slot). Sim side:
``game_dynasty.rookie_class`` run over many seeds against the synthetic veteran
pool (the generator scales itself to whatever pool it is handed).

Everything is expressed relative to the position's 12th-best veteran projection
("ref12") so the real PPR panel and the game's scoring-agnostic pool compare.
Pure stdlib + numpy; reads only the committed panel.
"""

from __future__ import annotations

import statistics
from collections import Counter
from typing import Any

from modules.sim.calibration.age_curve import _load

POS = ("QB", "RB", "WR", "TE")
SLICES = (12, 24, 36)


def _ref12(rows: list[dict[str, Any]], key=lambda r: r["proj_ppg"]) -> dict[str, float]:
    out = {}
    for pos in POS:
        v = sorted((key(r) for r in rows if r["pos"] == pos and not r["_rookie"]), reverse=True)
        out[pos] = v[min(11, len(v) - 1)] if v else 1.0
    return out


def class_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Stats of ONE class. Rows: dicts with pos, proj (projection), age, rookie flag ``_rookie``
    over vets AND rookies of that year."""

    ref = _ref12(rows, key=lambda r: r["proj_ppg"])
    rooks = sorted((r for r in rows if r["_rookie"] and r["pos"] in POS), key=lambda r: -r["proj_ppg"])
    rank = {}
    for pos in POS:
        pool = sorted((r for r in rows if r["pos"] == pos), key=lambda r: -r["proj_ppg"])
        for i, r in enumerate(pool):
            rank[id(r)] = i + 1
    rel = {k: sum(1 for r in rooks if rank[id(r)] <= k) for k in SLICES}
    by_bucket = {}
    for name, lo, hi in (("1-6", 1, 6), ("7-15", 7, 15), ("16-30", 16, 30), ("31+", 31, 999)):
        xs = [r["proj_ppg"] / ref[r["pos"]] for i, r in enumerate(rooks) if lo <= i + 1 <= hi]
        by_bucket[name] = xs
    return {
        "n": len(rooks), "mix": Counter(r["pos"] for r in rooks), "rel": rel, "bucket": by_bucket,
        "ages": [r["age"] for r in rooks],
        "strength": sum(r["proj_ppg"] / ref[r["pos"]] for r in rooks[:12]),
    }


def real_classes() -> list[dict[str, Any]]:
    rows = _load()
    out = []
    for season in sorted({r["season"] for r in rows}):
        pool = [
            {"pos": r["pos"], "proj_ppg": float(r["proj_ppg"]), "age": float(r["age"]), "_rookie": bool(r["rookie"])}
            for r in rows if r["season"] == season and r["pos"] in POS and r["proj_ppg"]
        ]
        out.append({"season": season, **class_stats(pool)})
    return out


def summarize(classes: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(classes)
    mix = Counter()
    for c in classes:
        mix.update(c["mix"])
    total = sum(mix.values()) or 1
    ages = [a for c in classes for a in c["ages"]]
    strength = [c["strength"] for c in classes]
    return {
        "classes": n, "avg_size": sum(c["n"] for c in classes) / n,
        "mix": {p: mix[p] / total for p in POS},
        "rel": {k: sum(c["rel"][k] for c in classes) / n for k in SLICES},
        "bucket": {b: statistics.median([x for c in classes for x in c["bucket"][b]] or [0.0]) for b in ("1-6", "7-15", "16-30", "31+")},
        "age_mean": statistics.mean(ages), "age_sd": statistics.pstdev(ages),
        "strength_mean": statistics.mean(strength), "strength_cv": statistics.pstdev(strength) / statistics.mean(strength),
    }


def sim_classes(seeds: range, *, teams: int = 12, rounds: int = 4) -> list[dict[str, Any]]:
    from modules.sim.game_dynasty import rookie_class
    from modules.sim.game_setup import build_snapshot
    from modules.sim.game_types import GameSettings
    from modules.sim.synthetic import build_synthetic_pool

    rows, byes = build_synthetic_pool(7)
    out = []
    base = None
    for seed in seeds:
        if base is None:
            st = GameSettings.parse({"mode": "dynasty", "teams": teams, "start_year": 2026, "rookie_rounds": rounds, "seasons": 5})
            base = build_snapshot(rows, byes, st, seed)
        # The generator only reads ``base.settings`` and ``base.seed``; swap the seed per draw.
        object.__setattr__(base, "seed", seed)
        vets = {p.pid: {"pid": p.pid, "pos": p.pos, "mean": p.mean, "market": p.market, "nfl_team": p.nfl_team}
                for p in base.players.values() if p.pos in POS}
        new = rookie_class(base, vets, 2)
        pool = [{"pos": v["pos"], "proj_ppg": v["mean"], "age": 26.0, "_rookie": False} for v in vets.values()]
        pool += [{"pos": r["pos"], "proj_ppg": r["mean"], "age": r["age"], "_rookie": True} for r in new]
        out.append(class_stats(pool))
    return out


def main() -> None:  # pragma: no cover - a reporting tool
    real, sim = summarize(real_classes()), summarize(sim_classes(range(1000, 1600)))
    print("metric | real (2021-25) | generated (600 classes)")
    print(f"avg class size | {real['avg_size']:.1f} | {sim['avg_size']:.1f}")
    for p in POS:
        print(f"mix {p} | {real['mix'][p]:.2f} | {sim['mix'][p]:.2f}")
    for k in SLICES:
        print(f"rookies in pos top-{k} by projection | {real['rel'][k]:.1f} | {sim['rel'][k]:.1f}")
    for b in ("1-6", "7-15", "16-30", "31+"):
        print(f"median proj/ref12, class rank {b} | {real['bucket'][b]:.2f} | {sim['bucket'][b]:.2f}")
    print(f"age mean/sd | {real['age_mean']:.2f}/{real['age_sd']:.2f} | {sim['age_mean']:.2f}/{sim['age_sd']:.2f}")
    print(f"class strength cv | {real['strength_cv']:.3f} | {sim['strength_cv']:.3f}")


if __name__ == "__main__":  # pragma: no cover
    main()
