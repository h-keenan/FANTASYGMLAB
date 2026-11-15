# Logic audit 4: Fantasy Sim stress harness and Fantasy Desk read-through (2026-11)

Ask (coridian_): a deep end-to-end logic audit of both products, plus "run some more deep simulations to find niche problems".
Standing rules held: sim logic never touches real-product logic, old saves replay identically (every change below is either a bug in a path that
could not have produced a replayable result before, or a replay-tool fix that changes no stored state), no `load_players` on the real db, no
production keys, no live sign-ins, no band-aids.

PRs: sim fixes + harness #1946, Desk fixes #1937, this doc.

## Method

**Sim.** New harness `modules/sim/calibration/league_integrity_stress.py` (pattern of `kicker_trade_stress.py`, multi-process). One run = one whole
game under a random scenario: redraft, fresh dynasty (up to 20 seasons), league import with 4-16 teams, odd playoff fields (2-8 teams), 13-17 regular
weeks, and mid-season starts (real records, schedule, played weeks); flex / rb_wr flex, superflex, K and DEF in or out, ppr / half / std, TE premium,
bench 4-10, IR 0-4, taxi 0-4 with 1-3 taxi years, both tiebreakers, difficulty, auto-lineup; every optional rule generation (`hint_v`, `limit_v`,
`kd_v`, `world_v`, `econ_v`, `ai_v`, `block_v`, `aging_v`) randomly rolled back to a pre-gate save; a mid-run Realism update; and four user styles
(idle, auto-set, chaos = random lineups with empty and ineligible slots, claims, IR / taxi moves, trades, trade block; simto = random Sim-to-N /
deadline / playoffs / season-end jumps with random stop toggles and auto-set).
Invariants (all checked at the week and offseason boundaries): one owner per player, IR / taxi / roster limits, lineup slot order, eligibility and
duplicates, finite non-negative points / standings / pool values, games played = weeks played, wins = losses, points for = points against, head-to-head
symmetry, streak format, PF = sum of game scores, one game per team per week, no self games, seeds are the top of the standings at seeding, bracket
is a permutation of the seeds, byes go to the top seeds, every game is between teams alive, a tied playoff game goes to the higher seed, one champion
who actually won the final, label counts, pick ledger (owned + spent = created), rookie draft length / uniqueness / ownership / ages, ages move one year a
season, retired players never come back, event log folds to the identical digest, a resume from a random mid-log checkpoint reaches the same digest,
and redrafts replay command by command in strict mode.

Volume: about 140 whole games (a mix of redrafts, dynasties of 3, 5 and 10 seasons, league imports and mid-season starts; roughly 400 offseason
roll-overs). A 20-season sweep (70 seeds) was started but killed after 80 minutes without finishing: a 20-season dynasty with chaos users is
minutes per seed per core, so run `--seasons 20` with `--seeds 6-8` (it now prints progress per finished seed).

**Desk.** Read-through of trade grade / valuation, FAAB, notifications, season clock, league calendar, decision queue, web vs mobile twin libs, billing
(read-only). Report from the Desk pass is folded in below.

## Findings, ranked

