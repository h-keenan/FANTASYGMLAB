"""Grade the harness trade universe under a tuning variant, point-in-time (clock frozen), then score outcomes.

python grades_run.py --out DIR --variant base --per-league 200 [--seasons ...]
"""
from __future__ import annotations

import os

import argparse
import time
import zlib
from pathlib import Path

import replay_lib as R
from replay_lib import B, O, np, pd, lvs
from modules import rankings, trade_grade, trade_ideas

DATA = os.environ["REPLAY_DATA"]


def apply_variant(name: str) -> None:
    if name == "base":
        return
    kind, _, rest = name.partition(":")
    if kind == "floor":  # starter-strength floor for rebuild / tank (P1-5)
        x = float(rest)
        trade_grade.STARTER_STRENGTH_WEIGHTS["rebuild"] = max(trade_grade.STARTER_STRENGTH_WEIGHTS["rebuild"], x)
        trade_grade.STARTER_STRENGTH_WEIGHTS["tank"] = max(trade_grade.STARTER_STRENGTH_WEIGHTS["tank"], x)
    elif kind == "redund":  # roster redundancy discount (P1-3): redund:<scope>[:retention]
        parts = rest.split(":")
        scope = parts[0]
        if len(parts) > 1:
            trade_grade.BENCH_CHIP_RETENTION = float(parts[1])
        trade_grade.roster_redundancy_enabled = lambda: True
        orig = trade_grade.roster_redundancy_adjustment
        if scope != "all":
            def scoped(send_assets, receive_assets, **kw):
                if scope == "qb":
                    vo = kw["value_of"]
                    kw = dict(kw, value_of=lambda a: vo(a) if str(a.get("position") or "").upper() == "QB" else 0.0)
                    return orig(send_assets, receive_assets, **kw)
                if scope == "recv":
                    return orig([], receive_assets, **kw)
                return orig(send_assets, receive_assets, **kw)
            trade_grade.roster_redundancy_adjustment = scoped
    elif kind == "pick1e":  # early-first base value (top end of the pick curve)
        trade_ideas.PICK_TIER_BASE_VALUES[1]["early"] = int(float(rest))
    elif kind == "pickall":  # scale every pick base value
        s = float(rest)
        for r, tiers in trade_ideas.PICK_TIER_BASE_VALUES.items():
            for k in tiers:
                tiers[k] = int(round(tiers[k] * s))
        for r in list(trade_ideas.BASE_PICK_VALUES):
            trade_ideas.BASE_PICK_VALUES[r] = int(round(trade_ideas.BASE_PICK_VALUES[r] * s))
    elif kind == "age":  # age:<old|rb|young>:<exponent>
        grp, s = rest.split(":")
        s = float(s)
        for pos, pts in list(rankings.AGE_CURVE_CONTROL_POINTS.items()):
            new = []
            for age, m in pts:
                hit = (grp == "old" and age >= 27) or (grp == "rb" and pos == "RB" and age >= 25) or (grp == "young" and age <= 23)
                new.append((age, float(m) ** s if hit else m))
            rankings.AGE_CURVE_CONTROL_POINTS[pos] = tuple(new)
    else:
        raise SystemExit(f"unknown variant {name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--variant", default="base")
    ap.add_argument("--per-league", type=int, default=200)
    ap.add_argument("--seasons", default="2021,2022,2023,2024,2025")
    ap.add_argument("--dates", default=",".join(B.DATES))
    ap.add_argument("--leagues", default=",".join(B.LEAGUES))
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tag = a.variant.replace(":", "_")
    logf = open(out / f"grades_{tag}.log", "a")

    def log(m):
        logf.write(m + "\n")
        logf.flush()

    apply_variant(a.variant)
    env = R.Env(DATA + "/nv", DATA + "/dp")
    h = env.h
    base_defaults = dict(lvs.DEFAULT_LEAGUE_VALUE_SETTINGS)
    rows = []
    for season in [int(s) for s in a.seasons.split(",")]:
        for mmdd in a.dates.split(","):
            R.freeze(pd.Timestamp(f"{season}-{mmdd}"))
            lvs.DEFAULT_LEAGUE_VALUE_SETTINGS = dict(base_defaults, season=season)
            for lname in a.leagues.split(","):
                rng = np.random.default_rng(zlib.crc32(f"{a.seed}|{season}|{mmdd}|{lname}".encode()))
                t0 = time.time()
                r = B.run_league(h, season, mmdd, lname, B.LEAGUES[lname], a.per_league, rng, log)
                rows += r
                log(f"{season} {mmdd} {lname}: {len(r)} trades {time.time() - t0:.0f}s")
        df = pd.DataFrame(rows)
        df.to_parquet(out / f"graded_{tag}.parquet")
    scored = O.score(pd.DataFrame(rows), env.sc)
    keep = [c for c in scored.columns if c not in ("roster_ids", "send_names", "recv_names")]
    scored[keep].to_parquet(out / f"scored_{tag}.parquet")
    (out / f"graded_{tag}.parquet").unlink(missing_ok=True)
    log("done")


if __name__ == "__main__":
    main()
