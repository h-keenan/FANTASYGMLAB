"""Part (c): win-probability calibration on synthetic head-to-head matchups built from real weekly pools."""
import sys
sys.path.insert(0, ".")
from math import erf, sqrt
from pathlib import Path
import numpy as np
import pandas as pd
from modules import matchup_win_probability as M
from modules import projection_calibration as PC

CS = Path("calibration_scratch")
SEED = 7
N_PER_WEEK = 300
TIMES = [3600, 2700, 1800, 900, 300]  # 3600 = pregame
d = pd.read_parquet(CS / "checkpoints.parquet")
pre = d[d.t == 300].copy()  # one row per player-game
pre["t"] = 3600
pre["remaining"] = 1.0
pre["cum"] = 0.0
d = pd.concat([pre, d[d.t.isin([2700, 1800, 900, 300])]], ignore_index=True)


def starter_dict(r):
    s = {"game_started": r.t != 3600, "game_final": False, "actual_points": r.cum, "game_remaining": r.remaining,
         "projection": {"status": "ok", "point_estimate": r.est, "mean_estimate": r.mean_est, "low": r.low, "high": r.high}}
    return s


mv = np.zeros((len(d), 2))
for i, r in enumerate(d.itertuples(index=False)):
    m, v, ok = M._starter_distribution(starter_dict(r))
    assert ok
    mv[i] = (m, v)
d["m"], d["v"] = mv[:, 0], mv[:, 1]
d = d.set_index(["season", "week", "t", "pid"]).sort_index()

rng = np.random.default_rng(SEED)
POOL = {"QB": 24, "RB": 48, "WR": 60, "TE": 24}


TEAMS = {}


def draw(pool):
    qbs = [q for q in pool["QB"] if q in TEAMS and len(TEAMS[q]["WR"]) >= 2 and TEAMS[q]["TE"]]
    q1, q2 = rng.choice(qbs, 2, replace=False)
    while TEAMS[q1]["team"] == TEAMS[q2]["team"]:
        q1, q2 = rng.choice(qbs, 2, replace=False)
    sides = []
    used = {q1, q2}
    for q in (q1, q2):
        w = TEAMS[q]["WR"][:2]; te = TEAMS[q]["TE"][0]
        used |= set(w) | {te}
        sides.append([q, *w, te])
    pool2 = {k: [p for p in pool[k] if p not in used] for k in ("RB", "WR", "TE")}
    rbs = list(rng.choice(pool2["RB"], 4, replace=False))
    rest = [p for k in ("WR", "TE") for p in pool2[k]] + [p for p in pool2["RB"] if p not in rbs]
    fl = list(rng.choice(rest, 6, replace=False))
    a = sides[0] + rbs[:2] + fl[:2] + fl[4:5]
    b = sides[1] + rbs[2:4] + fl[2:4] + fl[5:6]
    return a, b


def draw_old(pool):
    """pool: dict pos -> list of pids. 9 starters per side, 2 sides, all distinct."""
    take = {"QB": 2, "RB": 4, "WR": 6, "TE": 2}
    got = {k: list(rng.choice(pool[k], take[k], replace=False)) for k in take}
    rest = [p for k in ("RB", "WR", "TE") for p in pool[k] if p not in got[k]]
    flex = list(rng.choice(rest, 4, replace=False))
    a = [got["QB"][0], *got["RB"][:2], *got["WR"][:3], got["TE"][0], flex[0], flex[1]]
    b = [got["QB"][1], *got["RB"][2:4], *got["WR"][3:6], got["TE"][1], flex[2], flex[3]]
    return a, b


matchups = []
base = d.xs(3600, level="t").reset_index()
for (season, week), g in base.groupby(["season", "week"]):
    pool = {k: list(g[g.pos == k].sort_values("est", ascending=False).pid[: POOL[k]]) for k in POOL}
    if any(len(pool[k]) < 12 for k in pool):
        continue
    TEAMS.clear()
    gg = g.set_index("pid")
    for q in pool["QB"]:
        tm = gg.loc[q, "team"]
        same = g[g.team == tm]
        TEAMS[q] = {"team": tm, "WR": list(same[same.pos == "WR"].sort_values("est", ascending=False).pid), "TE": list(same[same.pos == "TE"].sort_values("est", ascending=False).pid)}
    for _ in range(N_PER_WEEK):
        a, b = draw(pool)
        matchups.append((season, week, a, b))
print("matchups", len(matchups), flush=True)

recs = []
for t in TIMES:
    sub = d.xs(t, level="t")
    for season, week, a, b in matchups:
        ra = sub.loc[(season, week, a)]
        rb = sub.loc[(season, week, b)]
        recs.append((t, season, week, ra.m.sum() - rb.m.sum(), ra.v.sum() + rb.v.sum(), ra.final.sum() - rb.final.sum(),
                     ra.cum.sum() - rb.cum.sum()))
R = pd.DataFrame(recs, columns=["t", "season", "week", "dmean", "var", "dfinal", "dcum"])
R = R[R.dfinal != 0]
R.to_parquet(CS / "wp_matchups_stack.parquet")
