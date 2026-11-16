# Sim + Desk logic audit and sim realism audit (2026-11-16)

Ask (product owner): an end-to-end logic audit of Fantasy Sim and Fantasy Desk, plus a large realism audit of the sim. Run on `origin/main`
(`9aa567c8`). No app code is changed in this PR. Earlier audits were read first and are not repeated (see "Already covered" at the end); every
finding below is either new or a measurement of something earlier docs only asserted.

Evidence rules: every Desk finding has an executable repro in `scripts/audits/desk_logic_repros.py` (pure functions, no network, no `data/players.db`).
Every sim number comes from headless runs on the committed 2025 panel pool (never `data/players.db`): `python -m modules.sim.calibration.realism_sweep seasons|dynasty|real`
and the new `modules/sim/calibration/dynasty_run.py` + `dynasty_distributions.py` (4 dynasties x 10 seasons, 12 teams, 3 rookie rounds, 6,720 team-weeks of
box scores). Real baselines marked "panel" come from `modules/sim/calibration/data/panel.json.gz` (5 seasons); baselines marked "memory" are
from general NFL / fantasy knowledge and are not checked in this repo.

Severity: P0 = wrong answer, broken state or exploit. P1 = clearly unrealistic or inconsistent. P2 = polish.

## Findings, ranked

### P0

**P0-1. Injury text detection is negation-blind and treats any "torn" / "acl" as season-ending (Desk trade grading).**
Evidence: `modules/trade_grade.py:270` (`SEASON_ENDING_TERMS` includes `"acl"`, `"torn"`, `"rupture"`), `:341` (`any(term in detail ...)` over body part + notes + status text),
then `:340-343` sets `weeks = window.remaining_weeks`. Callers pass the player's free-text `injury_notes` (`trade_grade.py:502`, `:550`, `trade_lineup_model.py:494`,
`external_interesting_trades.py:540`).
Repro (`desk_logic_repros.py`, window = week 6, 12 weeks left):

| status | body part | notes | result |
| --- | --- | --- | --- |
| Questionable | Knee | "MRI rules out a torn ACL; day-to-day" | 12 weeks, season-ending |
| Questionable | Hamstring | "Partially torn hamstring, expected to miss 1-2 weeks" | 12 weeks, season-ending |
| Questionable | Ankle | "No ACL tear, ankle sprain only" | 12 weeks, season-ending |

Why it matters: a good-news report ("rules out ACL") prices the player as lost for the year. The trade grader then marks him down (contender weight 0.95, cap 25% of value),
so the Analyzer says "you win" on a deal where the other side is selling a healthy player cheaply, Trade Ideas can suggest buying low on an injury that is not real, and the
same estimate feeds the lineup model and the external-trades feed. This is a wrong answer on exactly the screens where users act on the number.
Fix (shared source): one injury-text parser in `modules/injury_status.py` (where the status table already lives) that handles negation ("no", "rules out", "cleared of", "not"),
"partial", and "expected to miss N weeks" (use N when present), and that returns a confidence flag. `estimate_injury_absence` consumes it; when the evidence is only a keyword,
price a mid estimate and say "possibly season-ending, unconfirmed" instead of the whole season. Add the three repro rows as tests.

**P0-2. The free-game limit can be beaten with two simultaneous requests (Fantasy Sim).**
Evidence: `modules/sim/game_api.py:619` `if store.count_games(uid) >= limit` then `:655` `store.create_game(...)`. `create_game` (`:579`) does not take the per-game lock
(`_lock_for`), the store write is an upsert by new uuid (`game_store.py:293-307`), and nothing in the repo shows a database constraint on games per user.
Repro: a Free user (limit `MAX_GAMES_FREE = 1`, `game_types.py:80`) sends two `POST /games` within the same compute window. Both read count 0, both pass, both insert.
Pro (limit 3) can do the same to reach 4+. Not executed here (needs a running API and storage), found by reading; two requests is also what a double-tap on "Start" sends.
Why it matters: the only per-user cap on sim storage and compute is bypassed by an accident, not just an attack; each extra game is a stored snapshot plus a full draft compute.
Fix (principled, at the source): enforce the cap where the rows live. A unique partial index or a counting insert (`insert ... where (select count(*) ...) < limit`) in the store, or one
per-user lock around count-and-insert. Also count the cap in `list_games`, which currently reads at most 20 rows (`game_store.py:285`).

**P0-3. Two different "what NFL week is it" clocks disagree on Tuesday and Wednesday, the waiver days.**
Evidence: `modules/trade_grade.py:228-238` (`estimate_nfl_week`, week rolls on Tuesday, 17 weeks, 0 after) versus `modules/season_clock.py:63-82` (`nfl_kickoff`, week rolls on Thursday,
`REGULAR_SEASON_WEEKS = 18`). `estimate_nfl_week` is imported by `modules/sleeper.py:663`, `modules/live_policy.py:55` and the bye check at `services/mobile_api_service.py:9312`;
everything else reads `season_clock`.
Repro (2026, kickoff Thu Sep 10):

