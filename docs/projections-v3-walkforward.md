# Projections v3: walk-forward evaluation (2026-10)

The concern: v2 (`docs/projections-v2-backtest.md`) was tuned on 2024 and scored on 2025, so a
good number could be a one-year fit. v3 replaces that single split with a walk-forward test and
re-checks every change against it. Sleeper's projections are never a model input; they are only a
benchmark.

## Method

- Data: Sleeper's public weekly stats and projections for 2021-2025 and 2026 weeks 1-6 (fetched
  into a throwaway cache, nothing committed). Headline numbers use weeks 4-17, point-in-time
  (a player's projection sees only his earlier games).
- Walk-forward: every season is scored with constants fitted **only on earlier seasons**:
  2022 (fit 2021), 2023 (2021-22), 2024 (2021-23), 2025 (2021-24), and 2026 weeks 4-6 as the
  frozen holdout (fit 2021-25). Fitted per fold: usage coefficients, shrinkage settings, error
  scale, interval multipliers. A season that disagrees with the others would show up as an outlier
  row below.
- Pools: **relevant players** (Sleeper's top N per position-week among players who played: QB 24,
  RB 48, WR 60, TE 24, K 16; selection does not use our model) and **all with a Sleeper
  projection**. Hit rate is the share of same-position, same-week pairs ordered correctly.
- Tooling: `scripts/projection_walkforward.py` (`fetch`, `evaluate`). The vectorised estimator
  equals `player_projections._player_usage_trend` to 1e-14 and reproduces the v2 doc's 2025
  numbers (5.76 vs 5.77 MAE).
- "v2" below is v2 exactly as shipped (tuned on 2024). It is genuinely out-of-sample only for
  2025 and 2026; for 2022-23 it was tuned on the future, and 2024 is its own training year.

## Per-season results

Relevant players, MAE (lower is better):

| Season | n | v2 | v3 | Season avg | Sleeper |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2022 | 2,408 | 5.722 | **5.700** | 5.852 | 5.647 |
| 2023 | 2,408 | 5.688 | **5.648** | 5.787 | 5.488 |
| 2024 | 2,408 | **5.643** | 5.668 | 5.762 | 5.511 |
| 2025 | 2,408 | 5.762 | **5.732** | 5.858 | 5.676 |
| 2026 wk 4-6 (holdout) | 516 | 6.005 | **5.922** | 6.361 | 5.675 |
| Mean | | 5.764 | 5.734 | 5.924 | 5.599 |
| Spread (sd) | | 0.142 | 0.110 | 0.248 | 0.092 |

Relevant players, start/sit hit rate:

| Season | v2 | v3 | Season avg | Sleeper |
| --- | ---: | ---: | ---: | ---: |
| 2022 | 62.6% | 62.7% | 61.7% | 65.0% |
| 2023 | 62.6% | 62.5% | 62.5% | 64.6% |
| 2024 | 63.7% | 63.4% | 63.4% | 64.8% |
| 2025 | 62.7% | 62.9% | 62.5% | 64.9% |
| 2026 wk 4-6 | 61.9% | 62.1% | 60.7% | 63.6% |

All players with a Sleeper projection (n about 4,900 per season, 1,102 in 2026): MAE

| Season | v2 | v3 | Season avg | Sleeper |
| --- | ---: | ---: | ---: | ---: |
| 2022 | 4.241 | **4.224** | 4.318 | 4.145 |
| 2023 | 4.189 | **4.173** | 4.268 | 4.044 |
| 2024 | **4.219** | 4.238 | 4.309 | 4.115 |
| 2025 | 4.202 | **4.181** | 4.279 | 4.126 |
| 2026 wk 4-6 | 4.239 | **4.194** | 4.416 | 4.029 |

Hit rate on that pool: v3 73.8%, 74.5%, 75.4%, 74.5%, 75.5% (v2 within 0.1 point; season average
about 0.7 lower; Sleeper 75.3-76.7%).

How sure is v3 over v2? Paired mean difference in absolute error, relevant players (v3 minus v2,
standard error): 2022 -0.022 (0.016), 2023 -0.039 (0.016), 2024 +0.025 (0.015), 2025 -0.030
(0.013), 2026 -0.084 (0.031). v3 is better in 4 of 5 seasons by 0.02-0.08; the one loss is the
season v2 was tuned on. These are small gains; the large, repeatable result is that **both beat
the season average by about 0.1-0.15 MAE every single season, and trail Sleeper by about
0.1-0.2**. v2's edge over the season average was not a 2025 fluke.

## Calibration (68% intervals)

Coverage on all eligible player-weeks (n about 5,500 per season; 1,700 in 2026), v3:

| Season | Overall | QB | RB | WR | TE | K |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2022 | 67.8% | 70.2% | 67.8% | 66.9% | 67.6% | 70.7% |
| 2023 | 69.9% | 67.5% | 71.1% | 70.5% | 69.0% | 69.3% |
| 2024 | 68.7% | 63.3% | 69.7% | 69.8% | 68.6% | 67.3% |
| 2025 | 67.6% | 60.7% | 69.9% | 68.7% | 65.9% | 69.1% |
| 2026 wk 4-6 | 65.4% | 63.8% | 67.2% | 65.2% | 65.1% | 64.0% |

Overall coverage is within 65-70% in every season (v2: 65-70% as well). The 2026 holdout is 3 points
low, on 3 weeks of data. Per position, the old per-confidence-bucket multipliers were off by up
to 11 points (QB 56.6% in 2025, K 60%); fitting the 16th/84th percentile multipliers per position
roughly halved the mean per-position miss in every fold. QB is still the weakest (61-70%).
On the "relevant players" pool coverage is only 58-63% because Sleeper's top-N picks are the
players with the biggest outcomes, which any shrinkage model under-rates; that is a
selection effect, not a calibration bug, and the same as in v2.

## Knobs

v2 had about 80 fitted numbers: per-position usage coefficients (13), usage half-lives (5),
efficiency half-lives (RB only), shrinkage k (5), error-scale knots (50), interval multipliers
(6). v3:

| Knob | v2 | v3 | Why |
| --- | --- | --- | --- |
| Usage half-life | QB 2, RB 3, WR 6, TE 4 | 6 for QB/RB/WR/TE | Per-position tuned values jumped between folds (TE: infinity vs 10; QB 2-4); the pooled optimum was stable at 6 |
| Efficiency half-life | RB 3, others none | 6 for QB/RB/WR/TE | same |
| Shrinkage k | QB 4, RB 6, WR 3, TE 3, K 32 | 8 for QB/RB/WR/TE, K 48 | pooled optimum 6-8 in every fold, K 16-48 |
| Usage coefficients | fit on 2024 | refit on 2021-25, same form | coefficients barely move between folds (WR targets 1.70-1.73) |
| Error-scale knots | 5 per position, 2024 | 5 per position, 2021-25 | descriptive only (interval width) |
| Interval multipliers | per confidence bucket (6) | per position (10) | per-position coverage; see above |

Pooling is not a free win in accuracy (per-position tuning is within 0.01 MAE in 4 of 5 folds)
but it cuts the shrinkage knobs from 10 to 4 and, importantly, is stable across folds, which is the
sign it is not fitting one year's noise. The hill is flat: re-tuning in the new script lands on
usage half-life 4-6, efficiency half-life 4-10, k 6-8, all within 0.03 MAE of each other.

## Layers re-checked

Each candidate was fitted on training seasons only (its one parameter per fold), stacked on the
walk-forward base, and scored on the next season. Rule: ship only if it improves MAE by at least
0.01 on **both** pools in at least 3 of 5 seasons (the "majority of seasons" rule, with a floor
because the paired standard error is about 0.01-0.015). MAE change versus base, relevant players /
all players, seasons 2022-2026:

| Layer | Relevant-player MAE change | All-player MAE change | Hit rate | Decision |
| --- | --- | --- | --- | --- |
| Opponent strength (pooled exponent 0.25 on shrunk points-allowed) | -0.013, -0.011, -0.000, -0.006, +0.008 | -0.007, -0.005, -0.002, -0.004, +0.002 | mixed (-0.15 to +0.12 pts) | Rejected: 2 of 5 reach 0.01, the 2026 holdout gets worse |
| Opponent strength, per-position exponent | -0.001, -0.005, -0.003, +0.003, +0.024 | about 0 | flat | Rejected |
| Returning-player ramp (missed 2+ weeks) | +0.011, -0.017, +0.009, -0.007, +0.052 | -0.006, -0.016, +0.002, -0.011, +0.028 | mixed | Rejected (the fitted factor sat at the grid edge, 0.7: it is a down-weight, not a ramp-up) |
| Small-sample adjustment (1 game), weeks 4-17 | +0.012, 0.000, +0.012, +0.009, +0.029 | -0.001, -0.005, +0.003, +0.004, +0.010 | flat | Rejected |
| Small-sample adjustment, weeks 2-17 | -0.014, +0.025, +0.008, -0.004, -0.050 | -0.022, +0.007, -0.006, -0.001, -0.046 | flat | Rejected: sign flips between seasons |
| Rookie prior from draft capital (nflverse `draft_picks`, matched by name+year, about 80% of rookies matched; blend toward the position x round-bucket mean of earlier rookies) | 0 (weeks 4-17: tuned weight is 0 in every fold); -0.005, -0.009, 0, 0, 0 (weeks 2-17) | 0 to -0.003 | flat | Rejected: after 1+ games the player's own usage already beats the draft-slot prior |

Not re-opened: team-QB-quality multiplier (worse in both v2 seasons), affine bias correction
(helped top-N, hurt all-played in v2).

## What changed vs v2

- Constants refit on 2021-2025 instead of 2024 only; the usage-based estimator and its form are
  unchanged. Model version `v3-usage-eb-2026-10`.
- Shrinkage settings pooled across QB/RB/WR/TE (see Knobs).
- Interval multipliers per position instead of per confidence bucket. One consequence: a one-game
  player's interval is no longer widened (data: 1-game players were already covered about 70% at
  the position-level width). The "low confidence" label still marks them. One unit test that
  asserted the wider band now asserts the label and ordered interval instead.
