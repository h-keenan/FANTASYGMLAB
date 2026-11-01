"""Estimate how weather changes fantasy production, per position.

Reproduces the numbers in docs/weather-effects.md. Inputs are all public:

- nflverse games.csv        (game list, kickoff time, stadium_id)
- nflverse stats_player_week_<year>.csv  (player-game fantasy points)
- Open-Meteo historical archive (hourly wind / gusts / precipitation / temp
  at the stadium for the 4 hours from kickoff)

Usage:  python scripts/weather_effects_analysis.py <work_dir>
where <work_dir> holds games.csv, ps_<year>.csv and wx/<stadium>_<year>.json
(the fetch helpers at the bottom create them).  Nothing here is imported by
the app; it is an offline research script.

Design (see the doc for the reasoning):
- outdoor stadiums only (fixed domes and retractable roofs are excluded)
- unit of analysis is a player-game; player-season fixed effects remove who
  the player is, his team, and his role
- covariates are indicator tiers of wind / rain / cold in the 4-hour game
  window, entered together so one condition is not credited with another's
  effect
- standard errors are clustered by game (teammates in one game share the
  same weather and the same game script)
- points are winsorised at the position's 99th percentile so one 60-point
  game cannot move a tier
- the raw effect is then shrunk toward zero (empirical Bayes) and only kept
  if it clears a significance bar
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SEASONS = range(2011, 2026)
WINDOW_HOURS = 4
# Fantasy-relevant players only: a player-season counts if his mean points
# over the games used clears this bar and he has enough games for a
# meaningful fixed effect.
MIN_MEAN_BY_POS = {"QB": 12.0, "RB": 8.0, "WR": 8.0, "TE": 6.0, "K": 5.0}
MIN_GAMES = 6
Z_BAR = 2.5
POSITIONS = ["QB", "RB", "WR", "TE", "K"]

# Tier definitions (the model in modules/game_weather.py must use the same).
TIERS = {
    "wind_15_19": lambda d: (d.wind >= 15) & (d.wind < 20),
    "wind_20p": lambda d: d.wind >= 20,
    "rain_light": lambda d: (d.precip >= 1.0) & (d.precip < 4.0),
    "rain_heavy": lambda d: d.precip >= 4.0,
    "cold_le32": lambda d: d.temp <= 32,
}


def kickoff_utc(games: pd.DataFrame) -> pd.Series:
    naive = pd.to_datetime(games.gameday + " " + games.gametime.fillna("13:00"))
    return naive.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")


def load_weather(work: Path, stadium_id: str, season: int) -> pd.DataFrame | None:
    path = work / "wx" / f"{stadium_id}_{season}.json"
    if not path.exists():
        return None
    h = json.loads(path.read_text()).get("hourly")
    if not h:
        return None
    df = pd.DataFrame(h)
    df["time"] = pd.to_datetime(df["time"]).dt.tz_localize("UTC")
    return df.set_index("time")


def game_weather(work: Path) -> pd.DataFrame:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from modules.nfl_stadiums import STADIUMS

    games = pd.read_csv(work / "games.csv", low_memory=False)
    games = games[(games.season.isin(SEASONS)) & (games.game_type == "REG") & games.home_score.notna()].copy()
    games["ko"] = kickoff_utc(games)
    games = games[games.stadium_id.map(lambda s: s in STADIUMS and STADIUMS[s].roof == "outdoor")]
    rows = []
    cache: dict[tuple[str, int], pd.DataFrame | None] = {}
    for g in games.itertuples():
        if pd.isna(g.ko):
            continue
        key = (g.stadium_id, g.season)
        if key not in cache:
            cache[key] = load_weather(work, *key)
        wx = cache[key]
        if wx is None:
            continue
        start = g.ko.floor("h")
        win = wx.loc[start : start + pd.Timedelta(hours=WINDOW_HOURS - 1)]
        if len(win) < WINDOW_HOURS or win[["wind_speed_10m", "precipitation", "temperature_2m"]].isna().any().any():
            continue
        rows.append(
            dict(
                game_id=g.game_id,
                season=g.season,
                wind=win.wind_speed_10m.mean(),
                gust=win.wind_gusts_10m.max(),
                precip=win.precipitation.sum(),
                temp=win.temperature_2m.mean(),
                obs_wind=g.wind,
                obs_temp=g.temp,
            )
        )
    return pd.DataFrame(rows)


def kicker_points(d: pd.DataFrame) -> pd.Series:
    fg = d.fg_made.fillna(0) - d.fg_made_40_49.fillna(0) - d.fg_made_50_59.fillna(0) - d.fg_made_60_.fillna(0)
    return 3 * fg + 4 * d.fg_made_40_49.fillna(0) + 5 * (d.fg_made_50_59.fillna(0) + d.fg_made_60_.fillna(0)) + d.pat_made.fillna(0)


def player_games(work: Path) -> pd.DataFrame:
    frames = []
    for y in SEASONS:
        f = pd.read_csv(work / f"ps_{y}.csv", low_memory=False)
        f = f[(f.season_type == "REG") & f.position.isin(POSITIONS)].copy()
        f["pts"] = np.where(f.position == "K", kicker_points(f), f.fantasy_points_ppr)
        frames.append(f[["player_id", "position", "season", "week", "game_id", "pts", "attempts", "passing_yards", "targets"]])
    return pd.concat(frames, ignore_index=True)


def fe_cluster_ols(y: np.ndarray, X: np.ndarray, groups: np.ndarray, clusters: np.ndarray):
    """Within-group (fixed effect) OLS with cluster-robust SEs."""
    df = pd.DataFrame(X)
    df["y"] = y
    df["g"] = groups
    means = df.groupby("g").transform("mean")
    Xd = (df.drop(columns=["y", "g"]) - means.drop(columns=["y"])).to_numpy()
    yd = (df["y"] - means["y"]).to_numpy()
    xtx_inv = np.linalg.pinv(Xd.T @ Xd)
    beta = xtx_inv @ Xd.T @ yd
    resid = yd - Xd @ beta
    codes, _ = pd.factorize(clusters)
    scores = np.zeros((codes.max() + 1, Xd.shape[1]))
    np.add.at(scores, codes, Xd * resid[:, None])
    meat = scores.T @ scores
    n_groups = len(pd.unique(groups))
    n_clusters = len(pd.unique(clusters))
    dof = (n_clusters / (n_clusters - 1)) * ((len(y) - 1) / max(len(y) - n_groups - Xd.shape[1], 1))
    cov = dof * xtx_inv @ meat @ xtx_inv
    return beta, np.sqrt(np.diag(cov))


def analyse(
    work: Path,
    wind_col: str = "wind",
    temp_col: str = "temp",
    with_loso: bool = True,
    seasons: tuple[int, int] | None = None,
) -> dict:
    gw = game_weather(work)
    gw = gw.copy()
    if seasons is not None:
        gw = gw[gw.season.between(*seasons)]
    gw["wind"] = gw[wind_col]
    gw["temp"] = gw[temp_col]
    gw = gw.dropna(subset=["wind", "temp"])
    pg = player_games(work).merge(gw.drop(columns=["season"]), on="game_id", how="inner")
    out: dict = {"n_games_with_weather": int(len(gw)), "tier_games": {}, "positions": {}}
    for name, fn in TIERS.items():
        out["tier_games"][name] = int(fn(gw).sum())
    out["wind_corr_with_observed"] = float(gw[["wind", "obs_wind"]].dropna().corr().iloc[0, 1])
    for pos in POSITIONS:
        d = pg[pg.position == pos].copy()
        d["ps"] = d.player_id.astype(str) + "_" + d.season.astype(str)
        cap = d.pts.quantile(0.99)
        d["y"] = d.pts.clip(upper=cap)
        stats = d.groupby("ps").y.agg(["mean", "size"])
        keep = stats[(stats["size"] >= MIN_GAMES) & (stats["mean"] >= MIN_MEAN_BY_POS[pos])].index
        d = d[d.ps.isin(keep)]
        # Fixed effects use every outdoor game; require both calm and
        # adverse games implicitly through within-demeaning.
        X = np.column_stack([fn(d).astype(float).to_numpy() for fn in TIERS.values()])
        beta, se = fe_cluster_ols(d.y.to_numpy(), X, d.ps.to_numpy(), d.game_id.to_numpy())
        base = float(d.y.mean())
        res = {"player_games": int(len(d)), "player_seasons": int(d.ps.nunique()), "mean_points": base, "tiers": {}}
        for i, name in enumerate(TIERS):
            mask = X[:, i] == 1
            pct, pct_se = 100 * beta[i] / base, 100 * se[i] / base
            # leave-one-season-out range of the raw effect
            loso = []
            for s in sorted(d.season.unique() if with_loso else []):
                sub = d[d.season != s]
                Xs = np.column_stack([fn(sub).astype(float).to_numpy() for fn in TIERS.values()])
                b, _ = fe_cluster_ols(sub.y.to_numpy(), Xs, sub.ps.to_numpy(), sub.game_id.to_numpy())
                loso.append(100 * b[i] / base)
            res["tiers"][name] = {
                "player_games_treated": int(mask.sum()),
                "games_treated": int(d.game_id[mask].nunique()),
                "effect_pts": float(beta[i]),
                "effect_pct": float(pct),
                "se_pct": float(pct_se),
                "z": float(pct / pct_se) if pct_se else 0.0,
                "loso_min_pct": float(min(loso)) if loso else None,
                "loso_max_pct": float(max(loso)) if loso else None,
            }
        out["positions"][pos] = res
    # Empirical-Bayes shrinkage with ONE prior spread estimated from the data
    # itself (method of moments over every position x condition estimate):
    # tau^2 = mean(est^2) - mean(se^2), floored. Each estimate is then pulled
    # toward zero by tau^2 / (tau^2 + se^2), so noisy cells (few games) move
    # the most and a single extreme game cannot set a number.
    cells = [t for v in out["positions"].values() for t in v["tiers"].values()]
    tau2 = max(np.mean([c["effect_pct"] ** 2 for c in cells]) - np.mean([c["se_pct"] ** 2 for c in cells]), 4.0)
    out["prior_sd_pct"] = float(np.sqrt(tau2))
    for v in out["positions"].values():
        for c in v["tiers"].values():
            c["shrunk_pct"] = float(c["effect_pct"] * tau2 / (tau2 + c["se_pct"] ** 2))
            c["z_ok"] = bool(c["z"] <= -Z_BAR)
    return out


def decide(primary: dict, early: dict, late: dict, alt: dict) -> None:
    """Mark each cell adopted only when it (1) is harmful with z <= -Z_BAR
    (above 2 because 25 cells are tested at once), (2) points the same way in
    BOTH halves of the sample (2011-2018 and 2019-2025), and (3) for wind and
    cold, is corroborated (same sign, z <= -1.5) when the weather is taken
    from the stadium-reported game-day numbers instead of the reanalysis."""

    for pos, v in primary["positions"].items():
        for tier, c in v["tiers"].items():
            e, l, a = (x["positions"][pos]["tiers"][tier] for x in (early, late, alt))
            c["early_pct"], c["late_pct"] = e["effect_pct"], l["effect_pct"]
            c["alt_pct"], c["alt_z"] = a["effect_pct"], a["z"]
            c["halves_agree"] = bool(e["effect_pct"] < 0 and l["effect_pct"] < 0)
            c["alt_ok"] = True if tier.startswith("rain") else bool(a["effect_pct"] < 0 and a["z"] <= -1.5)
            c["adopted"] = bool(c["z_ok"] and c["halves_agree"] and c["alt_ok"])


if __name__ == "__main__":
    work = Path(sys.argv[1])
    result = analyse(work)
    # Robustness: the same wind tiers using the stadium-reported wind that
    # nflverse publishes instead of the reanalysis wind.
    alt = analyse(work, wind_col="obs_wind", temp_col="obs_temp", with_loso=False)
    early = analyse(work, seasons=(2011, 2018), with_loso=False)
    late = analyse(work, seasons=(2019, 2025), with_loso=False)
    decide(result, early, late, alt)
    result["split_games"] = {"early": early["n_games_with_weather"], "late": late["n_games_with_weather"], "alt": alt["n_games_with_weather"]}
    (work / "weather_effects_result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
