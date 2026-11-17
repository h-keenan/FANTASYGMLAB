# Realism and advice-logic audit 2: FantasyDesk and Fantasy Sim (2026-11-16)

Ask (product owner): an end-to-end realism and advice-logic audit for both FantasyDesk and Fantasy Sim, aimed at realistic logic that produces good, multi-factor
advice. Standing rule applied throughout: every recommendation should weigh several real factors (context, competition, need, posture, schedule, injuries,
value) and say why, and any single-rule shortcut is flagged. Run on `origin/main` after `2026-11-sim-desk-logic-realism-audit.md` (read first; its findings are
not repeated: verdict bands, one playoff-odds number, waiver label meanings, locked-player advice, QB `vorp_v`, kicker `pos_v`, `incumbent_v`, `defense_v`,
`injury_v`, `advice_v`, `stability_v`).

Evidence rules: Desk repros use synthetic fixtures and seeded leagues (no network, never `data/players.db` except one read-only column count). Sim numbers come from
headless runs on the committed 2025 panel pool (`modules/sim/calibration`), never the real database. "Real" means the committed 2021-25 panel
(`modules/sim/calibration/data/panel.json.gz`). Real samples for top-12 cohorts are 35-60 per position, so the intervals printed with them matter.

Severity: P0 = wrong or unsafe answer, broken state or exploit. P1 = clearly unrealistic or inconsistent. P2 = polish.

## Delivered

| Item | PR | State |
| --- | --- | --- |
| Trade reason names a position the Needs tag and the offer do not support (the "They need a RB" case) | #2021 | merged, `eb0ad6e5` |
| Desk P0 batch: IR on roster status for pushes and team sheet, FAAB lineup-displacement, backup QB behind a Doubtful starter | #2023 | open at time of writing, merge SHA in the delivery report |
| `player-model-8`: shallower, rarer busts for top-tier players (the season low tail) | #2027 | open at time of writing, merge SHA in the delivery report |
| `stability_v 2`: flatter late-career knots, per-position outcome carry and pull (late-career decline, persistence) | #2029 | merged, `df4dd57e`, upgradable, season boundary |
| `rookie_v 1`: rookie classes sized like real ones (controllers read the league with the class in it, tapered scarcity, solved and capped depth response) | see the delivery report | upgradable, season boundary, dynasty only |

### The trade reason that named the wrong position (reported)
Partner tags NEEDS WR, NEEDS K, DEEP RB, DEEP TE; the user sends a WR and receives an RB; the verdict reason read "They need a RB and this fills it. NEEDS RB".
That string is canned in `scripts/sim_layout_playwright/simmock.mjs` (the layout and ad mock), not engine output. The real desk said only "They like how this
fits their roster" and never named a position, so the reason could not contradict the tag but also never explained itself. Fix (`pos_v 1` only, old saves
unchanged): `TradeDesk.filled_needs` reads the same `game_need.position_report` that drives the NEEDS tag and the valuation, and the reason names a position only
if it is tagged "need" for the partner and the user is sending it. The mock follows the same rule. Test: `tests/test_sim_verdict_reason.py`.

## Sim: the season variance tail (`player-model-8`)
Known open item: a QB2 collapsing to QB41, and next/this points per game p10 of 0.43-0.54 against a real 0.59-0.69. Measured with
`python -m modules.sim.calibration.season_variance_report --seeds 8 --seasons 5 --seed0 8` (12-team PPR dynasties; `--off` zeroes the new terms). The gap has three
separate sources; only the first is fixed by the model change.

**1. A star's bust is drawn from the starter's distribution (fixed, `player-model-8`).** A bust season had median 0.76 of projection, log-sd 0.37 and about 17
percent probability for every player above the reference tier, so a top-12 projected RB, WR or TE finished under 0.6 of his projection about one season in eight.
v8 ramps both the bust depth (`bust_sd_star` 0.60) and probability (`pu_star` -0.70) in over a log-tier of 0.3 (`star_tau`); starters, flex and depth players and all
rookies are untouched (rookies keep the v7 year-one bust variance, real classes bust about one time in five). Old saves keep `player-model-7`
(`player_model_v7.py`, hash-pinned, golden digests pinned) and replay identically; the model id is stored per save, so this applies to new games only and is not
upgradable on an existing game (a model change cannot be re-timed inside a played season; a season-boundary flag is proposed below for the part that can).

Top-12 projected, realized / projected points per game (hold-out seeds 9-16, 5 seasons, 480 player-seasons per position):

| Position | Real n=60: sd, p05 / p10 / p50 | Model-7 (off) | Model-8 |
| --- | --- | --- | --- |
| QB | 0.164, 0.63 / 0.66 / 0.85 | 0.212, 0.54 / 0.61 / 0.81 | 0.167, 0.59 / 0.64 / 0.81 |
| RB | 0.215, 0.68 / 0.72 / 0.93 | 0.354, 0.43 / 0.58 / 0.92 | 0.319, 0.47 / 0.65 / 0.94 |
| WR | 0.212, 0.70 / 0.73 / 0.97 | 0.347, 0.47 / 0.58 / 0.95 | 0.323, 0.50 / 0.61 / 0.94 |
| TE | 0.267, 0.58 / 0.63 / 0.91 | 0.361, 0.42 / 0.54 / 0.94 | 0.335, 0.53 / 0.62 / 0.97 |

Next / this points per game, top-12 by ppg, same NFL team, 8+ games both years (p10 / p25 / p50, share under 0.7):

