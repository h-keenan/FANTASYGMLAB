# Posture coherence (DYNASTYGM_POSTURE_COHERENCE_V1): point-in-time replay, ON vs OFF (2026-11-19)

Question: does the flag shipped OFF in #2209 (injury weights never below the starter weights, multi-team Finder tank pick want 2.0 -> 2.667,
fringe pick-sale priority 6 -> 4) change what the Hub / Finder suggest for tank and rebuild teams, or how those ideas turn out?
Decision rule (owner): flip the default ON only if the replay is not negative overall and idea counts do not drop meaningfully.

**Result: no measurable effect on tank / rebuild (every outcome metric identical), idea counts not reduced (+2 multi-team ideas, +1 Finder idea). Default flipped ON.**

## Method

Harness from #2164 (`docs/audits/historical-replay/code/ideas_run.py`, see `2026-11-historical-replay.md` section 8), at `origin/main` 80c5488c, seasons **2024 and 2025**, three dates
(Aug 20, Oct 20, Dec 1), three formats (1QB, Superflex, SF+TEP), 12-team synthetic leagues, base seed, all other flags at their defaults. 18 league-dates, 216 team-dates
(25 tank, 40 rebuild, 41 fringe, 75 retool, 35 contender). Every run is executed twice on identical leagues and clocks, only `DYNASTYGM_POSTURE_COHERENCE_V1=0` vs `=1` differs
(the flag is read at import, so one process per setting; verified `INJURY_POSTURE_WEIGHTS['tank']` 0.05 -> 0.20, fringe priority 6 -> 4, tank pick want 2.0 -> 2.667 in the ON process).
Postures are identical in both runs (216/216 teams).

Four surfaces, because the flag's three changes live in different code paths:

| surface | run | what it exercises |
|---|---|---|
| Trade Hub | `generate_trade_idea_records`, 8 ideas per team | injury weights (grade path); no pick-sale term |
| Trade Finder, shop own 1st | same call with `trade_block_pick_ids` = the team's own 1st (all 216 teams) | fringe pick-sale priority, pick-sale fit |
| Trade Finder, shop top vet | `trade_block_player_ids` = highest-value player aged 26+ (the sell-a-vet case for tank / rebuild) | injury weights on the sent player |
| Multi-team (3-team) Finder | `find_three_team_ideas` per team, unbounded time budget | tank pick want 2.667 |

Outcomes are the harness's own: hindsight lineup points over the rest of the season (ROS) and ROS + next season (2024 only, 2025 has no following season), win % (ties under 3 points dropped),
partner points, playoff / title odds change (pp), market value change +1y. ON minus OFF with a 95% bootstrap interval (2,000 resamples, ideas resampled independently).
Multi-team ideas are not scored for outcomes by the harness (no 3-team scorer); only counts and which ideas appear.

## Results

### Outcome metrics, tank + rebuild teams (65 team-dates), ON vs OFF

| surface / scope | n ideas OFF / ON | ROS pts OFF -> ON (diff, 95% CI) | ROS+next 2024 | win % ROS | playoff odds pp | title pp | partner pts |
|---|---|---|---|---|---|---|---|
| Hub, all ideas | 504 / 504 | -20.32 -> -20.32 (0.00, [-6.8, +6.9]) | -21.66 -> -21.66 (n=246, 0.00) | 29.9 -> 29.9 | -2.77 -> -2.77 | -0.11 -> -0.11 | 26.6 -> 26.6 |
| Hub, pick-sale (receive picks, send players) | 296 / 296 | -38.57 -> -38.57 (0.00, [-7.3, +7.4]) | -56.66 -> -56.66 (n=148, 0.00) | 12.3 -> 12.3 | -5.21 -> -5.21 | -0.54 -> -0.54 | 41.0 -> 41.0 |
| Finder, shop own 1st (pick sale) | 518 / 518 | +38.43 -> +38.43 (0.00, [-6.3, +6.2]) | identical | identical | identical | identical | -33.95 -> -33.95 |
| Finder, shop top vet | 358 / 358 | -42.90 -> -42.90 (0.00, [-9.0, +8.4]) | -69.40 -> -69.40 (n=173, 0.00) | 19.8 -> 19.8 | -5.98 -> -5.98 | -0.56 -> -0.56 | 50.2 -> 50.2 |

Tank and rebuild separately (Hub, ideas 196 + 308; Finder pick, 198 + 320; Finder vet, 142 + 216) are also identical to the last digit on every metric and surface (diff 0.00 everywhere; the
intervals above are the uncertainty a real difference would have had to clear). Over all 216 teams the only outcome movement is in the Finder vet surface from one extra fringe-team idea
(ROS diff +0.31, CI [-5.7, +6.0]; playoff odds +0.07 pp, CI [-1.3, +1.5]), which is noise.

