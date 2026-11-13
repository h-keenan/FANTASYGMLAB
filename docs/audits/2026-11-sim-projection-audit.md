# Simulation projection audit (2026-11)

Scope: the Fantasy Sim player model (`modules/sim/player_model.py`, calibrated on the 2021-25 real panel), then a read-only
review of the real projection logic against the same real outcomes, then an injury audit. The sim and the real logic stay
decoupled: the real-logic findings below are suggestions for normal, separately tested PRs, nothing here changes
`modules/player_projections.py` or `modules/projection_calibration.py`.

## TLDR

- **Sim model (player-model-2).** Same-protocol refits (fit 2021-23, test 2024-25): QB season-variance ratio 1.44 -> 1.10, rookies
  0.67 -> 0.74, tier-hit MAE 0.077 -> 0.070. Shipped refit on all five seasons: overall variance ratio 0.78 -> 0.90, rookies
  0.56 -> 0.70, QB 1.76 -> 1.28, WR top-12 retention 39.6% -> 45.2% (real 52.1%). **Costs:** in-sample PIT KS 0.079 -> 0.107 and
  80% coverage 0.71 -> 0.69; rookie left tail and TE spread still thin. Determinism, isolation tests and about 72 us per player-week
  unchanged.
- **Backup coupling** exists now (`apply_depth_coupling`), calibrated to measured real backup uplift (RB 0.36, WR 0.20 of the
  starter's PPG for the first backup), validated on 2024-25. Not wired into the game engine.
- **Real projections.** Band coverage is honest overall (67.3% vs 68%) but biased in structured ways: under-24s and rookies
  under-projected (+0.9 PPG), week-1 projections for age 30+ and for returners from 5+ missed games over-projected (-1.9 / -1.0),
  low-estimate bands under-cover (59%), week-1 estimates are 20-35% noisier than Sleeper's preseason number at RB/WR but better centred.
  Eight specific suggested changes in 3.2.
- **Injuries.** Only about half of missed games are injuries (nflverse weekly reports; the panel alone cannot tell). Incidence is flat
  by position/age, season-to-season persistence is weak (r 0.07) and does not hold out of sample, so no persistence feature was added.
  The sim's "injury" bundle really is injuries plus benching/rest. Point-in-time injury history does not exist in the repo; capture
  proposal in 4.4.
- **Artifact.** `docs/audits/2026-11-season-ppg-range-table.csv`: empirical season-PPG outcome multipliers by position x tier / rookie /
  age. Not wired into anything.

## 1. Data and honest limits

- Panel: 1,794 QB/RB/WR/TE/K player-seasons 2021-25 with weekly box scores, Sleeper week-1 projection and ADP
  (`modules/sim/calibration/data/panel.json.gz`). The "preseason projection" in it is **Sleeper's**, not ours; our projections are weekly and
  usage-based, so the real-vs-sim comparison is done by replaying our shipped estimator on the panel (section 3).
- The optimiser is a stochastic evolution strategy; reruns land on similar but not identical constants (e.g. rookie spread parameters
  moved between runs), so small differences between structures should not be over-read. All held-out numbers use 20 simulated copies.
- No raw weekly cache is committed; the panel is what every number here is computed from. Injury reports come from public nflverse
  files fetched into a throwaway directory.

## 2. Sim model changes

See `docs/fantasy-sim-player-model.md` section 4.0 for the before/after tables, the parameter list and the limitations that remain.
Summary of method: a new `fit.py season2` stage (full simulator across worker processes, loss on group quantiles, breakout/bust rates,
SD of log(actual/projection) and ADP-rank finish rates), a before-baseline refit of the **old** structure with the same loss and budget so
the comparison is like for like, held-out scoring on 2024-25, then a refit on all five seasons for the shipped constants. New in the code:
`SeasonParams` (role collapse `pc*`, `collapse_*`, `pu_qb`, `qb_bust_mult`, `sig_rook`, `te_sig`), `InSeasonParams` (`role_star`, `role_qb`,
`absorb`), `RoleChange.end_week`, `apply_depth_coupling`, `backtest.simulate_weeks_coupled` / `depth_cover_report`, backtest
`--params-json` for before/after runs, and guard tests. `MODEL_VERSION` is now `player-model-2`.

### 2.1 Year-to-year drift (no change)

Median log(actual PPG / projection) for vets with 8+ PPG by season: -0.213, -0.132, -0.113, -0.026, -0.130 (SD 0.066 with n-1). Each
year's median has a sampling SE of 0.033-0.044, so the true shared-year SD is about 0.054; the shipped `ENV_SD` of 0.057 is correct.
Position x year deviations (RB 2024 +0.17, TE 2025 +0.21) are within 1-2 sampling errors (n 16-40 per cell). The held-out PIT shortfall is the
realised 2024 draw, not a mis-sized environment; refitting the level on those years would be fitting noise.

### 2.2 What did not work or is unresolved

Rookie left tail (5th percentile 0.31 vs 0.21 real), TE season spread out of sample, and PIT centre calibration after the left-tail change.
The ES hits bounds on `b_solid` (1.05), `pb_tier`, `pu_rook`, `ps_tier`, which says the archetype mixture is still the wrong shape for
depth players; the next step would be a latent per-player "role security" variable shared by season level, role changes and injuries instead of
more archetypes.

## 3. Real projections vs real outcomes (review, no code coupling)

What is being reviewed. The real logic is a **weekly, point-in-time usage empirical-Bayes estimator**
(`modules/player_projections.py`, v3.2, plus `modules/projection_calibration.py`: top-tier shrink, prior-season seeding).
It has no preseason season-long projection of its own; the preseason number in the panel (and the one the sim is anchored
on) is Sleeper's week-1 projection. So the comparison has two legs:

1. **Replay of the shipped estimator** on the committed panel (`scripts/sim_projection_audit.py`): for every
   player-season with a prior season in the panel (2022-2025 plus 2021 in-season only), re-run the shipped constants, top-tier
   shrink, prior-season seeding and 68% band point-in-time for every game the player played: 21,070 player-weeks, 4 positions.
   Caveats: PPR only (no league-scoring conversion), no availability adjustments, the panel pool is players with a preseason
   ADP or 6+ PPG projection (selection on preseason, not on outcome, but sleepers outside the pool are absent), scored on games
   played (same protocol as `docs/projections-v3-walkforward.md`).
2. **Season-level**: the week-1 estimate (needs a prior season; 898 of 1,607 player-seasons) against the actual season PPG,
   next to Sleeper's preseason number on the same players and next to what the (re-calibrated) sim says about season outcomes.

### 3.1 Headline

- Overall the shipped band is honest: 67.3% of games land inside the 68% band (v3 doc: 65-70%). Bias is **+0.52 PPR points**
  per played game (actual above estimate), by season 0.40 to 0.70, same sign as the v3 doc's "recent seasons under-project".
- The structure of the miss is not uniform. It is concentrated in four places: **young players and rookies
  (under-projected), week-1 projections for older players (over-projected), the top estimate tiers of TE/QB, and
  skewed low-estimate bands.**

### 3.2 Findings and suggested real-logic changes (each for a normal PR, each needs its own walk-forward test)

| # | Finding (panel replay, n) | Evidence | Suggested change for review |
| --- | --- | --- | --- |
| R1 | **Players under 24 are under-projected**, every position | bias +0.88 PPG (n 5,253): RB +1.05, TE +1.07, WR +0.76, QB +0.54; the band misses high 20.0% vs low 13.9% (age 30+: 15.8% / 16.4%) | An age term in the baseline (a growth uplift that fades by about 25, or a position x age intercept) fitted walk-forward. The usage estimator is age-blind. |
| R2 | **Rookies are under-projected all season**, worst at RB/TE | rookie bias +0.87 (n 2,789; RB +1.04, TE +1.20, WR +0.72); stays +0.8 to +1.0 at 1-3, 4-8 and 9+ games, so it is a level problem not a small-sample one; above-band 20.8% | A rookie intercept or a slower decay of rookie early-season games (they are improving through the year, the estimator averages the early weeks in at equal weight). |
| R3 | **Week-1 projections for older players are too high**, and for players coming off a missed-games year | week 1: age 30+ bias -1.86 PPG (n 132, band covers only 61.4%), prior year missed 5+ games -0.97 (n 129, covers 61.2%). Season level: WR 30+ median actual / week-1 estimate = 0.76 (n 52), prior missed 5+ = 0.80 vs 1.01 for 0-1 | Shrink the prior-season seed toward a position x age mean for 30+ and for returners from 5+ missed games (the seed is currently age-blind; the v3.2 offset was tuned only on MAE overall). |
| R4 | **Week-1 estimate is noisier than Sleeper's preseason number on the same players** | log(actual PPG / estimate) SD 0.69 vs 0.58 (n 757); RB 0.79 vs 0.60, WR 0.75 vs 0.64, TE 0.58 vs 0.58, QB 0.22 vs 0.18; QB is the exception on bias (est +0.03 vs Sleeper -0.18) | The week-1 seed is carrying more last-season noise than it should. Candidate: stronger shrinkage of the prior-season residual toward zero when only the seed exists (k larger for seeded-only players), tested on week 1-3 only. |
| R5 | **Low and mid estimates under-cover; high TE/QB bands are one-sided** | 68% band coverage: RB estimate < 5: 59.0% (23.1% below the band, the low edge is clipped at 0); estimate quintile 2 (2.5-5.7): 59.5%; TE 10-15: 67.3% but 23.0% above vs 9.7% below | Band shape: use a skewed (lognormal or gamma-like) band for low estimates instead of a symmetric knot-interpolated scale, and per-position low/high z knots that already exist should be refit with the low edge unclipped. Matters for start/sit low-end decisions. |
| R6 | **Top-tier TE and QB bias** | TE estimate 10-15: +1.58 (n 309), TE 5-10: +1.03 (n 1,782); QB 10-15: +0.92 | `TOP_SHRINK` was fit one-sided at the top; the TE/QB-mid bias suggests its anchor for TE (5.12) shrinks a tier that is already under-projected. Re-fit anchors with the young/rookie term (R1/R2) in, since those players populate this tier. |
| R7 | **No week-1 projection for rookies at all** | rookies are absent from the week-1 replay (no prior games); they are also the widest season outcomes (log SD 0.79, 10th-90th percentile 0.31x to 1.93x of Sleeper's number) | A draft-capital prior for **week 1 only**. v3 rejected it for weeks 2+ (own usage wins after a game) but never tested week 1. Draft round/pick is now obtainable keyed by Sleeper id (dynastyprocess `db_playerids.csv` carries `sleeper_id`, `draft_round`, `draft_pick`), which removes the 80% name-match limitation noted in v3. |
| R8 | **Season-to-season level drift in our own bias** | bias by season 2021 0.70, 2022 0.40, 2023 0.40, 2024 0.70, 2025 0.50; 2021 MAE 5.62 vs 4.4 elsewhere (only the in-season history exists that year) | Do not chase it with a level constant; the sim's shared environment shock (sd 0.057) is the correct model of it. If a correction is wanted, make it a recency-weighted league-level scale updated through the season (the v3 doc already proposes this). |

Things checked and **not** a problem: overall band coverage (67.3%), QB week-to-week MAE ordering, the age 24-29 groups
(bias +0.4 to +0.5, in line with the overall level), and prior-year injury history in-season (bias +0.4 to +0.6 whatever the
prior missed games; the injury effect lives in the week-1 seed, R3).

### 3.3 Real estimate vs the sim's season-outcome distribution

The sim (calibrated to Sleeper's preseason number, section 2) and the real week-1 estimate describe the same quantity:
season PPG over games played relative to a preseason anchor. Log ratio actual / anchor, 2021-25:

| group | real week-1 estimate: SD, median, 10th-90th | Sleeper preseason, same players: SD, median, 10th-90th | sim (all seasons, re-fit): SD |
| --- | --- | --- | --- |
| all | 0.69, 0.99, 0.38-1.48 (n 757) | 0.58, 0.90, 0.46-1.43 (n 737) | 0.53 (real 0.55) |
| QB | 0.22, 1.05, 0.79-1.32 | 0.18, 0.85, 0.66-1.03 | 0.23 |
| RB | 0.79, 0.91, 0.36-1.48 | 0.60, 0.95, 0.46-1.57 | 0.56 |
| WR | 0.75, 0.97, 0.32-1.46 | 0.64, 0.92, 0.37-1.41 | 0.55 |
| TE | 0.58, 1.04, 0.39-1.60 | 0.58, 0.91, 0.48-1.50 | 0.56 |

Reading: the shipped estimate is **better centred than Sleeper** (median 0.99 vs 0.90; QB 1.05 vs 0.85, Sleeper's QB number
runs 20% hot, which is why the sim carries a QB discount) but **more dispersed**, so a user-facing season-long range built on
it must be about 20-35% wider than one built on Sleeper's number at RB/WR (R4). Neither anchor supports a tight season band:
a depth RB's 5th-95th percentile outcome is 0.21x to 2.66x his preseason number.

## 4. Injury audit

### 4.1 What data exists

| Source | What it has | Usable for injuries? |
| --- | --- | --- |
| Panel (`panel.json.gz`) | per week: played flag + box score, 2021-25, bye weeks | Games missed only. **Cannot separate injury from benching, rest, suspension, cut or inactive-by-choice.** |
| `data/players.db`, `data/sleeper_players.json` | **current** `injury_status`, body part, notes, start date | Snapshot only. The status column is overwritten every 30 minutes by `injury-status-sync.yml`; no history is kept (commits touch only the db). |
| Sleeper weekly stats/projections cache (local scratch, 2021-26) | `gms_active`, stats, projections; player object carries today's injury fields | No point-in-time injury status (the `player` blob is as of fetch time). |
| nflverse `injuries_<season>.csv` (public, fetched for this audit into a throwaway dir) | weekly report status (Out / Doubtful / Questionable), practice status, primary injury, 2021-25 | **Yes, the only point-in-time source**, joined to the panel through Sleeper id -> gsis id (dynastyprocess `db_playerids.csv`; all 737 core player-seasons matched). Limits: only players on a weekly report appear; long IR stays and some designations drop off it; no onset game or body-part severity. |
| depth charts (`data/depth_chart_snapshots.json`) | snapshots | Not a history either (current). |

So: **real injury data exists only as nflverse weekly reports, outside the repo.** A missed game is classed injury-listed when
the player was Out or Doubtful on the report in any week of the missed run.

### 4.2 What the data says (737 core player-seasons: QB/RB/WR/TE with ADP <= 120 or 9+ PPG, 2021-25; `scripts/sim_injury_audit.py`)

- **Only about half of missed games are injuries.** 1,879 missed games in 630 runs; 48.1% of missed games (47.5% of runs) sit
  in runs with an Out/Doubtful report. The other runs are unexplained: half are a single game (50.5%), mean length 2.95. These are
  bench, rest, suspension, cut, trade or IR-off-report. Injury-listed runs: mean 3.0 games, pmf 1: 31%, 2: 22%, 3: 19%, 4: 10%,
  5: 5%, 6-8: 9%, 9+: 3.7%.
- **Incidence is flat by position and age**, which the data can resolve only coarsely: injury-listed runs per 100 games available
  2.4 QB, 2.4 RB, 2.6 WR, 2.7 TE; by age 2.6 (<24), 2.5 (24-26), 2.3 (27-29), 2.8 (30+). Games missed to injury per player-season
  1.0 (<24) -> 1.2 -> 1.3 -> 1.5 (30+); rookies 1.0.
- **Season-to-season persistence is weak and does not hold out of sample.** Correlation of this year's injury-listed games with last
  year's: 0.07 (all missed games: 0.03). Prior year 0: mean 1.05 injury games missed (n 274); 1-2: 1.29 (58); 3-5: 1.48 (48);
  6+: 1.61 (18). P(miss 3+) 17.5% / 20.7% / 27.1% / 22.2%. Fit years 2022-23 show a gradient (0.16, 0.19, 0.31, 0.33 for the four
  buckets); held-out 2024-25 do not (0.19, 0.23, 0.21, 0.11, with n of 9 in the top bucket). The most the data supports is a
  mild, noisy tilt for 3+ games missed last year.

### 4.3 Sim comparison and decisions

| Quantity | Real (all absences / injury-listed) | Sim (v2) |
| --- | --- | --- |
| Runs per 100 available games | 5.3 all runs / 2.4-2.8 injury-listed | 6.0 "injury" events |
| Mean games missed per core player-season (held-out 2024-25) | 2.37 all absences | 2.6 (labelled injury) |
| Duration pmf, 1 game | 40% all runs / 31% injury-listed | 38% |
| 9+ games | 5-6% all / 3.7% injury-listed | 9.8% (widened by design, real runs are truncated by season end) |
| Persistence across seasons | corr 0.07, not stable held-out | none (each season is independent; frailty gamma and the 2x `injury_prone` archetype act within a season only) |

Decisions:
1. **Persistence: no model change.** The effect is small, the held-out years contradict the fit years, and it is not separable from
   benching. An optional `prior_games_missed` hazard multiplier is easy to add once there is data that holds out (see 4.4).
2. **Hazard and durations: no change**, because they are calibrated to *all* absences, which the game shows as injuries. The honest
   reading of the data is that the sim's "injury" bundle is about half injuries and half benching/rest/suspension. If the game wants
   truthful reasons (a "healthy scratch / rest" label, 1-game, with its own rate near 2.5 per 100 games) the split is supported by
   this data and should be a follow-up with the game engine, since `calendar_weeks_out` and the injury UI read `unavailable_reason`.
3. **Starter-injury to backup-role coupling: built** (`apply_depth_coupling`), calibrated to the real backup uplift in 2021-23 and
   validated on 2024-25 (model doc section 4.0).

### 4.4 Insufficient-data statement and recommended capture

For severity, body-part effects, practice-status signals, onset-game partials and a clean injury-vs-bench split we do not have
point-in-time data in the repo, and the single source we used lives outside it. Recommended small, safe capture (needs a human
decision, not done here): extend `scripts/sync_injury_status.py` (already reading every player every 30 minutes) to append one
compact row per **change** of `(player_id, injury_status, injury_body_part, practice_participation)` with a timestamp to a
separate append-only table or file (Supabase table `player_injury_events`, about a few hundred rows per week in season), plus a
once-weekly Tuesday and Friday snapshot of the full active-skill-player status. Never touches `players.db`. After one season it gives
onset dates, return dates and body parts, which is what a duration/persistence model needs.

## 5. Range-calibration artifact

`docs/audits/2026-11-season-ppg-range-table.csv`: for each position x anchor tier, rookie/veteran and age bucket, the 5/10/25/50/75/90/95th
percentiles of (season PPG over games played) / (preseason anchor), from the panel; two anchors, Sleeper's week-1 projection (all
player-seasons) and the shipped estimator's own week-1 value (returning players). Cells under 25 player-seasons are dropped. It is useful
because the real logic only publishes **weekly** bands; a season-long or rest-of-season range has no calibrated source in the repo
(a depth RB's 5th-95th percentile outcome is 0.21x-2.66x of his number; QB starters are 0.59x-1.07x). Caveat: conditioned on playing 4+ games.
It is a reference for human review and is not read by any code.

## 6. Reproducing

```
python scripts/sim_projection_audit.py --json OUT.json --range-csv docs/audits/2026-11-season-ppg-range-table.csv
python scripts/sim_injury_audit.py --inj-dir DIR      # DIR holds nflverse injuries_<season>.csv and dynastyprocess db_playerids.csv as ids.csv
python -m modules.sim.calibration.fit season2 [--v1-structure] --train 2021 2022 2023 --gens 50 --copies 4 --workers 4
python -m modules.sim.calibration.backtest --copies 20 --seasons 2024 2025 --params-json P.json
```
