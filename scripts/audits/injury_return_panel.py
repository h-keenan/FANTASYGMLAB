"""Build the player-game injury panel used to fit/test the injury return curves (docs/audits/2026-11-injury-discount.md).

usage: injury_return_panel.py NV_DIR OUT_PARQUET

NV_DIR holds nflverse files: games.csv, inj_<season>.csv, spw_<season>.parquet (2020-2025).
One row per (player, team game) for QB/RB/WR/TE players who had a stat line or an injury-report listing that season,
state "none" rows (healthy comparison) are kept too:
  state     none | Questionable | Doubtful | Out | IR  (IR = proxy: no stat line, not on the report, previous week was Out/IR;
            nflverse has no IR flag)
  age_k     weeks since the current run of non-none states started (1 = first week listed)
  baseline  mean PPR points of the previous (up to) 6 games with a stat line, across seasons; needs >= 3 games and >= 4.0
  played    has a stat line this week; pts = PPR points (0 when no stat line)
  f1/f4/f8  forward production fraction sum(pts g..g+k-1)/(k*baseline) (NaN when the window is not fully observed)
  p4/p8     share of the next 4/8 team games with a stat line
  lost17    games without a stat line in the next 17 team games (spans into the next season when the player is in it)
Memory-light: columns selected early, one season at a time, parquet out.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

POS = {"QB", "RB", "WR", "TE"}
SEASONS = range(2020, 2026)
BODY = {
    "knee": "knee", "ankle": "ankle", "hamstring": "hamstring", "concussion": "concussion", "illness": "illness",
    "calf": "lower_leg", "foot": "foot", "toe": "foot", "achilles": "foot", "shoulder": "shoulder", "back": "back",
    "groin": "hip_groin", "hip": "hip_groin", "quadricep": "thigh", "thigh": "thigh",
}


def body(x) -> str:
    return BODY.get(str(x).strip().lower(), "other") if isinstance(x, str) and x.strip() else "none"


def season_frame(nv: Path, s: int, team_weeks: dict) -> pd.DataFrame:
    st = pd.read_parquet(nv / f"spw_{s}.parquet", columns=["player_id", "position", "season", "week", "season_type", "team", "fantasy_points_ppr"])
    st = st[(st.season_type == "REG") & st.position.isin(POS)].drop(columns="season_type")
    inj = pd.read_csv(nv / f"inj_{s}.csv", usecols=["season", "game_type", "week", "team", "gsis_id", "position", "report_status", "report_primary_injury"])
    inj = inj[(inj.game_type == "REG") & inj.position.isin(POS) & inj.report_status.isin(["Out", "Doubtful", "Questionable"])]
    inj = inj.rename(columns={"gsis_id": "player_id"}).drop_duplicates(["player_id", "week"], keep="last")
    pl = pd.concat([st[["player_id", "position", "team"]], inj[["player_id", "position", "team"]]])
    main_team = pl.groupby("player_id").agg(position=("position", "first"), team=("team", lambda x: x.mode().iat[0]))
    rows = [(pid, r.position, s, w) for pid, r in main_team.iterrows() for w in team_weeks.get((s, r.team), [])]
    base = pd.DataFrame(rows, columns=["player_id", "pos", "season", "week"])
    base = base.merge(st[["player_id", "week", "fantasy_points_ppr"]], how="left", on=["player_id", "week"])
    return base.merge(inj[["player_id", "week", "report_status", "report_primary_injury"]], how="left", on=["player_id", "week"])


def player_rows(g: pd.DataFrame) -> pd.DataFrame:
    pts = g.pts.to_numpy()
    played = g.played.to_numpy()
    n = len(g)
    rs = g.report_status.to_numpy(object)
    seas = g.season.to_numpy()
    state = np.empty(n, object)
    age = np.zeros(n, int)
    prev, run, prev_season = "none", 0, None
    for i in range(n):
        if seas[i] != prev_season:
            prev, run, prev_season = "none", 0, seas[i]
        if isinstance(rs[i], str):
            cur = rs[i]
        elif prev in ("Out", "IR") and not played[i]:
            cur = "IR"
        else:
            cur = "none"
        run = run + 1 if cur != "none" else 0
        state[i], age[i], prev = cur, run, cur
    base = np.full(n, np.nan)
    hist: list[float] = []
    for i in range(n):
        if len(hist) >= 3:
            base[i] = float(np.mean(hist[-6:]))
        if played[i]:
            hist.append(pts[i])
    cs = np.concatenate([[0.0], np.cumsum(pts)])
    cp = np.concatenate([[0], np.cumsum(played)])

    def window(k, fn):
        v = np.full(n, np.nan)
        for i in range(n - k + 1):
            if seas[i + k - 1] - seas[i] <= 1:
                v[i] = fn(i, k)
        return v

    o = g[["player_id", "pos", "season", "week", "pts", "played", "body"]].copy()
    o["state"], o["age_k"], o["baseline"] = state, age, base
    o["f1"] = window(1, lambda i, k: cs[i + k] - cs[i])
    o["f4"] = window(4, lambda i, k: cs[i + k] - cs[i])
    o["f8"] = window(8, lambda i, k: cs[i + k] - cs[i])
    o["p4"] = window(4, lambda i, k: (cp[i + k] - cp[i]) / k)
    o["p8"] = window(8, lambda i, k: (cp[i + k] - cp[i]) / k)
    o["lost17"] = window(17, lambda i, k: 17 - (cp[i + k] - cp[i]))
    return o


def main(nv: Path, out: Path) -> None:
    games = pd.read_csv(nv / "games.csv", usecols=["season", "game_type", "week", "away_team", "home_team"])
    games = games[(games.game_type == "REG") & games.season.between(2020, 2026)]
    tw = pd.concat([games[["season", "week", "home_team"]].rename(columns={"home_team": "team"}),
                    games[["season", "week", "away_team"]].rename(columns={"away_team": "team"})])
    team_weeks = {k: sorted(v.week.tolist()) for k, v in tw.groupby(["season", "team"])}
    d = pd.concat([season_frame(nv, s, team_weeks) for s in SEASONS], ignore_index=True)
    d["played"] = d.fantasy_points_ppr.notna()
    d["pts"] = d.fantasy_points_ppr.fillna(0.0)
    d["body"] = d.report_primary_injury.map(body)
    d = d.sort_values(["player_id", "season", "week"]).reset_index(drop=True)
    panel = pd.concat([player_rows(g) for _, g in d.groupby("player_id", sort=False)], ignore_index=True)
    panel = panel[panel.baseline >= 4.0].copy()
    panel["f1"] = panel.f1 / panel.baseline
    panel["f4"] = panel.f4 / (4 * panel.baseline)
    panel["f8"] = panel.f8 / (8 * panel.baseline)
    panel["prod_ratio"] = np.where(panel.played, panel.pts / panel.baseline, np.nan)
    for c in ("pos", "state", "body"):
        panel[c] = panel[c].astype("category")
    panel.to_parquet(out)
    print(panel.groupby("state", observed=True).size(), len(panel))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
