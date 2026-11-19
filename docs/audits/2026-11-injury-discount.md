# Injury discount audit, November 2026

Date: 2026-11-19. Question from the front desk: Puka Nacua is 7th on the market and 61st on our public board; is the IR discount
right for dynasty? Run on live FantasyCalc values (fresh fetch through the fixed parser, current Sleeper cache), valuation
settings = defaults (12-team, 1QB, PPR), dynasty and redraft lenses. Harness: `scripts/audits/injury_horizon_diff.py`.

## Verdict

- The dynasty discount is large and mechanical: an injured 25-year-old keeps about 72% of his composite whatever the injury,
  and the same discount applies to a 4-week and a 12-week absence. The IR players below sit a median of **79 ranks below the
  market in dynasty (healthy players: -1)** and 146 below in redraft.
- The backtest (below) says the market has usually already priced the injury, and does not take a further large cut from
  injured players afterwards. Point estimates favour a smaller dynasty discount, but the sample is **too thin to call** (n of 5 to
  19 injured player-dates per horizon, in-season n of 1 to 2; confidence intervals include "no further loss" and "a 25% loss").
- So: a flag-gated, no-special-case fix is shipped **OFF** (`DYNASTYGM_INJURY_HORIZON_V1`). It is not turned on because the data
  neither proves the old discount wrong nor the new one right. What would decide it is in "What would settle it".

## Where the discount comes from

1. `rankings.apply_injury_risk_fields` -> `risk_multiplier = min(non_injury_risk_multiplier, injury_multiplier_for_age)`.
2. `injury_multiplier_for_age` (dynasty): the severity table (`injury_status.DYNASTY_VALUE_MULTIPLIER`: major 0.68, moderate
   0.80, minor 0.95) is replaced for major and moderate by an age curve (major: 24y 0.80, 27y 0.70, 30y 0.52, 34y 0.45; moderate:
   24y 0.88, 28y 0.80, 32y 0.70). It does not look at how long the player will be out.
3. `non_injury_risk_multiplier` returns 0.72 for any non-Active roster status. Sleeper reports an IR'd player as `Inactive`, so
   the injury is counted a second time as a roster-presence risk, and `min()` picks the harsher of the two. For a 25-year-old
   IR the age curve says 0.767 and the status penalty says 0.72: he gets 0.72.
4. `compose_composite_score` multiplies market, age, production, scarcity and role (90% of the weight) by that one number.
5. Redraft: `league_value_settings.apply_valuation_lens` blends 40% of that dynasty base with 60% of a current-season score built
   with `current_availability_multiplier` (major 0.42, status penalty 0.72). The redraft IR discount is therefore far larger by
   design (about 0.54 of composite for IR (0.4 x 0.72 + 0.6 x 0.42) vs 0.72 in dynasty), which is right for a player who misses the season.
6. `trade_grade.injury_availability_cost` (games missed, used in the trade analyzer) is a separate, already horizon-aware path;
   it was read for this audit and not touched.

Counterfactuals on the same frame (dynasty rank of the IR players, market rank in brackets): removing only the double count
(status 0.72 stacked on the injury) moves Nacua 72 to 67 and Love 114 to 101: a small effect. Removing the injury multiplier
entirely moves Nacua 72 to 10 (7), Love 114 to 78 (15), Achane 130 to 97 (30), L. Jackson 169 to 106 (63), Adams 255 to 116 (93).
So the injury multiplier is the whole story in dynasty; the redraft ranks barely move (Nacua 166 to 164) because the current-season
lens carries its own, separate discount.

## Backtest: did injured players' market value recover?

Data: nflverse injury reports and weekly stats 2020-2025 plus the DynastyProcess snapshots on 04-15, 05-20, 08-20, 10-20 and 12-01
of 2021 to 2025. nflverse has no IR flag (IR players drop off the weekly report), so "injured at date D" is a proxy: the
player played earlier that season, was absent for all of the last four completed weeks, and had an Out/Doubtful/Questionable
listing in the season. Value = DynastyProcess `value_1qb` at D at or above 1,500 (the threshold asked for; 800 and 3,000 also run).
Control = same-position players on the same date, not in the injured set, within 15% of the injured player's value and 2.5 years
of his age (up to 15 each). "Relative" = injured value ratio over control value ratio at the snapshot nearest the horizon, so a
market-wide drift cancels. A relative value of 1.00 means the injured player kept pace with healthy peers; below 1.00, he fell
further after the market had already priced the injury.

