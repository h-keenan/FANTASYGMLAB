# Live projection calibration (2026-11-19)

coridian_: "we will also have to audit our live game projections and new projections as the game goes on against real results."
Scope: the live model shipped in #2228/#2230 (`modules/matchup_win_probability.py`; clock from `modules/live_scoreboard.py`,
see `2026-11-live-matchup-clock.md`). Step 1 is a historical backtest on public nflverse data; step 2 is the forward log and
weekly scorer that audit the model on real league matchups from now on. No tuning ships (step 3, below).

## Method

* Data: nflverse public play-by-play 2023-2025 (regular season) plus the same weekly files the projections backtest uses
  (`scripts/projections_audit_backtest.py`). About 130 MB downloaded to a scratch directory and deleted afterwards.
  `rankings.load_players` was never called and `data/players.db` was never opened.
* Pregame projection, point in time: the REAL `project_player_week` replay from `scripts/projections_audit_backtest.py`
  (`run_season`), which uses only data published before each week's kickoff (earlier weeks, prior season, Friday injury report,
  derived depth order = documented proxy because Sleeper depth charts have no history). Rows with status `ok`, QB/RB/WR/TE,
  players who played. 17,107 player-games (2023: 5.6k, 2024: 5.7k, 2025: 5.9k) x 11 checkpoints.
* Scoring: **PPR** (what the projection pipeline emits and nflverse reports; not league-specific). Cumulative points at each
  checkpoint are rebuilt from play-by-play (pass/rush/receiving yards, TDs, receptions, interceptions, lost fumbles, successful
  2-pt conversions). Player-games whose pbp total differs from nflverse's final by 0.5 or more (0.7-1.3%: return TDs, laterals)
  are dropped. The actual final is nflverse's weekly total.
* Clock: checkpoints every 5 game-minutes by real clock (`game_seconds_remaining` 3300 ... 300; plays with remaining strictly
  greater than the checkpoint count as played), `remaining = seconds / 3600`. Games that go to OT get one extra OT checkpoint at
  `remaining = 0.03` (`live_scoreboard.OVERTIME_FRACTION_REMAINING`); OT points are in the actual final. 5-min checkpoints are
  grouped into elapsed buckets 0-25 (8%, 17%), 25-50 (25%-42%), 50-75 (50%-67%), 75-100 (75%-92%).
* Live model: the real `matchup_win_probability._projected_final_raw` (pace blend, cap 0.25, ramp to 0.5 elapsed) fed the
  backtest's point estimate (what the app shows as `projected_final`) and, separately, the mean estimate (what the win
  probability sums). Baselines: pregame projection only; naive = points so far + pregame x remaining (no pace blend).
* Win probability: 16,200 synthetic head-to-head matchups (300 per season-week), each side 9 starters (1 QB, 2 RB, 3 WR, 1 TE,
  2 FLEX) drawn without replacement from that week's top-N pool by pregame estimate (QB 24 / RB 48 / WR 60 / TE 24). Per-starter
  (mean, variance) come from the real `_starter_distribution`; team sums and the normal-difference CDF with
  `WIN_PROB_SPREAD_MULTIPLIER` = 1.70 reproduce `compute_live_win_probability` to 1e-3 (asserted on 80 matchup-states).
  Both orientations of each matchup enter the reliability tables. Ties dropped.

## (a)/(b) Projected final vs actual final (MAE, mean bias = projected minus actual, fantasy points)

| elapsed | n | pregame MAE | naive MAE | **live MAE** | pregame bias | naive bias | live bias |
|---|---|---|---|---|---|---|---|
| 0-25% | 34,214 | 4.31 | 4.05 | **4.05** | -0.92 | -0.94 | -0.94 |
| 25-50% | 51,321 | 4.31 | 3.54 | **3.53** | -0.92 | -0.91 | -0.91 |
| 50-75% | 51,321 | 4.31 | 2.67 | **2.67** | -0.92 | -0.46 | -0.41 |
| 75-100% | 51,321 | 4.31 | 1.59 | **1.59** | -0.92 | -0.35 | -0.33 |
| OT checkpoint | 902 | 5.03 | 0.93 | **0.92** | -2.46 | -0.66 | -0.64 |

By position (all checkpoints, live): QB MAE 4.25 / bias -1.13, RB 2.74 / -0.51, WR 2.84 / -0.57, TE 2.25 / -0.59.
By position and bucket (live MAE; pregame in brackets): QB 5.71 (6.00), 5.11 (6.00), 4.07 (6.00), 2.63 (6.00); RB 4.01 (4.29),
3.43, 2.53, 1.45; WR 4.06 (4.32), 3.53, 2.64, 1.58; TE 3.19 (3.42), 2.80, 2.13, 1.23. Per season the picture is identical
(2023/2024/2025 live MAE in the 25-50% bucket: 3.50 / 3.62 / 3.48).

