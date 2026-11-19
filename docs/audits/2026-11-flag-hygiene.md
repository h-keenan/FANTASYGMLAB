# Flag hygiene audit, November 2026

Date: 2026-11-19. Branch base: `origin/main` at 73d6a036 (later main for the fix PRs).
Extends the flag inventory in `docs/audits/2026-11-band-aid-audit.md` (section 4); that section is not repeated here, only completed with the added-in commit, proof, owner and class columns.

Classes: (a) proven ON and stable, promote; (b) dead, delete; (c) stopgap still OFF, needs follow-up and owner; (d) Sim save-replay version flag, never removed; (k) kept kill switch or operational flag.

Method: `grep DYNASTYGM_` over `modules/ services/ scripts/`, `git log --reverse -S<name>` for the first commit that carried each name (commit subject cited; the PR number appears when the subject has one), and reading each reader function. "Proof" means a backtest or harness named in the adding commit or in the flag's own module docstring.

## 1. Product env flags (read in code)

| Flag | Default | Reader | Added in | Status | Proof | Owner / follow-up | Class |
|---|---|---|---|---|---|---|---|
| `DYNASTYGM_CANONICAL_AGE_CURVE` | ON | `age_profile` (`AGE_CURVE_ENV_KEY`, `:36`) | 672a1248 2026-11-18 "one age curve" | on | Docstring: off restores legacy cutoffs bit for bit; kill switch requested | none; revisit 2026-12-19 | k |
| `DYNASTYGM_CANONICAL_POSTURE` | ON | `league_rankings.canonical_posture_enabled` (`:348`), `mobile_api_service:2838` | 672a1248 | on | Comment names the kill switch and the exact legacy behaviour | none; revisit 2026-12-19 | k |
| `DYNASTYGM_PARTNER_CONTEXT_V1` | ON | `partner_context.enabled` (`:65`) | 574f7164 2026-11-18 (handshakes 3-5) | on | `scripts/audits/partner_context_diff.py` | in-flight area, not touched | k |
| `..._PARTNER_CONTEXT_FINDER_V1`, `_DASHBOARD_V1`, `_SEARCH_V1` | ON | `partner_context.surface_enabled` | c0b2bf66 #2130 2026-11-18 | on (SEARCH briefly parked OFF in ab363cc3) | `scripts/audits/handshakes_extension_diff.py` | in-flight area, not touched | k |
| `DYNASTYGM_ASK_PICK_IDEA_V1` | ON | `partner_context.ask_pick_enabled`, `trade_ideas:6028` | c0b2bf66 #2130 | on | same diff harness | in-flight area, not touched | k |
| `DYNASTYGM_LIVE_DRAFT_CONTEXT_V1` | ON | `live_draft_context` (`:37`) | 5f4bd465 2026-11-18 (handshake 8) | on | `handshakes_7_10_diff.py` | none | k |
| `DYNASTYGM_PLAYOFF_ODDS_CONTEXT_V1` | ON | `playoff_context` (`:38`) | 0eb55b7f 2026-11-18 (handshake 9) | on | `handshakes_7_10_diff.py` | none | k |
| `DYNASTYGM_USAGE_ROLES_TARGETS_V1` | ON | `usage_roles_targets` (`:34`) | 812b9476 2026-11-18 (handshake 10b) | on | `handshakes_7_10_diff.py` | none | k |
| `DYNASTYGM_ROLE_STARTING_DEMAND_V1` | ON | `valuation_anchors.starting_demand_enabled` (`:34`) | 5d9e2e43 2026-11-18, shipped OFF then flipped ON, "owner-approved 2026-11-18" | on | `docs/audits/2026-11-trade-advice-backtest.md` section 8 | none; revisit 2026-12-19 | k |
| `DYNASTYGM_NO_MARKET_FLOOR_V1` | ON | `valuation_anchors.no_market_floor_enabled` (`:35`) | 5d9e2e43 | on | same backtest | none; revisit 2026-12-19 | k |
| `DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY` | ON | `decision_memory`, `app_config`, `launch_analytics` | bda3bc0a #160 2026-08-07, graduated 2c699c5d #232 | on, 3+ months | `#232` matrix | none; kill switch named in the registry "launch_default" text | a candidate, kept (asked for) |
| `DYNASTYGM_EXPERIMENTAL_GM_TARGETS` | ON | `gm_targets:30` | graduated 2c699c5d #232 | on, 3+ months | `#232` | as above | a candidate, kept |
| `DYNASTYGM_EXPERIMENTAL_SHARE_CARDS` | ON | `share_recommendation_cards:28` | graduated 2c699c5d #232 | on, 3+ months | `#232` | as above | a candidate, kept |
| `DYNASTYGM_EXPERIMENTAL_TEAM_STANCE` | ON | `team_stance:55` | eca6e716 2026-09-24 | on, 2 months | docstring "Graduated: default ON. Kill switch" | none | a candidate, kept |
| `DYNASTYGM_STATS_SELF_HEAL` | ON | `stats_self_heal:146` (raw `os.environ`) | b0476bec 2026-11-17 | on | ops kill switch | none | k |
| `DYNASTYGM_NEWS_VALUE_EVENTS` (+ `_PATH`) | OFF | `news_value_events:40`, hook `rankings.py:4298` | 64786ab9 #1457 2026-10-22 | **stopgap OFF** | walk-forward backtest 2021-2025 in #1457 (69% first-game shortfall) | **no owner, no flip criterion.** Queued for a separate backtest. Listed, not deleted | c |
| `DYNASTYGM_COLLEGE_SCOUTING_CLASS_STRENGTH_SIGNAL` | OFF | `college_scouting:60` | b6cafef5 2026-09-26 | **stopgap OFF** | none | **no owner.** Waiting on "a real scouting pool"; queued for a separate backtest. Listed, not deleted | c |
| `DYNASTYGM_STARTER_WEIGHT_FLOOR_V1` | OFF | `trade_grade:241` (import time) | p1/floor-retune | **stopgap OFF** | band-aid audit | another agent, in flight, DO NOT TOUCH | c |
| `DYNASTYGM_ROSTER_REDUNDANCY_V1` | OFF | `trade_grade:269` | #2148, flipped OFF by #2149 | **stopgap OFF** | moved 45.8% of backtest verdicts | another agent, in flight, DO NOT TOUCH | c |
| `DYNASTYGM_EARLY_FIRST_TOP_END_V1` | ON | `trade_ideas:525` | #2169 (merged) | on | see PR | another agent, DO NOT TOUCH | k |

