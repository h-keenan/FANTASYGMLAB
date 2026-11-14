# Sim injuries and team usage: are they realistic? (2026-11)

Ask (coridian_): "audit the injuries within the SIM to see if they're realistic", then the evidence: (1) an RB (grade D+, ADP 482, projected 1.9 ppg for
the next season) who had "an arguably top-15 running back year" (about 12 ppg, weekly 5-38), and (2) "there's only 32 teams in the NFL so realistically
more than 32 quarterbacks should not play in a given week unless there are injuries ... There's really only three at the most decent wide receivers
on one team that has a good offense; other teams might just have one or two."

Shipped as `world_v` 1 (new games only; every older save replays byte-for-byte, golden digests pinned in `tests/test_sim_world_v.py`). No new player model:
player-model-6 is unchanged, the fixes are engine rules that read the public depth chart and add no random draw. Harness (committed):
`python -m modules.sim.calibration.injury_usage_report` (real panel vs 40 seeds x 3 dynasty seasons). The rest of the sweep: `realism_sweep seasons`,
`tail_report`, `dynasty_report`, all with `--world-v 0|1` for before/after.

## Findings, ranked (audit first)

| # | Sev | Finding | Evidence (real 2021-25 panel vs sim before) | Status |
| --- | --- | --- | --- | --- |
| 1 | High | **Backup quarterbacks played every week.** A healthy QB behind the starter got a 0.2 role multiplier, but the stat-line template has an intercept (27 pass attempts at 0 points), so each bench QB threw 20+ passes and scored. That is the "more than 32 quarterbacks" report: up to 36 QBs per week with 10+ attempts (95th percentile 34), and 7.7% of team-weeks had two QBs with 10+ attempts | per-week QBs with 10+ attempts: sim mean 26.3 / max **36** vs real 23.8 / 32 (both pool-limited: the pool is the fantasy-relevant players, not the 53-man rosters) | Fixed (world_v 1: bench QB does not play): mean 24.0 / max **32**, two-QB team-weeks 7.7% -> 0.0% |
| 2 | High | **A scrub could take a job nobody left (the Castillo mechanism).** The solid-season draw for a low-projection player has a log-sd up to 1.1 truncated at 2.3 sd (a 12x outcome), natural role promotions compound to 3.5x, and nothing ties either to the depth chart: a 2.0 ppg RB posted 20.2 ppg next to an 18 ppg starter who also scored 16.2 (the team RB group 63% above its baseline) | players projected 1.5-3 ppg, season ppg: p99 **14.1** (real 8.1), max **26.8** (real 11.3), 3.0% finish at 10+ ppg (real 0.6%); projected 3-4.5: p99 16.4 (real 11.0), max 29.4 (real 14.2). In five real seasons the largest riser from a sub-6 projection was 4.6 -> 12.6 ppg | Fixed (a per-tier upside ceiling plus a group usage cap): 1.5-3: p99 9.7, max 15.2, 0.8% at 10+; 3-4.5: p99 12.5, max 17.0 |
| 3 | Medium | **RB and TE group totals have a heavy upper tail.** The team RB group's season points over its preseason projection sum: sim p90/p50 1.45, cv 0.385 vs real 1.31 / 0.30 (WR is fine: 1.38 / 0.27 vs 1.36 / 0.25, QB fine) | `group_points_over_projection_sum` below | Fixed: RB 1.35 / 0.32, TE 1.52 / 0.41 (real 1.53 / 0.36), WR 1.31 / 0.24 |
| 4 | Medium | Deep breakouts 2x too frequent at RB: RBs projected beyond the 50th RB who finish top 24: **1.89 a season** vs 0.8 in the real panel (a lower bound: the panel only holds players with an ADP or a 6+ ppg projection). Causes of every 30+ place riser into the top 36: natural role promotion with no injury ahead 38%, breakout story 25%, luck 21%, injury cover **15%** | `breakouts` below | RB 1.21, WR 2.49 -> 1.61 (real 1.8), TE 2.93 -> 2.50 (real 2.4); cause mix after: promotion 32%, injury cover 26% |
| 5 | Medium | **Dynasty depth charts never update and rookies land on random teams.** `depth_chart_order` is copied forward unchanged, rookies have none (they sort behind every incumbent whatever their projection), and a rookie's NFL team is uniform among 32. After a few seasons a star can sit "bench" for years and a team can hold three rookie QBs | code reading: `season_snapshot` copies `extra`, `rookie_class` draws the team with one uniform integer | Fixed (depth charts re-ranked each season by projection; rookie team drawn with weight exp(-starters' strength / reference)) |
| 6 | Low | Injuries: **games lost match the real panel**; frequency and mix are within 10-20%; position, age and workload effects are not modelled the way the NFL has them (below) | section A | Reported, no change (the evidence does not call for one; see "What remains") |
| 7 | Info | No game statuses (Questionable / Doubtful / Out), no playing through an injury, no practice reports: an injury is revealed immediately with its exact length. The injury report has one state, "out" | engine design | Reported, not changed (a product decision: it changes the UI and the AI managers) |
| 8 | Info | Per-team usage budgets already hold in aggregate: shares of targets by rank in a team-week sim WR1 30.7% / WR2 16.3% / WR3 8.1% / TE1 16.0% / RB1 13.4% (real, same pool-limited basis: 32.3 / 18.0 / 8.0 / 17.4 / 13.8). The weekly sum of targets (26.3 vs 27.4 pool-limited) and rushes (22.3 vs 23.5) is right; the QB pass-attempt sum was 35.3 vs 32.5 only because of finding 1 | `target_share_ranked_in_team_week` | OK (after finding 1: 32.3) |

