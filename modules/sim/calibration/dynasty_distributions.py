"""Distributions from dynasty_run.py output.

    for s in 1 2 3 4; do PYTHONPATH=. python modules/sim/calibration/dynasty_run.py 10 $s OUT/dyn$s.pkl; done
    PYTHONPATH=. python modules/sim/calibration/dynasty_distributions.py OUT

Team-week score, blowouts, slot shares, parity, win% persistence, asset-value drift, age curves.
The user team never sets a lineup in this harness (it is the weakest team), read AI-only lines for parity.
"""
import sys, pickle
import numpy as np
from collections import Counter, defaultdict
D = sys.argv[1].rstrip("/")
R = {s: pickle.load(open(f"{D}/dyn{s}.pkl", "rb")) for s in (1, 2, 3, 4)}
allw, allm = [], []
for s, r in R.items():
    for x in r:
        allw += x["weekly"]; allm += x["margins"]
allw = np.array(allw); allm = np.array(allm)
print("team-week score mean %.1f sd %.1f p5 %.0f p95 %.0f max %.0f min %.0f" % (allw.mean(), allw.std(), *np.percentile(allw, [5, 95]), allw.max(), allw.min()))
print("margin mean %.1f median %.1f p>=30 %.3f p>=50 %.3f p>=70 %.3f  p<=5 %.3f" % (allm.mean(), np.median(allm), (allm >= 30).mean(), (allm >= 50).mean(), (allm >= 70).mean(), (allm <= 5).mean()))
# scoring by season number (drift)
for n in (1, 2, 3, 5, 8, 10):
    v = np.concatenate([np.array(r[n - 1]["weekly"]) for r in R.values()])
    print("season", n, "team-week mean %.1f sd %.1f" % (v.mean(), v.std()))
# slot shares
sl = defaultdict(list)
for r in R.values():
    for x in r:
        for k, v in x["slot_pts"].items(): sl[k] += v
tot = sum(np.mean(v) for v in sl.values())
print("slot means", {k: round(float(np.mean(v)), 2) for k, v in sl.items()}, "share", {k: round(float(np.mean(v)) / tot, 3) for k, v in sl.items()})
# champions / parity
for s, r in R.items():
    print("seed", s, "distinct champs", len(set(x["champ"] for x in r)), "user titles", sum(1 for x in r if x["champ"] == x["user"]))
cc = Counter(x["champ"] for r in R.values() for x in r)
print("champ counts", sorted(cc.values(), reverse=True), "user tid", R[1][0]["user"])
# repeat champions
rep = sum(1 for r in R.values() for a, b in zip(r, r[1:]) if a["champ"] == b["champ"]); tot_pairs = sum(len(r) - 1 for r in R.values())
print("repeat champion rate %.3f (iid 12 teams = 0.083)" % (rep / tot_pairs))
# win% persistence
xs, ys = [], []
for r in R.values():
    for a, b in zip(r, r[1:]):
        for t in a["wins"]:
            xs.append(a["wins"][t]); ys.append(b["wins"][t])
print("win%% year-over-year corr %.3f" % np.corrcoef(xs, ys)[0, 1])
xs, ys = [], []
for r in R.values():
    for a, b in zip(r, r[1:]):
        for t in a["pfs"]:
            xs.append(a["pfs"][t]); ys.append(b["pfs"][t])
print("PF year-over-year corr %.3f" % np.corrcoef(xs, ys)[0, 1])
# user vs AI
uw = [x["wins"][x["user"]] for r in R.values() for x in r]; aw = [np.mean([v for t, v in x["wins"].items() if t != x["user"]]) for r in R.values() for x in r]
print("user win%% mean %.3f vs AI mean %.3f ; user PF rank mean %.2f" % (np.mean(uw), np.mean(aw), np.mean([1 + sorted(x["pfs"].values(), reverse=True).index(x["pfs"][x["user"]]) for r in R.values() for x in r])))
# team value drift
for n in (1, 2, 4, 6, 8, 10):
    tv = [sum(x["team_val"].values()) / len(x["team_val"]) for r in R.values() for x in [r[n - 1]]]
    ta = [np.mean(list(x["team_age"].values())) for r in R.values() for x in [r[n - 1]]]
    tvs = [np.std(list(x["team_val"].values())) / np.mean(list(x["team_val"].values())) for r in R.values() for x in [r[n - 1]]]
    tm = [np.mean(x["top_market"][:12]) for r in R.values() for x in [r[n - 1]]]
    npl = [x["nplayers"] for r in R.values() for x in [r[n - 1]]]
    print("season", n, "mean team asset value %.0f  cv across teams %.3f  mean roster age %.2f  top12 player market %.0f  pool n %d" % (np.mean(tv), np.mean(tvs), np.mean(ta), np.mean(tm), np.mean(npl)))
# top-player dominance & position ranks
for n in (1, 5, 10):
    out = defaultdict(list)
    for r in R.values():
        pl = r[n - 1]["pl"]
        for pos in ("QB", "RB", "WR", "TE"):
            v = sorted([x[1] for x in pl.values() if x[0] == pos], reverse=True)
            if len(v) >= 24: out[pos].append((v[0], v[5], v[11], v[23]))
    print("season", n, {p: [round(float(np.mean([a[i] for a in o])), 1) for i in range(4)] for p, o in out.items()}, "(ppg rank 1/6/12/24)")
# age curves in sim: ppg ratio of starters by age (season n -> n+1)
ratios = defaultdict(list)
for r in R.values():
    for a, b in zip(r, r[1:]):
        for pid, (pos, ppg, age, tot, g) in a["pl"].items():
            if pid in b["pl"] and ppg >= 6:
                ratios[(pos, int(age))].append(b["pl"][pid][1] / ppg)
for pos in ("QB", "RB", "WR", "TE"):
    print(pos, {a: (round(float(np.mean(v)), 2), len(v)) for (p, a), v in sorted(ratios.items()) if p == pos and len(v) >= 15})
# age distribution of top-24 per pos
for pos in ("QB", "RB", "WR", "TE"):
    ages = []
    for r in R.values():
        for x in r:
            v = sorted([(p[1], p[2]) for p in x["pl"].values() if p[0] == pos], reverse=True)[:12]
            ages += [a for _, a in v]
    print(pos, "age of top-12 by ppg: mean %.1f p10 %.0f p90 %.0f" % (np.mean(ages), *np.percentile(ages, [10, 90])))
# AI roster composition
comp = defaultdict(list)
for r in R.values():
    for x in r:
        for t, c in x["comp"].items():
            if t != x["user"]:
                for p in ("QB", "RB", "WR", "TE", "K"):
                    comp[p].append(c.get(p, 0))
print("AI roster counts mean", {p: round(float(np.mean(v)), 2) for p, v in comp.items()}, "QB<2 share", np.mean([v < 2 for v in comp["QB"]]), "K==0", np.mean([v == 0 for v in comp["K"]]), "TE==0", np.mean([v == 0 for v in comp["TE"]]))
