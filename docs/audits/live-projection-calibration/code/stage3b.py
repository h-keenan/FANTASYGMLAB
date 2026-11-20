import numpy as np
import pandas as pd
from math import sqrt
import math
erf = np.vectorize(math.erf)

R = pd.read_parquet("calibration_scratch/wp_matchups.parquet")
R["win"] = (R.dfinal > 0).astype(float)


def prob(df, mult):
    return 0.5 * (1 + erf(df.dmean / (mult * np.sqrt(df["var"])) / sqrt(2)))


def sym(df, mult):
    p = np.asarray(prob(df, mult))
    y = df.win.values
    return np.concatenate([p, 1 - p]), np.concatenate([y, 1 - y])


LAB = {3600: "pregame", 2700: "25%", 1800: "50%", 900: "75%", 300: "92%"}
print("Brier by time (mult 1.70 = shipped; 1.0 = unwidened; 0.25 = no-skill)")
for t, g in R.groupby("t", sort=False):
    out = [LAB[t], len(g)]
    for m in (1.0, 1.35, 1.7, 2.0):
        p, y = sym(g, m)
        out.append(round(float(np.mean((p - y) ** 2)), 4))
    # log-loss optimum multiplier and Brier optimum multiplier
    grid = np.arange(0.8, 3.01, 0.05)
    best = min(grid, key=lambda m: np.mean((sym(g, m)[0] - sym(g, m)[1]) ** 2))
    out.append(round(float(best), 2))
    print(out)
print("cols: time n brier@1.0 @1.35 @1.7 @2.0 best_mult")
print("\nReliability (mult 1.70), predicted bins 10%: pred / actual / n")
bins = np.linspace(0, 1, 11)
tab = {}
for t, g in R.groupby("t", sort=False):
    p, y = sym(g, 1.7)
    idx = np.clip(np.digitize(p, bins) - 1, 0, 9)
    tab[LAB[t]] = [(round(float(p[idx == b].mean()), 3), round(float(y[idx == b].mean()), 3), int((idx == b).sum())) if (idx == b).any() else None for b in range(10)]
for b in range(10):
    print(f"{b*10}-{b*10+10}%", " | ".join(("%.2f/%.2f/%d" % tab[k][b]) if tab[k][b] else "-" for k in tab))
print(list(tab))
print("\nper-season Brier @1.7 and best mult")
for (s, t), g in R.groupby(["season", "t"]):
    p, y = sym(g, 1.7)
    grid = np.arange(0.8, 3.01, 0.05)
    best = min(grid, key=lambda m: np.mean((sym(g, m)[0] - sym(g, m)[1]) ** 2))
    print(s, LAB[t], round(float(np.mean((p - y) ** 2)), 4), round(float(best), 2))
# sharpness: mean |p-0.5|
print("\nmean predicted prob of the favorite / actual favorite win rate")
for t, g in R.groupby("t", sort=False):
    p = prob(g, 1.7)
    fav = np.where(p >= 0.5, p, 1 - p)
    won = np.where(p >= 0.5, g.win, 1 - g.win)
    print(LAB[t], round(float(fav.mean()), 3), round(float(won.mean()), 3))