## Sources and assumptions (read before trusting a number)

- **Real data in the repo**: `modules/sim/calibration/data/panel.json.gz`, 1,794 player-seasons 2021-25 (QB/RB/WR/TE/K with a preseason ADP or a 6+ ppg projection),
  weekly box scores, byes. Everything marked "real" below is computed from it by the harness, restricted to the same pool the sim has, so counts are
  *pool-limited* (the real panel has about 24 QBs a week with 10+ attempts, not 32). A missed game in the panel is any non-bye week with no game: it includes
  benching and healthy scratches, not only injuries; the model's "injury" bundle includes them too (see `2026-11-sim-realism-sweep.md`).
- **Not in the repo**: NFL injury-report statistics (Questionable / Doubtful / Out shares and play rates, injuries per team, position and workload hazards).
  Those are quoted from memory of the published NFL / league injury summaries and are **approximate**; none was used to fit anything and none is relied on by a
  test. I call them "published (approx.)".
- **Sim side**: 40 seeds x 3 dynasty seasons (12 teams, pool from the real 2025 panel, player-model-6, `ai_v` 1), regular season only; every healthy player is
  scored every week by the engine, so the harness wraps the engine's own scoring session and re-simulates nothing. Rank, tier and age cohorts use the preseason
  projection, as the real side does.

## A. Injuries against the real world

### A1. Games lost, and what the model draws (sim before = after except the QB row)