- Not changed: availability multipliers, opponent and team-QB signals (still reported in
  `basis`, not applied), the "Cooling" flag, anything outside `player_projections`.

## What we found that we did not fix

- Every method, including the plain season average, under-projects recent seasons: bias on all
  eligible player-weeks is about -0.2 to -0.5 points in 2024-2026 versus about 0 in 2022-23.
  v3's bias is more negative than v2's (-0.23 vs -0.11 mean) because its training window now
  includes the low-scoring early years. MAE still improves, so it was not corrected; a
  recency-weighted level adjustment is the obvious next experiment, and the live scoreboard will
  show whether the drift continues.
- Weeks 1-3 are not scored in the headline (too few games). The scoreboard includes week 2 onward.

## The ceiling

Weekly fantasy scoring is mostly noise: touchdowns, game script and injuries dominate and
nobody sees them in advance. Sleeper's own projections, which use injury news, depth charts and
full information on game context, beat the season average by only about 5% MAE and reach 63-65%
start/sit accuracy on the relevant-player pool. The realistic target for a usage-based model is
therefore MAE around 5.5-5.7 on relevant players and 62-65% start/sit, and no
evidence that a 20% improvement is available. v3 is at 5.73 and 62.7% on
average, about 0.13 MAE behind Sleeper and 2 hit-rate points behind. Anything that claims much
more should be treated as overfit until it survives a walk-forward test like this one.

