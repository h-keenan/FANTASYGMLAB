# Trade engine v2: expected lineup points and one trade score

Owner request (coridian_, 2026-10-27, screenshot of a -379 "Why this works" verdict that
sold a Questionable starting RB for a 2027 R2 and said the lineup "stays close to neutral"):
"do the proper fix, never do a band-aid fix."

PR #1568 added a single-rule downgrade (no startable player this week -> COUNTER). v2
replaces it, in season, with one model whose output decides the verdict, the confidence,
the risk text and the counter-offer search. Code: `modules/trade_lineup_model.py`
(the model), `modules/trade_analyzer_fit.py` (calls it), `modules/trade_offer_analyzer.py`
(verdict + counter search), `modules/trade_grade.py` / `modules/trade_ideas.py` (Trade Hub
gate), `services/mobile_api_service.py` (feeds it the league's waiver pool and projections).

## What it computes

For the user's roster before and after the trade, expected lineup points for every remaining
fantasy week (`current_week` .. 17):

1. **Points per player per week**, in the league's scoring (PPR / half / standard from the
   detected `rec` value, TE bonus per reception from the detected bonus key, else 0.5 when
   `te_premium` is on). Source, best first, and always labelled in `basis_counts`:
   - `projection`: the v3 walk-forward baseline in `modules/player_projections.py`
     (`baseline_weekly_points`, usage-based empirical Bayes; the same estimator behind
     `project_player_week`, minus its schedule/availability layers because the lineup
     solver applies byes and injuries itself).
   - `season_average`: the player's real season PPG, shrunk toward the value-derived prior
     by games played (`n / (n + 3)`).
   - `value_estimate`: rank-matching his model value to the PPG distribution of that
     position's active players in the same frame (documented static anchors only when the
     frame has fewer than 6 active players at a position).
   - nothing: a team defense, or a player with no value and no stats, gets no estimate. We
     never put a number on a defense; the D/ST and IDP slots are outside the model.
2. **Weekly optimal lineup** over the league's real slots (QB/RB/WR/TE/K, WR-RB, REC_FLEX,
   FLEX, SUPER_FLEX), solved best-first with the narrowest flex first (optimal for this
   nested structure, same rule as `team_eval.suggest_optimal_lineup`). A player on his NFL
   bye (schedule-backed, never guessed) is unavailable that week.
3. **Availability** from the repo's existing expected-weeks-missed estimate
   (`trade_grade.estimate_injury_absence`: Questionable 0.25, Doubtful 1, Out 2, IR/PUP/NFI 4,
   Suspended 3, season-ending body parts = rest of season, surgery >= 6). Player i is
   available in week w with probability `1 - clip(weeks_out - (w - current_week), 0, 1)`.
   Weeks with fractionally-available players are solved **exactly** by enumerating
   availability scenarios (up to 6 players per week, the rest folded in as expected value),
   so a backup has real insurance value and the variance is computed, not guessed.
4. **Replacement from the league's real waiver pool.** `waiver_df` is the unrostered,
   waiver-actionable pool; the best free agents at each position can fill open slots at a
   0.90 reliability discount (claims fail, one-week lag). An empty RB slot with a 3-point
   free agent costs a lot; with a similar RB on waivers it costs little. With no pool
   available the model fills holes at the market replacement level and says
   "(no waiver data, replacement level assumed)".

## The one number

Three lineup deltas (expected points, rest of season):

- `dPts`: the real one (slots, byes, injuries, depth, waiver replacement).
- `dPts0`: the one the market implicitly assumes (nobody hurt, nobody on bye, any hole filled
  at the market replacement level = the standard rank `league_size * (slots + flex share) + 1`).
- `F = dPts - dPts0`: roster-context **friction**, what a roster-blind price cannot see.

```
trade_score = raw_value_delta + injury_value_restore + consolidation
            + (w_now - 1) * k * dPts        posture: extra weight on REAL lineup points
            + (w_fut - 1) * d_value_future  posture: weight on market future capital
            + k * F                         friction at full weight
```

