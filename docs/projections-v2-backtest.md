# Projections v2: backtest and decisions (2026-10)

> Superseded for constants and evaluation method by
> `docs/projections-v3-walkforward.md` (walk-forward, 2021-2026). The layer
> decisions below still hold.

`modules/player_projections.project_player_week` was rebuilt as a usage-based
empirical-Bayes estimator. Sleeper's projections are never an input; they are
only the benchmark.

## Method

- Data: Sleeper weekly stats for 2024 and 2025, weeks 4-17, run through the
  real `project_player_week` point-in-time (weekly rows before the target week
  only; 0 leak mismatches on 2,027 reruns that were handed the full season).
- Train = 2024 (every constant tuned or fit there). Test = 2025, untouched.
- Pools: (a) "pool": Sleeper's top N per position-week (QB 24, RB 48, WR 60,
  TE 24, K 16) among players who played; selection does not use our model.
  (b) "all": every played player-week with a Sleeper projection.
- Baselines: v1 (= the code after #1355, zero-point weeks fixed), season-to-date
  average, Sleeper.

## Result (2025 held-out)

| Pool | Model | n | MAE | Bias | Spearman | Start/sit pairwise |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Sleeper top-N | v1 | 2,407 | 6.30 | +0.11 | 0.245 | 60.9% |
| | **v2** | 2,407 | **5.77** | -0.24 | 0.276 | 62.7% |
| | season average | 2,407 | 5.86 | -0.28 | 0.273 | 62.4% |
| | Sleeper | 2,407 | 5.68 | +0.70 | 0.317 | 64.8% |
| All played | v1 | 5,002 | 4.51 | -0.06 | 0.458 | 73.5% |
| | **v2** | 5,002 | **4.20** | -0.17 | 0.473 | 74.7% |
| | season average | 5,002 | 4.28 | -0.26 | 0.465 | 73.9% |
| | Sleeper | 5,002 | 4.13 | +0.31 | 0.503 | 76.0% |

2024 (train): top-N MAE v1 6.14, v2 5.64, season average 5.76, Sleeper 5.51.

v2 beats v1 and the season average out of sample and still trails Sleeper
(about 0.09 MAE on the top-N pool, 2 points of start/sit hit rate).

## Layers

| Layer | Decision | Evidence |
| --- | --- | --- |
| Usage baseline (volume-implied points + regressed efficiency, per-position half-lives and k) | Shipped | MAE -0.53 vs v1 on 2025 top-N, tuned on 2024 only |
| Honest range (binned error scale x 16/84 percentile multipliers by sample-size bucket) | Shipped | Overall coverage 69% (target 68%); "high" 69.2%, "medium" 69.2%, "low" 72.5% (2025). Top-N pool coverage is only 61% (Sleeper's top-N picks include players our model under-rates) |
| Availability: Out/IR/PUP/NFI/Sus -> 0; Doubtful x0.15; Questionable x0.85 | Shipped, **not backtestable** | Sleeper keeps no point-in-time injury history, so only the certain zeros are defensible; the two partial multipliers are priors, flagged `calibrated: false` |
| Opponent-defense multiplier | Not applied | Higher MAE at every exponent for WR and TE; the small QB (2025 only) and RB (2024 only) gains did not hold in the other season |
| Team-QB-quality multiplier (WR/TE) | Not applied | Worse in both seasons |
| Returning-from-absence ramp-up | Not applied | After the #1355 zero-weeks fix the ratio actual/estimate for 2+ week returners is 1.00 (2024) and 1.02 (2025); no bias left to correct |
| Small-sample uplift (1 game) | Not applied | Fixes the 1-game bias but MAE does not improve |
| Affine bias correction | Not applied | Improves top-N MAE slightly, worsens the all-played MAE |
| Rookie / draft-capital prior | Not built | No draft-capital field exists in the Sleeper dump or elsewhere in the repo; nothing to validate against |

## The old v1 complaints, re-measured

Most of the audit's v1 findings came from the zero-point-weeks bug fixed in
#1355: on the same pool the bias of players with 2 or fewer games is -0.4
(not +3.5) and of 2+ week returners +0.1 (not +4.4). v2 keeps those near zero
and lowers MAE for both groups. Elite producers are still under-projected: any
shrinkage model regresses the best outcomes toward the mean.

## Reproducing

Scratch harness lives outside the repo (point-in-time feature table plus the
real function). Re-run it by feeding player dicts with injury fields cleared,
since today's injury status must not leak into 2024/2025 weeks.
