"""Point-in-time playoff odds (no future leakage): played weeks are actual, later weeks come from projections."""
from __future__ import annotations

import os

import numpy as np

from replay_lib import B, LINEUP, REG_WEEKS


def lineup_mean(roster, proj, pos_of, sf):
    by = {p: [] for p in B.POS}
    for pid in roster:
        by[pos_of(pid)].append(proj.get(pid, 0.0))
    tot, rest = 0.0, []
    for pos, n in LINEUP.items():
        v = sorted(by[pos], reverse=True)
        n_eff = n + (1 if sf and pos == "QB" else 0)
        tot += sum(v[:n_eff])
        if pos in ("RB", "WR", "TE"):
            rest += v[n_eff:]
    return tot + (max(rest) if rest else 0.0)


def simulate_pit(Wpast, mu, opp, completed, n_po, rng, sd=22.0):
    n = Wpast.shape[0]
    sims = opp.shape[0]
    Wsim = np.empty((sims, n, 20))
    Wsim[:, :, :completed + 1] = Wpast[None, :, :completed + 1]
    Wsim[:, :, completed + 1:] = mu[None, :, None] + sd * rng.standard_normal((sims, n, 20 - completed - 1))
    wins = np.zeros((sims, n))
    for w in range(REG_WEEKS):
        o = opp[:, w, :].astype(np.int64)
        mine = Wsim[:, :, w + 1]
        theirs = np.take_along_axis(mine, o, axis=1)
        wins += (mine > theirs) + 0.5 * (mine == theirs)
    pf = Wsim[:, :, 1:REG_WEEKS + 1].sum(axis=2)
    order = np.argsort(-(wins * 1e6 + pf), axis=1)
    po = np.zeros(n)
    title = np.zeros(n)
    for s in range(sims):
        t = order[s, :n_po]
        po[t] += 1
        W = Wsim[s]
        if n_po == 6:
            w15, w16, w17 = W[:, 15], W[:, 16], W[:, 17]
            a = t[2] if w15[t[2]] >= w15[t[5]] else t[5]
            b = t[3] if w15[t[3]] >= w15[t[4]] else t[4]
            rem = sorted([a, b], key=lambda x: list(t).index(x), reverse=True)
            s1 = t[0] if w16[t[0]] >= w16[rem[0]] else rem[0]
            s2 = t[1] if w16[t[1]] >= w16[rem[1]] else rem[1]
            champ = s1 if w17[s1] >= w17[s2] else s2
        else:
            w16, w17 = W[:, 16], W[:, 17]
            s1 = t[0] if w16[t[0]] >= w16[t[3]] else t[3]
            s2 = t[1] if w16[t[1]] >= w16[t[2]] else t[2]
            champ = s1 if w17[s1] >= w17[s2] else s2
        title[champ] += 1
    return po / sims, title / sims, wins.mean(axis=0)