| date | season_clock | trade_grade |
| --- | --- | --- |
| Wed Sep 9 | preseason | in season, week 1 |
| Tue Sep 15 | week 1 | week 2 |
| Wed Sep 16 | week 1 | week 2 |
| Thu Sep 17 | week 2 | week 2 |
| Wed Jan 6 2027 | week 17 | offseason (week 0) |

Why it matters: for two days of every week (the days most waiver claims and trades are made) the injury-window cost, "on bye this week" flag and live-policy cadence use a different week than the
rest of the product. The grader's remaining-weeks count is off by one on those days, so injury costs, bye flags and "current week" text can contradict the Today and Waivers headers.
Fix: delete `estimate_nfl_week` / `season_window`'s calendar branch and read `season_clock` (with its Sleeper-state source), after deciding the roll day once (see decisions). One clock, one roll rule, 18 weeks.

### P1

**P1-1. Waiver "Add / Stash / Watch" label ignores roster need, and disagrees with the confidence badge on the same card (single-rule shortcut).**
Evidence: `modules/waivers_logic.py:285` (`position_rank <= 3` means "Add"), `:292` (`age <= 24` means "Stash"), served at `services/mobile_api_service.py:16660` next to the
confidence label from `waiver_confidence_label` (`:234-277`), which does use need.
Repro: a player that fills a real need but is 9th on the wire gets label "Watch" with confidence "High: Matches a real roster need". A player that fills no need and has no value signal, 3rd on the wire,
gets label "Add" with confidence "Low: Depth-level add without a strong need or value signal". `position_rank` is the rank among free agents only (`waivers_logic.py:122`), so
the 3rd-best free-agent kicker or the 3rd-best 3rd-string RB is an "Add" for a team that is stacked there. The dashboard headline uses the same label (`dashboard_engine.py:188`).
Why it matters: two verbs on one card tell the user opposite things; the label has no team context, no league format, no competition, and no cost (FAAB) in it.
Fix: derive the label from the same signals as the ranker and confidence (`priority_need_fit`, `priority_bigger_upgrade`, `priority_stash_for_need`, lineup points per week), and put position_rank in the "why" text only.
One function returns `(label, tone, confidence, reason)` so they cannot disagree.

**P1-2. "Elite wire value" is relative to the wire only, so a junk wire still produces "Elite" adds.**
Evidence: `waivers_logic.py:614` (85th percentile of the wire), `:637` (`overall_rank <= 2 or score >= top_cutoff`), `:273` copy "Elite wire value".
Repro: a wire scored `[900, 850, 800, 700, 650, 600]` and a wire scored `[6, 5, 4, 3, 2, 1]` produce the same two "Elite wire value" rows (`desk_logic_repros.py`).
Why it matters: late in the season, or in a shallow league, the top two leftovers are called elite regardless of whether they would start for anyone. The model-based path (`needs_model`) protects need-fit adds with `FILLS_NEED_MIN_PPW`, but the "value opportunity" path has no absolute floor.
Fix: require an absolute bar, for example projected points over the team's own replacement level (the model already knows it) or a percentile against the whole league-eligible pool (the `overall_rating` column the endpoint already attaches), not against the leftovers.

**P1-3. Trade verdict bands are absolute points, so the same 10 percent loss reads differently by deal size.**
Evidence: `modules/trade_value_bands.py:42-47` (SMASH 1500, ACCEPT 500, EDGE 150, COUNTER -400, DECLINE -1200, HARD -2200), `band_for_score` (`:93-110`).
Repro (`desk_logic_repros.py`): a 10 percent loss on a 500-point side = -50 = "essentially even"; on a 3000-point side = -300 = "slight edge to them"; on a 10000-point side = -1000 = COUNTER ("you are giving up value").
Also asymmetric on purpose or by accident: +499 is FAIR, -400 is COUNTER (the accept bar is 25 percent further out than the counter bar).
Why it matters: a bench-for-bench swap can never earn ACCEPT, while a star-for-star 10 percent miss earns COUNTER. The score is lineup-aware, which softens this for starters, but the ladder itself is not scaled to what is being traded.
Fix: express the ladder as the larger of an absolute floor and a share of the traded value (for example max(150, 4% of the bigger side)), keep one table in `trade_value_bands.py` (the TS ladder is already generated from it), and write the asymmetry down as a decision if it is intended.

**P1-4. Two independent playoff-odds engines serve the same real league.**
Evidence: Season Outlook uses the player-level sim (`modules/sim/forecast.py`, 48-80 replays of `simulate_season`); GM Plan, Dashboard and Trade Odds use `modules/playoff_simulator.py` (logistic on the Roster Power gap,
`services/mobile_api_service.py:3223`, `:3416`, `:13726`; `modules/gm_plan.py:284`). Neither reads the other and `modules/sim` imports nothing from Desk valuation (grep: no `from modules.<desk>` in `modules/sim/*.py`).
Why it matters: the same team can read "62 percent to make playoffs" on Season Outlook and "41 percent" on GM Plan. Roster Power is a value total (draft capital, age) while the sim forecast is production-based with injury and bye noise, so they diverge most for dynasty rosters.
Not measured against a real league here (needs a live Sleeper league), so the size of the gap is unverified.
Fix: pick one engine for the "playoff odds" number and make the other explain a difference, or feed the sim forecast's team strengths into the logistic model. At minimum label them differently ("Current roster odds" vs "Power-based odds") until merged.

