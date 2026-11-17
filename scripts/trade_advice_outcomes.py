"""Score graded backtest trades (``trade_advice_backtest.py run``) against what nflverse says happened.

Per trade, from the user's (receiving) side, over three windows (rest of that season, the next season, the one after):

* ``vor_*``  PPR points over replacement of everything received minus everything sent (hindsight replacement level =
  the PPG of the 12th QB / 30th RB / 42nd WR / 14th TE by that season's actual points, 24th QB in Superflex; TE
  premium adds 0.5/rec for TE in TEP leagues). A rookie pick is scored as the rookie it became (slot -> the
  slot-th rookie of that class by post-draft market value).
* ``spor_*`` change in the receiving roster's hindsight-optimal starting-lineup points (1QB/2RB/3WR/1TE/FLEX, +SFLEX),
  empty slots filled at replacement level.
* ``mv_chg`` change in the market margin (received minus sent, FantasyCalc-scale) one year later vs at the trade.

    python scripts/trade_advice_outcomes.py --nv NV --dp DP --graded OUT/graded.parquet --out OUT/scored.parquet
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trade_advice_backtest import LEAGUES, LINEUP, POS, History  # noqa: E402

LAST_FULL = 2025  # nflverse seasons with all 18 weeks


class Scorer:
    def __init__(self, h: History):
        self.h = h
        self._rookies = {}
        self._snap = {}

    def rookies(self, cls: int, sf: bool) -> list[str]:
        key = (cls, sf)
        if key not in self._rookies:
            label = f"{cls}-08-20" if cls <= 2025 else "2026-09-01"
            try:
                df = self.h.match(self.h.dp_players(label), pd.Timestamp(label))
            except FileNotFoundError:
                self._rookies[key] = []
                return []
            df = df[pd.to_numeric(df.draft_year, errors="coerce") == cls]
            col = "value_2qb" if sf else "value_1qb"
            self._rookies[key] = df.sort_values(col, ascending=False).player_id.tolist()
        return self._rookies[key]

    def snap(self, label: str):
        if label not in self._snap:
            try:
                df = self.h.match(self.h.dp_players(label), pd.Timestamp(label))
                self._snap[label] = df.set_index("player_id")
            except FileNotFoundError:
                self._snap[label] = None
        return self._snap[label]

    def weekly(self, pid: str, season: int, tep: bool) -> np.ndarray:
        arr = self.h.wk.get((pid, season))
        if arr is None:
            return np.full(20, np.nan)
        if tep and (pid, season) in self.h.te_rec:
            arr = arr + 0.5 * self.h.te_rec[(pid, season)]
        return arr

    def pos(self, pid: str) -> str:
        return self.h.players.at[pid, "position"] if pid in self.h.players.index else "WR"


def windows(season: int, completed: int):
    return {"ros": (season, completed + 1, 18), "y1": (season + 1, 1, 18), "y2": (season + 2, 1, 18)}


def vor_of(sc: Scorer, pid: str, win, sf: bool, tep: bool) -> float:
    s, w0, w1 = win
    if s > LAST_FULL:
        return np.nan
    arr = sc.weekly(pid, s, tep)[w0:w1 + 1]
    played = ~np.isnan(arr)
    repl = sc.h.repl_ppg(s, sf, tep)[sc.pos(pid)]
    return float(np.nansum(arr) - repl * played.sum())


def lineup_points(sc: Scorer, roster: list[str], win, sf: bool, tep: bool) -> float:
    s, w0, w1 = win
    if s > LAST_FULL:
        return np.nan
    repl = sc.h.repl_ppg(s, sf, tep)
    by_pos = {p: [] for p in POS}
    for pid in roster:
        by_pos[sc.pos(pid)].append(sc.weekly(pid, s, tep))
    mats = {p: (np.vstack(v)[:, w0:w1 + 1] if v else np.full((0, w1 - w0 + 1), np.nan)) for p, v in by_pos.items()}
    total = 0.0
    for wi in range(w1 - w0 + 1):
        used = {}
        flex_pool = []
        for p, n in LINEUP.items():
            n_eff = n + (1 if sf and p == "QB" else 0)
            col = mats[p][:, wi] if mats[p].shape[0] else np.array([])
            col = np.sort(col[~np.isnan(col)])[::-1]
            starters = list(col[:n_eff])
            starters += [repl[p]] * (n_eff - len(starters))
            total += sum(starters)
            rest = list(col[n_eff:])
            if p in ("RB", "WR", "TE"):
                flex_pool += [x - 0 for x in rest]
        # FLEX: best remaining RB/WR/TE (or replacement-level RB if none)
        total += max(flex_pool) if flex_pool else min(repl["RB"], repl["WR"])
    return total


def expand_assets(sc: Scorer, ids: str, pick_slot: int, pick_year: int, sf: bool):
    pl = [x for x in ids.split("|") if x]
    rookie = None
    if pick_slot:
        r = sc.rookies(int(pick_year), sf)
        rookie = r[pick_slot - 1] if len(r) >= pick_slot else None
    return pl, rookie


def score(df: pd.DataFrame, sc: Scorer) -> pd.DataFrame:
    out = []
    for r in df.itertuples():
        lg = LEAGUES[r.league]
        sf, tep = bool(lg["sf"]), bool(lg["tep"])
        send, srookie = expand_assets(sc, r.send_ids, r.send_pick, r.pick_year, sf)
        recv, rrookie = expand_assets(sc, r.recv_ids, r.recv_pick, r.pick_year, sf)
        roster = [x for x in r.roster_ids.split("|") if x]
        rec = {}
        wins = windows(r.season, r.completed)
        pick_missing = (r.send_pick and srookie is None) or (r.recv_pick and rrookie is None)
        for name, win in wins.items():
            if pick_missing:
                rec[f"vor_{name}"] = np.nan
                rec[f"spor_{name}"] = np.nan
                continue
            svs = [vor_of(sc, p, win, sf, tep) for p in send + ([srookie] if srookie else [])]
            rvs = [vor_of(sc, p, win, sf, tep) for p in recv + ([rrookie] if rrookie else [])]
            sv, rv = sum(svs), sum(rvs)
            rec[f"vor_{name}"] = rv - sv
            # a below-replacement asset is replaced off waivers, so it contributes 0, never a negative
            pos_ = lambda xs: sum(x if x != x else max(0.0, x) for x in xs)  # noqa: E731
            rec[f"vorc_{name}"] = pos_(rvs) - pos_(svs)
            rec[f"vor_recv_{name}"] = rv
            rec[f"vor_send_{name}"] = sv
            before = roster + ([srookie] if srookie else [])
            after = [p for p in roster if p not in set(send)] + recv + ([rrookie] if rrookie else [])
            rec[f"spor_{name}"] = lineup_points(sc, after, win, sf, tep) - lineup_points(sc, before, win, sf, tep)
        # What the shipped track-record grader sees (modules.trade_outcome_results): raw net PPR per week over the first
        # <=8 weeks after the trade, players only, no replacement level. In-season trades only.
        net8 = np.nan
        if 0 < r.completed < 17 and not (r.send_pick or r.recv_pick):
            w0, w1 = r.completed + 1, min(r.completed + 8, 17)
            tot = lambda ps: float(sum(np.nansum(sc.weekly(p, r.season, tep)[w0:w1 + 1]) for p in ps))  # noqa: E731
            net8 = (tot(recv) - tot(send)) / (w1 - w0 + 1)
        rec["tor_net_ppg_8w"] = net8
        # market-value change one year later (same calendar slot, next year)
        label1 = f"{r.season + 1}-{r.mmdd}" if r.season < 2025 else ("2026-09-01" if r.mmdd == "08-20" else None)
        mv = np.nan
        if label1:
            sn = sc.snap(label1)
            if sn is not None and not pick_missing:
                col = "value_2qb" if sf else "value_1qb"
                end = lambda ps: float(sum(sn[col].get(p, 0.0) for p in ps))  # noqa: E731
                e_send = end(send + ([srookie] if srookie else []))
                e_recv = end(recv + ([rrookie] if rrookie else []))
                mv = (e_recv - e_send) - (r.mkt_recv - r.mkt_send)
        rec["mv_chg"] = mv
        out.append(rec)
    return pd.concat([df.reset_index(drop=True), pd.DataFrame(out)], axis=1)




def asset_table(h: History, scorer: Scorer, seasons, dates, league_names) -> pd.DataFrame:
    """Player-level calibration: each valued player at each date, his engine score and what he then produced."""
    from trade_advice_backtest import build_frame

    rows = []
    for season in seasons:
        for mmdd in dates:
            label = f"{season}-{mmdd}"
            d = pd.Timestamp(label)
            completed = h.completed_weeks(season, d)
            in_season = 0 < completed < 17
            cw = completed + 1 if in_season else 0
            for lname in league_names:
                lg = LEAGUES[lname]
                if lname == "redraft_1qb" and not in_season and mmdd != "08-20":
                    continue
                frame, _ = build_frame(h, label, season, d, completed, lg, cw)
                sf, tep = bool(lg["sf"]), bool(lg["tep"])
                field = "value_score" if lg["lens"] == "Non-Dynasty" else "dynasty_score"
                wins = windows(season, completed)
                for r in frame.itertuples():
                    if getattr(r, field) < 300:
                        continue
                    rec = dict(season=season, mmdd=mmdd, league=lname, player_id=r.player_id, position=r.position, age=r.age,
                               years_exp=r.years_exp, score=getattr(r, field), market=r.value_2qb if sf else r.value_1qb,
                               market1=r.value_1qb, prior_ppg=0 if pd.isna(r.prior_ppg) else r.prior_ppg, injury=r.injury_status,
                               depth=r.depth_chart_order, draft_year=r.draft_year)
                    for name, win in wins.items():
                        rec[f"vor_{name}"] = vor_of(scorer, r.player_id, win, sf, tep)
                    rows.append(rec)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nv", required=True)
    ap.add_argument("--dp", required=True)
    ap.add_argument("--graded")
    ap.add_argument("--out")
    ap.add_argument("--assets-out")
    a = ap.parse_args()
    h = History(Path(a.nv), Path(a.dp))
    sc = Scorer(h)
    if a.graded:
        scored = score(pd.read_parquet(a.graded), sc)
        scored.to_parquet(a.out)
        print(len(scored))
    if a.assets_out:
        at = asset_table(h, sc, range(2021, 2026), ("04-15", "05-20", "08-20", "10-20", "12-01"), ("dynasty_1qb", "dynasty_sf", "dynasty_sf_tep", "redraft_1qb"))
        at.to_parquet(a.assets_out)
        print(len(at))


if __name__ == "__main__":
    main()