Mean-basis variant (what feeds the win probability): MAE 4.08 / 3.56 / 2.70 / 1.61 with bias -0.55 / -0.62 / -0.25 / -0.27.

Findings:

1. **The live model beats pregame-only everywhere**, by 0.26 / 0.78 / 1.64 / 2.72 MAE (SE below 0.02).
2. **The pace blend helps only a little.** Live vs naive paired MAE difference: -0.004 (SE 0.0006), -0.010 (0.0015),
   -0.004 (0.0019), +0.001 (0.0010) by bucket for the point basis; -0.004, -0.012, -0.009, -0.003 for the mean basis. It never
   hurts materially; the gain is 0.1-0.3% of MAE. Scanning `PACE_MAX_BLEND` in {0, 0.25, 0.5, 0.75, 1.0} (mean basis, train
   2023-24 / test 2025): test MAE 2.853 / **2.845** / 2.852 / 2.873 / 2.905, train 2.916 / **2.909** / 2.918 / 2.941 / 2.977.
   The shipped 0.25 is already the optimum in and out of sample; stronger pace reaction is worse.
3. **Bias is a level problem, not a pace problem.** The pregame point estimate is -0.92 below actual and the mean estimate -0.46
   even before kickoff; the live model inherits it and loses it as the game is played. Caveat: the sample is conditional on the
   player playing (the participation haircut in the pregame model is correct unconditionally but under-projects those who do play),
   so this is partly a selection effect. The remaining -0.3 late bias is overtime (not in `remaining`) and non-uniform scoring
   (late-game drives); QB bias is the largest (-1.1).

## (c) Win probability calibration (synthetic random lineups, multiplier 1.70)

Brier score (0.25 = coin flip), with the same matchups re-scored at other spread multipliers:

| game time | n | Brier @1.0 | @1.35 | **@1.70 (shipped)** | @2.0 | best multiplier |
|---|---|---|---|---|---|---|
| pregame | 16,199 | 0.2257 | 0.2269 | 0.2291 | 0.2309 | 1.0 |
| 25% elapsed | 16,199 | 0.1962 | 0.1978 | 0.2017 | 0.2052 | 1.05 |
| 50% | 16,199 | 0.1518 | 0.1537 | 0.1586 | 0.1636 | 1.05 |
| 75% | 16,199 | 0.1111 | 0.1125 | 0.1169 | 0.1219 | 1.05 |
| 92% | 16,199 | 0.0695 | 0.0699 | 0.0726 | 0.0760 | 1.1 |

Reliability at multiplier 1.70, cells are predicted / actual (n), bins of predicted probability of the side shown:

| bin | pregame | 25% | 50% | 75% | 92% |
|---|---|---|---|---|---|
| 0-10% | - | 0.08/0.01 (74) | 0.06/0.01 (1323) | 0.04/0.01 (4360) | 0.02/0.01 (8713) |
| 10-20% | 0.18/0.12 (16) | 0.16/0.06 (805) | 0.15/0.05 (2704) | 0.15/0.06 (3083) | 0.15/0.06 (2455) |
| 20-30% | 0.27/0.14 (615) | 0.26/0.14 (2725) | 0.25/0.14 (3615) | 0.25/0.14 (3021) | 0.25/0.14 (1847) |
| 30-40% | 0.36/0.28 (4485) | 0.35/0.27 (5356) | 0.35/0.26 (4090) | 0.35/0.26 (2952) | 0.35/0.29 (1676) |
| 40-50% | 0.45/0.42 (11055) | 0.45/0.42 (7239) | 0.45/0.42 (4467) | 0.45/0.41 (2783) | 0.45/0.42 (1508) |
| 50-60% | 0.55/0.57 (11111) | 0.55/0.57 (7239) | 0.55/0.58 (4467) | 0.55/0.58 (2783) | 0.55/0.58 (1508) |
| 60-70% | 0.64/0.72 (4485) | 0.65/0.73 (5356) | 0.65/0.74 (4090) | 0.65/0.74 (2952) | 0.65/0.71 (1676) |
| 70-80% | 0.73/0.86 (615) | 0.74/0.86 (2725) | 0.75/0.86 (3615) | 0.75/0.86 (3021) | 0.75/0.86 (1847) |
| 80-90% | 0.82/0.88 (16) | 0.84/0.94 (805) | 0.85/0.95 (2704) | 0.85/0.94 (3083) | 0.85/0.94 (2455) |
| 90-100% | - | 0.92/0.99 (74) | 0.94/0.99 (1323) | 0.96/0.99 (4360) | 0.98/0.99 (8713) |

Mean predicted win probability of the favourite vs the favourite's actual win rate: pregame 0.579 vs 0.627, 25% 0.630 vs 0.694,
50% 0.701 vs 0.776, 75% 0.772 vs 0.842, 92% 0.858 vs 0.903.