Sample (value >= 1,500): 80 injured player-dates, 30 players (11 in-season dates, 69 offseason). Median age 25.3, median DP value
3,419. The snapshot grid is sparse (the gaps between snapshots are 5, 6, 9, 14, 19, 24 and 25 weeks), so +4, +8 and +26 weeks are
matched to the nearest snapshot within 3, 3 and 4 weeks.

| horizon | n | injured ratio (median) | control ratio | relative, median | relative, mean [95% CI] | share relative > 1 |
|---|---|---|---|---|---|---|
| +4w | 7 | 0.932 | 0.972 | 0.959 | 0.963 [0.923, 1.007] | 29% |
| +8w | 10 | 0.933 | 0.931 | 0.988 | 1.007 [0.954, 1.062] | 50% |
| +26w | 15 | 0.858 | 0.917 | 0.955 | 0.891 [0.741, 1.023] | 40% |

Other cuts: value >= 800 (110 player-dates, 40 players): +4w 0.951 (n 8), +8w 0.959 (n 13), +26w 0.955 (n 19, mean CI 0.71 to
1.42). Value >= 3,000 (48 player-dates, 20 players): +4w 0.959 (n 5), +8w 0.988 (n 8), +26w 0.934 (n 10, mean CI 0.76 to 1.02).
At +26w for players aged 26 or under (the Nacua case) the relative median is 0.93 to 1.00 depending on the threshold.

Reading: injured players do **not** snap back relative to healthy peers (no recovery premium), and they also do not keep falling
by much: after the market has priced the injury the further relative change is a median of -1% to -7% across horizons. Our
discount is applied **on top of** a market value that already includes the injury, and it is 20% to 28% for the IR players above.
On these point estimates our extra discount is several times the realized extra loss. Honest limits: n is 5 to 19 per cell, the IR
proxy misses short IR stints and includes benchings that look like injuries, the controls are noisy, and the confidence intervals
span "no further loss" to a loss of about a quarter at +26 weeks. In-season dates (when the market is slowest to price a new
injury) have n of 1 to 2 and cannot be read at all. This is still too thin to flip a valuation default.

## The fix (shipped OFF) and what it does

`DYNASTYGM_INJURY_HORIZON_V1`, default off, registered in `FLAG_REGISTRY` with owner and review date. With it on:
- dynasty injury multiplier = (1 - expected games lost / 51) x age durability, where 51 is a three-season horizon (3 x 17 games),
  expected games lost comes from the one injury table (`injury_status.weeks_out`: IR 4, Out 2, Doubtful 0.98, Questionable 0.3),
  and durability is the existing age curve relative to its youngest anchor (so age-based decline is kept, not duplicated);
- the status that IS the injury no longer adds the 0.72 roster-presence penalty (a non-injury non-Active status keeps it).
No per-player or per-position special case. Redraft's `current_availability_multiplier` is untouched (asserted in tests).
IR's table default of 4 weeks is the league minimum stay, so a season-ending injury is under-charged by this table; if the flag
is ever turned on, the IR row should carry an evidence-based expected return (the Hub and trade analyzer already use richer
injury-note reads), which is why the flag stays off until more data is in.

Effect on the same frame (flag off to on, dynasty rank, market in brackets): Nacua 72 to 40 (7), Love 114 to 74 (15), Achane 130 to
104 (30), Dart 186 to 144 (88), Henderson 164 to 129 (86), Adams 255 to 247 (93, age 33 keeps most of the discount through the
age curve). Median dynasty rank gap to market for the injured group 79 to 54; healthy 0 to 0; redraft unchanged at 146. The rank
gap that remains (54) is production, role and opportunity components for players who are not playing, which this change does not touch.

Tests: `tests/test_injury_horizon.py` pins the legacy anchors with the flag off, golden values with it on, monotonic age ordering,
no-more-discount-than-legacy, count-once, and redraft unchanged.

## What would settle it

1. A longer, denser injured sample: snapshot values weekly through the season (the DP repo is dated, so start storing our own
   weekly `fantasycalc_value` per player now; the 6h refresh already carries it) and an IR flag from Sleeper's roster status
   instead of the absence proxy. One in-season year of weekly values gives dozens of in-season injured player-dates for the 4 and
   8 week horizons.