## Live scoreboard

`scripts/projection_scoreboard.py` replays the shipped model point-in-time against the current
season and writes `docs/projection-scoreboard.md` (MAE, bias, start/sit, 68% coverage, by position
and week, against season average and Sleeper). `.github/workflows/projection-scoreboard.yml`
runs it Tuesdays 12:00 UTC (after Monday Night Football) and commits the doc to main only when it
changes, using the same commit/push helper as `players-db-refresh.yml`. No database, no secrets
beyond the built-in `GITHUB_TOKEN`.

## Reproducing

```
python scripts/projection_walkforward.py fetch --cache /tmp/pwf
python scripts/projection_walkforward.py evaluate --cache /tmp/pwf
```

The layer experiments and the per-position coverage study used a scratch harness built on the
same panel code (not committed); the table above is the record.

## v3.1 interval recalibration (2026-10)

The single per-position 16th/84th multipliers under-covered the players people start (high
estimates): 68% coverage on the relevant-players pool was 61.2% overall (QB 67, RB 61, WR 60, TE 53)
over the 2022-26 walk-forward. Errors grow faster with the estimate than the 5-knot scale captures,
so the multipliers are now interpolated over the estimate (`_V2_INTERVAL_Z_KNOTS`, fit on estimate
quintiles per position). Coverage with the new knots on the same panel: relevant pool 67.3%
(QB 69, RB 67, WR 68, TE 66), all eligible 69.0% (was 68.4%), 2026 relevant pool 58.0% -> 65.4%.
The knots are fit on all five seasons (not held out), so expect a point or two less out of sample.
