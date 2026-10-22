# Logic audit — October 2026

Scope: the valuation, trade, lineup, pick, projection, win-probability and
recency logic that drives FantasyDesk recommendations. The audit had three
parts. First, a scenario matrix run on the real engine against a copy of
`players.db`. Second, targeted fixes for the defects that were clear-cut.
Third, a point-in-time backtest of the predictive logic against real 2024 and
2025 outcomes. The ranked recommendations below were not changed in code,
because each one needs an owner decision.

## 1. Scenario matrix (real engine, copy of players.db)

Every format ran without a crash, and values moved in the expected direction:

- League sizes 6, 10, 14 and 16 teams.
- Scoring: half PPR, standard, TE premium, 6-point passing TD.
- Lineups: 2QB, Superflex, no K/DEF, deep bench plus taxi.
- League types: redraft, keeper.
- Best ball: the setting is ignored (see recommendation 5).
- IDP: offensive values are inflated by about 6% (see recommendation 7).

Trade symmetry holds: A→B and B→A mirror correctly.

Trade edge cases gave sane results: 3-for-1 and 1-for-3, a handcuff, an
all-QB roster, a one-player roster, the same player on both sides, and
gift-only and dump-only offers. The one exception is that **sending a player
you do not own is accepted** (see recommendation 12).

Picks behave sensibly when a team holds 3 or more firsts and when picks belong
to an orphan team.

## 2. Fixes merged

| PR | Commit | Fix |
| --- | --- | --- |
| #1326 | `f88ddd00` | The Trade Analyzer priced assets with base scores and ignored league settings and the lens. In Superflex, Gibbs↔Allen moved from DECLINE −2186 to FAIR −165, and 12 of 48 SF Hub ideas changed verdict. |
| #1328 | `9e909c16` | Spent current-year picks were still offered and valued during the season. 2028 picks were missing, and the Analyzer dropped 2028 pick ids. Next-season picks got no future discount from January until the rookie draft. The Hub golden fixture was regenerated. |
| #1330 | `ef3c0aaf` | Lineups counted WRRB_FLEX twice, counted IDP_FLEX as an offensive slot, and filled FLEX before the narrower slots. |
| #1334 | `fc00633d` | Players with no birthdate were stored as age 99 (212 players), which polluted roster age averages. A rebuilder receiving a free rookie got the maximum −2 age penalty, and the posture could flip. |

## 3. Recommendations (ranked; not changed, owner decision needed)

1. **Trade Hub and Analyzer disagree.** The Hub suggests trades that the
   Analyzer grades DECLINE in 7–9 of 48 Superflex ideas. One contender's top
   idea was DECLINE −1441. The Hub applies a consolidation premium and a
   strategy age curve; the Analyzer applies neither.
2. **The Analyzer treats this week's Out/IR as a permanent loss.** With
   McConkey Out, a trade grades COUNTER, or DECLINE for a rebuilder.
3. **Contender strategy barely penalizes losing starter strength.** Trading a
   stud for 3 depth pieces costs −4426 starter strength and still grades FAIR.
4. **Suggested lineups ignore byes and weekly projections.** They use season
   dynasty value, so a player on bye can be started.
5. **Sleeper `settings.trade_deadline` and `best_ball` are never read.** Trade
   ideas continue after the deadline, and GM Plan's deadline phase is
   hardcoded to weeks 4–11.
6. **`settings.taxi_slots` is never detected.** As a result, the designed taxi
   boost (up to +12% for players 23 and under) has never been active.
7. **IDP leagues inflate offensive values about 6%** through starter pressure.
8. **FAAB issues:**
   - A 0.5 score floor gives a 100-value scrub the same bid as a 2500-value
     player.
   - Leagues without FAAB (`waiver_type` != 2) still get dollar bids.
   - The mobile endpoint never passes starter, week or strategy.
9. **Players missing from FantasyCalc fall back to Sleeper rank with no age
   adjustment.** For example, Aaron Jones Sr. (age 31) ranks above Derrick
   Henry. Locally only 322 of 1740 players have FantasyCalc values; check
   production coverage.
10. **Playoff simulator:**
    - Divisions are ignored.
    - The fitted slope can go negative.
    - Clinched and eliminated come from 3000 Monte Carlo trials, not from the
      math, so a team that is still alive can show as eliminated.
11. **Win probability counts starters with no projection as 0 points.** Up to
    40% of a lineup can be unmodeled (DEF is always unmodeled; see §4.2).