| metric | real (panel, relevant players) | sim | verdict |
| --- | --- | --- | --- |
| share of non-bye games missed, RB / WR / TE / QB | 16.6 / 14.9 / 13.9 / 18.9% | 15.6 / 15.5 / 15.6 / 18.1% (QB 17.1% after) | on target (QB real includes benching) |
| games missed a season, relevant players: 0 / 1-2 / 3-5 / 6-9 / 10+ | 39 / 26.5 / 17.8 / 11.7 / 5.0% | 45.3 / 23.1 / 18.4 / 10.1 / 3.1% | right body, long absences 40% light, scratch-free seasons 6 points high |
| absence episodes per 100 player-games (cohort of relevant players) | 5.2 (interior and trailing runs; 3.8 interior only) | 5.6-6.0 (new injuries per 100 games a player was healthy) | about 1.1x |
| episode length: 1 / 2 / 3 / 4 / 5 / 6+ games | 42 / 20 / 13 / 8 / 4 / 13% | 37 / 17 / 13 / 10 / 7 / 16% (calendar weeks, a bye inside counts) | same shape |
| nominal long absence (9+ weeks, often season-ending) | 3.6% of observed episodes (truncated by the season's end) | 10% of onsets by the pmf; 6-7% observed | consistent with published ACL/Achilles-class shares (about 8-10% of time-loss injuries, approx.) |
| missed-game share by age <=24 / 25-27 / 28-30 / 31+ | 12.3 / 14.8 / 14.6 / 16.0% | 11.5 / 13.6 / 15.8 / 18.4% | the oldest-to-youngest ratio is 1.6x vs 1.3x real; 31+ about 15% high |
| missed-game share by position, cohort | QB 15.0, RB 14.3, WR 14.2, TE 14.2 | QB 17.3, RB 14.1, WR 13.8, TE 14.1 | QB about 15% high; no position spread in either |
| episodes per 100 games by tier (top-12 / 13-36 / 37+ by projection) | 3.2 / 3.7 / 4.3 | 6.0 / 6.0 / 5.6 | flat in the sim; real depth players miss more (benching, release) |
| fantasy-relevant players out per NFL team-week | n/a | 1.74 of about 12 core pool players (p90 4) | 14.5%, in the real 10-15% band for starters |
| depth starters (QB1, RB1-2, WR1-3, TE1) out in a given week | published (approx.): 10-15% | QB 18.8, RB 15.4, WR 15.3, TE 16.0% | a little high at QB |
| new injury to a player who plays, per 100 player-games | published (approx.): 2.5-4 for starters | RB 6.8, WR 6.7, TE 6.8, QB 7.7 | high, but the sim's bundle counts benching and rest (the games lost are right) |
| second absence within 8 weeks of a return, per 100 games | published (approx.): 1.5-2x the base rate | 9.6 vs a base of 6.8 (1.4x, from per-player frailty) | OK |
| first game back | real 0.91 of normal (earlier audit) | 0.91 (`return_ramp`) | OK |
| the game he is hurt in | real 0.72 of a normal game (earlier audit) | 0.72 (`onset_game_mean`) | OK |

### A2. What the model has no concept of (honest gaps, none fixed)

- **Game statuses.** No Questionable / Doubtful / Out, no playing through, no practice reports. Published (approx.): about three quarters of Questionable
  players play, under one in ten Doubtful players play, and a team lists 8-12 players a week; the sim lists only the ones who are out for a stated
  number of weeks, immediately and exactly. A status system is a product feature (new UI states on web and mobile, new AI-manager rules), not a calibration.
- **Position and workload hazards.** Hazard is `0.065 x pos(1.2, 1.05, 1.0, 0.95) x age x frailty`; there is no workload term. Published (approx.): RB
  per-game injury risk is about 1.3-1.5x WR/TE and QBs are the lowest of the skill positions. The panel cannot confirm it (benching and scratches wash it
  out: real missed-game share is 14.2-15.0% at every position) so I did not move a calibrated constant on recollection; the model's QB hazard (1.2 x an
  older age) is the one that looks wrong (QB 17.3% vs 15.0%).
- **IR.** The engine and AI managers do use reserves (`reserve_v`, `ai_manage_reserves`), audited in `2026-11-sim-ai-managers.md`; not re-measured here.

### A3. Injuries and depth-chart promotion (backup becomes the starter)

