# Fantasy Sim player outcome model

`modules/sim/player_model.py` is the stats engine for the GM game: given a player's
preseason projection it draws a **season story** (breakout, solid, bust, slump,
injury-prone, injuries, role changes, hot and cold streaks, the bye) and then every
**weekly stat line** (attempts, yards, touchdowns, receptions) scored in the league's
own scoring. It is pure (stdlib + numpy), deterministic, and calibrated against five
real NFL seasons by `modules/sim/calibration/`.

## TLDR
- Two calls: `draw_season_profile(player, rng)` once per player per game, then
  `draw_week_points(player, profile, week, rng, scoring)` per week. Same seed, same
  season; weeks can be drawn in any order.
- Calibrated on **real data, 2021-2025**: 1,794 player-seasons (QB/RB/WR/TE/K with a
  preseason ADP or projection), real weekly box scores, real week-1 preseason
  projections and ADP, real bye weeks. Fit on 2021-23, scored on held-out 2024-25.
- Held-out 2024-25: season-PPG percentile KS distance **0.105** (mean PIT 0.555), 50/80/90% intervals cover **45/77/85%**, mean absolute error of breakout/bust tier hit rates **0.057** (0.026 in-sample), weekly points SD ratio sim/real **0.99-1.08** by position, boom/bust week rates within **0.03**, games missed 2.56 vs 2.37 per season; all five seasons in-sample: KS **0.050**, tier-hit MAE **0.026**.
- **player-model-2 (2026-11 audit)**: role-collapse tail, QB/star fixes and an opt-in depth-chart coupling; see 4.0 for the
  before/after. Tables 4.1-4.2 and the headline numbers above are the player-model-1 baseline.
- **player-model-3 (2026-11 team roles)**: same weekly draws, plus team-level role coupling in the engine (one fill-in per injured
  starter, other backups near baseline; see section 8). New games only; player-model-2 is frozen in `player_model_v2.py`.
- Honest weak spots are in "Limitations" below. The biggest: the real projection
  source runs hot or cold by season (median actual/projected PPG 0.80 in 2021, 0.97
  in 2024), so out-of-sample the model sits about 5 percentile points low (mean PIT 0.555) and is
  slightly over-confident; it also has players miss a bit more time than the held-out years (2.56 vs 2.37 games).

## 1. API (contract with the game engine)

```python
from modules.sim.player_model import (
    draw_season_profile, draw_week_points, profile_rng, week_rng,
    team_week_shock, draw_environment,
)

env = draw_environment(rng_for_the_game)                  # once per game, shared by all players
rng = profile_rng(game_seed, player_id)                   # SeedSequence stream, order independent
profile = draw_season_profile({**player, "season_environment": env}, rng)
result = draw_week_points(player, profile, week, week_rng(game_seed, player_id, week), scoring)
```

`player` (a `Mapping`): `player_id`, `pos` (QB/RB/WR/TE/K; DEF/DST works with a generic
points draw), `age`, `years_exp`, `is_rookie`, `team`, `projection_mean_ppg` (or
`projection_season_points`, divided by 17), `projection_sd` (optional, weekly; nudges the
player's volatility), `adp` / `value_rank` (optional), `bye_week` (optional; else a stable
team-keyed week 5-14), `team_shock` (optional standard-normal z the engine shares between
teammates for a game, see `team_week_shock`), `season_environment` (optional, default 1.0).

`SeasonProfile` (frozen, JSON round-trips with `to_dict`/`from_dict`, or just regenerate it
from the seed): `archetype` (`solid | breakout | bust | slump | injury_prone`), `tier`
(`elite | starter | flex | depth` by projection), `season_multiplier` and `season_mean_ppg`
(the hidden outcome), `volatility`, `bye_week`, `games_available_mask` (17 booleans; False =
bye or out injured) with `unavailable_reason`, `injury_events` (`week`, `weeks_out`,
`kind`), `role_changes` (`week`, promotion/demotion, multiplier), `form` (17 hot/cold
factors), `slump_window`, `style`.

`WeekResult`: `points` (league scoring), `stats` (Sleeper stat keys: `pass_att pass_cmp
pass_yd pass_td pass_int rush_att rush_yd rush_td rec_tgt rec rec_yd rec_td fum_lost`,
`fgm xpm` for kickers), `active`, `status` (`active | partial | bye | injured`),
`injury_incurred` (hurt in this game; he plays a partial game, `game_fraction`, and the
profile's `weeks_out` games after it), `components` (points by passing / rushing /
receiving / turnovers / kicking), `expected_points` (the hidden true mean, for recaps and
analysis; do not show it before the game, it leaks the season).

Hidden vs known: the preseason projection is public; `season_multiplier`, `archetype`,
`injury_events` and `role_changes` are the engine's secret. A good UI shows "Questionable"
only when the engine decides to reveal an event early; the model does not do news.

Speed: about 80 microseconds per player-week (pure Python + numpy scalars); a 12-team,
200-player pool is about 0.3 s per simulated week.

## 1a. Versions and replay safety

`modules/sim/player_model_v2.py` is the same kind of frozen copy of player-model-2 (sha256 pinned in
`tests/test_sim_game_model_versions.py`, golden digests for a v2 game too). `player_model.py` is now **player-model-3**.

`modules/sim/player_model_v1.py` is a **frozen byte-for-byte copy** of player-model-1 (sha256 pinned in
`tests/test_sim_game_model_versions.py`); never edit it. `modules/sim/player_model.py` is the current model (player-model-2).
`game_scoring.get_model(model_id)` routes by the id a game stored: `player_model-player-model-1` -> v1, `-2` -> v2 (frozen copy), `-3` -> the current module, the fallback id
-> `FallbackModel`; an unknown id falls back to the newest model and `resolve_model` returns a note saying so. New games use the
newest. A new generation = copy the then-current module to `player_model_vN.py`, register it in `_MODEL_MODULES`, add it to the
pure-engine list in `tests/test_sim_isolation.py`, and add a golden-digest replay test. Evaluate the old model with
`python -m modules.sim.calibration.backtest --model v1`.

## 1b. How the GM game uses it

