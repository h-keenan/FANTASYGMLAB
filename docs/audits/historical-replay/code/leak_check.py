"""No-future-leakage canaries.

1. POISON: scramble every nflverse row dated after the replay date, and make any DynastyProcess snapshot other than the one at
   the date unreadable. The valuation frame and the Hub ideas must be byte-identical to the clean run.
2. CLOCK: the same league with the wall clock left at today (2026-11) vs frozen at the replay date. Differences prove the freeze is needed.
"""
from __future__ import annotations

import os

import json

import replay_lib as R
import ideas_run as I
from replay_lib import B, np, pd, lvs

OUT = os.environ["REPLAY_OUT"] + "/results"
season, mmdd, lname = 2023, "10-20", "dynasty_sf"
label = f"{season}-{mmdd}"
d = pd.Timestamp(label)

env = R.Env(I.DATA + "/nv", I.DATA + "/dp")
completed = env.h.completed_weeks(season, d)
report = {"date": label, "weeks_completed": completed}


def frame_of(env_):
    R.freeze(d)
    lvs.DEFAULT_LEAGUE_VALUE_SETTINGS = dict(I.lvs.DEFAULT_LEAGUE_VALUE_SETTINGS, season=season)
    fr, _ = B.build_frame(env_.h, label, season, d, completed, B.LEAGUES[lname], completed + 1)
    return B.fit_weekly_baselines(fr).reset_index(drop=True)


clean = frame_of(env)
ideas_clean, _ = I.run_league(env, season, mmdd, lname, 12, 11, 8, print)

# ---- poison
h = env.h
spw = h.spw
future = (spw.season > season) | ((spw.season == season) & (spw.week > completed))
rng = np.random.default_rng(0)
num = spw.select_dtypes("number").columns.difference(["season", "week"])
spw_p = spw.copy()
for c in num:
    spw_p.loc[future, c] = rng.permutation(spw_p.loc[future, c].to_numpy())
report["poisoned_rows"] = int(future.sum())
h_spw_orig = h.spw
h.spw = spw_p
inj_orig = dict(h.inj)
for s in list(h.inj):
    if s > season or s == season:
        i = h.inj[s].copy()
        fut = i.week > (completed if s == season else 0)
        i.loc[fut, "report_status"] = rng.permutation(i.loc[fut, "report_status"].to_numpy())
        h.inj[s] = i
pl_orig = h.players.copy()
h.players["last_season"] = 2099  # future knowledge column used only as a duplicate-name tiebreak
dp_players_orig, dp_picks_orig = h.dp_players, h.dp_picks


def guard(fn):
    def w(lbl, *a, **k):
        if lbl > label:
            raise RuntimeError(f"future snapshot read: {lbl}")
        return fn(lbl, *a, **k)
    return w


# snapshots dated after the date must never be read during generation (outcome scoring reads them, generation must not)
h.dp_players, h.dp_picks = guard(dp_players_orig), guard(dp_picks_orig)
orig_snap = env.sc.snap
env.sc.snap = lambda lbl: None  # outcome snapshots are not needed for the frame / ideas comparison
poisoned = frame_of(env)
ideas_pois, _ = I.run_league(env, season, mmdd, lname, 12, 11, 8, print)
cols = [c for c in clean.select_dtypes('number').columns if c in poisoned.columns]
same_frame = bool(np.allclose(clean[cols].fillna(-1).to_numpy(float), poisoned[cols].fillna(-1).to_numpy(float)))
key = lambda ideas: [(r["team"], r["send_names"], r["recv_names"], r["analyzer_label"], r.get("trade_gain")) for r in ideas]  # noqa: E731
report["frame_identical_under_poison"] = same_frame
report["frame_columns_compared"] = len(cols)
report["ideas_clean"] = len(ideas_clean)
report["ideas_identical_under_poison"] = key(ideas_clean) == key(ideas_pois)

# ---- clock
h.spw = h_spw_orig
h.inj = inj_orig
h.players = pl_orig
h.dp_players, h.dp_picks = dp_players_orig, dp_picks_orig
env.sc.snap = orig_snap
import datetime as _dt  # noqa: E402
from modules import league_rankings, trade_lineup_model  # noqa: E402
trade_lineup_model.date = _dt.date
league_rankings.datetime = _dt.datetime
orig_freeze = R.freeze
R.freeze = lambda dd: None  # leave the wall clock alone (2026-11)
from modules import season_clock, trust_engine  # noqa: E402
import importlib  # noqa: E402
season_clock._today_utc = lambda: _dt.date(2026, 11, 18)
trust_engine._now_bucket = lambda now=None: (now.date().isoformat() if now else "2026-11-18")
ideas_wall, _ = I.run_league(env, season, mmdd, lname, 12, 11, 8, print)
R.freeze = orig_freeze
report["ideas_wall_clock"] = len(ideas_wall)
report["ideas_identical_wall_vs_frozen"] = key(ideas_clean) == key(ideas_wall)
conf = lambda ideas: pd.Series([r.get("trade_confidence_label") for r in ideas]).value_counts().to_dict()  # noqa: E731
report["confidence_frozen"] = conf(ideas_clean)
report["confidence_wall_clock"] = conf(ideas_wall)
report["trust_frozen"] = pd.Series([r.get("trust_enforcement") for r in ideas_clean]).value_counts().to_dict()
report["trust_wall_clock"] = pd.Series([r.get("trust_enforcement") for r in ideas_wall]).value_counts().to_dict()
json.dump(report, open(f"{OUT}/leak_check.json", "w"), indent=1, default=str)
print(json.dumps(report, indent=1, default=str))
