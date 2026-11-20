"""Build player-game x checkpoint table: cumulative PPR from pbp + point-in-time projection + final."""
from pathlib import Path
import numpy as np
import pandas as pd

CS = Path("calibration_scratch")
COLS = ["game_id", "week", "season_type", "qtr", "game_seconds_remaining", "passer_player_id", "passing_yards",
        "rusher_player_id", "rushing_yards", "receiver_player_id", "receiving_yards", "complete_pass", "pass_touchdown",
        "rush_touchdown", "interception", "fumble_lost", "fumbled_1_player_id", "two_point_attempt", "two_point_conv_result", "posteam"]
CHECK = [3300, 3000, 2700, 2400, 2100, 1800, 1500, 1200, 900, 600, 300]


def events(season):
    p = pd.read_parquet(CS / f"pbp/pbp_{season}.parquet", columns=COLS)
    p = p[p.season_type == "REG"].copy()
    p["gsr"] = p.game_seconds_remaining.astype(float)
    p["ot"] = p.qtr >= 5
    ev = []

    def add(mask, pid, pts):
        d = p.loc[mask, ["game_id", "week", "gsr", "ot"]].copy()
        d["pid"] = pid[mask]
        d["pts"] = pts[mask] if not np.isscalar(pts) else pts
        ev.append(d)

    def f(c):
        return p[c].fillna(0)

    two = ((p.two_point_attempt == 1) & (p.two_point_conv_result == "success")).astype(float)
    add(p.passer_player_id.notna(), p.passer_player_id, f("passing_yards") * 0.04 + 4 * f("pass_touchdown") - 2 * f("interception") + 2 * two)
    add(p.rusher_player_id.notna(), p.rusher_player_id, f("rushing_yards") * 0.1 + 6 * f("rush_touchdown") + 2 * two)
    add(p.receiver_player_id.notna(), p.receiver_player_id, f("receiving_yards") * 0.1 + f("complete_pass") + 6 * f("pass_touchdown") + 2 * two)
    add((f("fumble_lost") == 1) & p.fumbled_1_player_id.notna(), p.fumbled_1_player_id, -2.0)
    e = pd.concat(ev, ignore_index=True)
    g = p.groupby("game_id").agg(ot=("ot", "max")).reset_index()
    tw = p[p.posteam.notna()].groupby(["week", "posteam"]).game_id.first().rename("tw_game").reset_index()
    return e, g, tw


rows = pd.read_parquet(CS / "rows.parquet")
out = []
for season in (2023, 2024, 2025):
    e, g, tw = events(season)
    tot = e.groupby(["game_id", "pid"]).pts.sum().rename("pbp_final").reset_index()
    reg = e[~e.ot]
    spw = pd.read_parquet(CS / f"nv/spw_{season}.parquet")
    spw = spw[spw.season_type == "REG"][["player_id", "week", "fantasy_points_ppr"]]
    r = rows[(rows.season == season) & (rows.status == "ok") & rows.pos.isin(["QB", "RB", "WR", "TE"]) & (rows.played == True)].copy()
    pg = e[["game_id", "week", "pid"]].drop_duplicates()
    pg = pg.merge(spw, left_on=["pid", "week"], right_on=["player_id", "week"])
    r = r.merge(pg[["pid", "week", "game_id", "fantasy_points_ppr"]].rename(columns={"fantasy_points_ppr": "final_spw"}), on=["pid", "week"], how="left")
    r = r.merge(tot, on=["game_id", "pid"], how="left")
    r["pbp_final"] = r.pbp_final.fillna(0.0)
    r = r.merge(tw, left_on=["week", "team"], right_on=["week", "posteam"], how="left")
    miss = int(r.game_id.isna().sum())
    r["game_id"] = r.game_id.fillna(r.tw_game)
    r["final_spw"] = r.final_spw.fillna(0.0)
    r["pbp_gap"] = (r.pbp_final - r.final_spw).abs()
    print(season, "player-games", len(r), "no game id", miss, "gap<0.5:", round(float((r.pbp_gap < 0.5).mean()), 3),
          "mean|gap|", round(float(r.pbp_gap.mean()), 3), flush=True)
    print(r.loc[r.pbp_gap >= 0.5, ["pbp_final", "final_spw"]].describe().round(2).T.to_string())
    r = r[r.game_id.notna() & (r.pbp_gap < 0.5)]
    r = r.merge(g, on="game_id", how="left")
    base = r[["season", "week", "pid", "pos", "team", "game_id", "est", "mean_est", "low", "high", "final_spw", "ot"]].copy()
    for t in CHECK:
        c = reg[reg.gsr > t].groupby(["game_id", "pid"]).pts.sum().rename("cum").reset_index()
        d = base.merge(c, on=["game_id", "pid"], how="left")
        d["cum"] = d.cum.fillna(0.0)
        d["remaining"] = t / 3600.0
        d["t"] = t
        out.append(d)
    allreg = reg.groupby(["game_id", "pid"]).pts.sum().rename("cum").reset_index()
    ot = base[base.ot == True].merge(allreg, on=["game_id", "pid"], how="left")
    ot["cum"] = ot.cum.fillna(0.0)
    ot["remaining"] = 0.03
    ot["t"] = -1
    out.append(ot)
res = pd.concat(out, ignore_index=True)
res = res.rename(columns={"final_spw": "final"})
res.to_parquet(CS / "checkpoints.parquet")
print(len(res), res.groupby("t").size().to_dict())