On random lineups the shipped 1.70 widening is **underconfident**: every bin beyond 60/40 wins 6-14 points more often than
stated, and the Brier-optimal multiplier is 1.0-1.1 in each season. This is not enough to retune, because the synthetic design
has almost no correlation between starters (random players from different games). Re-running with same-team stacks (QB + two WR +
TE of one team on each side, opposite-team QBs) moves the optimum to 1.15 (pregame) ... 1.35 (92%), Brier at 1.70 still slightly
worse than at the optimum but the gap shrinks to 0.001-0.003, and real league matchups add more correlation (shared games, game
script, shared opponent defence) plus lineup choices that the pool draw does not capture. The 1.70 was set against real league
matchups; the synthetic population cannot overrule it.

## Limitations

* Synthetic lineups are not real leagues (no correlation structure beyond the stack test, no waiver/lineup decisions, no league
  scoring, no DEF/K/IDP). Treat (c) as a stress test of the independent-sum variance, not a verdict on the multiplier.
* Conditional on playing: DNPs and mid-game exits are excluded, so the injury-exit path (`exited_game`) is not exercised and
  the under-projection bias is overstated relative to a full lineup.
* Pregame projections use a usage-derived depth order, not the real depth chart. PPR scoring only. QB/RB/WR/TE only.
* All games are placed on the same elapsed fraction at once; real matchups mix games at different clocks.
* The pbp rebuild ignores laterals and special-teams TDs (those player-games are dropped, 0.7-1.3%). Regulation checkpoints
  see only regulation points while the final includes OT (the model has the same blind spot until OT starts).
* The pace blend is evaluated on the point basis (displayed) and the mean basis (win probability); neither is evaluated on
  league-specific scoring.

## Step 3: tuning (not shipped)

No new flag. The pace blend cap is already optimal out of sample, and the spread-multiplier gap is not established on real
matchups. Decision rule once the forward log has about one season of data (or sooner on roughly 500 scored matchups): compare the
reliability table below against this audit; if real matchups show the same favourite under-confidence after correlation, tune the
multiplier on 2026 weeks 1-9 / test weeks 10+ behind a new `DYNASTYGM_*` flag owned by coridian_, default OFF until
out-of-sample Brier is better and not negative in any elapsed bucket. Do not relax the existing goldens.

## Step 2: forward log and weekly scoring

* Code: `modules/live_projection_log.py`; hook in `services/mobile_api_service.py` (`_build_matchup`, after the win probability
  is computed; skipped for external leagues). Kill switch `DYNASTYGM_LIVE_PROJECTION_LOG` (FLAG_REGISTRY, default on, owner
  Zach); the log is also inert until `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` are configured. Runs on a daemon thread and
  never raises into the request.
* Volume: starters only. One row per (league, season, week, matchup, player, clock bucket) where the clock bucket is the real
  game clock in 5-game-minute steps (0-11, 12 = OT, 99 = final), plus one matchup-level row (`player_id = ''`) per bucket with the
  win probability. Not per poll: the primary key makes duplicates impossible, writes use `ignore-duplicates`, and an
  in-process set skips keys already sent. Final rows (bucket 99) carry each starter's final score and are logged the first
  time the matchup is read with every game final; matchups nobody opens after the games end are not scored (the report lists
  how many were).
* Table: `docs/supabase_live_projection_snapshots.sql` (additive; RLS on, no policies, service-role only) for
  `live_projection_snapshots` and `live_projection_reports`. **coridian_ must run it once in the Supabase SQL editor.**
  Retention: rows older than 400 days (about one season) are pruned by the weekly job.
* Scoring: `scripts/run_live_projection_scoring.py`, scheduled by `.github/workflows/live-projection-scoring.yml` (Tuesday
  09:00 UTC, after Monday Night Football). It scores every season-week with snapshots in the last 9 days against the final rows
  (live vs naive vs pregame MAE/bias by elapsed bucket, win-probability Brier and a 10% reliability table), upserts one row per
  season-week into `live_projection_reports` (idempotent) and writes the report to the job summary. Needs the existing
  `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` secrets. GitHub schedules can run late; for an on-time run use this root
  crontab line on the box (same pattern as the roster-pct snapshot; no percent sign in the line):

```
0 9 * * 2 flock -n /var/lock/fgl-live-proj.lock sh -c 'C=$(docker ps -qf name=mobile-api | head -n1); [ -n "$C" ] && docker exec "$C" python scripts/run_live_projection_scoring.py || echo "no mobile-api container"' >> /var/log/fgl/live-projection-scoring.log 2>&1
```

## Reproducing

Scripts in `docs/audits/live-projection-calibration/code/` (they expect a scratch dir `calibration_scratch/` with the nflverse
files, see `scripts/projections_audit_backtest.py fetch` for file names plus `pbp/play_by_play_<year>.parquet`): `build_rows.py`
(real projection replay), `stage1.py` (pbp checkpoints), `stage2.py` (projection error), `pace_scan.py`, `stage3.py` /
`stage3_stack.py` / `stage3b.py` (win probability).