Why almost nothing is class (a): every flag above that is old enough to be stable (the four graduated experiments) names its kill switch in the registry text or the module docstring, so the "keep it where the PR asked for one" rule applies. Every flag that ships in the 2026-11-18 batch is under a day to a week old, and a flag promoted before a release has passed is not "stable". Re-check on 2026-12-19.

## 2. Operational and dev flags (class k, not touched)

`DYNASTYGM_` `STARTUP`, `TEST_MODE`, `BUILD`, `DEPLOYED_AT`, `PERF`, `SPAN`, `TRUST`, `HOT_PATH`, `DASHBOARD_WATERFALL`, `DEBUG_PERF`, `DEBUG_UI`, `DEBUG_AUTH`, `ALLOW_PROD_DEBUG`, `FORCE_ADMISSION`, `FORCE_RATE_LIMIT`, `PREMIUM_OVERRIDE`, `RUNTIME`, `SELF_HOSTED`, `FOUNDER_OPS`, `DEV_REVIEW`, `SHOW_EXPERIMENTAL`, `SHOW_DEV_DESTINATIONS`, `DEV_RELOAD_MODULES`, `LAUNCH_ANALYTICS`, `LAUNCH_ANALYTICS_PATH`, `ANALYTICS_ENV`, `NEWS_EVIDENCE_FETCH`, `LEAGUE_IMPORT`, `PLAYER_ELIGIBILITY`, `STATS_CACHE_DIR`. All are documented in `docs/runtime-environment-contract.md` or `config/README.md`, and are read by app code or tests; none is dead. `SHOW_DEV_DESTINATIONS` and `DEV_RELOAD_MODULES` gate surfaces the contract says currently have nothing behind them ("No DEV_ONLY pages currently registered"), so they are the next deletion candidates but are runtime contract items and are left for an owner decision.