**P1-5. The forecast's recommended "swing factors" use a 3-point threshold on 20-30 paired replays.**
Evidence: `modules/sim/forecast.py:26-49` (`SCENARIO_SAMPLES = 30`, `MIN_SCENARIO_SAMPLES = 20`, `MIN_MOVE_PLAYOFF_GAIN = 0.03`, `MIN_BRANCH = 8`); the doc says odds are stable to about +-7 points at the 48-sample floor.
Why it matters: a "working the wire adds 3 points of playoff odds" statement is inside the sampling error of the estimate it is built on. Same-seed pairing removes much of the noise but the repo has no measurement showing it removes enough.
Fix: raise the move threshold to about the paired standard error (or add replays until it is) and show it as "small" rather than a number below the noise.

**P1-6. Dynasty leagues age and deflate: scoring falls 6 percent after year 1 and 10 percent by year 10; the league gets older.**
Measured (4 dynasties x 10 seasons, `sim_dynasty_report.py`): team-week mean score 99.9 (season 1), 93.8 (2), 92.9 (3), 93.0 (5), 93.4 (8), 90.2 (10); mean roster age 26.2, 26.5, 26.6, 26.9, 26.7, 27.0 (seasons 1, 2, 4, 6, 8, 10).
Real: league scoring levels are stable year to year (memory; panel top-12 points per game at QB/RB/WR/TE moves by under 5 percent across 2023-2025). QB12 points per game is 15.9-17.1 in the sim versus 17.5-18.1 in the panel; TE12 7.9-8.8 versus 9.0-10.8; QB24 falls from 11.2 (season 1) to 4.4 (season 10), the QB depth collapse already named in `2026-11-sim-long-dynasty.md`, now quantified for a 1QB league.
Why it matters: in a long dynasty the game gets worse to play, and a Season 10 "good" team is scored on a harder yardstick than season 1.
Fix: the retirement and rookie-supply side, not the aging curve: keep the starter-quality pool stationary (rookie classes and retirements should replace the points that leave). Add a stationarity test: top-12 points per game by position must stay within 5 percent across 10 seasons.

**P1-7. Early-career growth is missing from the age curve.**
Measured vs panel (mean next/this points-per-game, players at 6+ ppg and 8+ games both years; panel n is small): WR age 22: sim 0.83 vs real 1.05; WR 23: 0.85 vs 0.97; RB 22: 0.88 vs 1.07; TE 23: 0.79 vs 1.14 (n=10); TE 24: 0.84 vs 1.04 (n=10). Later ages are close (RB 27: 0.79 vs 0.70; WR 27-28: 0.82-0.86 vs 0.77-0.83).
Caveat: the real table is small and regression-to-the-mean affects both, but all three positions point the same way and the sim's top-12 are younger at RB/WR/TE (24.9 / 25.7 / 26.2 vs panel 25.8 / 25.9 / 27.5) and older at QB (29.5 vs 27.3).
Why it matters: dynasty value is the age curve. Selling every 22-year-old WR as "peaked" and over-valuing 26-year-old receivers misleads exactly the decisions dynasty players practice in the sim.
Fix: refit the ages 21-24 knots from the panel plus a second-year ratio table (`age_curve.py`, `aging.py`), with the survivorship conditioning the earlier audit already uses.

