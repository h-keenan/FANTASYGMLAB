import os
"""Post-hoc re-rankings / filters of the base idea set (no re-generation): train 2021-23 vs test 2024-25."""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.environ["REPLAY_OUT"])
import analyze_ideas as A

d = A.prep_ideas(A.read("ideas", "base"))
d["unit"] = d.season.astype(str) + d.mmdd + d.league + d.n_teams.astype(str) + d.team.astype(str)
out = []


def boot(delta, n=400, seed=3):
    x = np.asarray(delta, float)
    x = x[~np.isnan(x)]
    rng = np.random.default_rng(seed)
    b = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(n)]
    return float(x.mean()), float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5)), len(x)


# 1 ordering: top-3 per team-date under each ordering. Outcome = ROS lineup pts (all seasons) and ROS+next (<2025)
for name, col in (("current order (idea_rank)", None), ("market_realism_score desc", "market_realism_score"),
                  ("market value delta at trade desc", "mkt_delta_start"), ("trade_confidence_score desc", "trade_confidence_score")):
    for per, seasons in (("train", A.TRAIN), ("test", A.TEST)):
        s = d[d.season.isin(seasons)]
        if col is None:
            top = s[s.idea_rank < 3]
        else:
            top = s.sort_values(["unit", col], ascending=[True, False]).groupby("unit").head(3)
        out.append(dict(test="top-3 ideas per team: ordering", variant=name, period=per, ros=top.u_ros.mean(), h=top.u_h.mean(), win_ros=100 * top.win_ros.mean(),
                        dpo_pp=100 * top.u_dpo.mean(), n=len(top)))
# paired difference vs current order (per unit mean of ros), bootstrap over units
for col in ("market_realism_score", "mkt_delta_start"):
    for per, seasons in (("train", A.TRAIN), ("test", A.TEST)):
        s = d[d.season.isin(seasons)]
        cur = s[s.idea_rank < 3].groupby("unit").u_ros.mean()
        new = s.sort_values(["unit", col], ascending=[True, False]).groupby("unit").head(3).groupby("unit").u_ros.mean()
        m, lo, hi, n = boot((new - cur).dropna())
        out.append(dict(test="top-3 ordering paired gain (ROS pts)", variant=col, period=per, ros=m, h=lo, win_ros=hi, n=n))
# 2 filters: remove ideas that hand the user a QB / picks-only returns for contender postures
for name, mask in (("drop 'gets QB' ideas", d.pos_group == "gets QB"),
                   ("drop 'Convert veteran to picks' + 'Ask for their pick' for contender/fringe",
                    d.tag.isin(["Convert veteran to picks", "Ask for their pick"]) & d.posture.isin(["contender", "fringe_contender"])),
                   ("drop 'Thin' market-realism ideas", d.market_realism_label == "Thin")):
    for per, seasons in (("train", A.TRAIN), ("test", A.TEST)):
        s = d[d.season.isin(seasons)]
        mm = mask.loc[s.index]
        kept, dropped = s[~mm], s[mm]
        out.append(dict(test="filter", variant=name, period=per, ros=kept.u_ros.mean() - s.u_ros.mean(), h=kept.u_h.mean() - s.u_h.mean(),
                        win_ros=100 * (kept.win_ros.mean() - s.win_ros.mean()), dpo_pp=100 * (kept.u_dpo.mean() - s.u_dpo.mean()),
                        n=len(dropped), dropped_ros=dropped.u_ros.mean(), dropped_h=dropped.u_h.mean(), share=100 * len(dropped) / len(s)))
# 3 tag x posture
tp = d.groupby(["tag", "posture"]).agg(n=("u_ros", "size"), ros=("u_ros", "mean"), h=("u_h", "mean"), y2=("u_y2", "mean"), val1=("u_valchg1", "mean"),
                                       win_ros=("win_ros", "mean")).reset_index()
tp["win_ros"] *= 100
tp.to_csv(A.OUT / "ideas_tag_by_posture.csv", index=False)
o = pd.DataFrame(out)
o.to_csv(A.OUT / "ideas_posthoc.csv", index=False)
pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 100)
print(o.round(2).to_string())
print(tp[tp.n > 60].round(1).to_string())