12. **Low impact:**
    - The Analyzer API does not verify that you own the players you send.
    - The counter pick pool skips the crowd class-strength signal.
    - REC_FLEX is treated as RB/WR/TE.
    - A league with only a SUPER_FLEX slot gets an invented QB slot.
    - GM Plan has no playoff or eliminated phase.

## 4. Backtest against real 2024 and 2025 outcomes

### Method

- **Engine.** The backtest ran the real `player_projections.project_player_week`,
  `matchup_win_probability.compute_live_win_probability`,
  `rankings.compute_recency_features` and `rankings.age_multiplier`.
- **Inputs.** Each run was built point-in-time from Sleeper weekly stats:
  - weekly rows before the target week only;
  - defense-vs-position through week − 1;
  - a QB1 proxy taken from prior-week pass attempts.
- **Actuals and benchmark.** Actual PPR points come from Sleeper v2 stats.
  Sleeper's own pre-game projection is the benchmark. "Naive" is the
  player's season-to-date PPG.
- **Sample.** 2024 and 2025, weeks 4–17: 28 season-weeks and 13,261
  projected player-weeks.
- **Weights.** None were retuned.

### Leak check: no leakage detected

`leak_checks.csv` reruns 1,708 projections (weeks 6 and 12 of both seasons)
with the player's **full-season** rows, including the target week and later,
passed to the engine. All 1,708 matched the truncated run exactly on both
`point_estimate` and `low`: 0 mismatches. The engine ignores future rows, and
the harness truncates them anyway.

Code review of the harness found no other future-information path. Opponent
defense uses `upto_week = week − 1`, the QB proxy uses prior weeks only, and
Sleeper projections are pre-game. Two minor caveats:

- A player's team for the target week is taken from that week's stat row. This
  is normally known before kickoff.
- Player metadata (position, birthdate, rookie year) is today's
  `sleeper_players.json`. Players missing from it are dropped, which adds mild
  survivorship.

The metrics below are valid on those terms.

### 4.1 Weekly projection accuracy

**Pool.** The "relevant" pool is the top N per position-week by the app's own
projection (QB 24, RB 48, WR 60, TE 24, K 16): 4,816 player-weeks. 684 of
them (14.2%) did not play. In 681 of those 684, Sleeper had already projected
about 0, meaning the player was known to be out before the game, yet the app
still projected them at a mean of 13.2. The app has no injury or inactive
signal, so a known-Out player keeps a full projection.

**Accuracy, players who played (n = 4,132):**

| Pos | n | MAE app | Bias app (est − actual) | MAE naive PPG | MAE Sleeper | Spearman app | Spearman Sleeper |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| QB | 569 | 6.80 | +1.53 | 6.40 | 6.25 | 0.19 | 0.30 |
| RB | 1,168 | 6.41 | +0.79 | 6.04 | 5.60 | 0.44 | 0.57 |
| WR | 1,409 | 7.42 | +2.85 | 6.07 | 5.80 | 0.28 | 0.49 |
| TE | 596 | 6.25 | +2.37 | 5.15 | 4.98 | 0.27 | 0.44 |
| K | 390 | 4.39 | +2.08 | 4.24 | 3.85 | 0.09 | 0.09 |
| **All** | **4,132** | **6.60** | **+1.94** | **5.80** | **5.50** | — | — |

Spearman values are within position-week, averaged over 28 weeks.

Selecting the pool by the app's own estimate flatters its over-projections.
As a neutral check, the pool was also selected by Sleeper's top N (n = 4,813
played). On that pool the app's MAE is 6.24 with bias +0.34, against 5.81 for
naive PPG and 5.60 for Sleeper. Across all 10,117 played player-weeks, with
no selection, the app's bias is +0.74.

**Start/sit pairwise hit rate** (same position-week, both played): this is
the share of pairs where the app ranked the higher scorer first. Sleeper's
rate is in brackets.

| Pos | All pairs | Pairs with a ≥ 3-point projected gap |
| --- | ---: | ---: |
| RB | 65.5% [70.7%] | 71.0% |
| WR | 59.7% [67.7%] | 64.3% |
| TE | 59.7% [65.7%] | 65.0% |
| QB | 55.8% [60.5%] | 59.4% |
| K | 53.5% [53.9%] | 57.2% |

**Bands are too narrow.** The low–high band should hold about 68% of actuals
if it is ±1 sd. Coverage by confidence level:

- "high": 54.6%
- "medium": 62.4%
- "low": 63.1%

At WR and TE, 33% of actuals fall below `low`.