**P1-8. In-season scoring still decays 13 percent from week 1 to week 13.**
Measured (`realism_sweep seasons`, 3 seeds, 12 teams PPR): weekly team mean 107.8 (week 1) to 93.8 (week 13); the other nine shapes run from -7 percent (standard scoring) to -20 percent (no kicker), 8 teams -15, 14 teams -18. The earlier fix (#1861) cut the model-path slope; the team-level drop is still larger than the panel's flat per-game scoring for drafted players (12.7 points per played game in week 1 vs 12.8 in week 13, panel 2025, ADP <= 120).
Why it matters: lineups at week 12 score like a different league than at week 2; waiver value and trade deadlines are scored against a shrinking baseline.
Caveat: part is real injury attrition (the panel's played-game average excludes missed games), so a real team-week baseline is needed; I do not have one locally. Reported as likely too steep, not proven.
Fix: measure team-week means in the real panel (sum the top lineup by week) and set the target from that.

**P1-9. Rookie year-1 hit rates are high at the top of the class.**
Measured (`realism_sweep dynasty`, 651 rookies): share over 8 ppg in year 1 by class rank 1-12: 86 percent; 13-24: 54 percent; 25-48: 15 percent; 49+: 14 percent. Earlier sweeps reported 59 / 29 / 8 percent, so this is a different generated-class model and the top moved up. Real first-round skill rookies reach 8 ppg in year 1 roughly half the time (memory, not checked). Bust rate (year-1 under 0.6 of preseason projection) is 14 percent in the sim vs 21 percent real (panel, `2026-11-generated-rookie-classes.md`).
Why it matters: top-12 rookie picks are too safe, so picks are worth more than they should be, and "trade up for the pick" is a strong play.
Fix: widen the rookie outcome distribution (variance, not mean) so top-12 busts reach about 20 percent; keep the mean.

**P1-10. Team Situation cannot be cleared, and old `strategy` defaults differ by endpoint.**
Evidence: `services/mobile_api_service.py:11829-11846` (`strategy: null` is a "no-op"), defaults `"retool"` at `:17351`, `:17506`, `:17629`, `:17826`, `:17916` versus `trade_hub_engine.DEFAULT_ANALYZER_STRATEGY` at `:5898`, `:6760` and `""` at `:8614`.
`trade_hub_engine.roster_posture` (the unified resolver) correctly ranks declared > auto-classified > client value, so the multi-factor logic is sound; the concern is that several entry points still pass a literal "retool" as the client value.
Why it matters: when the declared stance is missing and the auto classification fails open, five endpoints fall back to "retool", one to the analyzer default, one to empty. The same roster could be graded as Balanced in one place and unset in another.
Fix: one default constant read by every request model; add a contract test that all `strategy` fields default to it.

### P2

- **P2-1. `undo_sim` has no paywall check** (`game_api.py:1096`; compare `_mutate` at `:864` and `post_advance` at `:1037`). A Free user at the paywall can undo back and replay weeks 1-3 with different lineups. Same dice, so it is a re-roll of choices, not of luck. Fix: gate it like `revert-week` (`:1161`).
- **P2-2. `trade_preview` is not gated and unlimited** (`game_api.py:931`). A paywalled Free user can still probe the AI desk's valuation indefinitely. Earlier audits showed probing is how the farm worked; the consensus anchor (`econ_v`) limits the damage, but a rate limit or a per-week preview budget is cheap.
- **P2-3. The free preview is restartable.** Deleting the one free game and creating another resets "weeks 1-3" each time (`game_api.py:689`, `:619`). Not a money loss, but "free preview" is unbounded. Needs the product decision below.
- **P2-4. Free gating is weeks 1-3 of one game, not "one free season"** (`game_types.py:78-80`, `game_view.py:42-47`). The enforcement is consistent (no unpaywalled mutating endpoint found other than P2-1, rookie-draft and start-season endpoints, which a Free user cannot reach because the game cannot leave week 3). Any copy that says "1 free season" is wrong; the true number is 3 weeks.
- **P2-5. Injury status odds are uncalibrated** (`modules/injury_status.py:75-77`, rows marked `calibrated=False`): Questionable 0.85 plays, Doubtful 0.15, Probable 0.95, "Out" defaults to 2 weeks, IR to 4. Questionable players play closer to 0.7-0.75 of the time in recent seasons (memory). Calibrate against the nflverse injury-report data the repo already ingests (`modules/nflverse_injury_reports.py`).
- **P2-6. Rank ties and missing data in League Rankings.** `league_rankings.py:172-187` uses dense ranks with `rank_points = n - power_rank + 1`, so ties produce a points table that does not span 1..n; missing scores become 0 (last) and a missing age becomes 999 (oldest) at `:211-220` instead of "no data". Cosmetic until a league has two empty rosters.
- **P2-7. Franchise Value adds raw draft capital to roster value in one number** (`league_rankings.py:174`), so in a redraft-style league with `include_picks` on, pick value counts as long-term strength with no age or horizon term. Check the label ("Long term") describes this honestly; the label change was not on `origin/main` when this audit ran (grep for "Long term" found none).

## Sim realism: sim vs real

Real = panel (committed 2025 panel, `modules/sim/calibration`) unless marked memory. Sim = player-model-5, 12 teams, PPR, 1QB/2RB/2WR/TE/FLEX/K.

| Metric | Sim | Real | Gap |
| --- | --- | --- | --- |
| Team score per week (mean / sd), season 1 | 99.9 / 24.4 | about 100-110 / 22-28 (memory) | in range |
| Team score per week, seasons 2-10 | 90.2-93.8 / 24.7-26.9 | stable (memory) | **-6 to -10 percent drift (P1-6)** |
| Score sd, p5 / p95 | 54 / 140 (min 7, max 203) | sd 22-28 (memory) | one team-week of 7 points, untraced (see "Not verified") |
| Blowout rate (margin >= 50 / >= 30) | 17.0 percent / 40.7 percent | about 15-20 percent / 38-42 percent (memory, follows from sd 26) | in range |
| Mean winning margin (mean / median) | 29.1 / 24.2 | about 28 / 23 (memory) | in range |
| Close games (margin <= 5) | 11.3 percent | about 10-12 percent (memory) | in range |
| Win% sd (AI teams only) | 0.182 | 0.17-0.19 (earlier audit, memory) | in range |
| Best / worst record (14 games, AI teams) | 11.4 / 3.2 wins | about 10-11 / 3 | in range |
| Champion = the top points-for team | 33 percent (n=40) | about 25-30 percent (memory) | slightly chalky |
| Same champion in back-to-back years | 13.9 percent | 8.3 percent if random | persistence is plausible for dynasty |
| Win% year over year (correlation) | 0.41 | about 0.2-0.4 (memory) | upper end |
| Points-for year over year (correlation) | 0.54 | n/a | high |
| Team asset value spread (cv across teams) | 0.13 (s1) to 0.38 (s10) | rising in real dynasty | top team 3.7x the bottom by s10 (1102 vs 286) |
| Top-3 teams' share of league asset value | 29 to 39 percent (s1 to s10) | n/a | wealth concentrates |
| QB12 / TE12 points per game | 15.9-17.1 / 7.9-8.8 | 17.5-18.1 / 9.0-10.8 | **-1.5 ppg (-8 percent QB, -15 percent TE)** |
| RB1 / RB12 / WR1 / WR12 ppg | 22.5-24.3 / 14.9-15.7 / 22.4-25.8 / 15.0-15.7 | 22.2-25.3 / 14.3-16.5 / 23.3-23.7 / 13.8-16.2 | in range |
| TE1 ppg | 15.7-18.9 | 14.6-18.9 | in range |
| Positional share of lineup points | QB 21.6, RB 18.4, WR 19.3, TE 13.5, FLEX 15.9, K 11.3 percent | n/a locally | QB share low (harness QB pool, see below) |
| Age of the top 12 by position (mean) QB / RB / WR / TE | 29.5 / 24.9 / 25.7 / 26.2 | 27.3 / 25.8 / 25.9 / 27.5 | **QB +2.2 years, TE -1.3, RB -0.9** |
| Age curve year-1 to year-2 ratio, WR 22 / WR 23 / RB 22 / TE 23 | 0.83 / 0.85 / 0.88 / 0.79 | 1.05 / 0.97 / 1.07 / 1.14 | **no early-career growth (P1-7)** |
| Rookie year-1 over 8 ppg, class rank 1-12 / 13-24 | 86 / 54 percent | about 50 / 25 percent (memory) | **too safe (P1-9)** |
| Injury new per 100 games QB / RB / WR / TE | 11.2 / 8.2 / 7.6 / 8.3 | 2.4-2.7 on reports, but sim bundles benching | not comparable |
| Games missed per drafted skill player (13 weeks) | 2.02 | 1.93 (2.38 of 17) | in range |
| Share missing 3+ games | 0.29-0.33 | 0.27-0.33 | in range |
| Week 1 to week 13 team score | -13 percent (107.8 to 93.8) | about flat per-game (panel 12.7 to 12.8) | **P1-8** |
| ADP vs finish rank correlation QB / RB / WR / TE | 0.36 / 0.86 / 0.89 / 0.83 | 0.56 / 0.81 / 0.82 / 0.76 | **QB ADP far less predictive; RB/WR/TE slightly more** |
| Retirement age QB / RB / WR / TE | 35.7 / 28.6 / 30.2 / 31.4 | n/a locally | plausible; RB 28.6 is young |
| AI roster composition (QB / RB / WR / TE / K) | 2.1 / 3.6 / 4.6 / 2.7 / 1.3 | n/a | 31 percent of AI teams carry one QB; 2.5 percent have no kicker |
| Trade volume AI-AI per season (12 teams) | 1.7-3.7 | n/a | reasonable |

Reading the table. The sim's single-season shape (score variance, blowouts, parity, positional ppg at the top) is close to real. The gaps are in time: scoring level, league age, early-career growth and
class safety all drift with the number of seasons. A QB ADP correlation of 0.36 against 0.56 means the sim's QB1-to-QB12 order is closer to random than real life. That one is a harness effect: the panel pool carries 33 QBs, so the
QB wire is empty and the QB field is thin (`2026-11-sim-realism-audit-3.md`, finding 13); treat QB rows as a lower bound on realism until the harness uses a full QB pool.

Caveats on measurement: (a) in `dynasty_run.py` the user team never sets a lineup, so it wins 35 percent vs 51 percent for AI teams, and no user titles in 40 seasons is expected from that, not a bug (`GameSettings.auto_lineup` is the product's remedy); AI-only lines are used for parity.
(b) The harness pool is PPR points, so scoring-format variants (std, half, TE premium) show almost no team-score change; the product converts at `RealSimInputs.player_pool` (earlier audit, finding 8).

## Sim correctness

Re-checked without a new bug: the season loop and weekly invariants (earlier fuzz coverage, ~140 whole games plus 56 fuzzed games in the two earlier audits); schedule (fresh round robin, bounded repeats), seeding and tiebreakers (seed order equals the standings order in all 10 shapes, 3 seeds each, this run), bracket shape and byes (earlier fuzz), pick conservation, retirement permanence and aging by one year per season. Nothing new broke in 40 headless dynasty seasons plus 30 redraft seasons (no exception, no illegal state seen; I did not add invariant checks beyond seed order).

New: gating (P0-2, P2-1 to P2-4), clock coupling is Desk-side only. Save/load integrity is covered by `2026-11-sim-realism-sweep.md` and `2026-11-logic-audit-4.md` (event-log replay, revert-week, checkpoints); I did not re-run the fuzzer.

Can a user fleece the AI? The earlier audit measured it: after `econ_v 1` the best bot gains +0.6 to +0.9 wins a season (farmer), the rest near zero. This PR found one more cheap lever, unlimited `trade_preview` (P2-2), which lowers the cost of finding the AI's edge. It does not create value by itself.

## Sim and Desk consistency

- The sim deliberately shares nothing with Desk valuation: `modules/sim` imports no Desk module and has its own valuation (`Evaluator.worth`, persona lenses, rookie-curve pick values), its own verdict wording ("too lopsided", `fair_floor`) and its own letter grades. That is by design (the standing rule that sim logic never touches real-product logic), so a trade graded "ACCEPT" in the Desk and the same trade in the sim can differ. This is expected, but nowhere tells the user, and there is no table of the two ladders.
- The one place where Desk reads the sim engine is Season Outlook (`modules/sim/forecast.py`, via `services/mobile_api_service.py:7498`). It runs next to `playoff_simulator` (P1-4): two models of the same quantity.
- Desk's injury cost (P0-1, `INJURY_POSTURE_WEIGHTS`, 25 percent cap) and the sim's injury discount (share of the season missed, `2026-11-sim-realism-audit-3.md`) are different curves for the same idea; the sim's is the better-specified one. If Desk adopts "share of remaining season missed" the two agree by construction.
- Age and aging: Desk's age curve (`trade_hub_engine.apply_strategy_age_curve`) and the sim's calibrated knots (`modules/sim/aging.py`) are separate tables. P1-7 says the sim's knots under-grow ages 21-24; check Desk's table against the same panel before fixing one in isolation.

## Web and app read the same numbers (lib twins)

`node scripts/check_lib_twins.mjs` passes (156 twin files). I read the diffs of the diverged files that carry logic: `myTeamAnalysis.ts` (web builds rows from `buildPositionGroupItems`, mobile from raw `classification`; both end in the same six statuses and the same order, the web file is a "byte-for-byte port of `room_outlook_label`"), `thisWeek.ts` and `tradeOffer.ts` (routing and presentation only), `playerTier.ts` (tier ids and labels the same; colors per platform), `portfolioProgress.ts` (shape differs, data identical), `todayPlan.ts` and `managerTendencies.ts` (types only). All verdict, band, waiver label, rank and odds numbers are produced once, server-side, and both clients render them (`tradeValueBands.generated.ts` and `injuryTone.generated.ts` are generated from the Python tables and are byte-identical). **No web/app number divergence found.** The risk lives upstream: the server-side duplicates in P0-3 and P1-4.

## Top-10 fix order

1. P0-1 injury text parsing (wrong trade verdicts today).
2. P0-3 one NFL-week clock (every Tue/Wed answer).
3. P0-2 free-game cap enforced in the store.
4. P1-1 and P1-2 waiver label and "elite" bar from one function with an absolute floor.
5. P1-3 trade verdict ladder scaled to deal size.
6. P1-4 one playoff-odds number (or two clearly named ones).
7. P1-6 dynasty stationarity (rookie supply, retirements) plus the test.
8. P1-7 early-career age-curve knots.
9. P1-8 and P1-9 in-season decay target and rookie bust variance (player-model owner).
10. P2-1 to P2-3 gate `undo-sim`, budget `trade-preview`, decide on the restartable preview.

## Decisions needed (product)

1. What does "free" mean for Fantasy Sim: the first 3 weeks of one game (what is enforced now), or one full season? And may a free player delete the game and start a new free preview as often as they like?
2. For Desk, what day does the "new week" begin: Tuesday after Monday night (how fantasy leagues work) or Thursday at kickoff? We need one answer for the whole product.
3. When an injury report is unclear ("torn something", "expected to miss 1-2 weeks"), should we show a firm number, a range, or "unconfirmed"? I recommend a range with an "unconfirmed" tag.
4. Should a trade verdict depend on the size of the deal (a 10 percent miss on a star is bigger than on a bench player), and is it intended that "you are giving up value" starts earlier (-400) than "you win" (+500)?
5. Should Season Outlook and GM Plan show one playoff-odds number, and if so which model do we trust, the production-based sim or the power-ranking one?
6. What should the three waiver words mean (Add, Stash, Watch)? My proposal: Add = fills a real need or is a big upgrade, Stash = cheap upside for later, Watch = nothing to do now.
7. In a 10-year dynasty, should scoring and the player pool feel the same in year 10 as in year 1? (Recommended yes.) Should young receivers and tight ends improve for their first 2-3 years? (Real life says yes; the sim says no.)
8. Should top-12 rookies in the sim be allowed to bust about one time in five, as in real life, even though that makes "first-round pick" feel riskier?

## Not verified

- No live web or app screen was opened; findings are from code, executable repros and headless sim runs. Screens that show these values were not visually checked.
- P0-2 was found by reading; I did not fire two real concurrent `POST /games` or inspect the production database for a uniqueness constraint (Supabase schema was not reviewed).
- P1-4: the numeric gap between Season Outlook and GM Plan on a real league was not measured; it needs a connected league.
- Real baselines marked "memory" (team score level, blowout rate, win-persistence correlation, rookie year-1 hit rate, Questionable play rate) are not checked against data in this repo.
- Team-week real baseline (needed for P1-8) is not in the committed panel.
- Minimum team score 7 in 6,720 team-weeks (0.03 percent are below 20 points) was not traced; likely a bye or injury cluster in a thin K/TE slot, not confirmed.
- The "This season / Long term" ranking labels were not on `origin/main` when this ran (another change is in flight), so Power vs Franchise labelling was reviewed through the scoring code only (`league_rankings.py:172-187`).
- Player eligibility (`player_eligibility.py`), keeper/IDP trade paths, multi-team trade fairness thresholds (`multi_team_trade.py` `BALANCED_SPREAD` / `TILTED_SPREAD`) and FAAB were skimmed, not stress-tested; multi-team grading reuses the two-team pipeline so P0-1 and P1-3 apply there too.
- The full test suite and CI were not re-run for this docs-only change beyond what the PR checks run.
- Mid-season league imports, public sim leagues and the 20-season case were not re-run (see earlier audits).

## Already covered (not repeated)

Trade desk farming and `econ_v` (`2026-11-sim-realism-audit-3.md`), schedule/tiebreaker/playoff invariants and fuzzing (`2026-11-logic-audit-4.md`, `2026-11-sim-realism-sweep.md`), injuries and usage (`2026-11-sim-injuries-and-usage.md`),
aging and retirement (`2026-11-sim-aging-retirement.md`), long-dynasty QB waves (`2026-11-sim-long-dynasty.md`), AI managers (`2026-11-sim-ai-managers.md`), generated rookie classes (`2026-11-generated-rookie-classes.md`), projection audit (`2026-11-sim-projection-audit.md`), hidden value oracles, single-game and tail realism, and team-role coupling.

## Reproducing

```
# Desk repros (no network, no data/players.db)
PYTHONPATH=. python scripts/audits/desk_logic_repros.py

# Sim distributions: four 10-season dynasties, then the report
for s in 1 2 3 4; do PYTHONPATH=. python modules/sim/calibration/dynasty_run.py 10 $s /tmp/sim_audit/dyn$s.pkl & done; wait
PYTHONPATH=. python modules/sim/calibration/dynasty_distributions.py /tmp/sim_audit

# Existing harness
python -m modules.sim.calibration.realism_sweep seasons --seeds 3
python -m modules.sim.calibration.realism_sweep dynasty --seeds 3
```


## Implemented (stability_v 1, player-model-7), 2026-11-16

New games carry `stability_v: 1` (an upgradable season-boundary flag, "A league that stays balanced") and score under `player-model-7`; old saves keep
`stability_v` 0 and `player-model-6` (frozen in `player_model_v6.py`, hash-pinned) and replay identically. Measured with `dynasty_run.py` (8 seeds x 10
seasons, 12 teams PPR, harness user team passive, AI-only parity) and `calibration/stability_report.py` (no games played, 8 seeds x 10 seasons).

| Metric | Before | After | Real / target |
| --- | --- | --- | --- |
| Team score per week, season 1 / season 10 | 98.5 / 89.9 | 99.2 / 96.2 | stable |
| Mean team score, seasons 2-10 vs season 1 | -7.5 percent | -1.1 percent | within noise |
| Asset-value spread across AI teams (cv), season 1 / 10 | 0.15 / 0.40 | 0.17 / 0.17 | stable |
| Top / bottom AI team asset value, season 10 | 3.2x | 1.9x | stable |
| Season points-for sd across AI teams, season 1 / 10 | 122 / 218 | 119 / 135 | stable |
| AI roster mean age, season 1 / 10 | 26.1 / 27.1 | 26.2 / 26.7 | stable |
| Pool: top-24 RB / WR projection, seasons 6-10 vs season 1 | 0.98 / 1.00 | 1.02 / 1.05 | within 12 percent |
| Realized next/this ppg, WR 22 / RB 22 / TE 23 | 0.93 / 0.91 / 0.91 (engine 0.83 / 0.88 / 0.79) | 1.08 / 1.06 / 1.12 | 1.05 / 1.07 / 1.14 |
| Top-12 rookie bust (under 0.6 of projection) | 13 percent | 18 percent (class rank 13-24: 21) | about 20 percent |
| Top-12 rookie class mean outcome / projection | 1.01 | 1.01 | unchanged (variance, not a nerf) |
| Week 1-3 vs week 11-13 team score | -7.6 percent | -8.7 percent | see P1-8 below |

Root causes and fixes (all behind `stability_v`):
* **P1-6.** (1) AI-AI trades included picks: a pick is priced at the league-average slot of its original team, but a team that sells vets for picks is the team
  whose own pick then lands early, so rebuilders harvested the gap every season (persona PF 1.14 vs contenders 0.80 by season 10). The AI-AI search is now
  player-for-player at consensus value; picks still trade with the user. This alone took the spread from 0.38 to 0.17 and removed most of the scoring drift.
  (2) Projections were a random walk (noise plus nothing pulling back) and a retiree's replacement was placed by a steep rookie slot curve, so the middle tier
  thinned (RB36 9.9 -> 7.6 ppg in one offseason) while stars inflated. Added regression to the typical starter above it, diminishing growth near the best the
  league has had, a cap on rookies at the same bound, and a second supply controller that deepens middle class slots when the mid tier is short.
* **P1-7.** Knots were fitted to realized ratios but applied to the hidden projection, which every season redraws around itself, so the realized ratio came out
  0.1-0.25 low and no persistence existed. Last season's result (realized/projected, position-centered, clipped, weight 0.5) now carries into next year's
  projection (`season_outcomes.py`), and `AGE_KNOTS_V2` carry the early-career growth. Shape source: the long-standing public dynasty aging curves (RB peak 22-23 and
  cliff from 26-27; WR improve to 24-25 and plateau to 27; TE slow starters peaking 25-28, the year-3 breakout; QB rising to the late 20s and holding), level
  checked against the panel through the engine's realized ratio. TE n = 10 per age, so only the level, not the shape, comes from it.
* **P1-9.** `player-model-7` adds mean-preserving log-sd for rookies (`sig_rook_add` 0.18 solid season, `bust_sd_rook` 0.18 bust depth). Top-12 bust 13 -> 18 percent.
  Year-1 hit rate over 8 ppg for the top 12 stays about 82 percent (the bust tail widened, the typical rookie did not move); not reduced further to avoid a nerf.
* **P1-8 (documented, not changed).** On the real panel an unmanaged cohort of starters (proj 8+ ppg) scores 12.05 points per player-week in weeks 1-3 and 9.38 in
  weeks 11-13 (-22 percent; 95 percent to 76 percent of them active, byes and injuries). The player model gives 11.82 -> 9.35 (-21 percent) with the same
  availability curve (`cohort_week` check, 805 starter-seasons). The team-level decay (about -9 percent) is that real attrition after managers' lineups and
  waivers, so there is no player-model defect to correct and no real team-week baseline to tune to; forcing flatness would be a scaling band-aid. Remaining
  levers found: all-QB-on-bye weeks with a single rostered QB (5-6 percent of AI team-weeks, 0.8 percent of league scoring; AI backup-QB planning deferred) and
  a thin wire after season 1, which the depth controller above improves.

Note: the league-level rows were measured with the star-regression weight at 0.25; it was raised to 0.40 afterwards so a single seed cannot run a position top-12 25 percent above season 1 (it only touches projections above the typical starter, so the early-career ratios are unchanged).

Deferred: AI backup-QB planning; proper endogenous-slot pick pricing so AI-AI pick trades can return; roster age still drifts about +0.5 year over ten seasons
(kickers and quarterbacks reach their natural older equilibrium); QB/TE pool depth beyond rank 24 still below season 1; engine realized ratios sit 0.03-0.05
under the pool-level ones.

## vorp_v 1: fair prices for backup quarterbacks (trade AI)

Report: "it's almost impossible to trade for a QB, even the worst one they counter for one of my best WRs along with everything else."

Root causes (synthetic pool, 4 seeds, week 3, 12 teams):
1. `Evaluator.replacement` priced "now" value as points over the free-agent wire. Every team stocks two QBs, so the wire is bare of them (QB wire mean about 8 in 1QB, about 2 in superflex) while a QB12-QB20 scores 13-16. A bench QB therefore looked like a star (worth 45-75 of 100 to the AI, more than a 44-worth RB1).
2. `TradeDesk.build_counter` only tried the AI's eight most wanted assets, which are by construction the user's best players, so even a small shortfall was "fixed" by asking for a star.

Fix (gated, `vorp_v`, boundary NOW, absent on every older save): replacement is the larger of the wire and the **starter line** (the best player ranked just past teams x starting slots at the position; a superflex slot counts as a QB start), the "now" scale is normalised to the same line, and a counter also tries the assets that just cover the shortfall so the cheapest sufficient add wins.

Measured (cheapest single user asset, neutral worth 0-100, an AI accepts for its backup QB / counters to a median-asset offer asking for a top-2 user asset):

| league | cheapest accepted old -> new | counters asking a top-2 asset old -> new |
|---|---|---|
| redraft 1QB | 39.9 -> 19.2 | 10 of 24 -> 0 of 9 |
| redraft superflex | 56.6 -> 14.7 | 16 of 19 -> 0 of 10 |
| dynasty 1QB | 57.8 -> 37.9 | 0 -> 0 |
| dynasty superflex | 61.9 -> 30.1 | 0 -> 0 |

A starting QB still costs a fair amount (`tests/test_sim_vorp_v.py`): his own lineup need and his above-line production keep a good starter from going for the user's worst asset.
