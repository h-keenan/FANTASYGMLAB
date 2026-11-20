"""Part (a)/(b): MAE and bias by elapsed bucket and position for the live model vs baselines."""
import sys
sys.path.insert(0, ".")
from pathlib import Path
import numpy as np
import pandas as pd
from modules import matchup_win_probability as M

CS = Path("calibration_scratch")
d = pd.read_parquet(CS / "checkpoints.parquet")


def starter(r, key):
    return {"game_started": True, "game_final": False, "actual_points": r.cum, "game_remaining": r.remaining,
            "projection": {"status": "ok", "point_estimate": r.est, "mean_estimate": r.mean_est, "low": r.low, "high": r.high}}


def live(frame, basis):
    out = np.empty(len(frame))
    for i, r in enumerate(frame.itertuples(index=False)):
        v = M._projected_final_raw(starter(r, basis), basis=basis)
        out[i] = r.cum + r.remaining * (r.est if basis == "point" else r.mean_est) if v is None else v
    return out


if __name__ == "__main__":
    d["elapsed"] = 1 - d.remaining
    d["live_point"] = live(d, "point")
    d["live_mean"] = live(d, "mean")
    d["pregame"] = d.est
    d["pregame_mean"] = d.mean_est
    d["naive"] = d.cum + d.remaining * d.est
    d["naive_mean"] = d.cum + d.remaining * d.mean_est
    d["bucket"] = pd.cut(d.elapsed, [-0.01, 0.25, 0.5, 0.75, 1.0], right=False, labels=["0-25", "25-50", "50-75", "75-100"]).astype(str)
    d.loc[d.t == -1, "bucket"] = "OT"
    d.to_parquet(CS / "checkpoints_pred.parquet")
    models = ["pregame", "naive", "live_point", "pregame_mean", "naive_mean", "live_mean"]
    for m in models:
        d["err_" + m] = d[m] - d.final
    def tab(by):
        rows = []
        for k, g in d.groupby(by):
            row = {"group": k, "n": len(g)}
            for m in models:
                row[m + "_mae"] = g["err_" + m].abs().mean()
                row[m + "_bias"] = g["err_" + m].mean()
            rows.append(row)
        return pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    for by in (["bucket"], ["pos"], ["bucket", "pos"]):
        print(by); print(tab(by).round(3).to_string(index=False))
    # per season
    print(tab(["season", "bucket"]).round(3).to_string(index=False))
    # pairwise: live vs naive paired difference, bootstrap-free SE
    for b, g in d.groupby("bucket"):
        for a, c in (("live_point", "naive"), ("live_point", "pregame"), ("live_mean", "naive_mean")):
            x = g["err_" + a].abs() - g["err_" + c].abs()
            print(b, a, "vs", c, "dMAE", round(x.mean(), 4), "se", round(x.std() / np.sqrt(len(x)), 4))
