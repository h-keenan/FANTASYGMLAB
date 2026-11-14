# Fantasy Sim letter grades: calibration (2026-11-14)

coridian_ (2026-11-14): inside the sim a numeric OVR, or any rank taken from the model's hidden rating, is a tell ("I just draft the
highest value players and it works"). The sim now shows Madden / 2K style **letter grades** only. Design and API: `docs/fantasy-sim-api.md`
("Letter grades"), UI: `docs/ui-patterns.md` ("Fantasy Sim letter grades"), code: `modules/sim/game_grades.py`.
Presentation only: nothing here touches the engine, the player model or saved state, so old saves replay identically
(`tests/test_sim_grades.py::test_old_saves_replay_identically_with_grades_in_the_view`).

## Scheme

- **Overall grade**: 12 bands (A+ A A- B+ B B- C+ C C- D+ D F) of `value percentile within position + noise`. Noise is a deterministic normal
  from `sha256(save seed | player | season | tag)` (never the engine's RNG): sigma 0.08 for an established player; a rookie's sigma is
  `0.07 + 0.17 * (1 - scouting confidence)` (about 0.19 fresh, 0.074 once scouts know him), and from sigma 0.12 up the row carries
  `grade_range` and a "?". Cuts (share of the position pool at or above the band): A+ 1.5%, A 4.5%, A- 9%, B+ 16%, B 24%, B- 34%, C+ 45%, C 56%,
  C- 67%, D+ 78%, D 88%, F rest.
- **Attributes** (player quick view only): position-specific (QB / RB / WR / TE / K / DEF) graded from usage shares, projection and its
  spread, age curve and injury history, each with its own noise (sigma 0.10, more for rookies). They are not derived from the hidden value and
  do not add up to the overall. Names say what the input is: the sim has no route-running or hands data and does not claim any.
- **Leak removal**: `value`, `overall`, `value_rank`, `pos_value_rank`, `adp_edge` (EDGE chip), pick `value`, `total_value`, `dynasty.picks_value`,
  retiree `market` and the trade counter's net values are gone from every response; `sort=overall` / `sort=value` order by the shown grade then
  the public projection, not by the hidden number (a deliberate change from "keep a server-side sort by the true number": a sort IS the leak).

## Grade distribution (generated league: 2025 real-panel pool, 12 teams, 18 games; % of players)

| Scope | A+ | A | A- | B+ | B | B- | C+ | C | C- | D+ | D | F |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pool ALL | 4.7 | 3.1 | 3.1 | 6.0 | 7.3 | 9.1 | 14.1 | 9.9 | 9.1 | 11.7 | 9.4 | 12.3 |
| pool QB | 9.1 | 0.0 | 3.0 | 9.1 | 3.0 | 12.1 | 9.1 | 15.2 | 9.1 | 6.1 | 6.1 | 18.2 |
| pool RB | 4.3 | 5.3 | 2.1 | 5.3 | 5.3 | 12.8 | 17.0 | 6.4 | 6.4 | 13.8 | 7.4 | 13.8 |
| pool WR | 4.8 | 2.1 | 4.1 | 6.2 | 9.7 | 6.9 | 12.4 | 11.0 | 9.7 | 9.7 | 11.7 | 11.7 |
| pool TE | 3.7 | 3.7 | 2.5 | 3.7 | 8.6 | 8.6 | 16.0 | 8.6 | 12.3 | 13.6 | 7.4 | 11.1 |
| drafted ALL | 9.0 | 5.7 | 5.8 | 11.2 | 13.5 | 15.6 | 18.4 | 8.7 | 3.5 | 3.4 | 2.0 | 3.2 |
| drafted QB | 9.1 | 0.0 | 3.2 | 9.1 | 2.7 | 12.7 | 9.1 | 16.0 | 8.4 | 6.5 | 6.3 | 16.9 |
| drafted RB | 7.3 | 8.7 | 3.7 | 9.4 | 8.6 | 20.7 | 23.9 | 6.6 | 3.3 | 4.6 | 1.7 | 1.6 |
| drafted WR | 11.4 | 4.9 | 9.5 | 14.4 | 21.9 | 13.6 | 15.6 | 6.9 | 1.7 | 0.3 | 0.0 | 0.0 |
| drafted TE | 8.9 | 8.2 | 6.0 | 8.5 | 19.9 | 16.2 | 23.9 | 4.8 | 2.9 | 0.5 | 0.2 | 0.2 |

The "drafted" rows are the players who actually get rostered: mostly B- to C+ starters with a thin elite tail, like a Madden roster.

## How informative is it (Spearman, per position, mean over 36 seeded seasons, players with 8+ games)

| Pos | grade vs ROS ppg | hidden rating vs ROS ppg | preseason projection vs ROS ppg | grade vs hidden | grade top-12 hit | hidden top-12 hit |
|---|---|---|---|---|---|---|
| QB | 0.532 | 0.552 | 0.552 | 0.964 | 0.66 | 0.66 |
| RB | 0.804 | 0.842 | 0.845 | 0.953 | 0.65 | 0.67 |
| WR | 0.808 | 0.853 | 0.853 | 0.955 | 0.52 | 0.54 |
| TE | 0.797 | 0.844 | 0.843 | 0.950 | 0.64 | 0.66 |

Real-world yardstick for the same panel (`realism_sweep real`): ADP vs finish Spearman QB 0.56, RB 0.81, WR 0.82, TE 0.76. The grade is about as good a
guide to the season as real ADP, a little below the hidden rating (about 0.04 Spearman, 0.01 to 0.02 top-12 hit rate) and **not** monotone in it
(Spearman 0.95 to 0.96: with 12 coarse bands and the noise, neighbours swap). QB is low for everyone (the panel pool's QB spread is narrow), the
hidden rating included.

## Does "draft the highest grade" win?

| Bot (user team, 12t PPR, 36 seeds, auto lineup) | wins | points for | mean finish | wins vs ADP+need (se) | PF vs ADP+need (se) |
|---|---|---|---|---|---|
| ADP + roster-need rules (public info, the baseline) | 6.06 | 1370 | 8.1 | baseline | baseline |
| highest shown grade among legal candidates | 4.44 | 1216 | 9.7 | -1.61 (0.45) | -154 (29) |
| highest shown grade within 12 ADP spots of the best | 5.42 | 1292 | 8.8 | -0.64 (0.47) | -78 (28) |
| engine auto-pick: hidden value + need (not available to a player) | 6.75 | 1411 | 6.9 | +0.69 (0.35) | +40 (23) |

No. Drafting by the shown grade **loses** to the plain ADP + need baseline (-1.6 wins, -155 points, 3.5 sigma), because a grade is position-relative:
an A at QB or TE is not worth an A at RB, so a grade-greedy drafter reaches for scarce-position stars. Even the smarter variant that
stays within 12 ADP spots of the board and only breaks ties by grade is below baseline (-0.6 wins, -78 points). The engine's own hidden-value
pick is the only thing above the baseline (+0.7 wins, 2 sigma), and a player cannot see it. This is the property the product owner asked for.

Reproduce: `python -m modules.sim.calibration.grade_report all --seeds 36` (about 25 minutes; `dist`, `corr`, `bots` run alone).

## What remains

- The draft "hint" and Auto-pick still choose with the engine's own value (changing them would change old saves); it is an oracle a player can
  click. If that is a concern, the clean fix is a new model-version gate, not a view change.
- ADP, the public preseason projection, floor / ceiling and ros_mean are still numbers (as in real fantasy). Projection tracks the hidden
  rating almost exactly in this pool (0.845 vs 0.842 vs ROS ppg), so "sort by Proj" is the real shortcut a player has; hiding it is a product call.
- The real-player quick view still fetches real-world detail for the non-numeric tabs (news is already cut); the numeric score ring, value tile and
  ranks are suppressed in the sim, other real stat tabs are as before.