- `k` (value per point over replacement) is **calibrated per league frame**: the median of
  `0.40 * value / (17 * (PPG - replacement PPG))` over the league's QB/RB/WR/TE starters (the
  0.40 is the repo's existing current-season value share). Static fallback 22.0 measured on
  the 2026 players table when the frame cannot calibrate.
- `w_now = 1 + trade_grade.STARTER_STRENGTH_WEIGHTS[posture]`: contender 1.50, fringe 1.35,
  retool 1.15, rebuild 1.05, tank 1.00 (the repo's existing "starter value counts more for a
  contender" weights, now applied to real points instead of season value). `w_fut = 1.0` for
  every posture on purpose: asset scores arrive already posture-priced (strategy age curve and
  strategy pick multiplier), so weighting future capital again would double count. The
  contender-vs-rebuilder weighting between this season and the future is `w_now / w_fut`.
- `injury_value_restore`: the market lists a short-term-injured player at a risk-discounted
  value. The old engine restored the healthy value and charged a flat availability cost. v2
  keeps the restore and charges the missed weeks as lineup points instead.
- A surplus asset gets no credit beyond its market price (selling it is the liquidation); a
  hole costs its full points. That asymmetry is in the definition of `F`, not a position rule.
- Nothing in the model is special-cased by position. Every rule is a parameter of
  `ModelParams`, the posture table, or the roster slots.

Output additions (all in `fit["lineup_model"]` and `verdict.lineup_model`; the schema is
additive, old app builds keep working):

| field | meaning |
| --- | --- |
| `points.ros_delta`, `per_week_delta`, `this_week_delta` | expected lineup points, rest of season |
| `points.ideal_delta`, `friction_delta` | what the market assumes vs. what this roster adds |
| `points.future_delta` | next 2 seasons (age-curved, healthy, informational, not in the score) |
| `positions[pos]` | before/after/delta/per-week and weeks worse, per position |
| `worst_position`, `pickup` | the biggest hole and the best free agent for it, with points recovered |
| `components` | raw value, restore, consolidation, posture now/future, roster friction |
| `win_now_delta`, `future_delta` | value-unit split of this season vs. future capital |
| `trade_score` | the combined score (value units, same scale as the value balance) |
| `uncertainty`, `confidence_pct`, `confidence_label` | below |
| `explanation` | the human sentence, built from the same numbers |

`value_delta` stays the market value balance (raw + consolidation) so the app's balance bar
keeps meaning "market fairness". `trade_score` is the number the verdict uses.

## Verdict, confidence, risk text, counters

- **Verdict bands** read `trade_score` alone in season: >= +1500 smash accept, >= +500 accept,
  <= -400 counter, <= -1200 decline, <= -2200 hard decline, else fair. (Offseason: legacy path,
  below.)
- **Confidence** is `P(sign of trade_score is right) = Phi(|score| / sigma)`, capped at 99%.
  `sigma` combines injury-timing variance (exact, from the scenario enumeration), the
  persistent error in each differing player's baseline (25% of his weekly spread, summed over
  the weeks he differs; game-to-game luck averages out of an expectation and is excluded from
  confidence but included in the reported outcome range), 40% of the future-points effect, and
  a 4% market-value noise on the gross value traded. Labels: >= 88% High, >= 70% Moderate,
  else Close call. Those cut points and the shares above are parameters, not validated
  numbers.
- **Risk text** is built from the model: who is estimated out and for how long (flagged as an
  estimate, no return date exists in the data), which slot stays open and for how many weeks,
  and the outcome range and confidence.
- **Counter-offer search** regrades every candidate (up to 20) through the same fit and keeps
  the packages with the highest `trade_score`, subject to the partner still seeing a roughly
  fair market balance (their loss <= 500 value). The hole position (`worst_position`) is
  ranked first when picking what to ask for, so a backup RB that fills the hole beats an
  equal-value WR.
