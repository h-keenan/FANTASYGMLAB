# Sim single-game tail: the 62-point WR (2026-11, player-model-6)

Report (coridian_): a WR (Denzel Boston, CLE) scored 62.3 in one game (Week 5 recap, the WR group 110.7 that week), another week 28.2 for Olave:
"I thought you said you compared our simulation to actual seasons and it held up". The earlier checks (`2026-11-sim-tail-realism.md`, player-model-4)
bounded the *expected* points and compared season totals and typical weeks; they never held the extreme single game against real NFL history.
This audit does, and ships `player-model-6` (new games only; every older save replays identically).

Harnesses (committed): `python -m modules.sim.calibration.single_game_tail --model v5|v6 --copies 20`,
`python -m modules.sim.calibration.single_game_batch --model <id> --seeds 40`, plus the existing `backtest --model`, `realism_sweep seasons`.
Real data: `data/panel.json.gz` (2021-25 weekly box scores of the fantasy pool, PPR; 5 seasons, 8.8k WR games / 624 WR seasons with 8+ games). Nothing reads
`data/players.db`. A "player-season" is a row with 8+ games played, real and simulated alike.

## (a) Single-game distribution, real vs sim (player model alone, the same projection inputs, 20 simulated copies of the panel)

Percentiles of one game's PPR points; `n40/n50/n60` = games per 1000 player-seasons.

| pos | source | p90 | p99 | p99.9 | p99.99 | max | n40 | n50 | n60 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WR | real 2021-25 (624 seasons) | 19.7 | 33.2 | 45.7 | 55.4 | 55.6 | 41.7 | 6.4 | 0 |
| WR | player-model-5 (before) | 19.5 | 35.2 | 49.6 | 65.1 | **94.1** | 66.4 | 13.6 | **2.8** |
| WR | player-model-6 (after) | 19.5 | 35.2 | 47.1 | 53.0 | **56.2** | 63.0 | 6.1 | **0** |
| RB | real (388) | 20.7 | 33.8 | 48.0 | 55.2 | 55.4 | 49.0 | 7.7 | 0 |
| RB | v5 | 19.2 | 35.5 | 50.9 | 68.8 | 84.5 | 74.2 | 16.9 | 3.9 |
| RB | v6 | 19.2 | 35.5 | 47.3 | 52.4 | 54.9 | 69.8 | 5.5 | 0 |
| TE | real (340) | 14.0 | 26.5 | 40.1 | 44.5 | 45.6 | 14.7 | 0 | 0 |
| TE | v5 | 13.9 | 27.3 | 39.8 | 49.9 | 67.4 | 14.1 | 1.5 | 0.4 |
| TE | v6 | 13.9 | 27.3 | 38.9 | 45.1 | 48.8 | 10.6 | 0 | 0 |
| QB | real (141) | 27.6 | 38.0 | 44.3 | 50.5 | 51.9 | 99.3 | 7.1 | 0 |
| QB | v5 | 26.9 | 39.1 | 49.1 | 60.0 | 63.4 | 113.0 | 12.4 | 1.7 |
| QB | v6 | 26.9 | 39.0 | 47.2 | 53.0 | 54.4 | 106.7 | 7.6 | 0 |

Reading: through p99 (and the body: sd, p50, p90) v5 matched real. Beyond it v5 had a fat tail: 50+ games twice as frequent as real, 60+ games (real: none in 2,800 skill-position
seasons) at 3-4 per 1000 seasons, and absurd maxima (94, 84, 67). The real record in the panel is 55.6 (WR); the sim now tops out at 54-56 in every position.
Real counts at 50+ are 4 games (WR), so real n50 has a +/-50% sampling band; the sim n50 after (WR 6.1, RB 5.5) sits inside it. Residual: n40 is still about 1.5x real for WR/RB
(63 vs 42, 70 vs 49): that is the 40-50 band, produced by the season-level spread of weekly means, left alone on purpose (it is a 1-in-16 vs 1-in-24 player-season
question and moving it would cost the weekly variance fit; p99 and sd are exact).

## (b) How a 62 was produced (v5, 6 copies of the WR panel, every game 50+, 53 games)

Not one cause; three multiplicative stat-line stacks, each unbounded:

- **Not the weekly mean.** Median expected mean of the 50+ games was 18.6 (p10 14.6, p90 23.3): an elite WR's normal week. Only 1 of the 12 largest had a role promotion (a 3.5 ppg depth WR
  on a 2.2 x 2.3 promotion path, weekly mean 29.7); none was an injury-replacement or partial game (`game_fraction` 1.0). The weekly/team/matchup multipliers are fine.
