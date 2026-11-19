"""Market-value recovery backtest for the dynasty injury multiplier (docs/audits/2026-11-injury-discount.md).

usage: injury_return_backtest.py NV_DIR DP_DIR PANEL_PARQUET OUT_JSON [--min-value 1500]

Re-runs the #2196 backtest with an observable injured definition: at a DynastyProcess snapshot date D the player's state in the
last completed regular-season week (the panel from injury_return_panel.py) is Out, Doubtful or IR (IR = absent after an Out).
"Relative value" at a horizon = (injured value ratio) / (median same-position control value ratio), controls = not injured, within 15%
of the injured value and 2.5 years of age (up to 15), at the snapshot nearest D + 4 / 8 / 26 weeks (within 3 / 3 / 4 weeks).
A relative value of 1.0 means the injured player kept pace with healthy peers after the market had priced the injury.

Each dynasty injury multiplier (legacy age curve, horizon model with the table's weeks_out, horizon model with the fitted games lost)
is scored by |multiplier - relative value|: the multiplier is the further discount the valuation applies on top of a market value that
already includes the injury, so the closer it sits to the realized further change, the better. Paired improvements carry 95% CIs
from resampling players. Date years 2024-25 are the out-of-sample cut for the fitted curves (fit on 2021-23 stats).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
HORIZONS = {4: 3, 8: 3, 26: 4}  # weeks -> tolerance in weeks
STATE_STATUS = {"IR": ("Inactive", "IR"), "Out": ("Active", "Out"), "Doubtful": ("Active", "Doubtful")}


def norm(name: str) -> str:
    s = re.sub(r"[^a-z ]", "", str(name).lower())
    return " ".join(w for w in s.split() if w not in {"jr", "sr", "ii", "iii", "iv", "v"})


def boot_ci(diff: np.ndarray, players: np.ndarray, n_boot: int = 4000, seed: int = 11) -> list[float]:
    ids, inv = np.unique(players, return_inverse=True)
    s, c = np.bincount(inv, weights=diff), np.bincount(inv).astype(float)
    idx = np.random.default_rng(seed).integers(0, len(ids), size=(n_boot, len(ids)))
    m = s[idx].sum(1) / c[idx].sum(1)
    return [float(diff.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))]


def main() -> None:
    nv, dp, panel_path, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
    min_value = float(sys.argv[sys.argv.index("--min-value") + 1]) if "--min-value" in sys.argv else 1500.0
    from modules import rankings

    flag_h, flag_c = rankings.INJURY_HORIZON_ENV_KEY, rankings.injury_return_curves.DYNASTY_FEED_ENV_KEY

    ids = pd.read_csv(nv / "players.csv", usecols=["gsis_id", "display_name", "position", "last_season"])
    ids = ids[ids.position.isin(["QB", "RB", "WR", "TE"])].sort_values("last_season")
    ids["k"] = ids.display_name.map(norm)
    idmap = {(r.k, r.position): r.gsis_id for r in ids.itertuples()}  # latest last_season wins

    games = pd.read_csv(nv / "games.csv", usecols=["season", "game_type", "week", "gameday"])
    games = games[(games.game_type == "REG") & games.season.between(2020, 2025)]
    wk_end = games.groupby(["season", "week"]).gameday.max().reset_index()
    wk_end["gameday"] = pd.to_datetime(wk_end.gameday)

    panel = pd.read_parquet(panel_path, columns=["player_id", "pos", "season", "week", "state", "age_k"])
    panel = panel[panel.state != "none"]
    state_at = {(r.player_id, r.season, r.week): (r.state, r.age_k) for r in panel.itertuples()}

    snaps = []
    for f in sorted(dp.glob("*_values-players.csv")):
        d = pd.read_csv(f, usecols=["player", "pos", "age", "value_1qb"])
        d = d[d.pos.isin(["QB", "RB", "WR", "TE"])].copy()
        d["date"] = pd.Timestamp(f.name[:10])
        d["gsis"] = [idmap.get((norm(n), p)) for n, p in zip(d.player, d.pos)]
        snaps.append(d.rename(columns={"value_1qb": "value"}))
    snaps_df = pd.concat(snaps, ignore_index=True)
    dates = sorted(snaps_df.date.unique())
    by_date = {pd.Timestamp(dt): g.set_index("gsis", drop=False) for dt, g in snaps_df.groupby("date")}

    rows = []
    for dt in dates:
        dt = pd.Timestamp(dt)
        past = wk_end[wk_end.gameday < dt - pd.Timedelta(days=1)]
        if past.empty:
            continue
        season, week = int(past.iloc[-1].season), int(past.iloc[-1].week)
        snap = by_date[dt]
        snap = snap[snap.gsis.notna() & ~snap.index.duplicated()]
        injured = {}
        for g in snap.itertuples():
            st = state_at.get((g.gsis, season, week))
            if st and st[0] in STATE_STATUS and g.value >= min_value:
                injured[g.gsis] = st
        for gsis, (state, age_k) in injured.items():
            inj = snap.loc[gsis]
            pool = snap[(snap.pos == inj.pos) & ~snap.index.isin(injured) & (abs(snap.value / inj.value - 1) <= 0.15) & (abs(snap.age - inj.age) <= 2.5)]
            pool = pool.assign(d=abs(pool.value / inj.value - 1)).sort_values("d").head(15)
            for h, tol in HORIZONS.items():
                target = dt + pd.Timedelta(weeks=h)
                cand = min(dates, key=lambda x: abs(pd.Timestamp(x) - target))
                if abs(pd.Timestamp(cand) - target) > pd.Timedelta(weeks=tol):
                    continue
                later = by_date[pd.Timestamp(cand)]
                later = later[later.gsis.notna() & ~later.index.duplicated()]
                if gsis not in later.index:
                    continue
                inj_ratio = later.loc[gsis, "value"] / inj.value
                ctrl = [later.loc[c, "value"] / snap.loc[c, "value"] for c in pool.index if c in later.index]
                if len(ctrl) < 3:
                    continue
                rows.append({"gsis": gsis, "date": str(dt.date()), "year": dt.year, "h": h, "state": state, "age_k": int(age_k), "age": float(inj.age),
                             "pos": inj.pos, "value": float(inj.value), "rel": float(inj_ratio / np.median(ctrl)), "in_season": bool(dt.month in (10, 12))})
    d = pd.DataFrame(rows)
    # dynasty multipliers under the three regimes (functions read the flags at call time)
    def mult(flag_horizon: str, flag_curves: str) -> np.ndarray:
        os.environ[flag_h], os.environ[flag_c] = flag_horizon, flag_curves
        return np.array([rankings.injury_multiplier_for_age(*STATE_STATUS[s], a) for s, a in zip(d.state, d.age)])

    d["m_legacy"] = mult("0", "0")
    d["m_horizon_table"] = mult("1", "0")
    d["m_horizon_fitted"] = mult("1", "1")
    os.environ.pop(flag_h, None)
    os.environ.pop(flag_c, None)

    res: dict = {"min_value": min_value, "n_rows": int(len(d)), "n_players": int(d.gsis.nunique())}
    def summarize(sub: pd.DataFrame) -> dict:
        o = {"n": int(len(sub)), "players": int(sub.gsis.nunique()), "rel_median": float(sub.rel.median()), "rel_mean": float(sub.rel.mean())}
        for m in ("m_legacy", "m_horizon_table", "m_horizon_fitted"):
            o[m + "_mean"] = float(sub[m].mean())
            o[m + "_mae"] = float((sub[m] - sub.rel).abs().mean())
        if len(sub) >= 3:
            pl = sub.gsis.to_numpy()
            el, et, ef = ((sub[m] - sub.rel).abs().to_numpy() for m in ("m_legacy", "m_horizon_table", "m_horizon_fitted"))
            o["improve_table_vs_legacy"] = boot_ci(el - et, pl)
            o["improve_fitted_vs_legacy"] = boot_ci(el - ef, pl)
            o["improve_fitted_vs_table"] = boot_ci(et - ef, pl)
            o["rel_ci95"] = boot_ci(sub.rel.to_numpy(), pl)
        return o

    for name, sub in (("all_years", d), ("oos_2024_25", d[d.year >= 2024]), ("in_2021_23", d[d.year <= 2023])):
        res[name] = {"pooled": summarize(sub)} | {f"+{h}w": summarize(sub[sub.h == h]) for h in HORIZONS}
        res[name]["in_season_pooled"] = summarize(sub[sub.in_season])
    out.write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
