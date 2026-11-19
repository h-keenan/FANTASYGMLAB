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