When a depth starter is out, exactly one healthy next-in-line player inherits the slot (`team_roles`, player-model-3+). Fill-in games per 100 starter
games: RB 10-11, WR 13, TE 15, QB 2. A fill-in scores 5.1-6.0 (RB), 4.2 (WR), 3.1-3.3 (TE), 11.5 (QB) against the starter's 8.6-8.9 / 8.5-8.8 / 7.3-7.5 / 15.8:
about 60% (RB), 50% (WR), 43% (TE), 73% (QB). Real backup uplift over the starter's own ppg (earlier audit, 2021-23 / 2024-25): RB 0.36 / 0.55, WR 0.20 / 0.18,
TE 0.08-0.26. So RB backups are about right against 2021-23 and light against 2024-25; unchanged.

## B. Team structure and usage

### B1. Quarterbacks (the reported "more than 32")

| metric (per simulated week, league-wide) | real panel | sim before | sim after |
| --- | --- | --- | --- |
| QBs with a game | 24.3 (max 32) | 26.3 (p95 34, **max 36**) | 24.0 (p95 30, **max 32**) |
| QBs with 20+ attempts | 22.6 (max 31) | 25.6 (max 36) | 23.5 (max 32) |
| team-weeks with two QBs at 10+ attempts | n/a | 7.7% | 0.0% |
| passes by a team's pool QBs (mean / sd) | 32.5 / 8.4 | 35.3 / 11.4 | 32.3 / 6.8 |

The invariant is now structural: at most one QB per NFL team scores in a week (the starter, or the one fill-in while the starter is out), so a 32-team world
cannot exceed 32 and the test asserts it on every team-week.

### B2. WR / RB / TE structure

| metric | real panel | sim before | sim after |
| --- | --- | --- | --- |
| target share by rank in a team-week: WR1 / WR2 / WR3 / WR4 / TE1 / RB1 / RB2 | 32.3 / 18.0 / 8.0 / 1.9 / 17.4 / 13.8 / 3.9% | 30.6 / 16.3 / 8.1 / 3.1 / 16.0 / 13.4 / 4.9% | 30.7 / 16.3 / 8.1 / 3.1 / 16.0 / 13.4 / 5.0% |
| pool targets / rushes a team-week (mean, sd) | 27.4 (8.3) / 23.5 (8.7) | 26.9 (8.9) / 23.0 (11.6) | 26.3 (8.4) / 22.3 (10.4) |
| teams with 3+ top-36 WRs in a season (by ppg, 8+ games) | 1.3% | 4.4% (max 4) | 3.2% (max 4) |
| teams with 3+ top-36 RBs | 0% | 3.8% (max 5) | 3.0% (max 5) |
| mean fantasy-relevant WR / RB / TE / QB per team | 1.12 / 1.12 / 0.56 / 0.75 | 1.11 / 1.10 / 0.56 / 0.77 | 1.11 / 1.09 / 0.56 / 0.76 |
| group points over the preseason projection sum, RB: mean / cv / p50 / p90 / p90:p50 | 0.85 / 0.30 / 0.88 / 1.15 / 1.31 | 0.84 / 0.39 / 0.81 / 1.18 / 1.45 | 0.80 / 0.32 / 0.79 / 1.07 / 1.35 |
| WR | 0.82 / 0.25 / 0.81 / 1.10 / 1.36 | 0.83 / 0.27 / 0.82 / 1.12 / 1.38 | 0.81 / 0.24 / 0.81 / 1.06 / 1.31 |
| TE | 0.87 / 0.36 / 0.84 / 1.28 / 1.53 | 0.83 / 0.46 / 0.80 / 1.25 / 1.58 | 0.80 / 0.41 / 0.79 / 1.19 / 1.52 |
| QB | 0.69 / 0.39 / 0.70 / 1.01 / 1.45 | 0.66 / 0.35 / 0.68 / 0.93 / 1.37 | 0.65 / 0.35 / 0.66 / 0.92 / 1.38 |

