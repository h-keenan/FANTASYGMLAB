import sys
sys.path.insert(0, "calibration_scratch"); sys.path.insert(0, ".")
import pandas as pd, numpy as np
import stage2 as S
from modules import matchup_win_probability as M
d = S.d[S.d.t != -1].copy()
for b in (0.0, 0.25, 0.5, 0.75, 1.0):
    M.PACE_MAX_BLEND = b
    d["p"] = S.live(d, "mean")
    e = (d.p - d.final)
    tr, te = d.season <= 2024, d.season == 2025
    print(b, "train MAE", round(e[tr].abs().mean(), 4), "test MAE", round(e[te].abs().mean(), 4), "test bias", round(e[te].mean(), 3),
          "test MAE 25-75%:", round(e[te & d.remaining.between(0.25, 0.75)].abs().mean(), 4))
