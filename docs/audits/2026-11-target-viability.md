# Trade Board target viability (flag DYNASTYGM_TARGET_VIABILITY_V1), 2026-11-19

Report: the Trade Board offered Trey Benson (ARI RB, 24, IR with a knee injury and no return date, sixth on the chart) as a target, with a
Decision Fit that named market value as the driver and role as the softest input.

## Diagnosis

* The "Trade Board" label is the source label on the player sheet opened from a trade idea. The automatic target pool is built in
  `modules/trade_ideas.py` (`partner_target_players`): ordered by `_target_trade_fit` (need, surplus, age, posture) and gated by value and a
  shallow-position check. **No availability or depth-role term exists in target selection.** An injured player entered only through his own
  `value_score`, whose dynasty injury multiplier is a three-season horizon and small; his market percentile stayed high.
* `DYNASTYGM_INJURY_RETURN_CURVES_DYNASTY_V1` being OFF is not the cause: the Analyzer prices injuries through `trade_grade`
  (`estimate_injury_absence`, `injury_availability_cost`), which the target picker never consulted.
* Card data: "0 missed in 2026" came from the data source (nflverse weekly reports carry no rows for IR players, so counting Out weeks
  yields 0). "RB6, 4 ahead, 6 on the chart" came from Sleeper's non-contiguous `depth_chart_order` (1,2,3,4,6,7) shown raw while "ahead"
  counted listed players. Both fixed in PR 2229.

## Fix

`modules/target_viability.py`, behind `DYNASTYGM_TARGET_VIABILITY_V1` (owner coridian_, kill switch = env 0, default OFF):

* availability: `trade_grade.estimate_injury_absence` + `season_window` + `injury_posture_weight`, blended with the fitted return curves'
  expected games lost over 17 (`injury_return_curves`). No new table, no copied constants.
* role: depth place against `sim.team_roles.STARTER_SLOTS`; snap share corroborates; a young player's future role is credited by the
  posture's weight.
* posture: the same weight blends this season and later.
* verdicts: target / stash / avoid. A stash is a cheap, young, injured or buried player for a retool-or-below team; the idea text says
  "Injured stash, buy-low only: <injury, timing, depth>; cheap now, value if he returns and the role opens.", and stash ideas always sort behind
  healthy ideas.

## Follow-up findings (why 15 IR/Out-and-deep contender targets remained, and why stash read 0)

* Remaining contender targets were (a) short-term Out designations, which are allowed, and (b) players whose snap share (>= 55%) shows a
  real role the chart understates; but also (c) a real defect: Sleeper numbers WRs inside each sub-slot (LWR / RWR / SWR), so a raw
  order of 6 on one sub-slot is not "sixth WR". The role factor now reads WR sub-slots per slot, and the buried cut is explicit:
  usable depth QB2 / RB4 / WR5 / TE3, anything deeper is buried (QB3+, RB5+, WR6+, TE4+). The target threshold also moved to 0.6, so an
  IR player with no return date is never a contender or fringe-contender target (availability alone is 0.45 / 0.53).
* The stash counter was not a counting bug: the stash was appended after the first `target_cap` candidates, where the generator never
  looks. It now sits at the end of that window, behind every healthy fit that fills it. Stash is plentiful on real data (pool scan, rebuild: 37 IR+deep
  players are stash-eligible), and a depth-only stash (healthy but buried, young, cheap) is labelled "Depth stash", not "Injured stash".

## Measurement (real player pool from a read-only copy of players.db, 3 synthetic leagues of 10/12/14 teams, 5 postures x 5 teams each, week 11)

"IR" = IR/PUP/NFI/reserve only (strict). "Deep" = raw depth order at or past QB3 / RB5 / WR6 / TE4. Flag OFF -> ON:

| posture | ideas | targets | IR targets | deep targets | IR and deep | stash targets |
|---|---|---|---|---|---|---|
| contender | 235 -> 209 (-11.1%) | 226 -> 200 | 47 -> 0 | 51 -> 0 | 36 -> 0 | 0 |
| fringe contender | 234 -> 214 (-8.5%) | 223 -> 203 | 46 -> 0 | 49 -> 0 | 34 -> 0 | 0 |
| retool | 239 -> 233 | 225 -> 217 | 42 -> 2 | 57 -> 19 | 39 -> 2 | 2 |
| rebuild | 245 -> 239 | 179 -> 170 | 27 -> 2 | 38 -> 12 | 24 -> 0 | 2 |
| tank | 244 -> 238 | 179 -> 170 | 26 -> 2 | 36 -> 11 | 23 -> 0 | 2 |

Per-league idea counts (OFF -> ON, 5 teams each): contender 76 -> 74, 81 -> 78, 78 -> 57 (the 14-team league); no posture loses all of its ideas in any
league. Contender volume falls 11.1%, 1.1 points over the 10% gate, almost all in the 14-team league; the lost ideas are the ones built on IR or buried
targets. Remaining deep targets for non-contenders are snap-share-corroborated roles or stash-labelled players.

## Replay

The replay inputs are small (public nflverse + DynastyProcess, about 9 MB as a tar.gz). A one-season, one-date, one-format slice ran locally in about 25 s and 480 MB. Run it on a box or in Actions:

* GitHub Actions: `.github/workflows/target-viability-replay.yml` (workflow_dispatch only; give it a `data_url` for a tar.gz holding `nv/` and `dp/`). It
  runs `ideas_run.py` with the flag OFF and ON and uploads both result sets.