2. The IR return time: expected games missed by designation and injury type from the injury-note reads, so IR stops defaulting to
   its 4-week floor.
3. Then re-run `scripts/audits/injury_horizon_diff.py` and decide with the owners; flip the flag only if the realized relative
   change stays above the shipped discount.

## IR / Out / Doubtful players on fresh values (market >= 1,000), flag off vs on

injured n=32, healthy comparison n=141
median dynasty rank gap to market, injured: off +79, on +54
median dynasty rank gap to market, healthy: off -1, on +0
median redraft rank gap to market, injured: off +146, on +146
healthy players whose dynasty rank changed: 121 of 141 (rank shifts from the injured players moving, never from a changed multiplier)

| player | pos | age | injury | market rank | dynasty rank off | dynasty rank on | redraft off | redraft on |
|---|---|---|---|---|---|---|---|---|
| Puka Nacua | WR | 25 | IR | 7 | 72 | 40 | 166 | 164 |
| Jeremiyah Love | RB | 21 | IR | 15 | 114 | 74 | 192 | 192 |
| De'Von Achane | RB | 25 | IR | 30 | 130 | 104 | 214 | 213 |
| Drake Maye | QB | 24 | Out | 44 | 61 | 48 | 106 | 105 |
| Lamar Jackson | QB | 29 | IR | 63 | 169 | 149 | 221 | 220 |
| Josh Jacobs | RB | 28 | Out | 78 | 145 | 135 | 154 | 153 |
| Michael Wilson | WR | 26 | IR | 84 | 142 | 121 | 246 | 245 |
| TreVeyon Henderson | RB | 24 | IR | 86 | 164 | 129 | 243 | 243 |
| Jaxson Dart | QB | 23 | IR | 88 | 186 | 144 | 248 | 246 |
| Davante Adams | WR | 33 | IR | 93 | 255 | 247 | 254 | 253 |
| A.J. Brown | WR | 29 | Out | 97 | 101 | 90 | 118 | 118 |
| Marvin Harrison Jr. | WR | 24 | Out | 108 | 147 | 136 | 182 | 182 |
| Jordan Addison | WR | 24 | Out | 110 | 155 | 142 | 193 | 193 |
| RJ Harvey | RB | 25 | IR | 112 | 185 | 153 | 256 | 256 |
| Alec Pierce | WR | 26 | IR | 114 | 214 | 192 | 276 | 277 |
| Jalen Hurts | QB | 28 | IR | 115 | 160 | 139 | 236 | 236 |
| De'Zhaun Stribling | WR | 23 | IR | 119 | 237 | 193 | 280 | 279 |
| Jonathon Brooks | RB | 23 | IR | 127 | 229 | 187 | 275 | 273 |
| Terrance Ferguson | TE | 23 | IR | 131 | 246 | 210 | 301 | 300 |
| Woody Marks | RB | 25 | Out | 132 | 158 | 151 | 203 | 203 |
| Jacory Croskey-Merritt | RB | 25 | IR | 136 | 196 | 168 | 272 | 272 |
| Jayden Higgins | WR | 23 | IR | 138 | 238 | 194 | 286 | 284 |
| Wan'Dale Robinson | WR | 25 | IR | 140 | 195 | 165 | 277 | 275 |
| Terry McLaurin | WR | 31 | IR | 143 | 263 | 250 | 259 | 259 |
| Romeo Doubs | WR | 26 | IR | 151 | 231 | 203 | 296 | 296 |
| Ricky Pearsall | WR | 26 | IR | 156 | 353 | 331 | 510 | 509 |
| Michael Pittman Jr. | WR | 29 | IR | 162 | 272 | 255 | 295 | 295 |
| Sam Darnold | QB | 29 | Out | 165 | 156 | 147 | 189 | 189 |
| Ty Simpson | QB | 23 | Out | 169 | 329 | 327 | 323 | 321 |
| Jayden Reed | WR | 26 | IR | 174 | 226 | 197 | 283 | 282 |
| Jaylin Noel | WR | 24 | IR | 182 | 270 | 245 | 335 | 333 |
| Jake Ferguson | TE | 27 | Out | 188 | 188 | 185 | 218 | 217 |

## Single count (owner decision 2026-11-19), shipped ON: `DYNASTYGM_INJURY_SINGLE_COUNT_V1`