| # | Sev | Finding | Evidence | Status |
| --- | --- | --- | --- | --- |
| 1 | High | **A league import longer than the player model's 17-week season crashed at its first overflow week.** `league_settings` accepts the real league's regular season (up to 18 weeks, `inputs._current_point`) and a playoff field of up to 16 teams (4 rounds), so 14 + 4 = 18, 15 + 3 = 18, 17 + 3 = 20 calendar weeks. The season profile only has 17 weeks: `player_model_v5._week_mean` raised `IndexError: tuple index out of range` inside `advance`, leaving the game unable to finish (every other call blocked behind it). Found on the first stress seed (8t, 5 playoff teams, 15 regular weeks). | harness seed 8; `test_league_longer_than_the_player_model_season_plays_to_a_champion` | Fixed: `PlayerModelAdapter` maps a week past the profile to the last modelled week and adds no new injury there. Only changes weeks that previously crashed, so no saved game can differ. Frozen models untouched. |
| 2 | Medium | **`replay_game` ignored `realism_upgrade`, `slot_move` (IR / taxi) and `block_set`.** It re-ran only the commands it knew, so for any game where the user used the Realism update, IR / taxi or the trade block, the replay was a different game: strict replay digest mismatch, and the "decisions that mattered" counterfactuals (`evaluate_decisions`) compare a vetoed replay under the wrong rules / rosters against the real final state, so a trade or waiver can be credited or blamed for the effect of the rule change or an IR move. | harness redrafts, 4 of ~45 seeds; `test_replay_reproduces_*` | Fixed in `game_result.replay_game` (replays the three commands through the same action functions, refreshing the rule view after an upgrade). Stored state and digests unchanged. |
| 3 | Low | Schedule home / away is unbalanced (e.g. 8 vs 4 home games out of 14 in an 8-team league): `round_robin` flips home by round parity only. Fantasy has no home field, so it is cosmetic. Opponent counts are the usual circle method repeat (10 teams, 14 weeks: some opponents twice). | harness stat `schedule_home_away_skew` (42 flagged checks over 80 seeds) | Report only; no score or tiebreak reads home. |
| 4 | Low | **AI teams draft a rookie and cut him in the same offseason step.** An AI team at its roster limit takes its round 2-3 rookies, then `enforce_roster_cap` drops the lowest-valued asset, which is often the rookie: 1650 of ~4900 rookie picks (about 1 in 3) in a 21-seed 10-season sweep were cut at the draft. Legal and the player lands in free agency (no pick is lost from the ledger), but it wastes picks and floods FA with rookies. | stat `rookie_dropped_at_draft`; events `rookie_pick` then `drop reason=roster_limit` | Report only: a fix changes AI behaviour (needs a new version flag, e.g. cut a veteran first or skip a pick when full) and belongs with the open "rookie hit rates / UDFA" item. |
| 5 | Info | Kickers / defenses: with `kd_v` 1 a second K or DEF still sits on AI rosters most weeks (stat `second_singleton_*`, thousands of team-weeks per sweep) from the draft and waivers; the earlier work (#1936) only blocks trades from creating it. | stat | Report only; consistent with the documented rule. |
| 6 | Info | Idle or random users score far below the AI (p5 38 vs 69): the user's lineup is never touched unless he acts, injured / bye starters score zero. By design. | `--stats` | None. |

No other invariant failed in about 140 games across all flag mixes, odd league shapes, mid-season starts, Sim-to jumps, offseason transitions and
mid-run upgrades: standings arithmetic, tiebreak ordering, byes, playoff brackets, champion counts, pick ledger, rookie / aging / retirement sanity,
event-log fold, mid-log resume and strict replay all held.

### Fantasy Desk

Fixed in #1937 (small tests included):
1. **Medium: FAAB wire self-match.** `recommend_faab_guidance` compared the wire's unrounded scores to the player's rounded score with `==`, so the
   player never found himself: "clear best on the wire" (+25 percent bid) never fired for a fractional score and he counted as a similar alternative
   (0.8x discount). Repro score 4000.6 bids 9 without the reason, 4000.0 bids 11 with it. Tolerance now 0.5.
2. **Medium: quiet-hours patch collapse.** A patch with one end only (stored 23-7, patch `quiet_start`=7) passed validation, then
   `normalize_prefs` saw start == end and reset both ends to the 22 / 8 defaults. `validate_patch` now takes the stored prefs and the endpoint answers 422.

Open (not fixed):
3. **Low-Med: bye starters lower the live win probability's coverage.** `matchup_win_probability._starter_distribution` returns an unmodelled
   (0, 0, False) for a `bye_week` starter, a known zero for an out starter; byes alone can push coverage below 60 percent and show
   "insufficient_coverage". `starter_expected_points` returning None for byes is also relied on by swap / gain logic in `mobile_api_service.py`
   (about lines 15654-15780), so a deliberate pass is needed.
4. **Low: two calendar week estimators.** `trade_grade.estimate_nfl_week` (week 1 = Tuesday after Labor Day) and
   `season_clock.clock_from_calendar` (week 1 at kickoff) disagree by a week between Tuesday and Wednesday after each game week when Sleeper is
   unreachable, and `estimate_nfl_week` calls week 18 offseason (`FANTASY_SEASON_WEEKS` = 17) so injury costs get the 0.10 offseason factor. Suggest
   `trade_grade.season_window` use `season_clock` when no `current_week` is passed.
5. **Low:** `estimate_competition` / `would_start` in `modules/faab.py` compare the rounded integer score with float rival scores (starter-threshold
   edge only).
6. **Low:** `build_faab_market`: one unknown rival budget turns `budgets_known` off for every rival, disabling the richer-rival and no-budget bid
   adjustments league-wide.
7. **Info:** `modules/revenuecat_webhook.py::_profile_update_url` interpolates `user_id` unencoded (module is deprecated / rollback-only; billing paths
   read-only here, nothing changed).

Checked, no defect: web-next vs mobile twin libs (`decisionQueue.ts` identical; differences in `todayPlan`, `thisWeek`, `myTeamAnalysis`,
`tradeOffer`, `pickGroups`, `guillotine`, `waiverGroups` are import / presentation only), `isWaiverDay`, `league_calendar` deadline math,
`season_clock` phase math, lineup slot greedy fill, trade grade consolidation and injury cost (divide-by-zero guarded), `in_quiet_hours` wrap, and the
#1311 / #1312 Sleeper rollover paths. The Desk pass was a time-boxed read, not exhaustive; golden-value drift was not re-checked (full suite not run).

## Still open from the earlier sim audits (not touched here)

Questionable / Doubtful game statuses, position and age injury hazard, rookie hit rates / UDFA, K / DEF tail refit, the K run in round 12, late-round ADP
looseness, early kicker exits, scoring-variant checks, QB cohort waves. This audit looked at logic invariants, not those calibrations; the harness
prints team-score and margin spreads (`--stats`) but does not refit anything.

## Running it

    python -m modules.sim.calibration.league_integrity_stress --seeds 24 --seasons 5 --workers 6 --stats
    python -m modules.sim.calibration.league_integrity_stress --seeds 7 --seasons 20 --workers 7

Exit code 1 on any invariant failure; failures print the full scenario label and seed (re-run one with `--seeds 1 --start <seed> --workers 1`).
Synthetic pool only (`modules.sim.synthetic`), never `data/players.db`. Regression tests: `tests/test_sim_logic_audit_four.py`.