Reading: the usage budgets (shares, targets, rushes) were already right in aggregate. What was wrong is the *tail of one team's group*: a team's RB group
could run 1.5-1.7x its baseline (real p99 1.48, sim 1.73), which is how a scrub gets a job without anyone losing one. "Three WRs on a good offense, one or two
elsewhere" holds: relevant WRs per team 1.1 on average, 3+ in 3.2% of team-seasons (real 1.3%), 4 in 0.3%.

### B3. Season-level upside by projection tier (who can "break out")

Season ppg of RB/WR/TE with 8+ games, by preseason projection (real n = 167 / 168 / 128 / 113; sim n about 6,600 / 5,700 / 5,000 / 3,600):

| projection | source | p50 | p90 | p97 | p99 | max | >= 8 ppg | >= 10 ppg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.5-3 | real | 2.3 | 5.7 | 7.3 | 8.1 | 11.3 | 1.2% | 0.6% |
| | sim before | 1.7 | 5.5 | **10.0** | **14.1** | **26.8** | 4.9% | **3.0%** |
| | sim after | 1.7 | 5.2 | 7.8 | 9.7 | 15.2 | 2.8% | 0.8% |
| 3-4.5 | real | 3.2 | 7.9 | 10.0 | 11.0 | 14.2 | 7.8% | 3.9% |
| | sim before | 3.2 | 8.4 | 12.8 | 16.4 | 29.4 | 11.2% | 6.4% |
| | sim after | 3.2 | 7.7 | 10.3 | 12.5 | 17.0 | 8.9% | 3.6% |
| 4.5-6 | real | 5.4 | 10.7 | 13.0 | 15.0 | 16.0 | 25.7% | 12.4% |
| | sim before | 4.7 | 9.5 | 12.9 | 16.0 | 23.8 | 17.1% | 8.5% |
| | sim after | 4.7 | 9.0 | 11.4 | 13.1 | 18.5 | 14.9% | 6.2% |

Breakouts, per season of a 12-team league (finish top-24 RB/WR, top-12 TE/QB from a preseason rank beyond 50 / 60 / 20 / 24 by projection):

| position | real panel | before | after |
| --- | --- | --- | --- |
| RB top-24 from rank > 50 | 0.8 | 1.89 | 1.21 |
| WR top-24 from rank > 60 | 1.8 | 2.49 | 1.61 |
| TE top-12 from rank > 20 | 2.4 | 2.93 | 2.50 |
| QB top-12 from rank > 24 | 0.8 | 0.97 | 0.95 |
| 30+ place riser into the top 36, RB / WR / TE per season | 2.2 / 6.2 / 2.6 | 3.92 / 6.62 / 2.46 | 3.08 / 5.78 / 2.02 |

Real values are lower bounds (the panel only holds players with an ADP or a 6+ ppg projection: a true unknown is not in it); the product owner's rule of thumb
of "2-4 RB/WR top-24 finishes a year from ADP > 200" is consistent with the after column (RB 1.2 + WR 1.6).

### B4. Tracing Isaiah Castillo (2031 offseason, S6)

His save is not in the repo, so the trace is statistical. His projection (1.9 ppg, ADP 482) puts him in the 0-3 ppg tier. Reproduced in the harness (`CIN`,
seed 3 season 1): projection 2.0, **20.2 ppg** over 13 games (natural role-promotion product 2.15 on top of a solid season whose normal draw was near
its truncation), RB1 on the same team projected 18.3 and scoring 16.2, RB3 4.0 -> 3.2: a team RB group of 39.6 ppg against a baseline of 24.3. His
weekly 5-38 is ordinary weekly variance (`player-model-6` is right in the single game). The cause mix over every deep riser (RB 30+ place risers, 40 seeds x 3
seasons, before): natural promotion with no injury ahead 38%, breakout story 25%, solid-season luck 21%, injury cover 15%. In real life the riser is almost
always a depth-chart event (the 2021-25 risers to the top 24 from a sub-6 projection were 4.6 -> 12.6, 5.6 -> 11.7, 6.0 -> 12.9, 6.3 -> 10.7 ppg, three of four with
the starter ahead out or collapsing); the model's season story was calibrated against the real *distribution* of actual / projection, which already contains
those events, and then team roles added injury cover on top.