The double count is a bug regardless of sample size: Sleeper reports an IR'd player's roster status as "Inactive", and that status
is the injury, yet it also cost the 0.72 roster-presence penalty on top of the injury table. One source now: the injury table
(severity bucket, age curve, current-season factor). The status penalty stays for non-injury statuses (e.g. retired), and the
no-team (0.35) and unranked (0.80) floors are untouched. It applies in three places that stacked or could stack:
dynasty `risk_multiplier`, the opportunity factor's `non_injury_risk_multiplier`, and redraft `current_availability_multiplier`.
In redraft the stack was a `min()` and the major-injury factor (0.42) was already below 0.72, so redraft ranks do not move; the
change there is that the status can no longer compete with the injury. The 51-game horizon (`DYNASTYGM_INJURY_HORIZON_V1`) stays OFF.

Ranks with only this fix (fresh values, same frame as above; market rank in brackets):

| Player | market | dynasty off to on | redraft off to on |
|---|---|---|---|
| Puka Nacua | 7 | 72 to 65 | 166 to 165 |
| Jeremiyah Love | 15 | 114 to 95 | 192 to 192 |
| De'Von Achane | 30 | 130 to 120 | 214 to 213 |

Median dynasty gap to market: IR/Out/Doubtful (n=32) +79 to +68; IR only (n=23) +99 to +73; healthy (n=141) -1 to -1. Redraft
medians unchanged (+146, +157 IR only). So the double count explains part of the dynasty gap, not all of it: the rest is the injury
curve itself (about 0.77 for a 25-year-old) and the production/role/opportunity components.

`trade_grade` (read only, not changed): `healthy_restore_factor` rebuilds the valuation's injury discount with the same
`rankings` functions and divides it back out before pricing an explicit availability cost, so the Analyzer's healthy value is
invariant to this change and `injury_availability_cost` does not stack the status penalty (it prices weeks missed only).

## Evidence-based return curves (owner-approved 2026-11-19)

Code: `modules/injury_return_curves.py` (runtime), `modules/injury_return_curves_table.py` (generated), harnesses
`scripts/audits/injury_return_panel.py` (panel), `injury_return_fit.py` (fit and test), `injury_return_backtest.py` (market backtest).
Flags: `DYNASTYGM_INJURY_RETURN_CURVES_V1` (redraft current availability, **ON**), `DYNASTYGM_INJURY_RETURN_CURVES_DYNASTY_V1` (fitted
games lost into the horizon model, **OFF**), and `DYNASTYGM_INJURY_HORIZON_V1` is now **ON** (all registered, owner coridian_).

Data and method. nflverse injury reports and weekly PPR stats, QB/RB/WR/TE, regular season. One row per player team-game in a listed
state: Out, Doubtful, Questionable, or IR (proxy: no stat line, not on the report, previous week Out/IR; nflverse has no IR flag).
Baseline = mean PPR of the previous (up to) 6 games with a stat line (>= 3 games and >= 4.0 points). Targets: share of baseline
produced over the next 4 team games (zeros for missed games), share of games played, and games missed in the next 17 (spans into
next season). "Excess" games lost subtract what a healthy same-position player misses (3.0 to 4.6 of 17; no stat line counts as a
miss, so this includes benchings). Fit on 2021-23 (n = 2,074 listed player-weeks with a baseline, 9,814 healthy comparison rows),
tested on 2024-25 (n = 1,273, 1,098 with a full 4-game window, 269 players). Shrinkage: empirical Bayes, 20 pseudo-observations per
level, state -> state x weeks -> position x state x weeks, and state -> position x state -> position x state x body group.
Limits: "played" means a stat line (a WR who dressed with no targets counts as absent), players with no listing and no stat line for a
whole season are invisible, the IR proxy includes non-injury absences, and 4 games is the horizon the redraft multiplier now means.

### Fitted curves (2021-23, shrunk)

By weeks since first listing, all positions (n = rows with a full 4-game window):