**Headline.** The weekly projection is **less accurate than a plain
season-to-date PPG average** at every position. It ranks players clearly worse
than Sleeper: rank correlation at WR is 0.28 against 0.49. The gap is
largest at WR and TE.

### 4.2 Win-probability calibration

**Sample.** 6,999 synthetic head-to-head matchups (about 250 per
season-week). No real league's matchups were reachable for this backtest.
Each lineup is QB, 2 RB, 3 WR, TE and FLEX, drawn from real players Sleeper
projected to play. Each matchup is scored with real points, and the real
`compute_live_win_probability` is applied before kickoff.

The same matchups were scored twice: once with the app's projections and once
with Sleeper's projection means fed into the same model (same band width).
Each column gives the actual win rate, with n in brackets.

| Predicted bucket | App projections | Sleeper means, same model |
| --- | ---: | ---: |
| 0.0–0.1 | 0.26 (101) | 0.00 (5) |
| 0.1–0.2 | 0.30 (384) | 0.19 (118) |
| 0.2–0.3 | 0.37 (755) | 0.25 (479) |
| 0.3–0.4 | 0.44 (1,044) | 0.33 (1,135) |
| 0.4–0.5 | 0.46 (1,257) | 0.47 (1,731) |
| 0.5–0.6 | 0.54 (1,104) | 0.56 (1,742) |
| 0.6–0.7 | 0.57 (1,074) | 0.65 (1,191) |
| 0.7–0.8 | 0.66 (763) | 0.77 (484) |
| 0.8–0.9 | 0.68 (417) | 0.79 (110) |
| 0.9–1.0 | 0.78 (100) | 1.00 (4) |

**Brier score.** With app projections the Brier score is **0.246**, against
0.25 for a coin flip, so skill is 1.6%. With K and an unmodeled DEF added it is
0.247. With Sleeper means it is **0.227** (skill 9.4%) and well calibrated:
for example, 64% predicted and 65% actual.

**Overconfidence.** With app projections the model is strongly
overconfident. A "93%" favorite wins 78% of the time, an "84%" favorite wins
68%, and a "6%" underdog wins 26%. The model's implied spread (sd 31.8)
matches the real error spread (32.5). Projected team totals also ran 15.7
points per team above actual; with Sleeper means the gap was 0.4.

**Conclusion.** The probability math is sound. The problem is the inputs: the
weekly projections from §4.1.

**Limits.** These are synthetic random lineups, not real league matchups, and
DEF is unmodeled. Roster managers who avoid known-Out players are simulated by
requiring a Sleeper projection of at least 1. `winprob.csv` was regenerated
after this audit's first read; the figures above come from the final file.

### 4.3 Declining-role ("Cooling" / sell-high) flag precision

**Sample.** Snapshots at weeks 6, 9 and 12 of both seasons, for players with
at least 6 PPG before the snapshot and at least 2 games after it: 1,013
player-snapshots, 243 of them flagged Cooling. Outcomes are measured over the
next 4 weeks.

| Group | n | Usage down ≥ 5% next | PPG down next | PPG down > 20% | Mean ΔPPG |
| --- | ---: | ---: | ---: | ---: | ---: |
| Cooling (sell-high trigger) | 243 | 54% | 65% | 42% | −0.82 |
| Not Cooling | 770 | 42% | 54% | 32% | −0.25 |
| Base rate (all) | 1,013 | 45% | 57% | 34% | −0.39 |
| Display "trending down" | 349 | 50% | 62% | 38% | −0.58 |
| Display "trending up" | 420 | 40% | 52% | 30% | 0.00 |

**What the flag gets right.** The flag has a real but weak edge: precision is
54% for lower usage against a 45% base rate, and 65% for lower PPG against
57%. A flagged player loses about 0.6 PPG more than an unflagged one.

**What it gets wrong.** In only **36%** of flagged cases did usage keep falling
below the recent low window. Most flagged players rebound toward their
baseline: the flag catches a dip, not a durable decline. The baseline it
compares against can be as short as 2–3 games. By position, the
share with lower usage next (flagged against unflagged) was:

- WR: 57% against 44% (n = 108)
- TE: 55% against 38% (n = 42)
- RB: 50% against 44% (n = 66)
- QB: 48% against 41% (n = 27; too small to rely on)

### 4.4 Systematic biases

The biggest misses, in order:

