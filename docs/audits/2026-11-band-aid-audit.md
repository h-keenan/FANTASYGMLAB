# Band-aid audit, 2026-11-18

Scope: Python backend (`services/`, `modules/`), `web-next/`, `mobile/`, the guard scripts in `scripts/`, tests and flags.
Method: static search (grep and git history) at `origin/main` e4c81298. Nothing here was run against production data.
"Band-aid" means a change that hides or routes around a symptom while the cause (a forked rule, a scale-blind constant, a missing shared model) stays in place.

Ranked by impact. Effort: S under a day, M a few days, L a week or more. Risk is the risk of making the principled fix.

Items marked **IN FLIGHT** touch a flag, branch or file another agent is actively working on (`p1/redundancy-scoped`, `p1/early-first-top-end`, `p1/floor-retune`, `modules/trade_posture.py`, the pick curve in `modules/trade_ideas.py`, the 3-team finder). They are listed only; nobody should fix them from this audit.

## Summary

1. The biggest remaining band-aid is the **posture vocabulary**: five-plus per-module tables keyed on rebuild/tank/retool/contender were tuned independently, so tuning one (the P1-5 starter-weight floor) broke another (`PRESENT_ADJUST`), and the response was a default-OFF stopgap flag. IN FLIGHT.
2. **Scale-blind absolute point thresholds** in `modules/trade_ideas.py` (1,800 / 3,200 / 5,200 / 7,600 and so on) are the same class of defect that made the franchise-rank test flip on a 3% knife-edge today. They only behave on the realistic player scale.
3. **Age cutoffs are only half migrated** to `modules/age_profile.py`: 22 hardcoded `age <= 25`-style cutoffs remain in `trade_ideas.py` and `rankings.py`, next to the canonical curve that replaced them elsewhere.
4. Two **default-OFF flags have no owner or follow-up** (`DYNASTYGM_NEWS_VALUE_EVENTS` since 2026-10-22, `DYNASTYGM_COLLEGE_SCOUTING_CLASS_STRENGTH_SIGNAL`), and two more are in-flight stopgaps (starter floor, roster redundancy).
5. Guard allowlists had **stale entries that nothing detected** (7 found and removed, fix PRs below); 41 of the 64 `RAW_ALLOWLIST` entries share one boilerplate reason that the guard never verifies.

## Ranked findings

### 1. Posture tables forked across modules (IN FLIGHT)