| Position | Real (p10 90% interval) | Model-7 (off) | Model-8 |
| --- | --- | --- | --- |
| QB | 0.71 / 0.84 / 0.94, 10.5% (0.68-0.76) | 0.66 / 0.77 / 0.89, 14.6% | 0.68 / 0.78 / 0.90, 11.3% |
| RB | 0.60 / 0.75 / 0.86, 20.0% (0.51-0.71) | 0.47 / 0.66 / 0.81, 30.0% | 0.53 / 0.67 / 0.83, 30.7% |
| WR | 0.62 / 0.82 / 0.91, 15.0% (0.60-0.78) | 0.45 / 0.60 / 0.77, 36.3% | 0.47 / 0.62 / 0.80, 35.9% |
| TE | 0.68 / 0.74 / 0.92, 20.0% (0.60-0.72) | 0.46 / 0.60 / 0.82, 37.0% | 0.48 / 0.63 / 0.85, 34.6% |

Mean team score per week 97.5 to 98.5 (season 1 is 99.2; the star tier now scores slightly more because fewer of its seasons collapse). Stronger settings were
tried (`bust_sd_star` 0.8-0.9 with `pu_star` -1.3 to -2.0) and gave only another 0.01-0.04 on p10 while pushing team score to 99.6, so v8 keeps the conservative
values. The QB row now sits inside the real interval and RB nearly does; WR and TE are still 0.1-0.15 low.

**2. Late-career decline is too steep and too noisy (P1, `stability_v 2`, see the next section).** Top-24 by ppg, next / this by age, sim vs real (n=15-36 real per cell):

| Cell | Real p50 / p10 / sd(log) | Sim (model-8 prototype, stability_v 1) |
| --- | --- | --- |
| RB 27+ | 0.71 / 0.52 / 0.28 | 0.51 / 0.23 / 0.54 |
| WR 27+ | 0.88 / 0.62 / 0.23 | 0.70 / 0.33 / 0.48 |
| TE 27+ | 0.97 / 0.73 / 0.22 | 0.74 / 0.32 / 0.63 |
| RB / WR / TE 25-26 | 0.90 / 0.81 / 0.72 | 0.82 / 0.78 / 0.90 |

The `AGE_KNOTS_V2` shapes were fitted on ages 21-24 only, and the 0.40 per-year `REVERSION` on top of them plus the outcome carry takes a lot off a 27-year-old
star. Experiment (8 seeds, not shipped): flatter knots for ages 25 and up (RB 27 0.86 / 28 0.78, WR 27 0.92 / 28 0.89, TE 27 0.99 / 29 0.88) cut the WR share under
0.7 from 36.7 to 30.5 percent and raised medians 0.02-0.03; adding `REVERSION` 0.25 helped a little more. Proposal: age knots v3 plus a lower `REVERSION` behind
`stability_v 2` (season boundary, upgradable). The real projection-to-last-year-result correlation is 0.66-0.77 and the sim's is 0.40-0.50, so outcome carry (`OUTCOME_WEIGHT`
0.5) is probably also low; tune together.

**3. Rookie classes are about three times too strong after the first offseason (P1, `rookie_v 1`, cause isolated in the section below).** Rookies per class inside a position's top-12 by
projection: RB 3.2, WR 2.7, QB 0.9, TE 0.5 (real: RB 0.8, WR 0.0, QB 0.4, TE 0.4 per season; the generated-class audit measured 1.6 in total before `stability_v`).
The best rookie RB projects at 1.34 times the 12th-best veteran (real 0.88), the top three rookie RBs at 20.0 / 18.4 / 17.1 ppg (real 13.9 / 12.1 / 9.3), WRs
17.6 / 16.4 / 15.1 (real 12.6 / 11.6 / 10.9). Rookies with a projection of 7+ average 12.7 (RB) and 13.2 (WR) ppg against 10.3 and 9.4 real. In later seasons a quarter of the
top-12 projections are rookies, who are the most bimodal players in the model (55-59 percent breakout, 35-38 percent bust). Likely cause: the scarcity multipliers
(`_supply_response`, `_equilibrium_plan`, `_supply_mid` in `game_dynasty.py`) stack on a class-strength factor that `stability_v` pushed harder; not isolated. This is
the root of "rookies are too safe and too good" (earlier P1-9) and it inflates the top of the draft board and the dynasty market. Proposal: cap class slot
projection at the real top-rookie curve (rank-1 about 0.9 of ref12) behind a season-boundary flag (`rookie_v 1`), and re-measure the supply controller.

## Sim: late-career aging and persistence (`stability_v 2`, delivered)