- **Trade Hub gate** (`_UserSideAnalyzerGate`) grades every idea with the same pipeline, with
  the league's real free-agent pool, and exposes `analyzer_trade_score` next to the verdict.

## Offseason and failure behaviour

With no fantasy week (`current_week = 0`, or the calendar says offseason) nothing weekly is
claimed: `lineup_model` is null, `lineup_warnings` is empty and the older value-based pieces
(season-value starter strength, injury availability cost) stand, exactly as before. If the
model raises for any reason the same legacy path is used.

`modules/trade_lineup_impact.py` (#1568) is kept for what it states as fact (this week's
startable counts, the "no startable RB" headline for the UI warning list) but no longer
affects the score.

## Parameters worth knowing

`fa_reliability` 0.90, `prior_games` 3, `baseline_error_share` 0.25, `max_enumerated` 6,
`future_years` 2, `future_discount` 0.70, `future_sigma_share` 0.40, `market_noise_share`
0.04, confidence cut points 0.88 / 0.70. All in `ModelParams`.

## Calibration check

`scripts/trade_engine_v2_calibration.py` (throwaway copy of `data/players.db`, opened
read-only, never `load_players`): a value-ordered snake draft builds 12 dynasty rosters from the
players table, everyone left is the waiver pool, and about 600 market-plausible trades are
generated (1-for-1 swaps within 15% value, sell a starter or a bench player for a pick of
85-115% value, buy a starter with a pick, 2-for-1 consolidation) across contender / retool /
rebuild. Each is graded by v2 and by the previous engine (same code, lineup model off). Week 8,
seed 7, 2026 players table. Byes are not applied (no schedule offline; never invented).

| | deep rosters (QB3/RB7/WR8/TE3) | thin rosters (QB2/RB3/WR4/TE1) |
| --- | --- | --- |
| cases graded | 570 | 558 |
| verdict tone changed vs old engine | 37.7% (99 harsher, 116 kinder) | 52.9% (73 harsher, 222 kinder) |
| old mix accept/fair/counter/decline | 176 / 198 / 126 / 70 | 137 / 165 / 93 / 163 |
| new mix accept/fair/counter/decline | 119 / 300 / 135 / 16 | 150 / 277 / 116 / 15 |
| median abs(trade_score - market balance) | 94 | 224 |
| confidence label High/Moderate/Close (new) | 190 / 202 / 178 | 122 / 167 / 269 |
| confidence label High/Moderate/Close (old) | 224 / 86 / 260 | 284 / 68 / 206 |
| confidence % (min / median / max) | 50 / 79 / 99 | 50 / 70 / 99 |
| lineup-points sign agrees with market sign | 51.8% | 53.6% |
| seconds per case, both engines | 0.12 | 0.12 |

Reading it honestly:

- The largest flow is old ACCEPT -> FAIR (71 deep, 52 thin). Those were small market edges
  (median +93 balance) the old `fit_total` components pushed to ACCEPT. v2 needs a +500 score
  to accept, so it is more conservative about accepting small edges. That is a calibration
  choice, not a discovery.
- Thin rosters: the old engine DECLINED 163 of 558 trades (29%), mostly through the full
  season-value starter weight, which ignored that a hole is filled from the waiver pool and
  ignored availability. v2 declines 15 (2.7%) and moves most to FAIR/COUNTER. Whether that is
  right depends on how good the waiver pool really is; with real league pools this should be
  re-checked after launch. The unit tests pin the direction (worse waiver pool => lower score,
  monotonically).
- Roster friction is small for most trades (|F| > 10 pts in 9% of deep-roster cases, 48% of thin)
  and moves verdicts only when there is a real hole, injury or bye problem. Position of the
  worst hole is reported only when the lineup as a whole loses points or leaves a slot open
  (a flex slot shifting from a TE to an incoming WR is not a "TE loss").