`modules/sim/game_scoring.py` is the only door. The model is the **single source of truth for
injuries**: `injury_incurred` maps to `newly_injured`, and "out N weeks" is read from the profile's
availability mask (`calendar_weeks_out`, bye weeks inside the window counted, since the game counts
calendar weeks). The game's own random 1-5 week draw now runs only for the labelled `FallbackModel`
(replay safety for old saves). The game passes its own bye week into the model. Projections users see
come from the public preseason mean and games played; `expected_points`, `season_multiplier`,
archetype and event lists never reach a game module (a test scans for it). When a starting slot cannot
be filled (injury, bye, lone kicker) the AI makes an emergency waiver claim. `tests/test_sim_game_player_model.py`
plays a full game and checks scoring, injury coherence, resume == replay and no writes under `data/`.

## 1c. Team roles (player-model-3)

The player model draws each player independently, so by itself two backups of one injured starter both score starter-level points. The
engine now resolves roles per NFL team, position group and week with `modules/sim/team_roles.py` (pure, deterministic, from public injury and
bye state only) and passes the result to the model as a one-week mean multiplier (`with_role_multiplier`, no extra draws). Only models with
`TEAM_ROLES = True` (player-model-3+) receive it; older saves never see it. Rules, in short: depth order from `depth_chart_order` (an injured
top-market star keeps the top spot), starters = QB 1 / RB 2 / WR 3 / TE 1, each vacated starter slot is inherited by exactly one next-in-line
healthy player, the QB who plays gets `0.2 x own + 0.6 x starter mean` and every other healthy QB behind him is a bench QB at 0.2, RB/WR/TE
inheritors get `own + absorb x 0.8 x starter mean` (calibrated `InSeasonParams.absorb`), K and defenses are exempt. The Players/waiver/draft
"Proj" is the role-resolved mean for the next game he can play (rows carry `role` with a label and `if_starts`). Full write-up and the real-app
check: `docs/audits/2026-11-sim-team-role-coupling.md`. Limits: roles use public depth order (a stale chart is wrong), and the Bayesian blend
of a player's actual games into his rest-of-season mean mixes games played in different roles.

## 2. What is modelled

**Season story** (`season_level`, vectorised, one categorical draw per player):

| Archetype | Mean for the season | Notes |
| --- | --- | --- |
| solid | projection x ~lognormal | spread grows as tier falls (depth players are wild) |
| breakout | projection + a gamma PPG gain | gain is additive (a 4 PPG backup becomes 9, a star does not double); rookies and young players likelier |
| bust | projection x ~0.7 lognormal | older and rookie players likelier |
| slump | solid mean, plus a 3-6 week dip (-30%) somewhere in the season | stars slump; no rookies |
| injury_prone | solid mean, 2x injury hazard | |

Probabilities are logistic in rookie flag, age, and log tier (projection / positional
starter PPG). Positions differ: QB seasons are tight and run 10-20% below the preseason number,
TE gains are smaller, kickers are treated as WR-like.

**League environment**: one lognormal (sd 0.057) multiplier per game shared by everyone,
because real seasons run hot or cold for all players at once (see Limitations).

**Injuries** (`hazard` per available week, scaled by position, age and a per-player
frailty gamma, and 2x for injury-prone): the game they get hurt in is a partial game
(about 72% of a normal one, matching the real "last game before missing time" at 0.72 of a
player's mean), then 1-8 games out with the real empirical pmf (42% are one game, 5-10%
season-ending), then a 0.91x first game back (real: 0.91).

**Role changes**: Poisson count per season (more for depth players); depth players are
likelier to be promoted and by more, stars are likelier to be demoted and a promotion barely
moves them.

**Form**: AR(1) log-normal weekly factor (phi 0.35, sd 0.06). Real streakiness is almost
all noise (real lag-1 autocorrelation of weekly points is -0.03 within a season), so streaks
are mild; the visible "hot hand" the game shows is mostly role changes and the touchdown
lottery, as in real fantasy.

**Weekly stat line**: the expected stat line at a PPR-points level is a position template
(least-squares fit of every component on points over real player-seasons). Given the week's
true mean in the *league's* scoring, the model solves for the template level that scores
that mean (so TE premium or half-PPR change the stat mix and the mean is exact), then draws:
a shared lognormal game-script factor (correlated across teammates through `team_shock`),
negative-binomial volume (attempts, carries, targets), binomial completions/receptions,
per-play gamma yardage summed over the plays (a handful of long plays gives boom weeks),
and Poisson touchdowns whose rate scales with volume and efficiency with a gamma mixing
term. Per-position dispersions were fit so weekly points and the headline stats match real
variance. Points come from the same scoring code the league uses (Sleeper stat keys, TE
premium, 100/200-yard and 300/400-yard bonuses).

## 3. Data and method

| Item | Detail |
| --- | --- |
| Real data | Sleeper public weekly `stats` and `projections` payloads, regular season, seasons 2021-2025 (weeks 1-17), the same files `scripts/projection_calibration_backtest.py fetch` writes. Compact derived panel committed at `modules/sim/calibration/data/panel.json.gz` (0.2 MB) |
| Preseason inputs | week-1 projection PPG (`pts_ppr`) and `adp_dd_ppr` (ADP 999+ = unranked); age on Sep 1; rookie = `rookie_year` equals the season |
| Pool | QB/RB/WR/TE/K with a ranked ADP or a projection of 6+ PPG: 1,794 player-seasons (407 in 2022, about 380 in 2023-25, 246 in 2021 where ADP is sparse) |
| Outcomes | per-week played flag (`gp`), PPR points and every stat component; bye weeks from the real schedule (a week with no player on the team playing) |
| Fit | evolution strategy with common random numbers (`fit.py`); season-level on 2021-23 (held-out run) and on all five seasons (shipped constants) |
| Scoring in the backtest | standard PPR, the units the real data is in |

What is *not* in the repo: nothing in `data/` holds multi-season history (only 2024 and 2025
season totals with partial weekly rows and no projections), so the raw weekly payloads
(about 270 MB, 2021-2026) live in a local cache that the fetch script builds; the committed
panel is what the tests and the backtest read. `python -m modules.sim.calibration.dataset
build --cache DIR --players data/sleeper_players.json` rebuilds it.

## 4. Calibration results

### 4.0 player-model-2 (2026-11 audit): what changed and the before/after

Full write-up, with the real-projection review and the injury audit, in `docs/audits/2026-11-sim-projection-audit.md`.
Tables 4.1 and 4.2 below are the player-model-1 baseline and are kept for the record.

