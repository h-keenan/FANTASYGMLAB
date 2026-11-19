"""Pick value curve vs realized rookies vs market, train (classes 2021-23) vs test (2024-25). Also age-curve slopes."""
from __future__ import annotations

import os

import replay_lib as R
from replay_lib import B, O, np, pd, lvs

DATA = os.environ["REPLAY_DATA"]
OUT = os.environ["REPLAY_OUT"] + "/results"

env = R.Env(DATA + "/nv", DATA + "/dp")
h, sc = env.h, env.sc
res = {}
for fmt in ("dynasty_1qb", "dynasty_sf"):
    lg = B.LEAGUES[fmt]
    sf, tep = bool(lg["sf"]), bool(lg["tep"])
    # --- 1. engine score -> realized points over replacement (veterans, 08-20, ROS + next season where complete)
    rows = []
    for season in range(2021, 2026):
        label = f"{season}-08-20"
        R.freeze(pd.Timestamp(label))
        lvs.DEFAULT_LEAGUE_VALUE_SETTINGS = dict(lvs.DEFAULT_LEAGUE_VALUE_SETTINGS, season=season)
        frame, _ = B.build_frame(h, label, season, pd.Timestamp(label), 0, lg, 0)
        field = "dynasty_score"
        for r in frame.itertuples():
            if getattr(r, field) < 800:
                continue
            v0 = O.vor_of(sc, r.player_id, (season, 1, 18), sf, tep)
            v1 = O.vor_of(sc, r.player_id, (season + 1, 1, 18), sf, tep)
            rows.append(dict(season=season, pid=r.player_id, pos=r.position, age=r.age, score=getattr(r, field),
                             market=(r.value_2qb if sf else r.value_1qb), v0=v0, v1=v1, rook=(pd.to_numeric(r.draft_year, errors="coerce") == season)))
    a = pd.DataFrame(rows)
    a["h2"] = a.v0.fillna(0) + a.v1  # NaN when next season incomplete
    # vor 'counted' above replacement only (a below-replacement player is replaced off waivers)
    a["v0c"] = a.v0.clip(lower=0)
    a["v1c"] = a.v1.clip(lower=0)
    a["h"] = a.v0c + a.v1c
    a.to_parquet(f"{OUT}/assets_{fmt}.parquet")
    # fit on veterans 2021-23 only (train), apply to rookies of every class
    vet = a[(~a.rook) & a.h.notna() & a.season.isin([2021, 2022, 2023])]
    X = np.column_stack([np.ones(len(vet)), vet.score.to_numpy()])
    beta, *_ = np.linalg.lstsq(X, vet.h.to_numpy(), rcond=None)
    # --- 2. rookies by slot: realized points (rookie season + next), market value, engine pick value
    cal = []
    for cls in range(2021, 2026):
        order = sc.rookies(cls, sf)
        snap = sc.snap(f"{cls}-08-20")
        for i, pid in enumerate(order[:48]):
            rnd, slot = i // 12 + 1, i % 12 + 1
            v0 = O.vor_of(sc, pid, (cls, 1, 18), sf, tep)
            v1 = O.vor_of(sc, pid, (cls + 1, 1, 18), sf, tep)
            cal.append(dict(cls=cls, rnd=rnd, slot=slot, pid=pid, v0=max(0.0, v0) if v0 == v0 else np.nan, v1=max(0.0, v1) if v1 == v1 else np.nan,
                            mkt_post=float(snap[("value_2qb" if sf else "value_1qb")].get(pid, np.nan))))
    c = pd.DataFrame(cal)
    c["h"] = c.v0.fillna(0) + c.v1  # nan when next season incomplete
    c["h_first"] = c.v0
    c["real_engine_scale"] = (c.h - beta[0]) / beta[1]
    c["real_engine_scale_first"] = (c.h_first * 2 - beta[0]) / beta[1]  # first season only, doubled to compare with a two-season total
    # engine pick values for the same slot (pre-draft, as of April 15 of the class year, 12 teams)
    def engine(rnd, slot, cls):
        pct = (12 - slot + 0.5) / 12.0  # engine convention: 1.0 = weakest team = earliest pick
        comp = R.trade_ideas.pick_value_components(
            cls, rnd, 0, pd.DataFrame(), {"league_format": "Dynasty", "qb_format": "Superflex" if sf else "1QB", "league_size": 12},
            team_context={"slot_percentile": pct}, next_draft_year=cls)
        return int(comp["score"])
    c["engine_pick"] = [engine(r, s, k) for r, s, k in zip(c.rnd, c.slot, c.cls)]
    # market value of the pick slot pre-draft (DP pick ECR -> rank-matched value) at the April 15 snapshot
    mk = []
    for cls in range(2021, 2026):
        label = f"{cls}-04-15"
        picks = h.dp_picks(label)
        fr = h.match(h.dp_players(label), pd.Timestamp(label))
        col, mcol = ("ecr_2qb", "value_2qb") if sf else ("ecr_1qb", "value_1qb")
        cv = fr.dropna(subset=[col, mcol]).sort_values(col)
        for rnd in (1, 2, 3, 4):
            for slot in range(1, 13):
                p = picks[picks.player == f"{cls} Pick {rnd}.{slot:02d}"]
                val = float(np.interp(float(p[col].iloc[0]), cv[col].to_numpy(), cv[mcol].to_numpy())) if len(p) else np.nan
                mk.append(dict(cls=cls, rnd=rnd, slot=slot, market_pick=val))
    c = c.merge(pd.DataFrame(mk), on=["cls", "rnd", "slot"], how="left")
    c["tier"] = np.where(c.slot <= 4, "early", np.where(c.slot <= 8, "mid", "late"))
    c["period"] = np.where(c.cls <= 2023, "train 2021-23", "test 2024-25")
    c.to_parquet(f"{OUT}/picks_{fmt}.parquet")
    t = c.groupby(["rnd", "tier", "period"]).agg(n=("pid", "count"), engine_pick=("engine_pick", "mean"), market=("market_pick", "mean"),
                                                  realized_engine_scale=("real_engine_scale", "mean"), realized_pts=("h", "mean"),
                                                  rookie_season_pts=("h_first", "mean"), mkt_post=("mkt_post", "mean")).reset_index()
    t["fmt"] = fmt
    t["fit_slope"] = beta[1]
    t["fit_icpt"] = beta[0]
    res[fmt] = t
    # --- 3. age slopes (veterans, train vs test): extra realized points per year of age at fixed engine score, by position
    ag = []
    for pos in ("RB", "WR", "TE", "QB"):
        for per, seasons in (("train 2021-23", [2021, 2022, 2023]), ("test 2024-25", [2024, 2025])):
            s = a[(a.pos == pos) & (~a.rook) & a.season.isin(seasons) & a.v0.notna() & (a.market > 1500)]
            col = "h" if per.startswith("train") else "v0c"
            s = s[s[col].notna()]
            if len(s) < 40:
                continue
            for lab, mask in (("<=26", s.age <= 26), (">=27", s.age >= 27)):
                pass
            X = np.column_stack([np.ones(len(s)), s.score.to_numpy(), (s.age.clip(lower=24) - 27).to_numpy()])
            b, *_ = np.linalg.lstsq(X, s[col].to_numpy(), rcond=None)
            resid = s[col].to_numpy() - X @ b
            se = np.sqrt(np.diag(np.linalg.inv(X.T @ X)) * resid.var())
            ag.append(dict(fmt=fmt, pos=pos, period=per, n=len(s), outcome=("ros+next" if per.startswith("train") else "rest-of-season"),
                           per_year_age_pts=b[2], se=se[2], per_1000_score=1000 * b[1]))
    res[fmt + "_age"] = pd.DataFrame(ag)
pd.concat([res["dynasty_1qb"], res["dynasty_sf"]]).to_csv(f"{OUT}/pick_calibration.csv", index=False)
pd.concat([res["dynasty_1qb_age"], res["dynasty_sf_age"]]).to_csv(f"{OUT}/age_slopes.csv", index=False)
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 200)
print(pd.concat([res["dynasty_1qb"], res["dynasty_sf"]]).round(0).to_string())
print(pd.concat([res["dynasty_1qb_age"], res["dynasty_sf_age"]]).round(2).to_string())