- **Targets x yards-per-catch x touchdowns inside one line.** The 50+ games averaged 17.3 targets, 13.9 catches, 222 receiving yards, 3.5 touchdowns (the real top ten:
  11-15 catches, 175-266 yards, 2-3 TDs). The yards-per-catch is a gamma draw with no limit (448 and 377-yard games; the all-time record is 336) and the touchdown
  count is a Poisson whose rate is multiplied by targets/expected targets, an efficiency draw and a gamma "luck" mixture (cap 4x): up to **9 receiving TDs** (record 5) in the 94-point game
  (15 of 16 targets, 251 yards, 9 TDs). A 62 is exactly this: 20 targets, 17 catches, 388 yards or 4 TDs plus 240 yards.
- The distributions are fine in the body: the stacking only shows in the last 0.1%, which is why season totals, p90 and the variance ratios looked right.

## (c) The fix (player-model-6; `modules/sim/player_model.py`)

Two principled layers, both applied to the drawn stat line (no new random draws: the RNG stream is consumed identically, so v6 differs from v5 only in the games the bounds bite):

1. **Per-game component limits (`STAT_CAPS`, `cap_stats`).** Counts are hard limits at the NFL single-game records (WR/TE receiving TDs 5/4, RB rushing TDs 5, QB passing TDs 7, catches 21/20/18,
   targets 28/24/20, attempts); yardage saturates smoothly above a knee toward a cap just below the all-time record (WR rec 190 -> 320, RB rush 160 -> 290, QB pass 420 -> 540). Normal games are untouched
   (knees are above the 99.9th percentile of yardage).
2. **Smooth saturation of the points of one game (`TAIL_SQUEEZE`, `squeeze_tail`).** `p' = K + C tanh((p - K)/C)` above a position knee (WR/RB 33, C 24; TE 30, C 20; QB 36, C 22), never above K + C (57 WR/RB, 50 TE, 58 QB in PPR).
   The excess is taken out of the yardage (one scaling factor, scoring-agnostic), never out of catches or touchdowns. Calibrated so the real record (55.6) is about the sim's maximum and 60+ does not occur;
   the knee is above p99 so p50/p90/p99 and the standard deviation are unchanged to 0.1 point.

Not changed: weekly means, season levels, role/matchup mechanics, injuries, the weekly volatility. Rejected: truncating the game-factor normal (Z 2.6 -> 2.2 moves nothing: the stacking is in the count and yardage draws, not the Gaussian) and capping the TD mixture (4.0 -> 2.5: RB n50 -15%, no effect on WR); a per-case "no WR over 55" clamp (a spike at the cap).

## (e) Before / after, whole GM game

Whole games on the real-2025 pool (`single_game_batch`): 40 seeds x 3 difficulties (easy, normal, hard) = 120 seasons per model, weeks 1-14, games per 1000 player-seasons (8+ games).

| pos | model | p99 | p99.9 | p99.99 | max | n40 | n50 | n60 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WR | v5 | 33.0 | 45.5 | 56.0 | 66.1 | 33.5 | 4.2 | 0.77 |
| WR | v6 | 32.9 | 44.4 | 50.4 | 54.0 | 32.3 | 1.5 | 0 |
| RB | v5 | 34.7 | 48.9 | 62.5 | 77.9 | 56.3 | 10.2 | 2.1 |
| RB | v6 | 34.7 | 46.5 | 52.6 | 55.1 | 53.0 | 3.3 | 0 |
| TE | v5 | 26.2 | 37.5 | 50.3 | 59.2 | 8.0 | 1.4 | 0 |
| TE | v6 | 26.2 | 37.2 | 45.4 | 47.1 | 5.6 | 0 | 0 |
| QB | v5 | 38.1 | 46.3 | 54.1 | 60.7 | 70.9 | 4.4 | 0.87 |
| QB | v6 | 38.0 | 45.5 | 50.8 | 53.6 | 67.4 | 1.8 | 0 |
| team lineup score | v5 / v6 | mean 100.9 / 100.8 | sd 23.5 / 23.4 | p99 162.1 / 160.2 | max 194.1 / 193.2 | | | |

(Whole-game counts differ from the player layer because the pools differ: games are played on the 2025 pool with 14 regular weeks.) In v5 a 60+ WR game occurred about once per 1,300 WR-seasons across these
120 leagues (max 66 WR, 78 RB); v6: none, max 54-55.

## Season totals, standings and ADP intact (`realism_sweep seasons`, 4 seeds per shape, v5 / v6; `backtest --model v5|v6`, 8 copies)