Item 2 of the variance section above, implemented. Season-boundary flag (`UPGRADABLE_FLAGS["stability_v"] = (2, "season")`): new games carry `stability_v 2`; a save on `stability_v 1`
(or an earlier Realism update that took it 0 -> 1) is offered the second generation again (`game_rules.pending_flags` now counts what an earlier update already scheduled, so a flag
is never offered twice at one value but can climb); a save that never updates replays exactly as before (40 seasons x 8 seeds of `dynasty_run` on `stability_v 1` compared with
`origin/main` before the change: projections, weekly team points, champions and every player's games identical).

What changed (`stability_v >= 2` only; `aging.py`, `season_outcomes.py`, `game_dynasty.py`):

* **`AGE_KNOTS_V3`** for RB, WR and TE (QB, K and DEF keep the v2 knots): flatter from 25 on (RB 27 0.78 -> 0.83, 28 0.70 -> 0.75; WR 27 0.85 -> 0.94, 28 0.82 -> 0.92, 30 0.75 -> 0.85; TE 27 0.95 -> 1.01, 29 0.80 -> 0.92).
  Early career is trimmed a little (RB 22 1.28 -> 1.18, 23 1.08 -> 1.04, TE 23 1.27 -> 1.20) because the stronger carry below keeps a young player's breakout, and
  the realized ratio of 22-year-olds has to stay on the panel's (RB 22 1.09, TE 23 1.10-1.15; the panel has 1.07 and 1.14).
* **A stronger, per-position outcome carry and a lighter pull** (`OUTCOME_WEIGHT_V2`, `REVERSION_V2`). Stability_v 1 had one weight (0.5) and one pull (0.40) for every position. The carry now follows
  the persistence the panel shows per position (QB 0.7, RB 1.0, WR 0.8, TE 0.7) and the pull is set per position so each position's top 12 and depth stay on the season-1 level (QB 0.15, RB 0.10, WR 0.45, TE 0.35).
  The audit's first guess (REVERSION 0.25 everywhere, weight 0.5) was run first: it left the persistence at 0.43-0.46 and the late-career medians 0.05-0.10 short.

Measured with `python -m modules.sim.calibration.dynasty_tables --seeds 8 --seasons 10 --seed0 8` (new harness; 12-team PPR dynasties, headless, seeds 9-16 are hold-out: nothing was tuned on them;
the design seeds were 1-8, a third set 17-24 gave the same picture). "Before" = `--flags '{"stability_v": 1}'`.

Late career, hold-out seeds 9-16, top 24 by points per game, next / this ppg, same NFL team, 8+ games both years (p50 / p10 / sd of the log; real n = 14-27 per cell):

| Cell | Real | Before (stability_v 1) | After (stability_v 2) |
| --- | --- | --- | --- |
| RB 25-26 | 0.90 / 0.63 / 0.22 | 0.82 / 0.49 / 0.39 | 0.90 / 0.58 / 0.36 |
| RB 27+ | 0.71 / 0.52 / 0.28 | 0.64 / 0.30 / 0.48 | 0.76 / 0.47 / 0.35 |
| WR 25-26 | 0.81 / 0.58 / 0.25 | 0.76 / 0.43 / 0.42 | 0.88 / 0.55 / 0.33 |
| WR 27+ | 0.88 / 0.62 / 0.23 | 0.65 / 0.32 / 0.51 | 0.78 / 0.45 / 0.40 |
| TE 25-26 | 0.72 / 0.50 / 0.48 | 0.87 / 0.46 / 0.53 | 0.96 / 0.42 / 0.61 |
| TE 27+ | 0.97 / 0.73 / 0.22 | 0.78 / 0.38 / 0.56 | 0.89 / 0.43 / 0.52 |

Top 12 by ppg, next / this (p10 / p50, share under 0.7; real n = 35-40):

| Position | Real | Before | After |
| --- | --- | --- | --- |
| QB | 0.71 / 0.94, 10.5% | 0.69 / 0.92, 11.5% | 0.72 / 0.95, 7.6% |
| RB | 0.60 / 0.86, 20.0% | 0.52 / 0.82, 31.7% | 0.58 / 0.87, 25.8% |
| WR | 0.62 / 0.91, 15.0% | 0.46 / 0.79, 36.0% | 0.53 / 0.82, 31.2% |
| TE | 0.68 / 0.92, 20.0% | 0.49 / 0.85, 31.9% | 0.55 / 0.89, 25.3% |

Persistence (correlation of a top-24 player's projection change with last season's realized / projected result): real RB 0.77, WR 0.66, TE 0.73; before 0.48 / 0.46 / 0.39; after 0.63 / 0.52 / 0.54.
The sim's number is measured on games played (weekly noise in the result, like the panel's); on the season story alone (`tests/test_sim_stability_v.py`, no games) it goes from 0.51 to 0.76, inside the real band.

Balance over ten seasons (hold-out seeds 9-16; projection at rank 12 and 24 of each position, mean team points per week). Year 10 is as strong as year 1 and no position drifts more than the real years differ
among themselves (RB 12th: 13.8 to 17.1 over 2021-25), but with the old rookie controllers still in place the top of QB and RB drifts up (QB 12th 20.3 -> 22.8): `rookie_v` (next) is the half that removes it.

| Season | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Team points per week, before | 99.4 | 100.5 | 99.6 | 97.3 | 95.7 | 96.9 | 96.7 | 98.4 | 99.7 | 98.1 |
| Team points per week, after | 99.4 | 102.4 | 101.9 | 101.5 | 100.6 | 100.2 | 98.3 | 99.3 | 101.2 | 100.0 |
| RB12 before / after | 16.2 / 16.2 | 18.9 / 17.8 | 16.9 / 17.8 | 16.1 / 17.1 | 15.4 / 17.3 | 15.8 / 16.8 | 16.0 / 16.8 | 15.9 / 16.8 | 16.3 / 17.4 | 15.9 / 17.1 |
| WR12 before / after | 15.3 / 15.3 | 15.8 / 16.2 | 16.2 / 16.4 | 15.9 / 16.3 | 15.8 / 16.3 | 15.8 / 16.3 | 16.0 / 16.0 | 15.9 / 15.9 | 16.0 / 16.0 | 16.2 / 16.6 |
| TE12 before / after | 9.2 / 9.2 | 9.0 / 10.0 | 9.2 / 9.9 | 9.5 / 10.5 | 9.4 / 10.7 | 10.0 / 10.2 | 9.7 / 10.4 | 9.7 / 10.5 | 9.6 / 10.0 | 9.3 / 9.8 |
| RB24 before / after | 12.7 / 12.7 | 13.9 / 13.2 | 13.6 / 13.2 | 13.1 / 13.2 | 12.7 / 13.1 | 12.9 / 13.4 | 12.6 / 12.9 | 12.9 / 12.8 | 13.4 / 13.2 | 12.9 / 13.2 |
| WR24 before / after | 13.7 / 13.7 | 13.2 / 14.1 | 13.0 / 13.8 | 13.2 / 13.6 | 13.4 / 13.6 | 13.2 / 13.8 | 13.3 / 13.6 | 13.3 / 13.5 | 13.5 / 13.4 | 13.1 / 13.8 |