## C. What changed (`world_v` 1; `modules/sim/game_usage.py`, `game_engine.py`, `game_eval.py`, `game_dynasty.py`)

1. **A bench QB does not play.** `Evaluator.role` returns a `backup` role with scale 0 and no added points; `run_week` skips a `backup` player (no draw: the
   stat streams are per (week, player), so nothing else moves). He is the starter's insurance and plays when the starter is out (the existing one-fill-in
   rule). UI: the row shows "Backup" with a 0.0 projection; no endpoint changes.
2. **Group usage cap** (RB / WR / TE, per NFL team and week). `game_usage.group_factors` computes the group's public baseline (the same depth chart and roles
   at the frozen preseason projections) and the hidden expected points of the healthy members. If the hidden total passes `USAGE_CAP x baseline` (RB 1.12,
   WR 1.18, TE 1.35), every member's role (scale and added points) is scaled by cap / total: the breakout is paid for by his teammates pro rata, never created.
   Caps fitted so the simulated season-level group-over-projection upper tail matches the real panel's (table B2).
3. **Per-player tier ceiling.** Without a vacancy a RB/WR/TE's expected weekly points cannot pass `6.0 + 1.5 x projection` (plus the points a vacancy adds), the
   upper tail of the real panel by tier (table B3). A 10-ppg scrub season now needs an injury ahead of him.
4. **Dynasty depth charts follow the players** (`refresh_depth_charts`, each season from season 2: rank by aged projection, then market), and **rookies are placed by need**
   (`_need_team`: weight `exp(-sum of the team's top starters' means / (slots x reference))`, one draw like the uniform pick it replaces).
5. **Gate.** `settings.world_v` (`WORLD_VERSION = 1`), serialized only when set, read nowhere else. A save without it keeps bench QBs playing, no caps, static
   depth charts and uniform rookie teams. Tests (`tests/test_sim_world_v.py`): gate / serialization / round trip; old-save golden digests (redraft and 3-season
   dynasty, `player_model-player-model-5` and `-6` ids as a save records them, captured on origin/main `5a68a6fe` and reproduced); the new world is deterministic and
   differs; at most one QB per team-week and at most the number of teams per week; backup QB projection 0; a scrub's breakout is capped and the group total never
   passes its cap (usage shares sum), a vacancy lets a scrub score, normal groups and QB/K/DEF untouched; depth charts equal the projection order every season and
   stay static without the flag; rookies go where there is need; injury-rate bands on the model.

## Before / after, whole games

`realism_sweep seasons` (4 seeds each, 12 teams unless noted; before = `--world-v 0`):

| metric | before | after |
| --- | --- | --- |
| team score per week, 12-team PPR / superflex / 10-team PPR | 101.9 / 115.2 / 107.0 | 100.4 / 113.5 / 104.7 (about -1.5% to -2.2%) |
| team weekly sd (12-team PPR) | 22.4 | 22.2 |
| win% sd / PF rank vs wins rho (12-team PPR) | 0.148 / 0.68 | 0.142 / 0.66 |
| best / worst wins of 14 (12-team PPR) | 10.5 / 3.5 | 10.25 / 3.75 |
| slot means QB / RB / WR / TE (12-team PPR) | 15.8 / 14.5 / 14.3 / 9.3 | 15.9 / 14.0 / 14.1 / 9.3 |
| week 1 -> week 13 team score | 111.2 -> 95.7 | 110.0 -> 98.2 |
| ADP-finish Spearman QB / RB / WR / TE (real 0.56 / 0.81 / 0.82 / 0.76) | 0.50 / 0.82 / 0.87 / 0.84 | 0.45 / 0.86 / 0.89 / 0.85 |
| ADP top-12 finishing top-12, RB (real 0.58) | 0.69 | 0.79 (0.66 -> 0.73 with 8 seeds, usage rules on vs off) |
| injuries per 100 games QB / RB / WR / TE (`injury_per_100_games`) | 10.7 / 8.3 / 7.6 / 8.5 | 10.8 / 8.3 / 7.6 / 8.5 |