- Location: `modules/trade_grade.py:225-230` (`STARTER_STRENGTH_WEIGHTS`), `:470-476` (`INJURY_POSTURE_WEIGHTS`), `modules/trade_posture.py:73-96` (`PRESENT_ADJUST` and two siblings), `modules/trade_hub_engine.py:197-198` (youth multipliers), `modules/trade_ideas.py:1556` (`fit_term`), `modules/multi_team_trade_finder.py:86` (`PICK_WANT_BY_GROUP`).
- Why a band-aid: each table encodes "how much does a rebuilder value now vs later" on its own scale. `trade_grade.py:233-240` records the symptom: with the floor on, `PRESENT_ADJUST` "was tuned for the old weights and a tank paying firsts for old vets stopped reading as a decline", so the floor was shipped default OFF (#2158) instead of retuning in one place.
- Principled fix: one `PosturePolicy` (weights for now, future, youth, pick want, window cost) read by grade, posture, hub, finder; tuned and golden-tested as one unit.
- Effort L. Risk high (moves verdicts; needs the backtest harness and a flag).

### 2. Scale-blind absolute thresholds in trade ideas

- Location: `modules/trade_ideas.py:1660-1668` (`_is_throw_in_asset`: 1800 / 2600 / 3200), `:1689`, `:1715-1719` (4200, 7600), `:3252` and `:3278` (5200), `:3529` (6000), `:1890` (`value_delta < -700`).
- Why a band-aid: fixed point cutoffs assume the 10-14 team, 26-man scale. Today's test churn is the evidence: the franchise-rank test used 2,000-point players and flipped on a 3% knife-edge; the value-band test only passed while a 2026 3rd was over-priced (see "Tests changed today", item 5). Hub/Finder already scale window cost to league value (#1602); these do not.
- Principled fix: express thresholds as shares of the league's own value distribution (percentile or share of top-end), computed once per league and passed in.
- Effort M. Risk medium (changes which ideas appear; flag plus before/after idea diff). Shares a file with the early-1st branch, so sequence after it merges.

### 3. Age logic duplicated beside the canonical curve

- Location: `modules/trade_ideas.py:1666, 1689, 1715-1719, 3252, 3278, 3521-3574, 6525-6594`; `modules/rankings.py:1915, 2868, 5917, 5928`. Canonical home: `modules/age_profile.py` (module docstring: "Before this module each advice surface kept its own hardcoded cutoffs").
- Why a band-aid: `_asset_age_band` (`trade_ideas.py:1633`) already uses `age_profile.group_band`, while the Finder ranking terms two screens down (`_target_trade_fit`, `:3559-3574`) still say rebuild means `age <= 25` and contender means `27 <= age <= 30`. One player can be "young" for the band and "old" for the fit.
- Principled fix: replace each literal with `age_profile.is_young/is_prime/...` (they already accept the legacy cutoff, so the kill switch keeps working).
- Effort M. Risk medium (output shifts for QB and RB at the margins; needs a flag and a diff harness). `trade_ideas.py` is contested, so this waits.
- Client side is clean: web and app share `playersPresentation.ts` filters (`web-next/src/lib/playersPresentation.ts:60-62`), which are UI filter buckets, not valuation.

### 4. Stopgap and dark flags without a follow-up

| Flag | Default | Where | Note |
|---|---|---|---|
| `DYNASTYGM_STARTER_WEIGHT_FLOOR_V1` | OFF | `modules/trade_grade.py:241` | In-flight (`p1/floor-retune`). Read at import time, so a runtime flip does nothing; tests use subprocesses. |
| `DYNASTYGM_ROSTER_REDUNDANCY_V1` | OFF | `modules/trade_grade.py:269` | In-flight (`p1/redundancy-scoped`). Moved 45.8% of backtest verdicts. |
| `DYNASTYGM_EARLY_FIRST_TOP_END_V1` | ON on branch only | `p1/early-first-top-end`, not on main | In-flight. |
| `DYNASTYGM_PARTNER_CONTEXT_SEARCH_V1` | ON | `modules/partner_context.py:39` | Introduced ON in #2130, parked OFF in `ab363cc3`, back ON in `d35c436e`, all 2026-11-18. The parking mechanism `SURFACE_DEFAULT_ON` (`:44`) is now an empty dict with a comment describing a state that no longer exists. |
| `DYNASTYGM_NEWS_VALUE_EVENTS` | OFF | `modules/news_value_events.py:40`, hook at `modules/rankings.py:4302` | Dark since #1457 (2026-10-22). Ships a central hook in the valuation path with no owner or flip criterion. |
| `DYNASTYGM_COLLEGE_SCOUTING_CLASS_STRENGTH_SIGNAL` | OFF | `modules/college_scouting.py:60` | Waiting on "a real scouting pool"; no metric or date. |

Default-ON kill switches (graduated; each is a permanent second code path until removed): `PARTNER_CONTEXT_V1`, `_FINDER_V1`, `_DASHBOARD_V1`, `_SEARCH_V1`, `ASK_PICK_IDEA_V1`, `CANONICAL_AGE_CURVE`, `CANONICAL_POSTURE`, `GM_PLAN_PROFILE_V1`, `LIVE_DRAFT_CONTEXT_V1`, `PLAYOFF_ODDS_CONTEXT_V1`, `USAGE_ROLES_TARGETS_V1`, `ROLE_STARTING_DEMAND_V1`, `NO_MARKET_FLOOR_V1`, `EXPERIMENTAL_TEAM_STANCE`, `_DECISION_MEMORY`, `_GM_TARGETS`, `_SHARE_CARDS`, `STATS_SELF_HEAL`.
Operational and debug flags: `STARTUP`, `TEST_MODE`, `BUILD`, `DEPLOYED_AT`, `PERF`, `HOT_PATH`, `DASHBOARD_WATERFALL`, `DEBUG_PERF`, `DEBUG_UI`, `DEBUG_AUTH`, `ALLOW_PROD_DEBUG`, `FORCE_ADMISSION`, `FORCE_RATE_LIMIT`, `PREMIUM_OVERRIDE` (all `DYNASTYGM_`-prefixed; `PREMIUM_OVERRIDE` and `DEBUG_AUTH` are auth-adjacent, not touched).

- Principled fix: every default-OFF flag gets an owner, a flip criterion and a removal date in `modules/experimental_graduation.py`'s registry; graduated kill switches older than one release get deleted with their legacy branch.
- Effort S for the registry, M for pruning. Risk low for the registry, medium for deleting legacy branches.
- Flag parsing used four idioms. Three are now one (fix PR below); `trade_grade.py` (`config_value(...) in {"1","true"...}`) and `stats_self_heal.py:146` (`os.environ.get` directly) differ. The trade_grade pair is in flight.

### 5. Production code that knows it is under test

- Location: `services/mobile_api_service.py:518, 7429` (seven in that file), `modules/stats_self_heal.py:143`, `modules/league_prewarm.py`, `modules/launch_analytics.py`, `modules/admission.py`, all branching on `PYTEST_CURRENT_TEST`; opt back in via `DYNASTYGM_FORCE_RATE_LIMIT` / `FORCE_ADMISSION`.
- Why a band-aid: the rate limiter and admission control are disabled under pytest, so the code paths that run in production are the ones tests exercise least.
- Principled fix: inject the limiter and clock through app config (tests pass a no-op), and delete the env sniffing.
- Effort M. Risk medium (touches request admission; not auth or billing, but near it).

### 6. Silent failure handling

- Python: 810 broad `except Exception`/bare `except` under `services/` and `modules/`; 134 of them are a bare `pass`. Most are best-effort telemetry or cache (`services/mobile_api_service.py:587, 957, 992, 1092, 1157, 4599`). Worth a look: `:4588` (saved-league migration swallowed) and the 6-7 per file in `modules/prepared_player_frame.py`, `modules/nflverse_contracts.py`, `modules/game_plan_process_cache.py`, `modules/session_integrity.py`, `modules/free_tier_ledger.py`, `modules/auth_supabase.py`, `modules/auth_storage_handshake.py`. Auth and billing files are listed only.
- Web/app: 173 empty `catch {}` or `.catch(() => {})`. Most are secondary reads. A real one: `web-next/src/components/SimGameTrades.tsx:312, 322` (and the mobile twin) swallow a failed roster load, leaving the trade builder empty with no message; `ShareToCommunityToggle.tsx:82` swallows a failed delete after already flipping the toggle off.
- Principled fix: one `bestEffort(label, fn)` helper that logs to the existing error reporter and counts; user-visible loads get an error state. Precedent: #1614 "Stop swallowing engine failures".
- Effort M. Risk low.

### 7. Duplicated helpers and maps

- 32 per-module float coercers (`_num` x19, `_safe_float` x9, `safe_float` x2, `_float` x2) with different NaN and exception semantics (`modules/trade_ideas.py:170` catches `Exception`; `modules/live_draft.py:61` also maps NaN to the default; `modules/trade_outcome_results.py:107` returns None). Fix: three named variants in one `modules/coerce.py`. Effort M, risk medium (NaN semantics differ per call site).
- Web grade-tone colour maps disagree: `web-next/src/lib/leagueRecapsPresentation.ts:110` maps `positive` to information blue and `risk` to warning; `web-next/src/lib/managerTendencies.ts:90` maps `positive` to accent and `risk` to **danger red**; `mobile/src/lib/managerTendencies.ts:52` and `mobile/src/lib/sharedTrades.ts:45` are two more variants. Fix: one `toneToken(tone)` in `verdictTone.ts`, which the verdict colours already share. Effort S, risk low but it changes colour on two surfaces (design call).
- Pick labels: `pickCompactLabel` (`web-next/src/lib/tradeIdeaPick.ts`) says it is "the one short pick label every trade surface shows", yet `Round N` strings remain at `leagueRecapsPresentation.ts:119`, `shareCard/tradeCard.tsx:50`, `shareCard/analyzerShare.ts:87`, `mobile/src/components/TradeShareCard.tsx:199`, `mobile/src/lib/tradePitch.ts:57`, `web-next/src/lib/simGame.ts:3430`, `PickRow.tsx:43`. Share cards may legitimately want the long form; decide per surface.
- 37 web/mobile lib twins sit in `DIVERGED` in `scripts/check_lib_twins.mjs` (acknowledged debt). Several diverge only in types (`guillotine.ts`, `scoutingLens.ts`) and could use `SHARED BEGIN/END` markers; real drift: `managerTendencies.ts` (191 differing lines), `playerTier.ts` (261), `tradeOffer.ts` (102), `leaguePlatform.ts` (108), `percentileExplorer.ts` (162).
- Sim: `modules/sim/player_model.py` plus `_v2` through `_v7` are seven near-copies. Intentional for replay determinism, but the shared 4:1 promotion logic is repeated in each.

### 8. Guard allowlists

- `scripts/check_player_tap.mjs:39` `RAW_ALLOWLIST`: 64 entries; 41 carry the same sentence "draws its own identity markup and wires its own tap ... audited in the 2026-11-14 tap sweep". The guard already fails on entries that no longer draw a raw avatar, but nothing checks the claim. 12 of those files contain no tap symbol from the set (`PlayerTap`, `PlayerIdentityTrigger`, `openPlayer`, ...): `mobile/.../MatchupLineup.tsx`, `PlayerCard.tsx`, `PlayerCardKit.tsx`, `PlayerListRow.tsx`, `SimDraftBar/Grid/Hero.tsx` (both trees), `TradePickerSheet.tsx` (both trees). The Sim draft files do wire taps through an `onOpen` callback, so the reason is only imprecise, but the sweep was not mechanically verified. Fix: replace the boilerplate with a per-file reason or an `exempt:` entry, and have the guard require a tap symbol or callback prop. Effort S-M, risk low.
- `scripts/check_skeleton_identity.mjs` `ALLOW` / `SPINNER_ALLOW` ("it should only shrink") had no stale-entry check; 7 stale entries found (fixed, below). `scripts/check_motion_usage.mjs` `LAYOUT_TRANSITION_ALLOW` had none either (all 9 live today; check added). `check_presence_usage.mjs` and `check_player_tap.mjs` already detect stale entries. `check_nav_sheet.mjs` lists implementers rather than exceptions and is fine.
- `view-select-ok` (12 uses). Two say "pre-existing ... candidate for chips" with no tracker: `web-next/src/components/WaiversContent.tsx:725`, `LiveDraftContent.tsx:332`. The rule is a 4-or-fewer-options one, and "Overall + 5+ position filters" is above 4, so the comment is not needed there at all; confirm the guard needs it.
- Added today and healthy: `check_verdict_colors.mjs` rules 10a/10b (#2161) are patterns, not allowlists.

### 9. Skipped, seed-dependent and regen tests

- No `xfail`, no retry-on-flake config, no `describe.skip`/`it.skip` in web or app. TODO/FIXME/HACK markers: effectively none (5 hits, all `XXX` placeholder team codes or a comment about the word TODO). The discipline lives in comments saying "stopgap" instead; see item 4.
- Conditional skips that silently drop coverage when a seed or fixture changes: `tests/test_sim_dynasty.py:376`, `test_sim_game_api.py:394, 434`, `test_sim_pages_multiseason.py:129`, `test_sim_block.py:266`, `test_sim_pos_v.py:135`, `test_sim_byes_picks.py:168`, `test_sim_simto.py:306`, `test_sim_game_engine.py:244, 653, 726`. Fix: pin a seed known to produce the scenario and assert, or build the scenario directly. Effort M, risk low.
- Environment skips (no `players.db` / `sleeper_players.json`): `test_sim_isolation.py:416, 443, 455`, `test_sim_game_settings.py:572`, `test_sim_game_engine.py:921`, `test_injury_status_table.py:19`, `test_build_players_table_skips_identical_rewrite.py` x4. These only run in a checkout with data, so CI may never exercise them.
- `tests/test_lineup_solve_golden.py:92` skips by design when `LINEUP_GOLDEN_REGEN` is set (regeneration switch for the #2160 golden). Fine, but note a regen run reports "skipped", not "regenerated".
- Web: `playerAvatarRule.test.ts:79` and `shareCard/render.test.tsx:94` skip when the mobile tree or a preview dir is absent.

### 10. Billing-adjacent simplification (escalated, not touched)

- `modules/saved_leagues.py:63-72` and `services/mobile_api_service.py:1747-1757`: Front Office was folded into Pro ("until we have enough features to segregate", coridian_, 2026-10-19) by editing the cap function and removing the checkout plan. It is labelled temporary in both places, and the one existing Front Office subscriber is special-cased by comment. This is a product-direction and billing call, so it is listed for the owner and not changed.

### 11. Hardcoded players, teams or leagues

None found in `services/`, `modules/`, `web-next/src` or `mobile/src` outside fixtures, design-system pages and name-formatting examples (`web-next/src/app/design/DesignSystemContent.tsx:58`, `playerNameFixtures.ts`). The only literal id compare is the "0" sentinel at `services/mobile_api_service.py:16547`. The one hardcoded person-specific rule is the Front Office subscriber note in item 10.

## Tests changed today (2026-11-18)

Verified against merge commits (`git diff <merge>^1 <merge> -- tests`) and `gh pr view`. Corrections to the brief are in bold.

1. **#2156** (merge 8197fac3), `tests/test_trade_posture.py`: the tank old-vets assertion was relaxed from `{"DECLINE", "COUNTER"}` to `{"DECLINE", "COUNTER", "FAIR"}`, because the starter-weight floor (tank 0 to 0.20) stopped it reading as a decline. Reverted by #2158 (merge b192ba85; on main as `efdf438c`). Reason it was a band-aid: the test caught a real behaviour change and the assertion was loosened instead of retuning `PRESENT_ADJUST`; the revert plus the OFF default is the correct outcome.
2. **#2156**, `tests/test_age_curve_qb_scale_smoothing.py`: age-27 rebuild multiplier `1.01` to `1.005` (youth bonus halved, comment "audit P1-5"). Reverted by #2158. Re-application in the P1-5 retune PR with a ramp/no-cliff assertion: not on main yet, so unverified (branch `p1/floor-retune`).
3. **#2156**, `tests/test_trade_grade.py::test_breaking_up_a_stud_for_depth_is_a_decline`: rebuild `lineup_model.weights.now` `1.05` to `1.20`. Reverted by #2158. Re-application with the decline property kept: not on main yet (`p1/floor-retune`). **Also in #2156 and rewritten (not just reverted) by #2158:** three new subprocess tests, `test_starter_floor_defaults_on_for_rebuild_and_tank_only`, `..._can_be_switched_off` and `test_youth_bonus_is_tempered_by_default_and_restored_when_off`, which #2158 turned into default-OFF versions.
4. **#2148** (merge 7f535d7f) added the pins; **#2149** (merge d57aca39) removed them. #2148 added `monkeypatch.setenv("DYNASTYGM_ROSTER_REDUNDANCY_V1", "0")` to `tests/test_trade_finder_pick_search.py` (autouse), `tests/test_trade_target_offers.py` (autouse) and `tests/test_multi_team_trade_finder.py` (one test), with the reason "pins pick-search mechanics on synthetic full rosters; the depth player would be priced at the 50% bench-chip rate". **Correction:** the flag was default ON in #2148, so the pins were needed then; #2149 flipped it OFF and deleted all three pins. #2148 also changed `tests/test_trade_grade.py` expected points `-2000/2000` to `-2500/2500` (bench retention 0.50) and flipped `test_redundancy_flag_defaults_off` to defaults-on; #2149 flipped it back.
5. **The early-1st PR is not merged.** It is commits `14192db6` and `248a1699` on `p1/early-first-top-end` (no PR number on main). Three fixture changes in `248a1699`, each with its reason:
   - `tests/test_mobile_api_service.py::test_team_rankings_returns_power_and_franchise_ranks`: the 2-team, 2,000-point-player fixture became a realistic 10-team league (`_realistic_rank_frame`, assertions `len == 10`, roster 2 `power_rank` and `standing_rank` 10, plus `franchise_rank` ordering). Reason: one roster's whole value (~11k) was the size of one team's pick capital, so the franchise rank flipped on a 3% knife-edge whenever the pick curve moved. New `tests/test_franchise_pick_share.py` pins the cause (picks stay a minor share of franchise value: under 15% for 12 teams, under 50% for 2 teams, with the flag on and off).
   - Selection-contract test: unchanged; made to pass by the Finder leave-one-out probe fix in `modules/trade_ideas.py`, not by editing the test. (Same commit also touched `tests/test_pick_early_first_top_end.py` to add a generic `_value` helper and a future-discount-unchanged assertion, strengthening it.)
   - `tests/test_trade_finder_pick_search.py::test_value_band_scales_with_the_selection_instead_of_a_fixed_floor`: `roster_size=32`. Reason: the 26-man fixture's cheapest player is 1,292, so it never held the 200-1,000 assets the test is about; it only passed while a 2026 3rd was priced above the market (~1,480). Assertions unchanged. Labelled "coordinator-approved fixture change".
6. **#2161** (merge 9ba97ce1), `web-next/src/components/TradeAnalyzerContent.test.tsx`: button name `"Add 2027 Round 1"` to `"Add 2027 1st"`. Intended copy change: `tradeAnalyzerPresentation.ts` now routes pick labels through `pickCompactLabel`. Same PR added check_verdict_colors rules 10a/10b and the `sideDotColor` mapping (grey for "You send").
7. **#2147** (merge 14debc85), `scripts/check_player_tap.mjs`: three `RAW_ALLOWLIST` entries, not two: `web-next/src/components/SeasonWrapped.tsx` and `mobile/src/components/SeasonWrapped.tsx` ("full-screen Season Wrapped story: player sheets would open underneath it") and `mobile/src/components/WrappedShareCard.tsx` ("exempt: a rendered share-card image"). The web share card (`web-next/src/lib/shareCard/wrappedCard.tsx`) needed none. The same PR also added `"wrapped.ts"` to the lib-twins registry in `scripts/check_lib_twins.mjs`.

No sanity or golden test was deleted or relaxed on main by this audit.

## Part 2: fixes made from this audit

Rule applied: highest impact and lowest risk first, output identical unless the fix is the point, no billing/auth/secrets/data-deletion/product-direction work, nothing in flight.

| Item | Fix | PR | Output change |
|---|---|---|---|
| 8 | Stale-entry detection in `check_skeleton_identity.mjs` and `check_motion_usage.mjs`; 7 dead `ALLOW` entries removed | see PR list in the hand-off | None (guards only; both trees covered) |
| 4 | `valuation_anchors.flag_default_on` delegates to `graduated_kill_switch_enabled` | see PR list in the hand-off | None; equivalence checked for 16 env values |

Escalated or left for the owner: items 1, 2, 3, 4 (in-flight flags), 5, 10 and the client-side items in 7 (colour change is a design decision).