| shape | team score / wk | team sd | win% sd | PF rank vs wins (rho) | best-worst wins |
| --- | --- | --- | --- | --- | --- |
| 12t PPR | 102.2 / 102.1 | 23.2 / 23.1 | 0.141 / 0.141 | 0.62 / 0.64 | 10.0-3.8 / 10.0-3.8 |
| 12t half | 102.5 / 102.3 | 24.3 / 24.0 | 0.155 / 0.155 | 0.58 / 0.58 | 10.5-3.2 / 10.5-3.2 |
| 12t std | 101.7 / 100.9 | 23.6 / 22.7 | 0.156 / 0.160 | 0.63 / 0.59 | 11.2-3.8 / 11.5-3.8 |
| 8t PPR | 110.2 / 110.1 | 25.4 / 25.3 | 0.198 / 0.199 | 0.79 / 0.78 | 11.2-2.5 / 11.2-2.5 |
| 10t PPR | 106.2 / 106.1 | 24.4 / 24.3 | 0.148 / 0.148 | 0.72 / 0.72 | 9.8-3.0 / 9.8-3.0 |
| 14t PPR | 97.3 / 97.2 | 23.3 / 23.2 | 0.168 / 0.168 | 0.83 / 0.83 | 10.8-2.5 / 10.8-2.5 |
| 12t superflex | 115.0 / 114.9 | 25.4 / 25.4 | 0.169 / 0.169 | 0.74 / 0.74 | 11.5-2.2 / 11.5-2.2 |
| 12t DEF+K | 109.7 / 109.6 | 23.8 / 23.7 | 0.134 / 0.134 | 0.75 / 0.75 | 9.8-3.5 / 9.8-3.5 |
| 12t no K | 93.9 / 93.8 | 22.8 / 22.7 | 0.152 / 0.152 | 0.59 / 0.58 | 10.8-3.2 / 10.8-3.2 |
| 12t TE premium | 102.5 / 102.4 | 23.2 / 23.1 | 0.148 / 0.148 | 0.67 / 0.66 | 10.8-4.2 / 10.8-4.2 |

ADP vs finish Spearman (QB / RB / WR / TE) is identical to two decimals in every shape (0.50 / 0.82 / 0.87 / 0.84). The only visible shift is standard scoring (-0.8 points a team and sd -0.9 on 4 seeds; half and PPR shapes move 0.1-0.3, so this is most likely seed noise, but it is not proven). Backtest (season-level, 8 copies, all five seasons): PIT KS 0.1584 -> 0.1590, 80% coverage 73.2% -> 73.2%, mean PIT 0.547 -> 0.547, QB KS 0.178 -> 0.185 (a
few extreme QB seasons), others identical. Season totals, projections and the weekly variance ratios are untouched by construction.

## Versioning and tests

`player_model-player-model-6` is the new default. `player_model_v5.py` is a frozen byte-copy of player-model-5 (sha256 `7f7aac6d...cda8a1` and golden state digests for weeks 2-6 pinned in
`tests/test_sim_game_model_versions.py`, computed from origin/main's code before v6 existed); v1-v4 unchanged. `game_scoring._MODEL_MODULES` routes `player-model-5` to the frozen file. Tests:
`tests/test_sim_single_game_tail.py` (caps bound each component, squeeze is monotone/bounded/yards-only, v6 body equals v5, panel extremes, resume == replay), `test_sim_isolation.py` lists the new pure file.
The Fantasy Sim never touches real projections, valuations or `data/players.db`.

## The recap `PROJ -` bug (same PR)

Cause: server. `_lineup_rows` built each recap row with `_brief(...)` (id, name, pos, team only), but the clients rendered PROJ from `row.player.projection`, a field that brief does not have, so `simFmtPts(undefined)` = "-" for every row on web and app.
Fix at the source: each recap row now carries `proj`, the engine evaluator's projection for that player that week (`Evaluator.proj`, the number the lineup was set against; 0 for bye/out), and web + mobile read `simRecapProj(row)`
(`simRecapStory.ts` twins), still "-" for a recap saved before the field existed. `proj` is excluded from `GameState.digest()` (display-only), so no old save's digest changes. Tests: `tests/test_sim_single_game_tail.py::test_recap_rows_carry_...`,
`simRecapStory.test.ts` (web vitest, mobile node:test).

## Not done / follow-ups

- n40 for WR/RB is still about 1.5x real; the cause is the season-level spread of weekly means, left alone to keep variance and season calibration.
- Real data is 5 seasons: n60 = 0 and the max are the constraint, the real "mid-50s record once every few seasons" is encoded through K + C, not fitted beyond the panel.
- Recaps of already-played weeks in older saves have no stored `proj` (they show "-"); new weeks of every save, old or new, carry it.