Still open (not reachable by the age curve and carry, and not changed here):

* The log sd of next / this for 27+ (0.35-0.52 against 0.22-0.28 real) and the share under 0.7 at the top 12 (25-31% against 15-20%) are mostly the season story's own spread (`season_multiplier`, sd 0.26-0.47 for RB and TE
  veterans, a player-model topic like model-8's star bust), not the projection change (its sd is 0.19-0.27 and now follows the result). A model change cannot be re-timed inside a played season, so it is not part of this flag.
* WR and TE 27+ medians are 0.78 / 0.89 against 0.88 / 0.97; flattening the knots further lifted the WR and TE levels past the season-1 pool, so the remaining gap is left as it is. TE 25-26 (real 0.72, n = 14) is the cell with the
  thinnest panel sample and is not a target.
* Persistence on games played is 0.52-0.63 against 0.66-0.77. The carry reads the season's story, not its weekly noise, which the panel's projections also saw; a higher weight only widened the projection spread.

Tests: `tests/test_sim_stability_v.py` (gate and serialization for 0 / 1 / 2, the v3 knots against v2 and earlier, the per-position carry, a digest pin that a `stability_v 1` pool is unchanged, the persistence band, late-career ratios against `stability_v 1`, ten-season
stationarity under v2, and an end-to-end 1 -> 2 offseason upgrade that replays to the same digest), `tests/test_sim_realism_update.py` (a flag that gets a newer generation is offered again and never twice at one value).

## Sim: rookie class strength (`rookie_v 1`, delivered)

Item 3 of the variance section above, implemented and the cause isolated. Season-boundary flag, dynasty only (`UPGRADABLE_FLAGS["rookie_v"] = (1, "season")`; new dynasties carry `rookie_v 1`, older saves and non-dynasty games 0
and replay exactly as before: 80 seasons (8 seeds x 10) of `dynasty_run` with `rookie_v 0` compared with the build before this change: projections, weekly team points, champions and every player's games identical;
digest pin in `tests/test_sim_rookie_v.py`). It sits on the stability rules (`rookie_sized` needs `stability_v 1+` and the league-anchored class) and is measured on top of `stability_v 2`.

### Cause (isolated)

Ablation on `origin/main` before `stability_v 2` (8 seeds x 5 seasons, `SUPPLY_BAND` / `MID_BAND` pinned to (1, 1) through the harness; rookies per position top 12 after the first offseason, best rookie RB against the 12th veteran):

| Variant | RB | WR | QB | TE | best RB / 12th veteran |
| --- | --- | --- | --- | --- | --- |
| Real panel 2021-25 | 0.8 | 0.0 | 0.4 | 0.4 | 0.91 |
| As shipped (both controllers) | 3.59 | 2.59 | 0.64 | 0.62 | 1.37 |
| `_supply_response` off | 2.88 | 1.97 | 0.56 | 0.41 | 1.28 |
| `_supply_mid` off | 2.53 | 1.56 | 0.41 | 0.50 | 1.37 |
| Both off (the slot curve alone) | 1.16 | 1.00 | 0.19 | 0.19 | 1.10 |

The slot curve itself is calibrated (`rookie_audit`: 1.6 rookies per class in a position's top 12 against 1.6 real, class rank 1-6 median 0.87 against 0.88). The excess is the two scarcity controllers, and they are wrong by construction, not just
strong: they compare the veterans AFTER aging and retirement but BEFORE the class arrives with the season-1 pool, and the season-1 pool is a finished league that already contains its rookies. A position's pre-class pool therefore always reads "short"
(seed 3, ten seasons: the veterans' top 36 RB average 12.1 / 13.9 / 13.2 / 13.6 / 12.9 / 12.5 against the season-1 pool's 14.6 every offseason, `_supply_response` RB 1.36 / 1.08 / 1.18 / 1.12 / 1.23 / 1.29,
`_supply_mid` RB 2.2 / 1.13 / 1.59 / 1.42 / 1.64 / 1.78), and the class is asked to refill that gap on top of the class the slot curve already writes. `stability_v` amplified it twice: the middle-tier controller was added with it, and the steep late-career decline plus
the 0.40 pull kept the veterans' level low, so the controllers never saw the gap close (the stable level they held was an inflated class, not a stable league). `stability_v 2` (previous section) removes much of the second part on its own: RB top 12 3.15 -> 1.64, WR 2.58 -> 0.62, QB 1.72 -> 1.56.
Taking the controllers' reading alone (like for like, nothing else) only moved RB 3.59 -> 2.56: with the old decline the league was genuinely short, so the depth had to be answered separately (point 4 below). The final flag also stands on its own on a `stability_v 1` save (hold-out seeds 9-16: rookies in a position's top 12 0.74 RB / 0.68 WR / 0.49 QB / 0.24 TE, best rookie RB 1.01, team points 99.4 -> 98.2 over ten seasons, RB 12th 16.2 -> 14.7), so the two upgrades can be taken in either order.

### What `rookie_v 1` does (`game_dynasty.py`)

1. **The controllers read the league with the class in it** (`_class_aware_supply`): the veterans plus the class at neutral strength (slot curve x class factor) against the season-1 pool, so a full league draws no extra and a thin one does.
2. **The class is sized against this year's 12th veteran** at each position (the yardstick the real classes were measured against), not the season-1 pool's.
3. **Scarcity does not make the best rookies better than a real class's best** (`_scarcity`): the top-level response tapers from none at slot 1 to full at slot 24 (quarterbacks, whose class is one to three players, are exempt).
4. **The depth response is solved, not nudged, and capped** (`_depth_response`): the smallest multiplier on the class's middle slots (none through slot 10, full from slot 20) that brings the ranks a roster keeps under its starters back to the season-1 level, within `MID_BAND`, and never lifting a rookie past 0.8 x the 12th veteran:
   depth comes from usable players drawn out of the middle of the class, not from stars. A proportional step for this tier left RB 24th about 10 percent short in every ten-season run; the solve closes it.