What changed (all general model changes, fit by `fit.py season2`, which scores position/tier/rookie/age groups on quantiles,
breakout/bust rates, SD of log(actual/projection) and preseason-rank finish rates):

| Weak spot | Change |
| --- | --- |
| Rookie / depth downside too thin | a **role-collapse** component (heavy left tail: the season keeps about 33% of the projection, likelier for depth and rookies), rookie spread term, widened bust SD bound |
| QB seasons too loose | QB-specific bust depth and probability, QB role changes damped (`role_qb` 0.1, a one-dimensional fit: QBs rarely change roles), `qb_sig` bound lowered |
| Stars too unstable (WR1 retention) | role-change rate falls with tier (`role_star`): a star keeps his job more often |
| No starter-injury / backup coupling | `apply_depth_coupling(players, profiles)`: temporary promotions for same-team same-position backups for exactly the games a starter misses, absorb shares measured on the real panel. Pure, no extra random draws; **not wired into the game engine** (needs every NFL teammate's profile, an engine decision) |
| Year-to-year drift | audited, **no change**: the shared environment SD 0.057 is right (year medians have SD 0.066, of which sampling noise accounts for about 0.038) and position x year differences are mostly noise |

Out-of-sample, apples to apples (both structures refit with the same optimiser, loss, budget and data: fit 2021-23, scored on
held-out 2024-25, 20 simulated copies):

| metric | v1 structure | v2 structure | real |
| --- | --- | --- | --- |
| season log-ratio variance ratio sim/real, all | 0.97 | 0.93 | 1.0 |
| QB | 1.44 | 1.10 | 1.0 |
| rookies | 0.67 | 0.74 | 1.0 |
| TE | 0.62 | 0.58 | 1.0 |
| tier-hit MAE | 0.077 | 0.070 | 0 |
| PIT KS / mean PIT | 0.171 / 0.590 | 0.164 / 0.586 | 0 / 0.5 |

The held-out years were hot (mean PIT 0.59 whichever structure), which dominates the PIT numbers. Shipped constants, refit on all
five seasons (in-sample, 14 copies), against the previous shipped constants:

| metric | player-model-1 | player-model-2 | real |
| --- | --- | --- | --- |
| variance ratio all / rookies / QB / RB / WR / TE | 0.78 / 0.56 / 1.76 / 0.71 / 0.79 / 0.79 | 0.90 / 0.70 / 1.28 / 0.83 / 0.92 / 0.95 | 1.0 |
| season log-ratio SD, all | 0.490 | 0.526 | 0.554 |
| WR ADP top-12 finishing top-12 | 0.396 | 0.452 | 0.521 |
| RB ADP top-12 finishing top-12 | 0.460 | 0.500 | 0.562 |
| WR top-12 finishing outside 36 | 0.257 | 0.235 | 0.146 |
| 5th percentile of actual/projection, rookies | 0.38 | 0.31 | 0.21 |
| tier-hit MAE | 0.0252 | 0.0267 | 0 |
| PIT KS / 80% coverage | 0.079 / 0.71 | 0.107 / 0.69 | 0 / 0.80 |
| games missed (mean) | 2.53 | 2.54 | 2.55 |
| weekly SD ratio QB/RB/WR/TE | 1.04/1.02/0.99/1.05 | 1.01/1.02/1.00/1.05 | 1.0 |

Honest reading: spread, QB looseness and star retention moved the right way; **PIT KS and the 80% coverage got slightly worse**
(the wider left tail and lower QB centre cost some centre calibration), the rookie 5th percentile is still not low enough
(0.31 vs 0.21 real) and TE variance out of sample did not improve. Determinism and cost are unchanged (about 72 us per player-week
both versions on the same machine, profile draw 104 -> 134 us).

Backup coupling (`backtest.depth_cover_report`, backup uplift in games the starter missed over the starter's PPG, first / second
backup): real 2021-23 RB 0.36 / 0.22, WR 0.20 / 0.09, TE 0.08 / 0.13. Simulated panel uncoupled: about 0.0 everywhere. Coupled:
RB 0.36 / 0.17, WR 0.18 / 0.07, TE 0.14 / 0.04. Held-out 2024-25 real RB 0.55 / 0.50, WR 0.18 / 0.11, TE 0.26; coupled sim RB 0.36 / 0.11,
WR 0.20 / 0.09, TE 0.11: RB cover was stronger in the held-out years than the fit years (28 cases), so the RB value is conservative.

### 4.1 (player-model-1 baseline) Out-of-sample: fit on 2021-2023, scored on held-out 2024-2025 (754 player-seasons, 30 simulated copies each)

The season-level story constants (`SeasonParams`) were fit on 2021-23 only; the weekly dispersion, templates and injury pmf were also fit on 2021-23. This is the honest generalisation number.

#### Season PPG percentile calibration (PIT)

| group | n | KS | mean PIT | 50% cov | 80% cov | 90% cov | < p10 | > p90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all | 754 | 0.1053 | 0.555 | 0.448 | 0.773 | 0.853 | 0.097 | 0.13 |
| all_total | 754 | 0.1133 | 0.55 | 0.424 | 0.744 | 0.842 | 0.114 | 0.142 |
| season 2024 | 348 | 0.1121 | 0.545 | 0.397 | 0.736 | 0.836 | 0.124 | 0.141 |
| season 2025 | 346 | 0.0918 | 0.549 | 0.486 | 0.792 | 0.861 | 0.087 | 0.121 |
| QB | 65 | 0.1273 | 0.57 | 0.508 | 0.815 | 0.877 | 0.0 | 0.185 |
| RB | 181 | 0.1249 | 0.548 | 0.381 | 0.718 | 0.84 | 0.138 | 0.144 |
| WR | 293 | 0.0684 | 0.521 | 0.485 | 0.795 | 0.867 | 0.109 | 0.096 |
| TE | 155 | 0.1608 | 0.584 | 0.4 | 0.735 | 0.806 | 0.103 | 0.161 |
| rookies | 98 | 0.1374 | 0.475 | 0.388 | 0.694 | 0.776 | 0.204 | 0.102 |
| veterans | 596 | 0.1144 | 0.558 | 0.45 | 0.775 | 0.859 | 0.089 | 0.136 |
| age <24 | 79 | 0.2052 | 0.594 | 0.367 | 0.835 | 0.899 | 0.076 | 0.089 |
| age 24-26 | 261 | 0.0843 | 0.529 | 0.49 | 0.797 | 0.885 | 0.096 | 0.107 |
| age 27-29 | 164 | 0.1695 | 0.594 | 0.445 | 0.75 | 0.835 | 0.079 | 0.171 |
| age 30+ | 92 | 0.1493 | 0.546 | 0.413 | 0.707 | 0.793 | 0.098 | 0.196 |

#### Tier hit rates (breakout >= 1.25x projection PPG, bust <= 0.75x)

**by_pos** (MAE 0.062)

| group | n | real breakout | sim breakout | real bust | sim bust |
| --- | --- | --- | --- | --- | --- |
| QB | 64 | 0.0 | 0.013 | 0.281 | 0.378 |
| RB | 134 | 0.343 | 0.22 | 0.246 | 0.325 |
| TE | 91 | 0.286 | 0.195 | 0.297 | 0.3 |
| WR | 207 | 0.232 | 0.198 | 0.271 | 0.327 |

**by_age** (MAE 0.0594)

| group | n | real breakout | sim breakout | real bust | sim bust |
| --- | --- | --- | --- | --- | --- |
| 24-26 | 198 | 0.237 | 0.189 | 0.268 | 0.319 |
| 27-29 | 120 | 0.25 | 0.157 | 0.25 | 0.352 |
| 30+ | 68 | 0.162 | 0.11 | 0.338 | 0.369 |
| <24 | 110 | 0.291 | 0.231 | 0.255 | 0.293 |

**by_rookie** (MAE 0.0452)

| group | n | real breakout | sim breakout | real bust | sim bust |
| --- | --- | --- | --- | --- | --- |
| rookie | 57 | 0.316 | 0.288 | 0.263 | 0.288 |
| vet | 439 | 0.232 | 0.166 | 0.271 | 0.333 |

**by_proj_tier** (MAE 0.052)

| group | n | real breakout | sim breakout | real bust | sim bust |
| --- | --- | --- | --- | --- | --- |
| depth | 138 | 0.42 | 0.334 | 0.283 | 0.379 |
| elite | 38 | 0.105 | 0.103 | 0.211 | 0.238 |
| flex | 149 | 0.235 | 0.159 | 0.322 | 0.326 |
| starter | 171 | 0.135 | 0.091 | 0.228 | 0.309 |

**by_adp_tier** (MAE 0.0596)

| group | n | real breakout | sim breakout | real bust | sim bust |
| --- | --- | --- | --- | --- | --- |
| 13-24 | 95 | 0.158 | 0.092 | 0.211 | 0.314 |
| 25-36 | 87 | 0.184 | 0.134 | 0.241 | 0.312 |
| 37+ | 218 | 0.358 | 0.278 | 0.317 | 0.361 |
| top12 | 96 | 0.115 | 0.085 | 0.25 | 0.283 |

Overall tier-hit MAE: **0.0568**

#### Weekly variance (played games, normalised by own half-season mean)

| pos | real SD | sim SD | ratio | real q05/25/50/75/95 | sim q05/25/50/75/95 | boom real/sim | bust real/sim |
| --- | --- | --- | --- | --- | --- | --- | --- |
| QB | 0.426 | 0.422 | 0.991 | 0.36/0.72/0.97/1.25/1.74 | 0.39/0.7/0.96/1.25/1.76 | 0.08/0.087 | 0.061/0.053 |
| RB | 0.553 | 0.569 | 1.029 | 0.24/0.63/0.93/1.28/2.02 | 0.23/0.59/0.91/1.32/2.04 | 0.128/0.142 | 0.126/0.123 |
| WR | 0.615 | 0.625 | 1.016 | 0.15/0.58/0.92/1.35/2.09 | 0.12/0.55/0.92/1.36/2.14 | 0.149/0.155 | 0.147/0.159 |
| TE | 0.636 | 0.683 | 1.074 | 0.1/0.55/0.92/1.34/2.17 | 0.0/0.51/0.89/1.39/2.26 | 0.156/0.175 | 0.161/0.186 |

Per-stat weekly SD (real / sim): QB: pass_att 0.296/0.191, pass_yd 0.346/0.273, pass_td 0.748/0.849, rush_yd 1.025/1.12; RB: rush_att 0.4/0.355, rush_yd 0.584/0.601, rec_tgt 0.634/0.605, rec 0.688/0.698, rec_yd 0.941/0.949; WR: rec_tgt 0.431/0.441, rec 0.525/0.549, rec_yd 0.653/0.675; TE: rec_tgt 0.483/0.491, rec 0.553/0.585, rec_yd 0.651/0.723

#### Games missed (core fantasy players)

| group | n | mean real/sim | P(0) real/sim | P(>=3) | P(>=6) | P(>=10) |
| --- | --- | --- | --- | --- | --- | --- |
| all core | 282 | 2.37/2.56 | 0.415/0.391 | 0.33/0.373 | 0.17/0.172 | 0.028/0.051 |
| QB | 64 | 2.77/3.09 | 0.453/0.318 | 0.391/0.444 | 0.266/0.221 | 0.031/0.063 |
| RB | 76 | 2.03/2.45 | 0.434/0.401 | 0.276/0.367 | 0.105/0.155 | 0.026/0.051 |
| WR | 110 | 2.45/2.39 | 0.382/0.418 | 0.327/0.346 | 0.164/0.157 | 0.036/0.047 |
| TE | 32 | 2.12/2.34 | 0.406/0.422 | 0.344/0.339 | 0.156/0.164 | 0.0/0.044 |
| age <24 | 57 | 1.74/1.9 | 0.526/0.504 | 0.298/0.277 | 0.07/0.12 | 0.018/0.03 |
| age 24-26 | 112 | 2.35/2.38 | 0.375/0.41 | 0.321/0.353 | 0.179/0.152 | 0.018/0.046 |
| age 27-29 | 66 | 2.08/2.91 | 0.455/0.335 | 0.288/0.422 | 0.152/0.199 | 0.015/0.065 |
| age 30+ | 47 | 3.6/3.29 | 0.319/0.287 | 0.447/0.468 | 0.298/0.243 | 0.085/0.072 |
| rookies | 24 | 0.83/1.56 | 0.708/0.565 | 0.125/0.232 | 0.042/0.093 | 0.0/0.022 |

#### Preseason-ADP rank vs season finish (share of group)

| group | n | top-12 real/sim | top-24 real/sim | outside 36 real/sim |
| --- | --- | --- | --- | --- |
| QB:13-24 | 24 | 0.375/0.339 | 0.667/0.722 | 0.0/0.0 |
| QB:top12 | 24 | 0.542/0.508 | 0.833/0.833 | 0.0/0.0 |
| RB:13-24 | 24 | 0.25/0.231 | 0.583/0.547 | 0.208/0.244 |
| RB:top12 | 24 | 0.583/0.506 | 0.833/0.731 | 0.125/0.128 |
| TE:13-24 | 24 | 0.292/0.239 | 0.708/0.568 | 0.125/0.2 |
| TE:top12 | 24 | 0.5/0.572 | 0.75/0.825 | 0.0/0.063 |
| WR:13-24 | 24 | 0.125/0.243 | 0.458/0.474 | 0.375/0.369 |
| WR:top12 | 24 | 0.417/0.401 | 0.625/0.619 | 0.208/0.251 |

#### Season-level variance ratio (log of season PPG / projection)

| group | n | real SD | sim SD | var ratio (sim/real) | real mean | sim mean |
| --- | --- | --- | --- | --- | --- | --- |
| all | 496 | 0.585 | 0.507 | 0.75 | -0.123 | -0.146 |
| QB | 64 | 0.221 | 0.295 | 1.79 | -0.184 | -0.268 |
| RB | 134 | 0.602 | 0.567 | 0.89 | -0.044 | -0.112 |
| WR | 207 | 0.591 | 0.525 | 0.79 | -0.137 | -0.137 |
| TE | 91 | 0.7 | 0.479 | 0.47 | -0.162 | -0.132 |
| rookies | 57 | 0.799 | 0.566 | 0.5 | -0.133 | -0.064 |
| veterans | 439 | 0.551 | 0.498 | 0.82 | -0.121 | -0.157 |
| proj >= 8 | 299 | 0.356 | 0.373 | 1.1 | -0.114 | -0.173 |
| proj < 8 | 197 | 0.818 | 0.659 | 0.65 | -0.136 | -0.105 |

Half-season split log-ratio SD: real 0.372, sim 0.404; lag-1 autocorrelation: real -0.029, sim -0.032.

#### Per-game stat lines (ADP top 100)

- QB: pass_att 31.21/32.92, pass_cmp 20.56/21.6, pass_yd 230.31/236.92, pass_td 1.63/1.49, pass_int 0.59/0.72, rush_att 4.54/3.98, rush_yd 22.43/18.64, rush_td 0.24/0.21
- RB: rush_att 13.71/12.27, rush_yd 61.6/53.48, rush_td 0.48/0.43, rec_tgt 3.27/3.19, rec 2.62/2.48, rec_yd 20.13/18.4, rec_td 0.11/0.11
- WR: rec_tgt 7.4/7.09, rec 4.76/4.68, rec_yd 61.99/60.37, rec_td 0.4/0.36
- TE: rec_tgt 6.11/5.98, rec 4.47/4.23, rec_yd 46.11/46.86, rec_td 0.37/0.31


### 4.2 (player-model-1 baseline) Shipped constants: refit on all five seasons, scored on all 1,757 usable player-seasons

In-sample (the shipped `SeasonParams` use every season), so these are optimistic; they are the regression guard `tests/test_sim_player_model.py` replays. Compare with 4.1 for how much generalisation costs.

#### Season PPG percentile calibration (PIT)

| group | n | KS | mean PIT | 50% cov | 80% cov | 90% cov | < p10 | > p90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all | 1757 | 0.0501 | 0.513 | 0.467 | 0.784 | 0.861 | 0.113 | 0.103 |
| all_total | 1757 | 0.0675 | 0.519 | 0.438 | 0.758 | 0.842 | 0.123 | 0.119 |
| season 2021 | 214 | 0.1634 | 0.408 | 0.453 | 0.846 | 0.897 | 0.117 | 0.037 |
| season 2022 | 362 | 0.0693 | 0.485 | 0.503 | 0.771 | 0.84 | 0.135 | 0.094 |
| season 2023 | 337 | 0.0687 | 0.496 | 0.46 | 0.757 | 0.84 | 0.131 | 0.113 |
| season 2024 | 348 | 0.1069 | 0.539 | 0.408 | 0.736 | 0.822 | 0.121 | 0.144 |
| season 2025 | 346 | 0.1001 | 0.538 | 0.462 | 0.786 | 0.879 | 0.107 | 0.107 |
| QB | 155 | 0.057 | 0.503 | 0.529 | 0.852 | 0.929 | 0.065 | 0.084 |
| RB | 421 | 0.071 | 0.508 | 0.43 | 0.767 | 0.843 | 0.131 | 0.102 |
| WR | 675 | 0.068 | 0.482 | 0.458 | 0.767 | 0.843 | 0.141 | 0.092 |
| TE | 356 | 0.0875 | 0.524 | 0.458 | 0.764 | 0.846 | 0.101 | 0.135 |
| rookies | 219 | 0.0934 | 0.483 | 0.438 | 0.726 | 0.795 | 0.16 | 0.114 |
| veterans | 1388 | 0.0483 | 0.503 | 0.461 | 0.782 | 0.862 | 0.115 | 0.102 |
| age <24 | 208 | 0.0676 | 0.51 | 0.471 | 0.841 | 0.904 | 0.087 | 0.072 |
| age 24-26 | 597 | 0.0586 | 0.489 | 0.461 | 0.786 | 0.873 | 0.126 | 0.089 |
| age 27-29 | 389 | 0.0757 | 0.529 | 0.473 | 0.761 | 0.843 | 0.108 | 0.131 |
| age 30+ | 194 | 0.0727 | 0.482 | 0.428 | 0.753 | 0.83 | 0.129 | 0.119 |

#### Tier hit rates (breakout >= 1.25x projection PPG, bust <= 0.75x)

**by_pos** (MAE 0.0246)

| group | n | real breakout | sim breakout | real bust | sim bust |
| --- | --- | --- | --- | --- | --- |
| QB | 154 | 0.0 | 0.013 | 0.357 | 0.348 |
| RB | 323 | 0.269 | 0.222 | 0.279 | 0.293 |
| TE | 224 | 0.214 | 0.203 | 0.344 | 0.301 |
| WR | 526 | 0.188 | 0.213 | 0.329 | 0.294 |

**by_age** (MAE 0.0196)

| group | n | real breakout | sim breakout | real bust | sim bust |
| --- | --- | --- | --- | --- | --- |
| 24-26 | 468 | 0.182 | 0.192 | 0.321 | 0.297 |
| 27-29 | 306 | 0.18 | 0.16 | 0.327 | 0.318 |
| 30+ | 156 | 0.141 | 0.119 | 0.397 | 0.338 |
| <24 | 297 | 0.242 | 0.249 | 0.279 | 0.273 |

**by_rookie** (MAE 0.0173)

| group | n | real breakout | sim breakout | real bust | sim bust |
| --- | --- | --- | --- | --- | --- |
| rookie | 144 | 0.326 | 0.308 | 0.306 | 0.274 |
| vet | 1083 | 0.173 | 0.173 | 0.324 | 0.305 |

**by_proj_tier** (MAE 0.0261)

| group | n | real breakout | sim breakout | real bust | sim bust |
| --- | --- | --- | --- | --- | --- |
| depth | 281 | 0.363 | 0.352 | 0.349 | 0.361 |
| elite | 123 | 0.073 | 0.111 | 0.195 | 0.236 |
| flex | 376 | 0.207 | 0.191 | 0.388 | 0.306 |
| starter | 447 | 0.101 | 0.105 | 0.284 | 0.279 |

**by_adp_tier** (MAE 0.036)

| group | n | real breakout | sim breakout | real bust | sim bust |
| --- | --- | --- | --- | --- | --- |
| 13-24 | 185 | 0.13 | 0.113 | 0.243 | 0.274 |
| 25-36 | 175 | 0.166 | 0.15 | 0.326 | 0.293 |
| 37+ | 463 | 0.296 | 0.292 | 0.374 | 0.335 |
| top12 | 190 | 0.105 | 0.097 | 0.189 | 0.268 |
| unranked | 214 | 0.112 | 0.142 | 0.393 | 0.29 |

Overall tier-hit MAE: **0.0261**

#### Weekly variance (played games, normalised by own half-season mean)

| pos | real SD | sim SD | ratio | real q05/25/50/75/95 | sim q05/25/50/75/95 | boom real/sim | bust real/sim |
| --- | --- | --- | --- | --- | --- | --- | --- |
| QB | 0.403 | 0.418 | 1.037 | 0.36/0.73/0.98/1.24/1.69 | 0.39/0.7/0.96/1.25/1.74 | 0.074/0.084 | 0.062/0.053 |
| RB | 0.55 | 0.556 | 1.011 | 0.24/0.62/0.93/1.3/2.0 | 0.25/0.6/0.92/1.32/2.02 | 0.136/0.137 | 0.122/0.118 |
| WR | 0.629 | 0.614 | 0.976 | 0.09/0.57/0.92/1.36/2.12 | 0.15/0.56/0.92/1.35/2.11 | 0.153/0.154 | 0.156/0.154 |
| TE | 0.651 | 0.687 | 1.055 | 0.0/0.53/0.9/1.38/2.2 | 0.0/0.51/0.9/1.39/2.27 | 0.168/0.173 | 0.171/0.188 |

Per-stat weekly SD (real / sim): QB: pass_att 0.266/0.19, pass_yd 0.318/0.271, pass_td 0.717/0.838, rush_yd 1.06/1.097; RB: rush_att 0.407/0.347, rush_yd 0.617/0.587, rec_tgt 0.612/0.591, rec 0.669/0.685, rec_yd 0.954/0.925; WR: rec_tgt 0.439/0.432, rec 0.536/0.538, rec_yd 0.661/0.663; TE: rec_tgt 0.484/0.493, rec 0.56/0.591, rec_yd 0.669/0.723

#### Games missed (core fantasy players)

| group | n | mean real/sim | P(0) real/sim | P(>=3) | P(>=6) | P(>=10) |
| --- | --- | --- | --- | --- | --- | --- |
| all core | 737 | 2.55/2.53 | 0.377/0.391 | 0.35/0.366 | 0.17/0.167 | 0.049/0.049 |
| QB | 158 | 3.02/3.05 | 0.399/0.318 | 0.411/0.433 | 0.222/0.213 | 0.076/0.064 |
| RB | 195 | 2.59/2.4 | 0.354/0.409 | 0.354/0.351 | 0.144/0.156 | 0.062/0.046 |
| WR | 294 | 2.35/2.38 | 0.381/0.415 | 0.32/0.344 | 0.16/0.153 | 0.037/0.045 |
| TE | 90 | 2.29/2.41 | 0.378/0.406 | 0.333/0.352 | 0.167/0.156 | 0.011/0.045 |
| age <24 | 168 | 1.84/1.96 | 0.458/0.487 | 0.256/0.281 | 0.101/0.121 | 0.03/0.034 |
| age 24-26 | 283 | 2.53/2.39 | 0.36/0.405 | 0.364/0.348 | 0.155/0.152 | 0.046/0.044 |
| age 27-29 | 177 | 2.73/2.8 | 0.367/0.351 | 0.367/0.405 | 0.192/0.19 | 0.045/0.056 |
| age 30+ | 109 | 3.4/3.36 | 0.312/0.273 | 0.431/0.48 | 0.275/0.239 | 0.092/0.075 |
| rookies | 58 | 1.66/1.62 | 0.552/0.556 | 0.224/0.236 | 0.086/0.094 | 0.034/0.026 |

#### Preseason-ADP rank vs season finish (share of group)

| group | n | top-12 real/sim | top-24 real/sim | outside 36 real/sim |
| --- | --- | --- | --- | --- |
| QB:13-24 | 48 | 0.396/0.343 | 0.708/0.747 | 0.0/0.0 |
| QB:top12 | 48 | 0.521/0.513 | 0.854/0.816 | 0.0/0.0 |
| RB:13-24 | 48 | 0.229/0.228 | 0.562/0.546 | 0.229/0.24 |
| RB:top12 | 48 | 0.562/0.498 | 0.833/0.733 | 0.083/0.135 |
| TE:13-24 | 48 | 0.271/0.245 | 0.646/0.572 | 0.229/0.187 |
| TE:top12 | 48 | 0.542/0.535 | 0.812/0.804 | 0.0/0.078 |
| WR:13-24 | 48 | 0.146/0.211 | 0.458/0.426 | 0.312/0.394 |
| WR:top12 | 48 | 0.521/0.38 | 0.75/0.592 | 0.146/0.274 |

#### Season-level variance ratio (log of season PPG / projection)

| group | n | real SD | sim SD | var ratio (sim/real) | real mean | sim mean |
| --- | --- | --- | --- | --- | --- | --- |
| all | 1227 | 0.554 | 0.488 | 0.78 | -0.185 | -0.116 |
| QB | 154 | 0.204 | 0.269 | 1.74 | -0.215 | -0.238 |
| RB | 323 | 0.619 | 0.525 | 0.72 | -0.127 | -0.084 |
| WR | 526 | 0.57 | 0.509 | 0.8 | -0.206 | -0.098 |
| TE | 224 | 0.576 | 0.487 | 0.72 | -0.199 | -0.121 |
| rookies | 144 | 0.742 | 0.565 | 0.58 | -0.138 | -0.023 |
| veterans | 1083 | 0.524 | 0.476 | 0.82 | -0.191 | -0.128 |
| proj >= 8 | 791 | 0.395 | 0.348 | 0.78 | -0.175 | -0.133 |
| proj < 8 | 436 | 0.762 | 0.67 | 0.77 | -0.203 | -0.084 |

Half-season split log-ratio SD: real 0.392, sim 0.396; lag-1 autocorrelation: real -0.035, sim -0.028.

#### Per-game stat lines (ADP top 100)

- QB: pass_att 32.58/33.24, pass_cmp 21.51/21.89, pass_yd 237.08/242.55, pass_td 1.63/1.58, pass_int 0.64/0.71, rush_att 4.92/4.27, rush_yd 24.07/20.36, rush_td 0.27/0.23
- RB: rush_att 13.38/12.83, rush_yd 59.15/56.01, rush_td 0.44/0.45, rec_tgt 3.36/3.32, rec 2.63/2.59, rec_yd 19.81/19.28, rec_td 0.1/0.11
- WR: rec_tgt 7.37/7.17, rec 4.74/4.73, rec_yd 62.11/61.03, rec_td 0.38/0.37
- TE: rec_tgt 6.13/5.95, rec 4.36/4.19, rec_yd 46.54/46.37, rec_td 0.33/0.31


## 5. Parameters and why

Season level (`SeasonParams`, fit by evolution strategy on the season-PPG quantiles and tier hit rates of
position x tier, rookie x tier, age and tier groups; bounded to plausible ranges so the search cannot
buy fit with nonsense such as negative breakout gains). Values at a bound in the v2 fit (`b_solid` 1.05, `pb_tier` 0.8, `pu_rook` 1.5, `ps_tier` 1.2, `gain_tier` near 0.27) say the
structure is still straining there; see Limitations. The v1 bounds that were hit (`qb_sig`, `bust_sd`, `pb_rook`, `gain_rook`,
`qb_gain`) were widened for the v2 fit (`fit.py` `SEASON2_BOUNDS`).

| Parameter | Value |
| --- | --- |
| `b_solid` | 1.05 |
| `b_solid_qb` | 0.8733 |
| `b_solid_k` | 0.93 |
| `b_tier` | 0.0784 |
| `sigma0` | 0.0708 |
| `sigma_tier` | 0.6782 |
| `qb_sig` | 0.2314 |
| `pb0` | -2.7566 |
| `pb_rook` | 2.6637 |
| `pb_age` | 0.5535 |
| `pb_tier` | 0.8 |
| `pu0` | -1.5948 |
| `pu_rook` | 1.5 |
| `pu_age` | 0.0158 |
| `pu_tier` | 0.1004 |
| `ps0` | -2.0203 |
| `ps_tier` | 1.2 |
| `pi0` | -2.2 |
| `bust_mult` | 0.7645 |
| `bust_sd` | 0.371 |
| `gain_mean` | 3.1523 |
| `gain_shape` | 2.5 |
| `gain_tier` | 0.2711 |
| `gain_rook` | 1.1329 |
| `qb_gain` | 0.2328 |
| `te_gain` | 0.6098 |
| `pc0` | -4.1131 |
| `pc_tier` | 1.1977 |
| `pc_rook` | 0.076 |
| `collapse_mult` | 0.3282 |
| `collapse_sd` | 0.2566 |
| `pu_qb` | -0.1733 |
| `qb_bust_mult` | 0.7853 |
| `sig_rook` | 0.0 |
| `te_sig` | 1.0325 |

In-season (`InSeasonParams`): hazard fit to games missed (mean, P(0), P(>=3), P(>=6), P(>=10)); the
duration pmf is the real episode-length distribution with the long tail widened to 10% because the
real episodes are truncated by the season end; role-change rate fit to the real half-season split
SD (0.40) and form AR(1) chosen so weekly lag-1 autocorrelation stays at the real -0.03.

| Parameter | Value |
| --- | --- |
| `form_phi` | 0.35 |
| `form_sd` | 0.06 |
| `slump_len` | (3, 6) |
| `slump_depth` | 0.3 |
| `role_rate` | 0.65 |
| `role_rate_deep` | 0.5 |
| `p_promotion` | 0.35 |
| `role_star` | 1.0137 |
| `role_qb` | 0.1 |
| `absorb` | (0.6, 0.33, 0.23, 0.1, 0.0) |
| `promo_mult` | (1.2, 1.9) |
| `demo_mult` | (0.45, 0.85) |
| `vol_sd` | 0.12 |
| `rookie_ramp` | 0.93 |
| `return_ramp` | 0.91 |
| `onset_game_mean` | 0.72 |
| `hazard` | 0.065 |
| `hazard_pos` | (1.2, 1.05, 1.0, 0.95, 0.6) |
| `hazard_age` | 0.3 |
| `prone_mult` | 2.0 |
| `rookie_hazard` | 0.75 |
| `frailty_shape` | 3.0 |
| `out_pmf` | (0.4029, 0.1638, 0.1067, 0.0924, 0.0543, 0.0352, 0.0238, 0.021) |

Weekly dispersion (`WEEK`, per position: game-script SD, volume dispersion, efficiency SD, yards-per-play
gamma shape, TD mixing): fit so the weekly points quantiles (5th to 99th), boom/bust rates and the
weekly SD of each headline stat match real normalised games. Stat templates (`TEMPLATE`) are the
least-squares line of each stat component on PPR points across real player-seasons.

| Position | sg | vol_cv | eff | kappa | rush_kappa | td_cv |
| --- | --- | --- | --- | --- | --- | --- |
| QB | 0.261 | 0.053 | 0.079 | 2.922 | 0.28 | 0.002 |
| RB | 0.234 | 0.009 | 0.139 | 1.087 | 0.386 | 0.734 |
| WR | 0.145 | 0.087 | 0.132 | 1.75 | 0.8 | 0.447 |
| TE | 0.168 | 0.032 | 0.194 | 2.062 | 0.8 | 0.388 |
| K | 0.2 | 0.35 | 0.1 | 1.0 | 1.0 | 0.5 |

Why these choices, in plain terms:
- **Additive breakouts.** Real outcomes in PPG terms are stationary: the 90th percentile of (actual - projected)
  is about +4 PPG at every tier from 3 to 20+ PPG, so a breakout is a PPG gain, not a multiple.
- **Busts and slumps are different things.** A bust is a season-long shortfall (0.75x); a slump is a 3-6 week
  dip inside an otherwise normal year and only happens to non-rookies, more to stars.
- **Injury durations are the real ones**, not a parametric guess: 42% one game, 17% two, 5% season-ending.
- **Role changes carry the excess variance.** Half-season PPG ratios have SD 0.40 in real data; weekly noise
  alone explains about 0.32 of it.
- **Environment shock** (SD 0.057) is the spread of the five real season-level actual/projected ratios.
- **Points are produced from a stat line**, then scored, so a TE-premium or half-PPR league automatically
  changes who is valuable instead of rescaling a number.


## 6. Limitations (honest)

1. **The real "preseason projection" is not FantasyDesk's.** It is the Sleeper/RotoWire week-1 projection PPG
   (healthy-game expectation). Real outcomes ran about 10% below it (QBs about 20%), and the shipped
   `b_solid` / `b_solid_qb` encode that. If the game feeds a better-calibrated projection (for example the
   `projection_calibration` outputs), the season level will be pessimistic; re-run `fit.py season` or
   set `SeasonParams.b_solid` to about 1.0. There is no multi-season history of *our own* preseason valuations
   in the repo (`data/` has only `sleeper_player_stats_2024/2025.json`: season totals, partial weekly rows,
   no projections or ADP); the 2021-2026 weekly projection and stats payloads come from a local fetch cache
   (`scripts/projection_calibration_backtest.py fetch`) and are not committed except as the derived panel.
2. **Year-to-year drift.** The median actual/projected ratio was 0.80 (2021), 0.88, 0.89, 0.97 (2024), 0.88
   (2025). One shared environment shock models it but five seasons barely identify its SD, and the held-out
   years were hot (mean PIT 0.555: the model sits about 5 percentile points low). Out-of-sample 50% intervals
   cover 45%, 90% intervals 85%: the model is slightly over-confident.
3. **Left tail of depth players is thinner than real** (v2 narrowed it: variance ratio 0.90 overall, 0.70 rookies, TE about 0.6-0.95). Real log(actual/proj) SD is 0.55 vs 0.49 simulated (variance
   ratio 0.78; rookies 0.5-0.6, TE 0.47 held out): real low-usage players can fall to a fifth of projection,
   the model rarely does. QBs go the other way (variance ratio 1.7; the real QB season is very tight and
   `qb_sig` is at its lower bound).
4. **Stars are a bit less stable than real.** Among preseason ADP top-12 WRs, 38% finish top-12 in the sim vs
   52% real over the seasons with ADP (4.2; held-out 40% vs 42%, 4.1), and 27% finish outside the top 36 vs
   15%. RB1 and QB1 are close, TE1 slightly too safe. Top-heavy WR outcomes are a bit too random.
5. **Games missed conflate injuries with benching, resting, suspensions and cuts.** The data only says
   "did not play". Injury types/body parts are not modelled, there is no probable/questionable news, and
   there is no preseason-injured start (the model has no one starting the season on IR).
6. **Rookies are thin.** 219 rookie seasons (58 core). Rookie PIT 80% interval covers 73% (in-sample) and the
   rookie season variance is under-dispersed (variance ratio about 0.5).
7. **Cross-player structure.** `apply_depth_coupling` (v2) promotes backups for the games a starter misses, but the game engine does
   not call it yet; without it injuries and role changes are independent per player. No opponent, weather or
   schedule strength.
8. **Weeks 15-17 are treated like any week.** Real week-17 resting of starters and playoff-week effects are
   not modelled, and the calibration data stops at week 17 (the NFL's 18th week is not in the panel).
9. **Kickers and defenses.** K is calibrated on 152 player-seasons with a two-component (FG, XP) line;
   DEF/DST is a generic gamma draw with no calibration data.
10. **Scoring bonuses** (300/400, 100/200 yard bonuses) are priced into the expected-points solve with a
    normal approximation of the yardage distribution, not a Monte Carlo; checked at the 1% level only for the
    300-yard QB and 100-yard receiving bonuses.
11. **Weekly dispersion was fit on ADP<=150 players of 2021-23** and is validated, not refit, on 2024-25. Depth players'
    weekly shape is the least validated.
12. **Fit quality of the optimiser.** The season-level search is a stochastic evolution strategy with a few
    parameters at their bounds; a different seed lands on similar fits but not identical constants.


## 7. Re-running

```
python -m modules.sim.calibration.dataset build --cache DIR --players data/sleeper_players.json
python -m modules.sim.calibration.fit templates|injuries|weekly|season|inseason [--train 2021 2022 2023]
python -m modules.sim.calibration.backtest --copies 30 --seasons 2024 2025 [--markdown]
pytest tests/test_sim_player_model.py tests/test_sim_isolation.py
```

Isolation: `player_model.py` and everything under `modules/sim/calibration/` import only
the stdlib, numpy and `modules.sim.*`; `tests/test_sim_isolation.py` lists `player_model.py`
as a pure-engine file, loads it in a clean interpreter with no real module imported, and
checks the calibration package's imports. Nothing here reads `data/players.db`.
