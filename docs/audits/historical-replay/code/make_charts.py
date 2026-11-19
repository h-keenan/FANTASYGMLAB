import os
"""Small PNG charts for the historical replay audit. Reads results/*.csv."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RES = Path(os.environ["REPLAY_OUT"] + "/results")
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
C_TRAIN, C_TEST, INK = "#2563eb", "#d97706", "#374151"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#9ca3af", "text.color": INK,
                     "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=100)
    plt.close(fig)


# 1 calibration
a = pd.read_csv(RES / "grades_calibration_train.csv")
b = pd.read_csv(RES / "grades_calibration_test.csv")
fig, ax = plt.subplots(figsize=(6.4, 3.2))
x = np.arange(len(a))
ax.bar(x - 0.2, a.win_pct, 0.38, yerr=a.ci95, color=C_TRAIN, capsize=2, label="train 2021-23")
ax.bar(x + 0.2, b.win_pct, 0.38, yerr=b.ci95, color=C_TEST, capsize=2, label="test 2024-25")
ax.axhline(50, color="#6b7280", lw=1, ls="--")
ax.set_xticks(x, [s.replace(" / PREFERENCE", "").title() for s in a.band], rotation=15)
ax.set_ylabel("trade won on lineup points (%)")
ax.set_title("Does the verdict call the winner? (ROS + next season)", loc="left", fontsize=10)
ax.legend(frameon=False, fontsize=8)
save(fig, "01_grade_calibration.png")

# 2 ideas by posture
s = pd.read_csv(RES / "ideas_stability.csv")
p = s[s.slice == "posture"]
order = ["contender", "fringe_contender", "retool", "rebuild", "tank"]
fig, ax = plt.subplots(figsize=(6.4, 3.0))
for i, (per, col) in enumerate((("train 2021-23", C_TRAIN), ("test 2024-25", C_TEST))):
    q = p[p.period == per].set_index("group").reindex(order)
    ax.bar(np.arange(5) + (i - 0.5) * 0.38, q.h_pts, 0.36, color=col, label=per)
ax.axhline(0, color="#6b7280", lw=1)
ax.set_xticks(range(5), order)
ax.set_ylabel("lineup points / idea\n(rest of season + next)")
ax.set_title("Trade Hub ideas: realized lineup points by posture", loc="left", fontsize=10)
ax.legend(frameon=False, fontsize=8)
save(fig, "02_ideas_by_posture.png")

# 3 pick curve
pc = pd.read_csv(RES / "pick_calibration.csv")
pc = pc[(pc.rnd == 1)]
fig, axs = plt.subplots(1, 2, figsize=(6.4, 3.0), sharey=True)
for ax, fmt in zip(axs, ("dynasty_1qb", "dynasty_sf")):
    q = pc[(pc.fmt == fmt)]
    tiers = ["early", "mid", "late"]
    g = q.groupby("tier").agg(eng=("engine_pick", "mean"), market=("market", "mean"), real=("realized_engine_scale", "mean")).reindex(tiers)
    x = np.arange(3)
    ax.bar(x - 0.27, g.eng, 0.25, color=C_TRAIN, label="engine (today)")
    ax.bar(x, g.market, 0.25, color=C_TEST, label="market (point in time)")
    ax.bar(x + 0.27, g.real, 0.25, color="#6b7280", label="realized rookie")
    ax.set_xticks(x, tiers)
    ax.set_title({"dynasty_1qb": "1QB", "dynasty_sf": "Superflex"}[fmt] + ", 1st round", loc="left", fontsize=10)
axs[0].set_ylabel("value (engine scale)")
axs[0].legend(frameon=False, fontsize=7)
save(fig, "03_pick_curve_round1.png")

# 4 tuning OOS gains
t = pd.read_csv(RES / "top10.csv") if (RES / "top10.csv").exists() else None
if t is not None:
    t = t.iloc[::-1]
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.barh(t.label, t.oos_gain_pct, color=[C_TEST if v else "#9ca3af" for v in t.supported])
    ax.axvline(0, color="#6b7280", lw=1)
    ax.set_xlabel("out-of-sample gain (% of the metric; grey = not supported)")
    ax.set_title("Tuning candidates, trained 2021-23, tested 2024-25", loc="left", fontsize=10)
    save(fig, "04_tuning_oos.png")
print("charts ok")