Hub ROS +next and the vet / pick surfaces carry the same pre-existing character as the base replay (rebuild / tank Hub ideas lose lineup points and win market value by design; Finder own-1st
sales win lineup points because a team that sells a pick for a player gets lineup help now). None of that moves with the flag.

### Idea counts per posture (ON = OFF unless shown)

| posture | teams | Hub ideas | Hub pick-sale | Finder own-1st ideas | Finder vet ideas | 3-team ideas OFF -> ON | 3-team zero-idea teams |
|---|---|---|---|---|---|---|---|
| tank | 25 | 196 | 118 | 198 | 142 | 55 -> 55 | 10 -> 10 |
| rebuild | 40 | 308 | 178 | 320 | 216 | 88 -> 88 | 15 -> 15 |
| retool | 75 | 586 | 332 | 575 | 290 | 161 -> 161 | 21 -> 21 |
| fringe_contender | 41 | 320 | 128 | 328 | 108 -> 109 | 103 -> 105 | 13 -> 13 |
| contender | 35 | 280 | 88 | 280 | 91 | 93 -> 93 | 14 -> 14 |
| **total** | 216 | 1,690 -> 1,690 | 844 -> 844 | 1,701 -> 1,701 | 847 -> 848 | 500 -> 502 | 73 -> 73 |

Ideas per team (Hub) 7.82 in both runs; zero teams without ideas. ON does not reduce Finder or Hub idea counts anywhere. 3-team ideas by team: 3 of 216 teams change count and 4 change identity
(fringe +2 ideas, one contender pick idea dropped, tank 1 pick idea added); tank and rebuild 3-team counts are unchanged (tank 2.20 per team, rebuild 2.20).

## Why the effect is nil (mechanism, confirmed in code)

* **Injury weights (change 2).** Only price per-asset injury cost for the consolidation term and the lineup-model-failed fallback; the production grade path never reads them (same finding
  as the backtest in `2026-11-posture-coherence.md`). In the replay no verdict, band or idea score moved.
* **Fringe pick-sale priority (change 5).** `trade_ideas.shop_candidate` subtracts the posture term from the package fit priority and adds it back as the user's own selection, so it cancels
  by design. Confirmed: in the Finder own-1st run `priority` differs on exactly the 328 fringe ideas, and the idea set, order, score, acceptance, and every outcome are identical.
* **Tank pick want (change 3).** Only the 3-team search reads it; tank pick want rises 2.0 -> 2.667, but in these 25 tank team-dates no cycle gained or lost a pick idea beyond the one noted above.

## Decision

Rule met: replay not negative (all tank / rebuild differences exactly zero with 95% intervals centred on zero), no idea-count drop (net +1 Finder, +2 3-team, 0 Hub).
**`DYNASTYGM_POSTURE_COHERENCE_V1` default flipped ON** (`modules/posture_model.py`, `modules/experimental_graduation.py` registry). OFF stays available as a kill switch (`=0`) and is
the review target for deletion with the 2026-12-19 flag review.

Test changes: assertions about the default only. `test_coherence_flag_off_is_the_default` became `test_coherence_flag_on_is_the_default`. The existing pre-coherence goldens
(`tests/fixtures/posture_golden.json`, unchanged, not regenerated) are now checked with the flag switched OFF in a subprocess (the flag is read at import), and the flag-OFF floor
subprocess also sets coherence OFF. `posture_golden_coherence.json` (the ON golden) is unchanged and still passes.

## Limits

* Synthetic leagues (as in the base replay): no real trade history, partner tendencies neutral, 3 dates per season, 2 test seasons. Interval widths of roughly +-6 to +-9 lineup points for tank /
  rebuild mean a true effect of that size could not be ruled out, but the effect measured is exactly zero because the idea sets are identical.
* 3-team ideas are counted, not outcome-scored. Finder shop scenarios are two canned selections (own 1st, top vet aged 26+), not every selection a user could make.
* Reproduce: `REPLAY_REPO=<repo> REPLAY_DATA=<nv/ + dp/> python docs/audits/historical-replay/code/ideas_run.py --out DIR --variant base --seasons 2024,2025` once with
  `DYNASTYGM_POSTURE_COHERENCE_V1=0` and once with `=1`; Finder modes wrap `generate_trade_idea_records` with `trade_block_pick_ids` / `trade_block_player_ids` as described above.