| state | weeks | n | plays next game | next-4 production | excess games lost /17 |
|---|---|---|---|---|---|
| Out | 1 | 278 | 0.00 | 0.32 | 2.8 |
| Out | 2 | 147 | 0.00 | 0.36 | 2.5 |
| Out | 3 | 78 | 0.00 | 0.40 | 2.6 |
| Out | 4 | 33 | 0.00 | 0.34 | 3.4 |
| Out | 5-6 | 26 | 0.01 | 0.39 | 4.3 |
| Out | 7+ | 19 | 0.01 | 0.28 | 6.0 |
| Doubtful | 1 | 54 | 0.03 | 0.47 | 1.5 |
| Doubtful | 2 | 31 | 0.02 | 0.35 | 2.5 |
| Doubtful | 3 to 6 | 24 | 0.03 to 0.05 | 0.39 to 0.42 | 1.9 to 2.6 |
| Questionable | 1 | 581 | 0.67 | 0.73 | 0.9 |
| Questionable | 2 | 202 | 0.70 | 0.76 | 0.6 |
| Questionable | 3 | 99 | 0.65 | 0.70 | 0.9 |
| Questionable | 4 | 61 | 0.71 | 0.79 | 0.6 |
| Questionable | 5-6 | 32 | 0.72 | 0.69 | 1.1 |
| Questionable | 7+ | 19 | 0.70 | 0.67 | 2.4 |
| IR (proxy) | 2 | 54 | 0.01 | 0.17 | 4.1 |
| IR (proxy) | 3 | 62 | 0.00 | 0.24 | 3.8 |
| IR (proxy) | 4 | 60 | 0.00 | 0.26 | 3.7 |
| IR (proxy) | 5-6 | 78 | 0.00 | 0.25 | 4.0 |
| IR (proxy) | 7+ | 67 | 0.00 | 0.18 | 4.5 |

By position (age pooled):

| pos | state | n | next-4 production | excess games lost /17 |
|---|---|---|---|---|
| QB | Out / IR / Q | 97 / 59 / 101 | 0.26 / 0.23 / 0.64 | 3.8 / 5.0 / 1.1 |
| RB | Out / IR / Q | 129 / 74 / 275 | 0.37 / 0.25 / 0.77 | 2.7 / 3.3 / 0.6 |
| WR | Out / IR / Q | 263 / 131 / 470 | 0.37 / 0.20 / 0.73 | 2.8 / 2.9 / 1.1 |
| TE | Out / IR / Q | 92 / 57 / 148 | 0.35 / 0.23 / 0.73 | 2.9 / 4.9 / 1.0 |

Doubtful (n 17 to 40 per position) is 0.37 to 0.47 with 0.5 to 3.3 excess games. Body-group cells (knee, ankle, hamstring,
concussion, ...) are in the generated table; the ones with n >= 30 are WR Out hamstring 0.42 (n 65), WR Out concussion 0.56 (n 32),
WR Out knee 0.32 (n 36), RB Out ankle 0.28 (n 37), WR Questionable knee 0.67 (n 70).

The pooled state curves the flag actually uses: Out 0.351, Doubtful 0.425, Questionable 0.730, IR 0.236 of baseline over the next four
games (the static table says 0.72, 0.72, 0.93, 0.42), and excess games lost of 3.0 (Out), 2.1 (Doubtful), 0.9 (Questionable), 3.9 (IR).
The evidence therefore confirms the old 4-week IR default for games lost (3.9) but not the short-term production factors.

### Out of sample, 2024-25

Next four games, points error (mean absolute error in PPR points over the 4 games; paired improvement vs the static current-season
multiplier, 95% CI from resampling players):

| predictor | mean predicted share | bias (pts) | MAE | RMSE | MAE improvement [95% CI] |
|---|---|---|---|---|---|
| static current-season multiplier (0.42 / 0.72 / 0.93) | 0.75 | +13.0 | 18.5 | 23.2 | reference |
| static weeks_out table | 0.60 | +6.8 | 14.9 | 20.2 | +3.6 [2.9, 4.4] |
| fitted, state only | 0.49 | +1.6 | 13.6 | 17.6 | +4.9 [4.0, 5.9] |
| fitted, position x state (the cell the API serves) | 0.49 | +1.4 | 13.4 | 17.5 | +5.1 [4.1, 6.1] |
| fitted, position x state x weeks since listing | 0.49 | +1.5 | 13.5 | 17.6 | +5.0 [4.0, 5.9] |

The actual share was 0.46 (Out 0.33, Doubtful 0.59, Questionable 0.69, IR 0.15). The static multiplier over-predicts by 29 points of
share; this is the short-term under-penalty from the #2205 side finding. Calibration of the fitted prediction in quintiles
(predicted / actual): 0.23 / 0.18, 0.36 / 0.34, 0.51 / 0.57, 0.74 / 0.68, 0.77 / 0.78. Next game only: MAE 2.4 vs 6.9 points
(+4.4 [4.1, 4.8]). Position, weeks-since-listing and body group did not beat the pooled state curve with a CI excluding zero (position
vs state only: +0.12 pts [-0.05, 0.31]; body group +0.14 [-0.05, 0.33]), so the flag path uses the pooled state curve and the finer
cells stay available through the API for callers that know them.