Measured with `python -m modules.sim.calibration.dynasty_tables --seeds 8 --seasons 10 --seed0 8` (hold-out seeds 9-16; design seeds 1-8 and a third set 17-24 give the same picture). Rookies after the first offseason, per season, `stability_v 2` on both sides:

| | Real 2021-25 | stability_v 1 (before both) | stability_v 2, rookie_v 0 (#2029) | rookie_v 1 |
| --- | --- | --- | --- | --- |
| QB in position top 12 / top 24 | 0.4 / 1.0 | 1.72 / 2.57 | 1.56 / 2.48 | 0.31 / 2.63 |
| RB in position top 12 / top 24 | 0.8 / 1.4 | 3.15 / 5.07 | 1.64 / 3.78 | 0.60 / 3.96 |
| WR in position top 12 / top 24 | 0.0 / 0.4 | 2.58 / 4.56 | 0.62 / 1.62 | 0.47 / 1.79 |
| TE in position top 12 / top 24 | 0.4 / 1.4 | 0.58 / 2.03 | 0.22 / 0.97 | 0.22 / 1.50 |
| Best rookie / 12th veteran, QB / RB / WR / TE | 0.97 / 0.91 / 0.82 / 0.99 | 1.18 / 1.38 / 1.23 / 0.93 | 1.13 / 1.10 / 0.94 / 0.74 | 0.93 / 1.00 / 0.97 / 0.82 |
| Top three projected rookies, RB (ppg) | 13.9 / 12.1 / 9.3 | 20.3 / 18.2 / 16.4 | 17.6 / 15.9 / 14.5 | 16.2 / 13.8 / 12.1 |
| Top three projected rookies, WR (ppg) | 12.6 / 11.6 / 10.9 | 18.5 / 16.9 / 15.4 | 15.0 / 13.2 / 11.9 | 15.9 / 13.8 / 12.5 |
| Class rank 1-12 busts (under 0.6 of the projection) | 16% | | 22% | 21% |

Top-12 intrusion is now at the real rate (1.6 rookies per class in all, 1.6 real; it was 8.0 before `stability_v 2`) and the best rookie is about the 12th veteran. The top-24 count is not moved by this flag (RB 3.96, QB 2.63 against 1.4 / 1.0 real): the depth response deliberately puts
usable players in ranks 13-24 (that is what holds the league's depth), capped at a solid starter. The owner's top-12 bust rate stays about one in five (21-23 percent in every set, 14-26 asserted in the test).

Balance over ten seasons (hold-out seeds 9-16, team points per week and projections at rank 12 / 24). Year 10 is as strong as year 1 (99.4 -> 100.5) and no position's top 12 drifts out of the range the real years span (RB 12th 13.8-17.1, WR 14.2-17.1, QB 19.7-21.9, TE 7.8-10.8, 2021-25):

| Season | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Team points per week, stability_v 1 | 99.4 | 100.5 | 99.6 | 97.3 | 95.7 | 96.9 | 96.7 | 98.4 | 99.7 | 98.1 |
| Team points per week, stability_v 2 | 99.4 | 102.4 | 101.9 | 101.5 | 100.6 | 100.2 | 98.3 | 99.3 | 101.2 | 100.0 |
| Team points per week, + rookie_v 1 | 99.4 | 101.4 | 105.1 | 102.5 | 101.7 | 103.7 | 100.8 | 101.0 | 100.0 | 100.5 |

Projections at rank 12 (QB / RB / WR / TE), season 1 -> season 10 with `rookie_v 1`: 20.3 / 16.2 / 15.3 / 9.2 -> 18.7 / 16.6 / 16.5 / 10.2; at rank 24 (RB / WR / TE): 12.7 / 13.7 / 7.3 -> 13.0 / 13.9 / 7.3.

The third set (seeds 17-24) reads the same (team points 101.3 -> 100.6; top-12 rookies 0.42 QB / 0.50 RB / 0.43 WR / 0.29 TE; best rookie 0.99 / 0.96 / 0.96 / 0.85; bust 21 percent), and the design set 100.2 -> 101.4.

Still open: QB 12th is the one level that sits lower (20.3 -> 18.7, real years 19.7-21.9): the 33-QB harness pool has no depth to draw replacement quarterbacks from, so this is partly a harness artefact, and quarterback retirement is an `aging_v` topic. The late-career and persistence tables of the `stability_v 2` section are unchanged by this flag.

Tests: `tests/test_sim_rookie_v.py` (gate, serialization and the stability dependency, the scarcity taper and the capped depth response, a digest pin that a `rookie_v 0` pool is unchanged, class sizing against `rookie_v 0`, the bust rate, ten-season stationarity, and an end-to-end offseason upgrade that replays to the same digest);
`tests/test_sim_realism_update.py` (`rookie_v` in the old-save flag list and the dynasty-only exclusions).

## Fantasy Desk findings (trace of every advice surface; repros on fixtures)

### P0 (fixed in #2023)
1. **Push injury and lineup-lock alerts never saw IR/PUP recorded on roster `status`** (`push_triggers.py`, `team_sheet.py`). A star RB on "Injured Reserve" with a blank
   injury designation produced no push; a bench WR who was "Out" did. The in-app Alerts feed already passed both fields.
2. **FAAB "would start" was inflated by flex slots** (`faab.py`). 1 TE + 2 FLEX counted as 3 TE slots, and a roster with fewer players than slots "would start" anyone, so
   11 rivals with two good TEs each "needed" one (x1.5 starter bid, x1.6 competition bid, "11 teams need a TE"). Now a lineup is built (dedicated slots, then flex from what is
   left; superflex and OP take any of QB/RB/WR/TE) and a candidate starts only if he improves it.
3. **A QB behind a Doubtful starter was projected at 20 percent** (`player_projections._role_adjustment`), so a Doubtful starter (p_play 0.15) plus his backup produced
   about 35 percent of a QB. The share is now `max(0.2, 1 - starter p_play)`.

### P1 (owner approved; delivered status in the "Desk P1 delivery" section below)
- **Win probability counts an unmodeled starter as 0 points and a bye starter as "unavailable"** (`matchup_win_probability._starter_distribution`). One starter with no
  history moves a mirror matchup to 36.6 percent (true 50); an Out starter is a known zero while a bye starter is not. Fix: treat bye as a known zero, impute an unmodeled
  starter at the position's replacement mean with the usual variance, keep the coverage flag.
- **FAAB raises the bid for rivals who cannot pay** (`faab.py` competition block). Five needy rivals with $1 left take a $12 bid to $19. Count a rival only if his budget covers
  the pre-competition bid; add the richest needy rival's budget as a bid-to-win ceiling.
- **FAAB ignores weeks left and waiver priority.** A starter RB bids $11 in week 3 and week 14; `waiver_position` is read nowhere. Add a late-season urgency term and say where the
  user sits in rolling / reverse-standings orders.
- **Add / Stash / Watch is blind to posture, league format and the candidate's own injury** (`waivers_logic.py`, `rank_priority_add_candidates`). An Out RB with score 5000
  ranks #1 "Add, fills a real need"; the posture clause reads a row field nothing sets; "Stash" fires in redraft on age alone. Pass posture and format, read the candidate's
  `injury_level`.
- **The same waiver question is answered three ways.** The Waivers page (needs model, posture, projections) versus the Today tile, league glance, push reminder and the trade-idea
  waiver guardrail (legacy rank-by-list, neutral posture). Today can name a different top add than Waivers; a trade card can say "a stronger option is on waivers" for a player
  Waivers would not list. Pass the same `needs_model` and `played_ids` at the four call sites.
- **No role change for RB/WR/TE** (`_role_adjustment` is QB-only): a handcuff next to an Out RB1 is projected at his old, low usage in the week he matters most. Add a depth-chart
  and teammate-availability role multiplier, labeled uncalibrated like the backup-QB layer.
- **GM Plan flags Roster Age as a weak spot for every stance** (`gm_plan.py`: oldest roster ranks last) and a declared Competing team at 0 percent playoff odds still reads
  "upgrade immediate production". Make the age flag stance-aware; condition the stance text on clinched / eliminated.
- **The trade season window ignores playoffs and elimination** (`trade_grade.season_window`, 17 equal weeks). Weight weeks by playoff-reaching probability; zero after elimination.
- **Start/sit lean disagrees with the planner's headline** (`start_sit_range.lean` hard cuts at 0.30 / 0.70 and a 0.5 ratio versus an expected-points maximizer). Derive the lean from
  the win-probability delta already computed in `matchup_what_if` with a minimum delta.

### Desk P1 delivery

| Item | Before | After |
| --- | --- | --- |
| Win % unmodeled starter | counted as 0 points, a mirror matchup read 36.6 percent | imputed at a replacement-level week for his position (`matchup_win_probability.REPLACEMENT_WEEK`, QB 12 / RB 4.5 / WR 5 / TE 3.5 / K 7 with a wide spread), coverage still counts only truly modeled starters, the result carries `imputed_starters` and a `note` that web and mobile show under the odds; a bye starter stays a known zero, DEF/IDP stay unmodeled |

### P2
- Confidence adds points for the explanation the same module wrote (`trade_ideas._trade_confidence_context`); candidate windows are absolute points (`_value_fits`); TE premium is a
  boolean in valuation (lineup model reads the magnitude); `required_depth = starters + 1` ignores bye overlap; `live_big_plays` omits some bonuses; "less competition" wording on a
  Stash card compares wire rank, not rivals.

### Desk P1 delivery: waivers and FAAB (FAAB bids, Add / Stash / Watch, one waiver source)

| Item | Before | After |
| --- | --- | --- |
| FAAB rival affordability | five needy rivals with $1 left took a $12 bid to $19 | `FaabCompetition.needing_budgets` carries each needy rival's remaining FAAB; a rival counts only if his budget covers the pre-competition bid (none can: x0.7 and the reason says so), and the richest needy rival's budget plus $1 is a bid-to-win ceiling that is named in the reason when it binds |
| FAAB weeks left | a starter RB bid the same in week 3 and week 14 | `faab.season_urgency`: a startable add is trimmed early (down to 0.85, "N weeks left, so budget can wait") and lifted late (up to 1.30, "Only N weeks left, so unspent FAAB is worth little later"), neutral at 8 weeks left; bench adds keep the redraft late discount. Waiver priority is still not read |
| Add / Stash / Watch | an Out RB ranked #1 "Add, fills a real need"; the posture clause read a field nothing set; "Stash" fired in redraft on age alone | `waiver_recommendation` weighs the candidate's own injury (Out / Doubtful / IR never an Add, held only in a long-term format for a rebuild, a young or role-driven player; Questionable keeps the Add at Medium and says so), the stance (a contender's add "helps you now", an older short-term add is Medium for a rebuild, young upside fits a rebuild) and the league format (age alone is not a stash in redraft). The ranker stamps `roster_posture` and `league_format` on every row and never lets an Out candidate fill a need or a bigger upgrade |
| One waiver answer | Waivers, Today, league glance, the waiver push and the trade card each ranked with different inputs | `waivers_logic.shared_waiver_adds` is the single ranking source: Waivers page, Today (`select_top_waiver_opportunity`), glance, push reminder and the trade-idea waiver guardrail all pass the same need model over the same pool, the has-played gate and the stance. The trade card passes the idea's own posture and rosters |

Gaps: the Today, glance, push and trade-card surfaces build their need model from the plain valued frame, the Waivers page from its projection-adjusted bundle, so a borderline add can still differ; the scheduled waiver push has no stance in scope and ranks neutral; waiver priority is not used in FAAB.

### Inputs used and missing, by surface
| Surface | Used | Missing or wrong |
| --- | --- | --- |
| Today "Do this now" / swaps | weekly lineup, bye, Out/Q, lock, weather note | waiver tile on the legacy path (neutral posture); no depth-chart role |
| Start/sit | point estimate, range, win probability, lock | role change; lean thresholds; opponent defense is computed but deliberately not applied (2024-25 backtest) |
| Matchup win probability | per-starter variance, calibrated spread, live clock, coverage | bye / unmodeled starters; K/DEF/IDP variance |
| Waivers Add/Stash/Watch | lineup model, byes, absence, depth, roster injuries, age, wire | candidate injury, format, posture on the legacy path, playoff schedule |
| FAAB | budget, rival budgets, wire depth, trending, catalysts, scoring, TE premium, stance | rival affordability, weeks left, waiver priority, roster-spot cost |
| Trade ideas / Analyzer / Finder | lineup model, posture, partner fit, share-based bands | playoff weeks, elimination, waiver alternative on the legacy ranker |
| GM Plan | declared stance, phase, ranks, playoff odds fact, injury exposure | age flag not stance-aware; stance text not conditioned on odds |
| Team sheet / needs | need model (rank, depth, injury, wire, dynasty gap) | neutral posture outside Waivers (IR on status fixed in #2023) |
| Alerts (push) | injury, lineup lock, waiver reminder, deadline, caps | no starter / bench weighting (IR on status fixed in #2023) |
| Projections | usage baseline, scoring conversion, availability, Q factor, QB backup | non-QB role (Doubtful-starter QB fixed in #2023) |

Contradictions between surfaces: Today top add vs Waivers #1 add vs the trade card's waiver alternative; FAAB "would start" vs the card's Add / Stash label; push and team
sheet vs the in-app feed on IR (fixed); GM Plan "Roster Age weak spot" vs the declared stance; planner headline vs lean on one card.

## Fantasy Sim findings (8 instrumented 10-season dynasties, 12 teams, seeds 1-8, about 15,000 AI team-weeks, 280 AI-AI trades, 4,700 AI waiver claims; user passive)

Checked and fine: AI lineups are exactly optimal (compared with an exact DP over 6,000 random rosters across standard, superflex and flex layouts) and no AI starter was ever
injured or on bye; AI-AI trades are fair (proposer's neutral net mean +0.30, p90 absolute 6.0 on the 0-100 scale; no team left without a QB, RB, WR, TE or K; persona direction is
right); offers to the user are fair (mean -1.2, 37.5 percent favour the user); scoring and age stay stationary (AI points-for -2.5 percent over ten seasons, roster age 26.2 to 26.7);
the roster limit is never exceeded.

### P0
None in the sim engine. The nearest is an exploit (P1-1).

### P1 (proposals, flag names for the owner)
1. **Waiver priority is meaningless against the user** (`game_engine.py:305` excludes the user's queued claims from the AIs' targets). AIs would have claimed those players 397
   times in 12 seeds; in 34 percent of them the AI had the better priority. The user wins every contest. Fix: generate AI claims ignoring the user's targets and resolve all
   claims in waiver order, rotating priority. Flag `wire_v` (boundary week, about 15 lines; the old path stays when 0). Fold in P2-1 (run AI IR moves before waivers).
2. **Superflex Needs / Strength tags count starters wrongly** (`game_need.py:27-40`): QB 1, TE 2 where `Evaluator.starter_count` says QB 2. A one-QB superflex team is never tagged
   Needs QB, and `TradeDesk.need_position` reads this under `pos_v`. Use one starter-count function. Flag `need_v` (boundary now).
3. **"Need" is a bottom tercile** (`game_need.py:49`): exactly 4 of 12 teams are tagged at every position in every league, however small the gap (strength 0.76-0.88 of the median), and the
   wire alone cures every K need (best FA 28 percent better than a "need" team's kicker). Tag only an absolute lineup shortfall against the league median and what the wire adds.
   Same `need_v`.
4. **Draft advice and the AI draft stack positions the waiver AI forbids** (`POSITION_CAP` QB 3 / TE 3 in `game_draft.py:29`, `_cap` QB 2 in `game_ai_depth.py`). Auto-pick ends with three
   QBs in 11 of 12 drafts; AI QB counts are 1 / 2 / 3 = 21 / 33 / 45 percent. One shared position-cap function with a bench value of marginal lineup and bye insurance (`advice_v 2` for
   the hint and auto-pick, `ai_v 2` for the AI draft).
5. **QB holes** (4.7 percent of AI team-weeks start with an empty QB slot, 7.7 percent in superflex; one-QB teams go from 4.5 to 22.6 percent over three seasons; 76 percent of hole weeks
   had a healthy free QB that the model cannot use because a backup QB's mean is 0 under `world_v`). Part is the 33-QB harness pool. Needs the shared cap plus an AI QB2-for-bye-hole search
   (`ai_v 2`). This quantifies the deferred "AI backup-QB planning".
6. **AI posture is a fixed persona constant** (`game_setup.py:256,378`, `game_eval.py:569`, `game_block.py:35`). Contenders average 6.0 wins and 355 market value against 588-617 for rebuilders
   (seasons 4-10) and receive no sustained age edge; trades do not follow standing. Derive horizon each week from persona, rank and record, roster age, asset slope and weeks left, and use
   it for `stance_of` too. Flag `posture_v` (boundary week).
7. **User waiver suggestions pick the drop by projection alone** (`game_home.py:341`): not the lowest-worth bench player in 33 percent (redraft) and 48 percent (dynasty) of
   suggestions, ignoring depth, byes and age. Reuse the AI's cut order. View-only; no flag.
8. **Late-career decline** and **rookie class strength**: see the variance section; flags `stability_v 2` and `rookie_v 1`.

### P2
- AI waivers run before IR moves, so 382 of 2,218 AI drops cost a healthy player (mean market 11.4, p90 21). 32 percent of AI claims are kickers (34.8 percent of team-weeks carry two).
- Team draft grade is rank-forced (always one A+ and one F); derive from the lineup gap to the league mean.
- No game-time uncertainty (a healthy starter essentially always plays, DNP 0.0003), so floor, ceiling and insurance have no lineup consequence.
- Rare kicker rookie picks (5 of 1,500); no bye diversification in the startup draft (same-position same-bye pairs 0.74-1.28 against about 1.1 expected).

Outputs vs the real panel (ppg at rank, 8+ games; panel mean of 2022-25): RB and WR match within noise in all seasons. QB12 is 13 percent low (the 33-QB harness pool), TE1 12 percent and
TE12 10 percent low. Kicker spread is too steep (K1 +1.4, K12 -0.8; K1 to K12 5.0 ppg sim against 2.8 real), a player-model topic left alone here.

## Sim P1 batch (owner approved 2026-11-16): `wire_v`, `need_v`, `cap_v`, `posture_v`

Harness: `python -m modules.sim.calibration.realism_p1_report <table> --seeds 8 [--flags '{"wire_v": 0}']` (12-team redraft on the committed 2025 panel pool, user slot rotating, seeds 1-8).

### `wire_v 1`: the waiver wire is contested (delivered, upgradable, week boundary)

`_resolve_waivers` seeded the AI's excluded set with every player the user had queued, so the AI never wanted the user's targets and the user won every contest whatever the priority. With `wire_v 1` the AI
generates its claims exactly as before (same persona gate, same need and roster-value scoring) but ignores the user's queue, and all claims, the user's included, settle in waiver order (worst record first, so priority
rotates with the standings). The sim has no FAAB budget, so priority is the only resolver. An AI that loses a contest simply does not get the player (the old AI-versus-AI de-duplication is unchanged). Old saves keep the old
path: three redraft seasons replay to pinned digests in `tests/test_sim_wire_v.py`.

User queues the three most valuable free agents every week (312 claims over 8 seeds):

| | `wire_v 0` | `wire_v 1` |
| --- | --- | --- |
| User claim win rate | 100% | 80.1% |
| ... when the user has a top-half priority | 100% | 88.7% |
| ... when the user has a bottom-half priority | 100% | 51.4% |
| AI claims placed per game (won or lost) | 56.6 | 71.6 |

## Decisions needed (product)
1. Ship the late-career age curve and a lower `REVERSION` (`stability_v 2`)? Done as an upgradable offseason change (it changes dynasty values for 27+ players, so it is not silent); the owner may still veto the Realism update copy.
2. Cap rookie class strength (`rookie_v 1`)? Done as an upgradable offseason change (it lowers rookie pick values and the top of the draft board; real classes are far less top-heavy); the owner may still veto the Realism update copy.
3. Should the AI's posture follow standing (`posture_v`)? It makes the league feel more alive and removes the persona-decides-the-decade effect, at the cost of more volatile AI behaviour.
4. Should the user's waiver claims be contested by AIs in priority order (`wire_v`)? This ends the "queue the best FA every week" edge.
5. Desk: should the Today tile and push reminder use the same needs model and posture as the Waivers page (one answer), even if it costs a heavier computation on Today?

## Not verified
- No live screen was opened; Desk findings come from code and fixtures, Sim findings from headless runs.
- Real next / this cohorts are 35-40 per position; their p10 intervals are wide and the WR and TE targets are uncertain.
- The harness pool has 33 QBs, no defense by default and synthetic byes, so QB scarcity and bye clustering are lower bounds. No real team-week baseline exists in the panel.
- (Resolved) Rookie class strength cause and age knots v3 were isolated and validated on hold-out seeds in the `rookie_v 1` and `stability_v 2` sections above.
- The Desk P1s were reproduced on fixtures, not on a connected league.

## Reproducing
```
PYTHONPATH=. python -m modules.sim.calibration.season_variance_report --seeds 8 --seasons 5 --seed0 8          # model-8
PYTHONPATH=. python -m modules.sim.calibration.season_variance_report --seeds 8 --seasons 5 --seed0 8 --off    # model-7 behaviour
PYTHONPATH=. python -m modules.sim.calibration.dynasty_tables --seeds 8 --seasons 10 --seed0 8                                         # stability_v 2 (balance, late career, persistence, rookies)
PYTHONPATH=. python -m modules.sim.calibration.dynasty_tables --seeds 8 --seasons 10 --seed0 8 --flags '{"stability_v": 1}'            # before
PYTHONPATH=. python -m modules.sim.calibration.dynasty_tables --seeds 8 --seasons 10 --seed0 8 --flags '{"rookie_v": 0}'              # stability_v 2 without rookie_v (rookie_v 1 is the default)
pytest tests/test_sim_verdict_reason.py tests/test_faab.py tests/test_push_triggers.py tests/test_team_sheet.py tests/test_projections_v2.py
```
