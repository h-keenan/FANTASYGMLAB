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

## Measurement (real player pool from a read-only copy of players.db, 3 synthetic leagues of 10/12/14 teams, 5 postures x 5 teams each, week 11)

Not a full replay: the #2164 harness needs several GB of nflverse and DynastyProcess history that is not on this machine, and the machine
is out of memory and disk headroom for it. So there is no out-of-sample outcome number for this change, and the flag ships OFF.
"IR" below includes any Out/IR/PUP status, so it over-counts short absences.

| posture | ideas off -> on | targets off -> on | IR/Out targets | deep-chart targets | IR/Out and deep |
|---|---|---|---|---|---|
| contender | 235 -> 215 | 226 -> 206 | 79 -> 33 | 54 -> 15 | 50 -> 15 |
| fringe contender | 234 -> 223 | 223 -> 212 | 79 -> 46 | 52 -> 18 | 50 -> 18 |
| retool | 239 -> 237 | 225 -> 222 | 74 -> 52 | 60 -> 26 | 58 -> 26 |
| rebuild | 245 -> 240 | 179 -> 176 | 45 -> 35 | 41 -> 26 | 41 -> 26 |
| tank | 244 -> 239 | 179 -> 175 | 44 -> 36 | 39 -> 26 | 39 -> 26 |

Target and idea counts hold (contender -8.5% ideas, others -2% or less). The remaining deep or out targets are mostly players whose snap share
shows a real role the chart understates, or one-week Out designations.