## 3. Dead code found (class b)

| Item | Evidence | Action |
|---|---|---|
| `partner_context.SURFACE_DEFAULT_ON` (empty dict) and its `.get(env_key, True)` reader in `surface_enabled` | Dict is `{}`; the only other reader is `tests/test_partner_context_extension.py:61` whose else branch is unreachable. The comment describes SEARCH being parked OFF, which was reverted | Deleted in the fix PR |

## 4. Sim save-replay version flags (class d, NEVER remove)

Source: `modules/sim/game_types.py` (field defaults 0, so every old save replays on its original rules) and `modules/sim/game_rules.py` `UPGRADABLE_FLAGS` (value switched to, boundary when it takes effect). All are on for new games, status "on". None has an env switch; the reader is the `GameSettings` field plus the capability property in `game_types.py`. "Proof" cites the adding commit; harnesses are named where the subject names one.

| Flag | New-game value | Upgradable (boundary) | Added in |
|---|---|---|---|
| `dynasty_v` | 3 | no | b0152182 #1787 2026-11-12 |
| `reserve_v` | 1 | no | b0152182 #1787 |
| `block_v` | 2 | no | 92171ee9 2026-11-13 |
| `ai_v` | 1 | no | 240eaa89 #1843 |
| `names_v` | 1 | yes (season) | 8a2b80e0 |
| `kd_v` | 1 | yes (now) | 1bf00872 |
| `limit_v` | 1 | yes (now) | 4428af02 |
| `hint_v` | 1 | yes (now) | 5202f835 |
| `aging_v` | 1 | yes (season) | 709300b3 |
| `world_v` | 1 | yes (week) | 5279b3dc, usage/injury audit harness |
| `econ_v` | 1 | yes (now) | 5b81195b, economy audit harness |
| `stability_v` | 4 | yes (season) | 214c09a1 #1985 |
| `vorp_v` | 1 | yes (now) | 81db22b1 |
| `advice_v` | 1 | yes (now) | 140b892f |
| `incumbent_v` | 1 | yes (season) | ae6d6f72 |
| `defense_v` | 1 | yes (week) | ae6d6f72 |
| `pos_v` | 1 | yes (now) | bd2e5d86 |
| `injury_v` | 1 | yes (week) | ad37ee9b #2015 |
| `rookie_v` | 1 | yes (season) | e03f823f |
| `posture_v` | 1 | yes (week) | 31e2fd99 |
| `cap_v` | 1 | yes (now) | f9a2ed9a |
| `need_v` | 1 | yes (now) | 828a96da |
| `wire_v` | 1 | yes (week) | 7932ec67 |
| `cover_v` | 1 | yes (week) | abd5affc, team-score harness vs real Sleeper 2021-25 |
| `wrapped_v` | 1 | no | 994ef861 #2146 |
| `watch_v` | 1 | no | caa41971 |

`start_week` is a settings field, not a version flag; it is serialized only when set. Owner for all: the Sim engine owner; follow-up is none by design. Removing any of these breaks deterministic replay of old saves.

## 5. Follow-ups

1. Stopgaps still OFF: see the table in section 1 (class c). Needs owner assignment for `NEWS_VALUE_EVENTS` and the college class-strength signal (backtest queued); the two trade_grade flags and the early-first flag stay with the agent that owns them.
2. The registry in `modules/experimental_graduation.py` now carries an owner, a flip criterion and a review date for each flag in sections 1 above (fix PR). Owners shown as "unassigned" need a human.
3. 2026-12-19: re-run this audit; delete the kill switch and legacy branch for flags that were never flipped in production, starting with `CANONICAL_AGE_CURVE`, `CANONICAL_POSTURE`, `ROLE_STARTING_DEMAND_V1`, `NO_MARKET_FLOOR_V1`.
4. Flag parsing: `stats_self_heal.py:146` and `trade_grade.py` still parse the env themselves (band-aid audit section 4).
