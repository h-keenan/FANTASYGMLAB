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

**2. Late-career decline is too steep and too noisy (P1, proposal).** Top-24 by ppg, next / this by age, sim vs real (n=15-36 real per cell):

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

**3. Rookie classes are about three times too strong after the first offseason (P1, proposal, new finding).** Rookies per class inside a position's top-12 by
projection: RB 3.2, WR 2.7, QB 0.9, TE 0.5 (real: RB 0.8, WR 0.0, QB 0.4, TE 0.4 per season; the generated-class audit measured 1.6 in total before `stability_v`).
The best rookie RB projects at 1.34 times the 12th-best veteran (real 0.88), the top three rookie RBs at 20.0 / 18.4 / 17.1 ppg (real 13.9 / 12.1 / 9.3), WRs
17.6 / 16.4 / 15.1 (real 12.6 / 11.6 / 10.9). Rookies with a projection of 7+ average 12.7 (RB) and 13.2 (WR) ppg against 10.3 and 9.4 real. In later seasons a quarter of the
top-12 projections are rookies, who are the most bimodal players in the model (55-59 percent breakout, 35-38 percent bust). Likely cause: the scarcity multipliers
(`_supply_response`, `_equilibrium_plan`, `_supply_mid` in `game_dynasty.py`) stack on a class-strength factor that `stability_v` pushed harder; not isolated. This is
the root of "rookies are too safe and too good" (earlier P1-9) and it inflates the top of the draft board and the dynasty market. Proposal: cap class slot
projection at the real top-rookie curve (rank-1 about 0.9 of ref12) behind a season-boundary flag (`rookie_v 1`), and re-measure the supply controller.

## Fantasy Desk findings (trace of every advice surface; repros on fixtures)

### P0 (fixed in #2023)
1. **Push injury and lineup-lock alerts never saw IR/PUP recorded on roster `status`** (`push_triggers.py`, `team_sheet.py`). A star RB on "Injured Reserve" with a blank
   injury designation produced no push; a bench WR who was "Out" did. The in-app Alerts feed already passed both fields.
2. **FAAB "would start" was inflated by flex slots** (`faab.py`). 1 TE + 2 FLEX counted as 3 TE slots, and a roster with fewer players than slots "would start" anyone, so
   11 rivals with two good TEs each "needed" one (x1.5 starter bid, x1.6 competition bid, "11 teams need a TE"). Now a lineup is built (dedicated slots, then flex from what is
   left; superflex and OP take any of QB/RB/WR/TE) and a candidate starts only if he improves it.
3. **A QB behind a Doubtful starter was projected at 20 percent** (`player_projections._role_adjustment`), so a Doubtful starter (p_play 0.15) plus his backup produced
   about 35 percent of a QB. The share is now `max(0.2, 1 - starter p_play)`.

### P1 (proposals)
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

### P2
- Confidence adds points for the explanation the same module wrote (`trade_ideas._trade_confidence_context`); candidate windows are absolute points (`_value_fits`); TE premium is a
  boolean in valuation (lineup model reads the magnitude); `required_depth = starters + 1` ignores bye overlap; `live_big_plays` omits some bonuses; "less competition" wording on a
  Stash card compares wire rank, not rivals.

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

## Decisions needed (product)
1. Ship the late-career age curve and a lower `REVERSION` (`stability_v 2`)? It changes dynasty values for 27+ players, so it is an upgradable offseason change, not silent.
2. Cap rookie class strength (`rookie_v 1`)? It lowers rookie pick values and the top of the draft board; real classes are far less top-heavy.
3. Should the AI's posture follow standing (`posture_v`)? It makes the league feel more alive and removes the persona-decides-the-decade effect, at the cost of more volatile AI behaviour.
4. Should the user's waiver claims be contested by AIs in priority order (`wire_v`)? This ends the "queue the best FA every week" edge.
5. Desk: should the Today tile and push reminder use the same needs model and posture as the Waivers page (one answer), even if it costs a heavier computation on Today?

## Not verified
- No live screen was opened; Desk findings come from code and fixtures, Sim findings from headless runs.
- Real next / this cohorts are 35-40 per position; their p10 intervals are wide and the WR and TE targets are uncertain.
- The harness pool has 33 QBs, no defense by default and synthetic byes, so QB scarcity and bye clustering are lower bounds. No real team-week baseline exists in the panel.
- Rookie class strength cause (supply multipliers) is a hypothesis, not isolated. Age knots v3 was tried on 8 seeds only and was not validated on hold-out seeds.
- The Desk P1s were reproduced on fixtures, not on a connected league.

## Reproducing
```
PYTHONPATH=. python -m modules.sim.calibration.season_variance_report --seeds 8 --seasons 5 --seed0 8          # model-8
PYTHONPATH=. python -m modules.sim.calibration.season_variance_report --seeds 8 --seasons 5 --seed0 8 --off    # model-7 behaviour
pytest tests/test_sim_verdict_reason.py tests/test_faab.py tests/test_push_triggers.py tests/test_team_sheet.py tests/test_projections_v2.py
```
