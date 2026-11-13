"""Year-over-year age curves from the real-history panel.

``python -m modules.sim.calibration.age_curve`` prints, per position and age
bucket, the median ratio of a player's next-season points per game to this
season's (players with at least ``MIN_GAMES`` games both years). The knots in
``modules/sim/aging.py`` are smoothed from this table; ``tests`` check the
baked curve stays within tolerance of it where the panel has enough players.
Pure stdlib; reads only the committed panel.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

from modules.sim.calibration.dataset import PANEL_PATH

MIN_GAMES = 8
MIN_PPG = 3.0
MIN_BUCKET = 8  # players needed before a bucket is reported


def _load() -> list[dict[str, Any]]:
    import gzip
    import json

    with gzip.open(PANEL_PATH, "rt") as fh:
        return json.load(fh)["rows"]


def season_ppg(rows: list[dict[str, Any]]) -> dict[tuple[str, int], tuple[str, float, float]]:
    out = {}
    for r in rows:
        played = [w[1] for w in r["weeks"] if w and w[0] == 1]
        if len(played) >= MIN_GAMES:
            out[(r["pid"], r["season"])] = (r["pos"], float(r["age"]), sum(played) / len(played))
    return out


def ratios(rows: list[dict[str, Any]] | None = None) -> dict[tuple[str, int], list[float]]:
    """{(pos, two-year age bucket): [next/this ppg ratios]}."""

    table = season_ppg(rows if rows is not None else _load())
    out: dict[tuple[str, int], list[float]] = defaultdict(list)
    for (pid, season), (pos, age, ppg) in table.items():
        nxt = table.get((pid, season + 1))
        if nxt and ppg > MIN_PPG:
            out[(pos, int(age // 2) * 2)].append(nxt[2] / ppg)
    return out


def curve_table(rows: list[dict[str, Any]] | None = None) -> dict[tuple[str, int], tuple[int, float]]:
    return {
        key: (len(v), statistics.median(v)) for key, v in sorted(ratios(rows).items()) if len(v) >= MIN_BUCKET
    }


def main() -> None:  # pragma: no cover - a reporting tool
    for (pos, age), (n, med) in curve_table().items():
        print(f"{pos} age {age}-{age + 1}: n={n:<4} median next/this ppg = {med:.2f}")


if __name__ == "__main__":  # pragma: no cover
    main()
