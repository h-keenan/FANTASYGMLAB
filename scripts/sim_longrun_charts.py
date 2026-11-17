"""Charts for the long-run soak (docs/audits/2026-11-sim-longrun.md): one PNG per metric group from the soak's run directories. Needs matplotlib.

    (first write tables.json with `longrun_soak report --out DIR [--before DIR3] --json tables.json`, see the audit)
    python scripts/sim_longrun_charts.py tables.json docs/audits/sim-longrun
"""

from __future__ import annotations

import argparse
import os
import json

import numpy as np

PANELS: list[tuple[str, str, list[str]]] = [
    ("scores", "Weekly AI team score", ["score_mean", "score_p1", "score_p99"]),
    ("scores_tail", "Share of AI team-weeks (percent)", ["score_lt70", "score_lt60", "score_gt170"]),
    ("positions", "Rank-12 points per game", ["QB12_ppg", "RB12_ppg", "WR12_ppg", "TE12_ppg"]),
    ("ages", "Age", ["starter_age", "roster_age"]),
    ("age_mix", "Share of rostered players (percent)", ["roster_age_u24", "roster_age_30plus", "starter_age_30plus"]),
    ("churn", "Players per offseason", ["retired", "rookie_class_n"]),
    ("economy", "Market value", ["top_market", "market_mean", "team_value_mean", "pick_value_12", "pick_value_36"]),
    ("price_curve", "log market on log projection", ["market_slope_RB", "market_slope_WR", "market_slope_TE"]),
    ("activity", "Events per season", ["waivers", "drops", "trades"]),
    ("qb", "Quarterbacks", ["qb_per_team", "teams_3plus_qb"]),
    ("rookies", "Rookie class", ["best_rookie_vs_vet12", "rookies_top12_skill"]),
    ("parity", "Parity", ["win_sd", "pf_cv", "team_value_cv"]),
]


def plots(tables: dict[str, dict[str, np.ndarray]], png: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(png, exist_ok=True)
    for name, ylabel, keys in PANELS:
        fig, axes = plt.subplots(1, len(keys), figsize=(3.6 * len(keys), 3.0), squeeze=False)
        for ax, k in zip(axes[0], keys):
            for mode, t in tables.items():
                if k not in t:
                    continue
                a = t[k]
                x =np.arange(1, a.shape[1] + 1)
                ax.plot(x, np.nanmean(a, axis=0), label=mode, lw=1.8)
                ax.fill_between(x, np.nanmin(a, axis=0), np.nanmax(a, axis=0), alpha=0.12)
            ax.set_title(k, fontsize=9)
            ax.set_xlabel("season")
            ax.grid(alpha=0.25)
        axes[0][0].set_ylabel(ylabel, fontsize=8)
        axes[0][0].legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(os.path.join(png, f"{name}.png"), dpi=110)
        plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tables", help="the JSON `longrun_soak report --json` wrote")
    ap.add_argument("png", help="output directory")
    a = ap.parse_args()
    with open(a.tables) as fh:
        tables = {m: {k: np.array(v, dtype=float) for k, v in t.items()} for m, t in json.load(fh).items()}
    plots(tables, a.png)


if __name__ == "__main__":
    main()