* Box: `REPLAY_REPO=<repo> REPLAY_DATA=<dir with nv/ and dp/> REPLAY_OUT=<dir>/off DYNASTYGM_TARGET_VIABILITY_V1=0 python docs/audits/historical-replay/code/ideas_run.py --out <dir>/off --variant base --seasons 2024 --dates 10-20,12-01 --formats dynasty_sf --sizes 12`, then the same with `=1` and `--out <dir>/on`, then `analyze_ideas.py` on each.
* Limit: the replay's depth order is usage-derived and its injuries come from nflverse reports (no IR rows), so it exercises the role term far more than the IR term.

### Replay input data asset

* Asset: `replay-data-2026-11.tar.gz` (8,905,411 bytes), sha256 `0d665ea348e9c57f955b3ba0d1f87cae13082b39341931811e567000f50542ec`. Contents: `nv/` (nflverse `spw_2020..2026.parquet`, `inj_2020..2026.csv`, `players.csv`, `games.csv`) and `dp/` (DynastyProcess `<season>-<mm-dd>_values-players.csv` and `_values-picks.csv` for Apr 15, May 20, Aug 20, Oct 20, Dec 1 of 2021-2025, the commit nearest each date). Public data only.
* Create the release (the user runs this):

```
gh release create replay-data-2026-11 --prerelease --title "Replay data 2026-11" --notes "Public nflverse + DynastyProcess inputs for the #2164 historical replay" <path-to-tarball>
gh workflow run target-viability-replay.yml -f data_url=https://github.com/<owner>/<repo>/releases/download/replay-data-2026-11/replay-data-2026-11.tar.gz -f seasons=2021,2022,2023,2024,2025 -f dates=04-15,05-20,08-20,10-20,12-01 -f formats=dynasty_sf -f sizes=12
```

* Workflow inputs: `data_url`, `seasons`, `dates`, `formats`, `sizes`. There is no train/test split input. Train 2021-23 / test 2024-25 is done by running the workflow twice, `-f seasons=2021,2022,2023` and `-f seasons=2024,2025`, and comparing the OFF/ON artifacts per run. The tarball holds all seasons (the harness always loads nflverse 2020-2026 for lookbacks). A private repo needs a `data_url` the runner can fetch without auth; a private release asset will not download via plain curl.
* Limitation: depth order is usage-derived and the nflverse injury source has no IR rows, so the replay exercises the role term more than the IR term.

### Replay results (run locally 2026-11-20, flag OFF vs ON)

Harness `ideas_run.py`, 12-team leagues, seasons 2021-2025, dates 04-15/05-20/08-20/10-20/12-01, formats dynasty_sf and dynasty_1qb, run sequentially (about 35 min per flag, under 0.5 GB RAM, 24 MB output). Train 2021-23 / test 2024-25 is the split `analyze_ideas.py` uses. Differences are ON minus OFF, paired by league-date-team, bootstrap 95% CI (1000 resamples). ROS / horizon points are the realised lineup points of the user side (`u_ros`, `u_ros + u_y1`); partner is `p_h`.

| | train SF | train 1QB | test SF | test 1QB | test both |
|---|---|---|---|---|---|
| ideas OFF / ON | 1427 / 1424 | 1412 / 1410 | 939 / 938 | 960 / 960 | 1899 / 1898 |
| ROS pts diff | +0.02 [-0.93, 0.96] | -0.09 [-1.26, 0.99] | +0.49 [-0.58, 1.73] | **-1.72 [-3.03, -0.71]** | -0.62 [-1.43, 0.17] |
| horizon pts diff | -1.33 [-3.41, 0.66] | -1.07 [-3.16, 0.88] | +0.76 [-1.95, 3.35] | **-3.70 [-7.46, -0.70]** | -1.47 [-3.65, 0.60] |
| partner pts diff | +1.71 [-0.13, 3.82] | +0.93 [-0.83, 2.86] | +0.12 [-3.04, 3.29] | **+3.59 [1.31, 6.47]** | +1.85 [-0.03, 4.03] |
| win % OFF -> ON | 48.4 -> 48.0 | 50.2 -> 50.0 | 46.4 -> 46.0 | 49.7 -> 48.9 | 48.0 -> 47.4 |
| win-win % OFF -> ON | 8.3 -> 8.1 | 13.7 -> 14.0 | 15.0 -> 15.4 | 16.7 -> 16.5 | 15.8 -> 15.9 |

* ON barely changes the idea set: 4738 OFF vs 4732 ON ideas overall; per-posture counts are identical except retool (-3 train, -1 test) and tank (-2 train). Mean ideas per team 7.91 vs 7.91 on test.
* Playoff-odds and title-odds deltas (`u_dpo`, `u_dti`) are within +-0.2 pp, CIs straddle zero except test 1QB dpo (-0.2 pp, tiny).
* Is ON negative on the test years? The point estimate is slightly negative on both formats combined (ROS -0.6, horizon -1.5 pts per idea, CIs include zero), and in test dynasty_1qb it is significantly negative for the user side (ROS -1.7, horizon -3.7) with the partner gaining +3.6. Test dynasty_sf is slightly positive and not significant, train is flat. This is not a clear win for the flag, and the 1QB test signal is the one to look at before turning it on. Only a handful of ideas change per slice, so it is a small sample of swapped ideas, and no multiple-comparison correction was applied across the 6 columns.
* Limitation: the replay's depth order is usage-derived and the nflverse injury reports have no IR rows, so it tests the role term far more than the IR term; the IR-driven part of the viability check is effectively unexercised.