`tail_report` (whole-game weekly scores of the starters' pool, 4 games, player-model-6 tail intact):

| position | mean before / after | p99 | max | share over 40 |
| --- | --- | --- | --- | --- |
| QB | 15.0 / 15.3 | 34.5 / 34.9 | 43.4 / 43.4 | 0.15% / 0.15% |
| RB | 8.0 / 7.6 | 36.9 / 36.2 | 52.1 / 52.1 | 0.68% / 0.54% |
| WR | 7.0 / 6.9 | 32.6 / 32.1 | 47.4 / 47.4 | 0.20% / 0.16% |
| TE | 4.4 / 4.3 | 24.0 / 23.4 | 36.5 / 36.5 | 0 / 0 |

`dynasty_report --seeds 3 --seasons 10` (season 1 / 5 / 10): team score 101.3 / 94.8 / 91.4 -> 99.5 / 94.4 / 89.2; top-12 QB / RB / WR / TE ppg at season 10
23.2 / 18.7 / 18.9 / 11.8 -> 23.5 / 18.9 / 18.7 / 11.8; rank-24 RB / WR ppg at season 10 11.3 / 11.9 -> 10.5 / 12.2; QBs in the pool 41 -> 41 (so the extra QBs
exist, as backups); weekly max score 51.5 -> 49.3; share over 40 0 -> 0.

## What remains (not fixed, and why)

- **Injury statuses and play-through** (finding 7) need product work on both clients and in the AI managers.
- **Hazards by position, age and workload**: QB (+15%) and 31+ (+17% relative) are slightly high against the panel; RB should be above WR/TE per published
  figures. A change needs a frozen copy of player-model-6 and a new id (`player-model-7`) to keep old saves identical; the panel cannot arbitrate (benching washes out
  position effects), so I did not move constants on recollection. A first candidate: `hazard_pos` QB 1.2 -> 1.0, `hazard_age` 0.30 -> 0.22, RB 1.05 -> 1.25, rescaled to keep games lost.
- **RB ADP predictability** was already above real (top-12 hit 0.69 vs 0.58) and moves to 0.79 here with fewer deep risers; RB top-12 busts (role loss, injuries) are
  too rare. That is a model-level issue (player-model-7), not an engine one.
- **Cross-group budgets** (RB carries vs QB scrambles, targets between RB and WR) are not modelled; each position group is capped alone.
- **Group-cap side effect**: team RB group mean falls to 0.80 of its projection sum (real 0.85; before 0.84), team scores fall 1.5-2.2%, rank-24 RB ppg in the long dynasty
  falls 8%. Raising `USAGE_CAP["RB"]` trades some of finding 3 back for scoring.
- **Real yardsticks are pool-limited**: the panel excludes unknowns, so "real" deep-riser counts are lower bounds.

## Reproduce

```
python -m modules.sim.calibration.injury_usage_report --real                         # real panel yardsticks
python -m modules.sim.calibration.injury_usage_report --seeds 40 --seasons 3 --world-v 0   # before
python -m modules.sim.calibration.injury_usage_report --seeds 40 --seasons 3 --world-v 1   # after
python -m modules.sim.calibration.realism_sweep seasons --seeds 4 --world-v 0|1
python -m modules.sim.calibration.tail_report --games 4 --world-v 0|1
python -m modules.sim.calibration.dynasty_report --seeds 3 --seasons 10 --probes "" --world-v 0|1
```

Tuning knobs for a run: `--cap RB=1.12,WR=1.18,TE=1.35`, `--tier 6.0,1.5`. Nothing reads `data/players.db`.