- Tone is monotone in `trade_score` (0 violations in 570 deep cases), and confidence rises with
  |score|: median 98% for decline, 89% counter, 88% accept, 68% fair.
- The calibration set is synthetic rosters from real players. It checks that the model is
  sane, calibrated in scale and stable; it is NOT a backtest of whether verdicts predict wins.

Example (week 8, retool, the owner's shape: a thin RB room, the only healthy RB, free agents at
3.5/3.0 PPG, 2027 R2 valued 4800 for a 5200 RB). Test scenario `test_owner_rb_scenario_*`:

```
value balance (market): -400        trade_score: -3892  -> DECLINE, 99% sure
net -109 lineup pts over Weeks 8-17 (-8.5 this week); friction -93 pts
"You lose ~10.9 pts/week at RB for 10 weeks (the best free agent, FA_RB0, ~3.0 ppg, only
 recovers ~30 pts); net -109 lineup pts over Weeks 8-17 (-8.5 this week). Posture retool
 weights real lineup points x1.15."
risk: "Jones (Questionable): part of a week estimated (default for Questionable; no return date
 in the data). Outcome range: about +/-39 lineup points ..."
```

The same package with free-agent RBs at 9.0/8.5 PPG scores -2646 (still a decline: in this
synthetic league the market replacement RB is 12 PPG, so a 9-PPG fill is still a hole). The
retool 3.5-PPG package is -3892; contender (w_now 1.50) -5113; rebuild (1.05) -3543.

## Limitations (what is and is not projection-based)

- Per-game points come from our own usage-based baseline when weekly rows are cached for the
  player, else season average, else a value-derived estimate. Value-derived estimates are
  rank-matched to the position's active-player PPG, not scouting; their spread is widened by
  30%. The response says which basis each player used (`basis_counts`).
- No opponent/matchup adjustment (backtests in `docs/projections-v3-walkforward.md` found it
  did not help out of sample), no weather, no game script, no rest-of-schedule strength.
- Injury timing is the repo's default estimate per status. There is no return date in the
  data and no point-in-time injury history, so Questionable/Doubtful probabilities cannot be
  backtested. A starter who is "Out" for 2 weeks is modeled as exactly 2, not as a distribution.
