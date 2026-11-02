# Backend band-aid audit (2026-11-02)

Request (coridian_): "make sure you didn't do any Band-Aid fixes with the logic, throughout the whole back end."

Audit only. Nothing was fixed in this pass. Read from `origin/main` at `5564ae3b` (#1608).

## Method and limits

- Read the recent trade-engine surface in full or in the relevant parts: `trade_posture`, `trade_value_bands`, `trade_offer_analyzer.decide_offer_verdict`, `trade_grade` (new gate helpers), `trade_hub_engine.roster_posture`, `trade_lineup_model` params, `trade_ideas` (guardrail, confidence, tier/protection helpers, Finder trace), `trust_enforcement`, `game_weather`, `player_availability`, `start_sit_range`, `opponent_profile`, `player_value_trend`, the trade-odds endpoint.
- Diffed the specific fix commits (#1601, #1602, #1588, #1608, #1607, #1596) and read the commit messages for the stated root cause.
- Swept `modules/` and `services/` with `git grep` for: TODO/HACK/workaround, broad `except Exception`, named-player/league special cases, allow/deny lists, absolute value thresholds, quarantined/skipped tests, flags.
- Not done: running the engine, re-deriving any calibration, reading every one of the 95 `except Exception` blocks in `mobile_api_service.py` (about 30 are silent-default; the load-bearing ones are listed). The sweep of `modules/` older than the last ~150 commits is a pattern sweep, not a line read.
- Clean results worth saying: no hard-coded player, team, league or user ids in logic (the only named players are in comments); no `# TODO/HACK/FIXME` markers in code; only one env kill switch (`FANTASYDESK_WEATHER_DISABLED`); `trust_engine.py` was not touched by any recent change.
- Severity: S1 = can silently change a user-visible verdict or number, or the same fact is decided two ways; S2 = real but contained; S3 = cosmetic/low risk. Effort: S under half a day, M up to 2 days, L more.

## Summary table

| # | Sev | Where | One line | Effort |
|---|-----|-------|----------|--------|
| 1 | S1 | `trade_analyzer_fit.py:583,621` | Engine failure silently swaps the verdict to the legacy ladder | S |
| 2 | S1 | `trade_hub_engine.py:870` (`roster_posture`) | Posture lookup fails open to "retool"/client default, re-creating the original contender bug | S |
| 3 | S1 | `trade_ideas.py:2669` `_temporary_injury_trade_guardrail` | Hand-tuned point penalties and hard-fails for injury cover, parallel to the v2 model that already prices injuries | M |
| 4 | S1 | `trade_ideas.py` (67 absolute thresholds, e.g. 1285-1383, 2623, 4674-4885) | Fixed value cut points in a market whose scale varies by league (the exact lesson of the 700/win fix) | L |
| 5 | S1 | `trade_ideas.py:1508` confidence score | A second, ad-hoc confidence model beside the lineup model's sigma-based one | M |
| 6 | S1 | `trade_posture.py:341` + `trade_offer_analyzer.py:753` | Verdict label and UI verdict overridden after the score; score still says accept | M |
| 7 | S1 | `rankings.py:2621` + 10 other places | Injury vocabulary decided in at least 10 separate places, with different answers | M |
| 8 | S2 | `player_tiers.py:59` | Tier cap added at the tag layer for one named player's case; values untouched | M |
| 9 | S2 | `team_eval.py:617` | `drop_duplicates` added because duplicates "not yet root-caused" | S |
| 10 | S2 | `mobile_api_service.py:12884,12899` | Keeper round penalty lookup returns 0 on any failure, silently changing prices | S |
| 11 | S2 | `mobile_api_service.py:15899` | All-Trades board `continue`s past any per-team exception | S |
| 12 | S2 | `trade_grade.py:601` `attach_projection_baselines` | Swallows all errors and returns frames without baselines, the exact divergence #1602 fixed | S |
| 13 | S2 | `mobile_api_service.py` `_trade_odds_effect_for_package` | Odds effect uses value-based Roster Power, not the v2 lineup model, so the two numbers on one screen can disagree | M |
| 14 | S2 | `tests/test_mobile_api_service.py` (4 `known_flaky`) + `ci.yml:60` | Tests quarantined for a fixable test-isolation cause | S |
| 15 | S2 | `trade_offer_analyzer.py:51,~770-800` | Legacy no-lineup verdict ladder (own magic numbers) still runs beside the score ladder | M |
| 16 | S2 | `trust_enforcement.py:132` + two guard tests | "Material missing metadata" rule keyed on column names; guard tests loosened in the same PR | S |
| 17 | S3 | `trade_posture.py:47-95`, `trade_lineup_model.py:80-91` | Uncalibrated tuned tables and one-snapshot anchors | M |
| 18 | S3 | `game_weather.py:72,77` | Tier fallback and a 10% total cap not tied to measured data | S |
| 19 | S3 | `start_sit_range.py:34-40`, `player_value_trend.py:26-36` | Hand-picked thresholds, openly labelled "product choices" | S |
| 20 | S3 | `rankings.py:2682` | `has_term` substring matching ("ir", "out") in `injury_level` | S |
| 21 | S3 | `player_value_trend.py:36` | Another private injury set (`OUT_STATUSES`) | S |

---

## S1 findings

### 1. Engine exception silently changes which verdict procedure runs
- `modules/trade_analyzer_fit.py:583` sets `lineup_model = None`; `:620-621` `except Exception: lineup_model = None`.
- What it does: if `trade_lineup_model.evaluate_trade` raises for any reason, the Analyzer does not error or flag. It falls into the legacy `value_delta` + `fit_total` ladder in `decide_offer_verdict`, which has different cut points, different confidence logic and no posture terms.
- Why a band-aid: it hides a crash behind a plausible-looking answer produced by a different decision procedure. Two identical trades can get verdicts decided by different engines depending on whether one threw. Nothing in the response says which ran.
- Root-cause fix: separate "no weekly data / offseason" (a legitimate, named, reported mode) from "model raised". On raise, log with context, return an explicit `engine: "degraded"` marker on the verdict (and have `verdict_assumptions` say it), or fail the request. Put the mode into the payload so clients and `clears_suggestion_bar` can see it.
- Effort: S.

### 2. `roster_posture` fails open to a default posture
- `modules/trade_hub_engine.py:870` (`try/except: declared = ""` at ~894, `except Exception: pass` at ~912).
- What it does: if the rankings frame or the stance lookup raises, posture falls through to `client_strategy`, which defaults to "retool", labelled source "client".
- Why: the original owner bug (#1597) was a contender graded as "retool". A cache miss or exception in `build_league_rankings_frame_cached` reproduces it silently for that request, and every surface (Hub, Finder, Analyzer, Dashboard) then grades under the wrong posture. The `source: "client"` label is the only trace.
- Root-cause fix: distinguish "no data" (a new league, no rankings) from "raised". Log and count the raise, and surface `posture.source == "client"` as a degraded state to the caller (do not rank ideas under it as if known). Consider failing the Hub board rather than ranking it under a guessed posture.
- Effort: S.

### 3. Temporary-injury trade guardrail is a rule pile parallel to the v2 model
- `modules/trade_ideas.py:2669-2745` (`_temporary_injury_trade_guardrail`), wired at `:3586`, consumed at `:1520`.
- What it does: for a team with a "temporary injury need", applies score deltas (-8, -14, -45, -12, -28, -18, +18), `hard_fail` flags, and thresholds `outgoing_best <= 3600`, `incoming_best >= outgoing_best + 900`, `+ 350`. Separately, `:1519-1522` subtracts 18/24 confidence when `value_delta < -700/-1200`.
- Why a band-aid: engine v2 (`trade_lineup_model`) already prices a short-term injury in expected lineup points with enumerated availability. This module decides the same question ("is this just injury cover?") with absolute value thresholds and tag-specific penalties that were tuned to individual complaints. Two models of the same fact can disagree, and the rule model has no tests that tie its constants to anything.
- Root-cause fix: delete the rules; let the lineup model's `points.ros_delta` and `absence` terms (already computed) carry the injury-cover story, and keep only the wording tags. If a protection against cheap sales of core starters is wanted, express it as a named, documented, league-scaled rule (see 4).
- Effort: M.

### 4. 67 absolute value thresholds in idea generation
- `modules/trade_ideas.py`: asset tiers `:1285-1383` (1800/2600/3200/4200/5400/7600/9800), protection `:2623-2668` (5000/5200/6500), throw-ins, `_value_fits(low=-1200, high=1200)`, `target["score"] < 1500`, `score > 3500`, `< 2500`, `>= 5000`, `7500`, `* 0.45`, `* 0.65`, `>= 600` gaps in `finder_closest_note`.
- What it does: classifies assets as throw-in/core/long-term and gates which packages are even considered, in raw value units.
- Why a band-aid: #1602 already found that value units are not comparable across leagues: "a first-round pick was ~3k; in a league whose R1 picks price at 5.5-9.8k [the 700/win] was a rounding error." The same failure mode applies to every fixed cut here (a "core starter" at 6500 in one league is a mid starter in another), and it also duplicates the percentile-based tiers in `player_tiers.py` with a second, absolute definition (`_tier_label_for_asset` falls back to score cut points when no tier is present).
- Root-cause fix: express thresholds as fractions of the league's own scale (e.g. percentile of the league's valued-asset distribution, or multiples of `value_per_point` / the median R1 price) through one helper, and use the stored `player_tier` as the only tier definition.
- Effort: L (many call sites; do it per helper, starting with `_is_core_or_protected_starter` and `_value_fits`).

### 5. A second confidence model in `trade_ideas`
- `modules/trade_ideas.py:1508-1533`.
- What it does: `confidence_score = round(market_score*0.62)`, plus clamps and bonuses (`+4`, `-12`, `-24`), then flag-driven caps (`protected_outgoing_override`, `superflex_qb_scarcity`, `consolidation_premium`) via `min(...)`.
- Why a band-aid: the Analyzer's confidence is computed from the score's own uncertainty (`adjusted_confidence`, sigma). This one is a weighted sum with post-hoc caps added per flag. Hub cards and Analyzer runs of the same package can show different confidence, and each flag cap looks like a patch for one observed card.
- Root-cause fix: use the Analyzer verdict's confidence for any idea that has one (the gate already runs the Analyzer for surfaced ideas); keep a market-realism score only as a pre-filter, not as a user-facing confidence.
- Effort: M.

### 6. Verdict label and UI verdict overridden after the score is decided
- `modules/trade_posture.py:341` (`verdict_label_override`) and `modules/trade_offer_analyzer.py:753-761`.
- What it does: when the market value says accept but the posture cost is material, the score is left alone and the label becomes "GOOD VALUE, COSTS YOUR LINEUP"; as of #1602 an ACCEPT/SMASH `scored.id` is also forced to UI verdict FAIR/tone "fair" for old clients. The docstring says so openly: "Structural, not a cap on the number: the score is untouched and the label only reports that market value and window disagree."
- Why a band-aid: this is a presentation-layer correction applied while the engine still returns an accept-level score. `trade_score`, `adjusted_confidence`, counter search and `clears_suggestion_bar` all still see the accept-level number, so surfaces that read the score (bot feed, share cards, push) can still call it a win. The #1602 UI demotion was added to hide one visible symptom (a green ACCEPT on a card showing a -90 lineup).
- Root-cause fix: decide whether the window cost is part of the score. If it is, `WINDOW_WIN_WEIGHT` should be large enough (and calibrated) that the score lands below ACCEPT; if it is a separate axis, return two explicit fields (value verdict, window verdict) and have every consumer render both, instead of a single overridden label.
- Effort: M.

### 7. Injury status is classified in at least 10 places
- Primary: `modules/rankings.py:2621` (`injury_level`), `:2727` (`is_ruled_out`). Others: `player_availability.py:20-33` (`_STATUSES`), `injury_tone.py:21-24`, `player_projections.py:1023-1024,1155-1170` (0.15 / 0.85 multipliers, flagged by its own code as "priors that could not be backtested"), `trade_grade.py:245-257` (`INJURY_STATUS_DEFAULT_WEEKS`), `trade_lineup_model` absence (weeks), `player_value_trend.py:36` (`OUT_STATUSES`), `player_state_authority.py`, `player_eligibility.py`, `news_signal.py`, `external_news_contract.py`.
- Why a band-aid: each was added when a surface got a wrong label. E.g. `is_ruled_out` special-cases the literal "out" token because `injury_level` groups "Out" and "Doubtful" together; the lineup model, projections and Analyzer then each decide availability with different numbers (questionable = 0.25 weeks out vs 0.85 multiplier vs "startable").
- Root-cause fix: one status table (`status -> kind, ruled_out, expected_weeks, p_play`) in one module, with `injury_level`, `is_ruled_out`, `availability`, projection multiplier and lineup absence all derived from it. Add a test that every Sleeper status string seen in `data/sleeper_players.json` maps to exactly one row.
- Effort: M.

## S2 findings

### 8. Tier cap added at the tag layer for one player's case
- `modules/player_tiers.py:43-59` (`BLOCKED_ROLE_TIER_CAP = "Depth"`) and `_cap_blocked_role_tier`.
- What it does: any player with `workload_trend == "Blocked"` is capped at Depth no matter his score percentile. The comment names the originating case (a 2026 WR with 7% snaps) and says "same philosophy as the waiver gate, applied at the tier-tag layer."
- Why: value_score/dynasty_score still say Starter-level, so the tier tag disagrees with the number every trade, ranking and rating uses. Fixing the label hides that the valuation does not know the player has no role.
- Root-cause fix: put the role signal into the valuation (a usage/role term in `dynasty_score`) so the tier falls out of the score; drop the cap.
- Effort: M.

### 9. `drop_duplicates` because duplicates are "not yet root-caused"
- `modules/team_eval.py:617`, comment at `:605-616`.
- What: dedupes roster rows by `player_id` in the lineup engine because upstream duplication put one player in two lineup slots.
- Why: the comment says the cause was not found. The guard is sound defensively, but it also means the duplicate source is still feeding other consumers unchecked.
- Fix: find where duplicates enter (candidates: roster `players` + `reserve`/`taxi` merge, or a merge on non-unique keys) and dedupe there; keep this as an assertion with a logged counter.
- Effort: S.

### 10. Keeper penalty lookup returns 0 on any failure
- `services/mobile_api_service.py:12884` (`_stored_keeper_round_penalty`), `:12899` (`_trade_idea_keeper_round_penalty`); also `trade_hub_engine.py:451` (`_apply_keeper_values` returns the unadjusted frame) and `:470`.
- Why: a Supabase blip prices every pick/player in a keeper league with no keeper adjustment, and the cached result is stored as if correct (`generate_trade_idea_records_cached`).
- Fix: distinguish "no setting" (0) from "lookup failed" (do not cache; return with a `keeper_pricing: unavailable` flag).
- Effort: S.

### 11. All-Trades board swallows per-team exceptions
- `services/mobile_api_service.py:15899`.
- What: `except Exception: continue` around posture resolution and idea generation for each team.
- Why: a bug in the engine silently shrinks the board and the free-tier ledger is unaffected, so nobody sees it. It is also how a regression would hide in prod.
- Fix: log with league/roster context and increment a metric; fail loudly in tests.
- Effort: S.

### 12. `attach_projection_baselines` swallows everything
- `modules/trade_grade.py:601-645`.
- Why: its docstring says the lack of baselines caused the Hub gate to pass a package the Analyzer graded as a loss (#1602). The helper now returns the unbaselined frames on any exception, which recreates that divergence silently.
- Fix: narrow the excepts to the data-not-available case, log and count the rest, and mark the verdict basis (the lineup model already labels `basis`).
- Effort: S.

### 13. Trade-odds effect uses a different model than the verdict
- `services/mobile_api_service.py:3259` (`_trade_odds_effect_for_package`), added in #1606.
- What: change in playoff/title odds is driven by `games.score_roster` (Roster Power, value-based), applied as a `power_overrides` delta to the shared simulator. Picks are excluded (flagged).
- Why: on the same Analyzer screen, the verdict says "-90 lineup pts over weeks 8-17" (v2 expected points) while the odds card can show a different direction because it is fed value, not points. That is two surfaces disagreeing by construction, and it is the pattern engine v2 was built to remove.
- Fix: feed the simulator the v2 `ros_delta` (points per week) converted through the simulator's own team-strength scale, or at least show them only together with a reconciliation line.
- Effort: M.

### 14. Known-flaky tests quarantined for a fixable cause
- `tests/test_mobile_api_service.py:2788, 8200, 9857, 10917`; `.github/workflows/ci.yml:60` (non-blocking, `continue-on-error`).
- Why: the comments state the cause: process-level `lru_cache` on `modules.sleeper.get_league_drafts` and unmocked network calls in `_resolve_my_roster`. These are test-isolation defects, and one of the quarantined tests (`test_dashboard_and_trade_hub_share_one_cached_idea_search`) is the only guard that the Dashboard and Hub share one cached search, which is the property most relevant to surfaces disagreeing.
- Fix: autouse fixture that clears the sleeper `lru_cache`s and patches `requests.get`/`account_store.fetch_rows` for these tests; remove the marker; keep CI blocking.
- Effort: S.

### 15. Two verdict procedures still coexist
- `modules/trade_offer_analyzer.py:51` (`_VALUE_CLOSE = 700`) and the `elif` ladder after the `lineup_model is not None` branch (`value_delta >= 150 and fit_total >= 4`, `fit_total <= -3`, etc.).
- Why: the no-lineup path (offseason, missing data, or item 1's failure) uses untied numbers (150, 700, fit totals) that `trade_value_bands` explicitly replaced for the main path. The audit doc 2026-10-28 already notes the scale mismatch.
- Fix: once item 1 is fixed, give the offseason path its own explicit mode on the shared score ladder (a value-only `trade_score`), and delete the `fit_total` ladder.
- Effort: M.

### 16. Trust rule keyed on column names; guard tests relaxed in the same PR
- `modules/trust_enforcement.py:132-163` (#1601) and `tests/test_league_switch_first_useful.py`, `tests/test_trade_hub_first_useful_result.py`.
- What: bye_week never degrades trust (a legitimate root-cause fix: byes derive from the schedule). Age degrades only a player with `fantasycalc_value`/`value` > 0.
- Concerns: (a) `_has_market_value` hard-codes two column names; a frame using `dynasty_score` only gets "no market value" and skips the age check; (b) the PR removed `trust_enforcement.py` from two guard tests that exist to stop presentation PRs touching Trust. The new test is good, but removing the guard is a loosening, not an exception scoped to that PR; (c) the symptom (every player DEGRADED, Hub rejects everything) went undetected, which says there is no test that a normal player PASSES in the real frame.
- Fix: add a fixture-based test that a realistic players-table row is PASS; use the score field the frame carries; restore the guard with an explicit allowlist of the one PR.
- Effort: S.

## S3 findings

### 17. Tuned tables presented as principled
- `trade_posture.py:47-95` (`WINDOW_WIN_WEIGHT` 0.5/0.35/0.15, `PRESENT_ADJUST`, `DIRECTION_RATE`, `GAIN_CREDIT`, `MATERIAL_*`, `WEEKLY_TEAM_SD = 22`); `trade_lineup_model.py:80-91` (`STATIC_ANCHORS`, `STATIC_VALUE_PER_POINT = 22.0`, measured on one 2026 snapshot); `ModelParams` (`fa_reliability 0.90`, `future_discount 0.70`, `market_noise_share 0.04`).
- The code labels these "approximate", the module header claims "no per-player rule and no hard cap," and `scripts/trade_engine_v2_calibration.py` exists. But the weights were set to make specific reported cases (the Higgins/IR-rookie trade; "~156 lineup points" for a pick-priced league) come out right, and there is no test that fits them to outcomes.
- Fix: run the calibration script against held-out historical trades (`trade_outcome_results`) and record the fit and date next to each constant; make `STATIC_*` fall back loudly.
- Effort: M.

### 18. Weather
- `game_weather.py:72` (`_TIER_FALLBACK`: a heavier tier inherits a lighter tier's effect, "conservative") and `:77` (`MAX_TOTAL_REDUCTION = 0.10`).
- The per-cell effects are measured and documented (good). The cap and the inheritance are judgment calls not backed by the regression; the cap is a post-hoc clamp on the output. The module also swallows all fetch errors by design ("weather never blocks a projection"), which is acceptable here because the state is reported as loading/unavailable.
- Fix: validate the cap against the stacked-cell estimates in `docs/weather-effects.md`; drop it if the data supports stacking.
- Effort: S.

### 19. Start/sit lean and value-trend thresholds
- `start_sit_range.py:34-40` (0.30/0.70, 1.5 pt, 0.5 giveup), `player_value_trend.py:26-36` (3 points, 15 percentile, age 29, 4 games).
- These are named constants with stated rationale ("product judgment", "not fitted to outcomes") so they are not band-aids per the brief. Flagged only because they are untested against outcomes and the Buy-low age exclusion has no Sell-high counterpart.
- Effort: S.

### 20. Substring matching in `injury_level`
- `rankings.py:2682` (`has_term`): `term in text` for terms such as `"ir"` and `"out"`. `is_ruled_out` fixed the "out" case with `_has_out_token`, but `injury_level` still substring-matches (e.g. any free-text status containing "ir"). A symptom was patched in one caller instead of the classifier.
- Fix: token-match inside `injury_level` (part of item 7).
- Effort: S.

### 21. `OUT_STATUSES` in `player_value_trend.py:36`
- See item 7; a new private copy added in #1608.

---

## Honest list: which of THIS session's recent changes might be band-aids

These are the changes made in the Claude session that produced the last stretch of commits (Claude-Session `014Kec2s...`). Judged strictly.

1. **#1602 verdict UI demotion (`trade_offer_analyzer.py:753`)**: a band-aid. The engine still returns an accept-level score; the UI verdict is overridden so old clients do not show green. Item 6.
2. **#1597/#1602 `verdict_label_override`**: same family; the header's claim "no hard cap" is accurate, but "label only reports" is exactly a presentation-layer fix.
3. **#1602 `clears_suggestion_bar` (`trade_grade.py:570`)**: partly root cause (it now uses the Analyzer's own ladder rung `EDGE`), but the "no lineup model -> return True" branch means the offseason gate is unfiltered, and the `-EDGE` cut was chosen to make one reported card pass/fail. The gate being a filter after generation (rather than the generator pricing under the same score) is a symptom-level approach; the principled change is the generator searching on the Analyzer score.
4. **#1602 `attach_projection_baselines`**: the root cause (gate graded on a different frame) was fixed, but the helper's blanket `except` quietly re-creates the divergence. Item 12.
5. **#1601 trust fix**: the diagnosis is right (bye_week is not player evidence). It is a band-aid only in what surrounds it: guard tests loosened in the same PR and column-name coupling. Item 16.
6. **#1588 Matchup suggested moves (`swap_is_justified`)**: a rule added after a bad suggestion ("never start an unprojected over a projected"). The underlying problem is that the lineup engine fills slots with a "value-matched placeholder" it admits is not evidence; the guard filters moves after they are built. Root fix: have the optimizer treat an unprojected player as unknown (not a point estimate) from the start.
7. **#1596 Finder "closest options" / near-miss trace**: it is a diagnostic UI that explains empty results rather than making a realistic result exist. Pattern 5 sizing by `finder_value_band` is a real fix; the "Stretch" list shows packages the engine rejected, with absolute-value gap wording (`>= 600`). Acceptable as a feature, but it should not be mistaken for the fix to "zero plausible trades" (item 4 is).
8. **#1606 trade-odds endpoint**: new duplicated model (value-based Roster Power) beside the v2 lineup model; picks excluded with a flag. Item 13.
9. **#1594 weather**: mostly principled (measured, documented, shrunk, flagged); the 10% cap and tier fallback are the only soft spots. Item 18.
10. **#1607 start/sit range lean, #1605 opponent profile, #1608 value signals**: new, named constants with rationale, derived from existing numbers. Not band-aids, but item 19 notes the thresholds are untested and `OUT_STATUSES` adds a tenth injury vocabulary (item 7/21).
11. **#1571 engine v2**: the right direction (one model decides verdict, confidence and counters). Remaining soft spots are not in the model but at its seams: the silent fallback to the legacy ladder (item 1) and the posture tables (item 17).
12. **#1603 share-card copy / #1598 PQV availability / #1599**: reviewed for duplication only; the share-card words come from shared `tradeCopy.ts` on both platforms (good); no band-aid found in the Python side.

## Suggested order if you want to fix a few

1. Items 1, 2, 10, 11, 12 together (stop swallowing engine failures; mark degraded modes). One PR, small, highest safety per hour.
2. Item 7 (one injury table) then 3 (delete the injury guardrail) then 20/21.
3. Item 6 (decide whether window cost is in the score) with item 17's calibration.
4. Items 4 and 5 (league-scaled thresholds, one confidence) as a longer track.
5. Items 14 and 16 (test hygiene) any time.