Games lost (excess, next 17, n = 588): actual mean 2.04, fitted 2.08 (bias +0.04), static table 1.56 (bias -0.48). The table is not
worse on dispersion though: MAE 2.97 vs 3.10 and RMSE 3.77 vs 3.83 (the fitted curve is worse by 0.14 [0.03, 0.24] MAE). Mean-unbiased
but not more precise, so it is not flipped on for dynasty.

### Dynasty backtest re-run (market value vs healthy peers)

Same DynastyProcess snapshots and control method as above, but "injured" is now observable at the snapshot: the player's state in the
last completed week (Out, Doubtful or IR proxy), value >= 1,500. n = 84 player-dates (25 players): 57 on 2024-25 dates (out of sample),
27 on 2021-23 dates. Relative value (injured over matched healthy peers) pooled median 1.00 overall and 1.02 out of sample: the market
does not take a further cut after it has priced the injury (+4w 1.01, +8w 1.02, +26w 1.06 out of sample). Each dynasty multiplier is
scored by its absolute distance to that realized relative value; improvement = legacy error minus model error:

| out of sample 2024-25 | n | legacy MAE | horizon (table weeks) MAE | horizon vs legacy [95% CI] | horizon with fitted games vs horizon with table |
|---|---|---|---|---|---|
| +4w | 13 | 0.179 | 0.109 | +0.070 [0.034, 0.092] | -0.010 [-0.018, -0.001] |
| +8w | 19 | 0.209 | 0.133 | +0.076 [0.048, 0.093] | -0.011 [-0.017, -0.004] |
| +26w | 25 | 0.368 | 0.316 | +0.052 [0.022, 0.083] | -0.007 [-0.015, 0.001] |
| pooled | 57 | 0.272 | 0.208 | +0.064 [0.042, 0.084] | -0.009 [-0.014, -0.003] |

In 2021-23 dates alone (n = 27) the horizon model is not distinguishable from legacy (about 0.00 [-0.04, 0.04] pooled); the in-season
subset is n = 7 out of sample. Mean multipliers: legacy 0.83, horizon 0.92. Caveat: because realized relative value is about 1.0, any
smaller discount scores better; the test says the legacy cut is larger than what the market later did, not that no discount is right.

### Decisions

- `DYNASTYGM_INJURY_RETURN_CURVES_V1` ON: the CI excludes zero on both next-game and next-4-game error.
- `DYNASTYGM_INJURY_HORIZON_V1` ON: out-of-sample positive with the table's weeks_out (CI excludes zero pooled and at every horizon).
- `DYNASTYGM_INJURY_RETURN_CURVES_DYNASTY_V1` OFF: feeding fitted games lost is mean-calibrated but slightly worse than the table on
  MAE, RMSE and the market backtest (CIs exclude zero in the wrong direction, by less than 0.01 of multiplier).
- Flags off is bit-identical legacy (`tests/test_injury_return_curves.py`, `tests/test_injury_horizon.py`). The existing tests that pin
  the legacy numbers now set the new flags to "0" explicitly; no assertion was changed or removed.

### Ranks (committed `data/players.db` frame, read only; dynasty / redraft rank; market rank in the header)

Market rank: Nacua 5, Love 7, Achane 13.

| flags | P. Nacua | J. Love | D. Achane |
|---|---|---|---|
| legacy (all off) | 48 / 156 | 75 / 166 | 98 / 187 |
| return curves only (redraft) | 48 / 224 | 75 / 235 | 98 / 246 |
| horizon only | 20 / 156 | 49 / 165 | 77 / 187 |
| horizon + curves (shipped defaults) | 20 / 224 | 49 / 235 | 77 / 244 |
| horizon + curves + dynasty feed | 19 / 224 | 48 / 235 | 76 / 244 |

(The earlier tables above used a fresh-values frame and the single-count flag in isolation; this frame differs, so ranks are not
comparable across the two.) Redraft falls hard for IR players because the evidence says an IR player yields about a quarter of his
baseline over the next four games, not 0.42. Median redraft gap to market for injured players: +147 to +250.