1. **Zero-point games are dropped from history.** Sleeper omits `pts_ppr`
   when a player plays and scores 0. The projection treats those weeks as
   missing, not as 0. This affected 5,786 of 13,261 player-weeks (44%),
   inflating them by +1.59 points on average.
   - In the relevant pool these players carry a bias of +4.50; with zero-fill
     it is +1.78.
   - Worst cases are projected about 14 points when the true value is 0, for
     example Jordan Whittington at 14.9 against 0.0 with zero-fill.
   - With zero-fill, overall bias drops from +0.74 to +0.07 and MAE improves
     at every position (WR 7.42 to 6.94, TE 6.25 to 5.73).
   - The same omission makes usage null in 984 of 2,333 recency rows.
2. **Known-Out players are projected at full value** (§4.1). 681 relevant
   player-weeks show a mean projection of 13.2 for a player who did not play.
3. **WR and TE are over-projected.** Bias in the relevant pool is +2.85 for WR
   and +2.37 for TE; RB is +0.79.
4. **Thin or interrupted history.** Bias is +3.52 with 2 or fewer games of
   history (n = 118), +4.43 when a player returns after 2 or more missed weeks
   (n = 86), and +6.09 after a team change (n = 7; too small to rely on).
   Rookies are close to normal, at +1.10 (n = 342).
5. **Elite producers are under-projected.** Examples: Chase Brown −4.5 per
   game in 2025, Trevor Lawrence −4.2, Brock Purdy −6.4 (n = 5), Christian
   McCaffrey −2.8. Sleeper was close on each.
6. **Age curve (dynasty valuation, partial check).** This compares the
   one-year step in `age_multiplier` with each player's actual 2024 to 2025
   PPG ratio (at least 8 games and 6 PPG in both seasons; n = 175).
   - Direction is right at every position, with Spearman 0.26–0.40.
   - Decline after 27 is steeper than the curve says. The actual median ratio
     is about 0.80 for WR 27–28 (curve 0.93) and about 0.55 for WR 29 and up
     (curve about 0.86). RB 27–30 is about 0.70 (curve 0.81–0.86), and TE 25
     and up is about 0.65–0.69 (curve 0.92–1.00).
   - Even the young cohorts fell year over year, with an overall median ratio
     of 0.87. That is regression to the mean from selecting 6-PPG seasons,
     so read the gaps as relative, not absolute.
   - Cells hold 1–24 players each, so this is directional only.

### 4.5 Bugs found by the backtest (not yet fixed)

A separate fix is in progress for items 1 and 2.

1. **Zero-point played games are dropped** (§4.4, item 1). Sleeper omits the
   points field for a 0-point game.
   `player_projections._player_recent_trend`, `_most_recent_played_week` and
   `rankings.weekly_usage_rate` then skip those weeks.
2. **Live win probability treats a game in progress as final**
   (`matchup_win_probability._starter_distribution`). Take identical lineups:
   5 minutes before kickoff they give 0.5, and 5 minutes after kickoff they
   give 0.0, because partial points are frozen and the rest of the
   projection is discarded.
3. **Projections ignore injury status** (§4.1).
4. **Playoff clinched/eliminated come from 3,000 samples, not exact math**
   (recommendation 10).
5. **Past-week external projections use later data.** In the app, not the
   harness, past weeks are shown with current opponent defense strength,
   current team and full-season QB quality.

### 4.6 Judgment calls for the owner

- Shrink weekly projections toward the season-to-date average, or blend in a
  market projection such as Sleeper's. Either one beats the current mean, and
  feeding Sleeper means into the same win-probability model already
  calibrates it (§4.2).
- Account for injury and inactive status in projections.
- Widen the projection bands. "High" confidence covers 55%, against a nominal
  68%.
- Require a longer baseline before showing Cooling or sell-high.
- Weigh the age-curve evidence (WR 29+ kept 55% of output against the curve's
  86%) before changing dynasty values. The samples are small.

### Limits

- **Two seasons only.** Rank correlations are means over 28 weeks.
- **Simulated win-probability matchups.** These are not real league
  matchups.
- **Kicker results are noise.** Kicker rank correlation is about 0.09 for
  everyone.
- **Small samples.** QB Cooling, team-change and age-curve cells are small.
- **Not backtestable.** Dynasty values, tiers, the Overall rating, playoff
  odds, and the trade, Hub, pick and FAAB valuations have no ground truth for
  this kind of test.

## 5. Not tested

- Real Sleeper league payloads. The pick default assumes Sleeper's documented
  `in_season` and `complete` statuses.
- Production FantasyCalc coverage.
- Divisions in a real league.
- The mobile and web UI.