- The expected-lineup solver sets the lineup knowing availability scenario by scenario (as
  Sleeper's late swaps allow); it does not model start/sit regret.
- Future seasons use age curves on current points and are informational: they do not enter
  `trade_score`. Future value in the score is the market's (already age-curved, posture-priced).
- The waiver pool is "who is unrostered and actionable today"; FAAB, waiver priority and what
  other managers will claim are not modeled beyond the 0.90 reliability discount.
- Playoff odds and standings are not used: the repo has no per-team playoff probability to read
  here, and the posture (contender / retool / rebuild) is the team-context input.
- D/ST and IDP slots are outside the model (no points data for defenses, IDP value-only).
- `k` is one rate for all positions, calibrated from the market's own value/points relationship
  for starters; it is only as good as that relationship (dynasty value includes age, so young
  players read as worth more points per value than they produce this season).
- Verdict bands and confidence cut points are product choices layered on the number, not
  fitted to outcomes.

## Trade Finder: shopping picks (and saying why nothing was found)

Owner report (coridian_, 2026-11-01, mobile screenshot): one pick ticked, "Any return",
"No realistic trades found for this selection right now" ("still no realistic trade").
Code: `modules/trade_ideas.py` (pattern 5, `FinderSearchTrace`, `finder_value_band`,
`finder_search_payload`, `finder_closest_note`), `modules/trade_hub_engine.py`
(`generate_trade_finder_records(finder_trace=...)`), `services/mobile_api_service.py`
(`GET /v1/leagues/{id}/trade-finder`), tests in `tests/test_trade_finder_pick_search.py`.

### Root causes (reproduced on the 12-team synthetic league, full 26-man roster)

Before the fix every one of the user's 8 picks, in contender / retool / rebuild, returned zero
ideas (24 of 24). Four independent causes stacked, each one enough to empty the list:

1. **Roster-full penalty.** A pick-for-player trade adds a roster spot, and
   `evaluate_trade_market_realism` docked 16 + 4n points whenever the roster was at its limit.
   Dynasty rosters are normally full, so every pick-for-player package fell below the 54
   acceptance bar (best candidate scored 52). The user chose what to shop, so adding a player is
   the purpose of the trade: it is now `4 + 2n`, never a veto, and the idea says "Your roster is
   full, so you would need to drop a player to fit this."
2. **Fixed target pool.** Targets came from the top 14 partner assets by roster fit, capped to 8,
   with a 1500 value floor and a fixed -1500/+1200 band. A 600-3000 pick was therefore matched
   against 5000+ players and failed the value band for every partner (88 of 88 candidates in the
   traced run). Targets are now every partner asset inside `finder_value_band(send_value)`
   (low = -clamp(30% of value, 400, 1500), high = clamp(40%, 400, 1200)), ranked by roster fit,
   then closeness.
3. **Posture veto.** `_fit_priority` (-7 per pick sold) and `_team_fit_assessment` (-12 rebuild,
   -16 tank) penalize selling picks. For a pick the user explicitly ticked those terms are added
   back (`_pick_send_posture_terms`); the partner's side and the market check are unchanged.
4. **"Any return" never tried pick-for-pick.** Pick swaps (move up, move down, consolidate two
   picks into one, spread one into two) only ran with "Picks back". They now run for every
   explicit pick selection (value within +/-20%, never a like-for-like swap), and send packages go
   up to 3 picks (14 packages from 4 picks).

After: contender and retool find options for every pick (1-9 ideas each), rebuild finds options
for the R1s and some late picks, and the rest are honest dead ends (below). Unchanged: Trust
enforcement, the Trade Analyzer FAIR gate, partner roster-fit (`partner_score > 0` for pick-for-
player, `> -4` for pick-for-pick because a swap carries no positional signal), market realism
hard fails (cornerstone, scarcity, protected assets).

### When there is still nothing: why, and the closest options

`FinderSearchTrace` counts where candidates died: `candidates`, `value_band` (nothing priced near
the selection), `my_fit`, `partner_fit`, `reasoning`, `market`, `market_hard`, `analyzer`,
`trust`, plus the nearest asset's value gap. `finder_search_payload` turns that into
`search = {status, headline, selection, reasons[], funnel, partners_checked}`. It only states
causes the funnel measured.

- `status`: `found`, `closest` (nothing realistic, near misses attached), `none`, or `error`.
  A crashed search used to surface as a 500 or an empty list, indistinguishable from "no trades
  exist"; it is now `error` ("not a real no-trades result, try again").
- `closest[]`: up to 3 near misses, one per partner, ranked analyzer-rejected (the partner may
  take it but it grades as a loss for you) < market-thin < weak-fit < partner-fit < value-gap.
  Trust hard-fails are never offered, and the near misses go through the same
  `enforce_generated_trade_ideas` as real results. Each carries
  `finder_note = {label: "Stretch", reason, value_gap, stage}`, for example "You would need to add
  about 580 more value to reach this." The list is only sent when `ideas` is empty, so an old
  client that ignores the new fields just shows its old empty state.
- Clients: web `TradeFinderNoResults.tsx` and mobile `TradeFinderNoResults.tsx` render the
  headline, the measured reasons, the "Closest options (stretch)" cards with a Stretch
  `ToneBadge`, and a retry for `error`.

Limits, stated plainly: "partner would likely take it" is inferred from roster fit and market
realism, not from manager behavior beyond the existing trade-style hints; value gaps use the
engine's pick values (posture-adjusted), not market consensus; the synthetic league has a smooth
value ladder, so real leagues will show different mixes of reasons.
