# Post-436 release stabilization

Base: `165a2ac239c8cb32fa7c484b9fb9da3c2e030722` (latest origin/main after #436 merged).
Release stabilization only. Keep the PR draft, labeled `human-approval-required`; no auto-merge. #435 is untouched.

## Baseline method

Environment: Windows, Python 3.14, Streamlit 1.58.0. `python -m pytest tests/ -q --tb=line` stopped at collection because `scripts/test_realistic_session_load.py` imported Unix-only `resource`. To enumerate every runnable node without concealing that error, a separate untouched worktree at the base SHA ran the same command with `--continue-on-collection-errors`: **22 failed, 3714 passed, 1 collection error, 12 subtests passed**. The collection error prevented 16 tests from running. One existing Starlette/httpx deprecation warning was reported.

An earlier run returned 21 failed / 3715 passed plus the same collection error. It was repeated because a concurrent production performance AppTest could write the player database. The isolated repeat reproduced all 21 failures and exposed an intermittent mobile viewport failure. The Trust profiling helper also independently writes/hydrates its input database; the new opt-in temporary-copy fixture fixes that contamination.

Chromium installed successfully with `python -m playwright install chromium`, without changing requirements. Browser failures are therefore investigated as contracts/harness failures, not labeled infrastructure-gated. Historical #436 totals (31/3721) are context, not substituted for this host's measured baseline.

## Exact baseline failure ledger

Categories: A product defect; B stale assertion/golden; C harness defect; D environment/browser dependency; E data/fixture staleness; F unknown.

| Failing node ID | Category | Contract traced and repair |
|---|---|---|
| `tests/test_app_css_architecture.py::test_route_owned_css_is_injected_by_owners` | B | PQV and Trade Detail owners now inject `DECISION_SURFACE_DIALOG_CSS +` their route CSS. Assert both exact combined injections; route-exclusion and size checks remain. |
| `tests/test_archetype_experiment_protocol.py::test_application_remains_unmodified_and_exposes_no_archetype_selector` | B | The public canonical valuation lens selector is intentional. Assert its supported-lens input and canonical session key, retaining the ban on experimental archetypes and radio controls. |
| `tests/test_canonical_player_state_authority.py::test_active_unsigned_cached_market_value_remains_globally_searchable` | E | The 1060 golden uses current/prior seasons 2025/2024. Pin those fixture seasons instead of letting September rollover choose 2026/2025. Retain 222 provider value, 1060 canonical value, and authoritative provenance assertions. |
| `tests/test_css_dom_ownership.py::test_production_equivalent_computed_styles_chromium_390` | B | Mobile PQV intentionally uses `clamp(2.75rem,14vw,3.5rem)` (54.6px at 390); compact trade assets use 2.25rem (36px). Assert exact dimensions within existing tolerances; retain image fill, square geometry, crop, Orb and dashboard checks. |
| `tests/test_css_dom_ownership.py::test_real_player_computed_styles_cover_several_headshots` | B | Replace obsolete >70px assumption with exact 54.6px mobile portrait geometry for every representative player; retain natural resolution and 1.65 crop. |
| `tests/test_css_dom_ownership.py::test_chromium_1440_keeps_filled_hero_and_standard_trade_portrait` | B | Fixture calls the default compact asset renderer, whose token is 36px, not the prior 52px. Desktop hero fill/crop and dashboard dimensions remain checked. |
| `tests/test_email_confirmation_pending_ux.py::test_email_confirm_callback_consumes_guest_resume` | C | Text slicing matched an earlier JavaScript payload occurrence. Anchor to the Python successful email-confirm assignment; retain peek/resume/email-confirm surface assertions. |
| `tests/test_executive_visual_finalization.py::test_legacy_avatar_black_gradient_removed_from_shared_portrait_classes` | C | Substring search matched `.trade-avatar,` inside an earlier scoped selector. Select the exact shared three-selector rule; preserve gradient token, black-color exclusion, and square-shape checks. |
| `tests/test_founder_beta_core_ux.py::test_landing_headline_wraps_by_words_on_narrow_phones` | B | Current compact welcome layout constrains the mobile main container to `calc(100vw - 1.25rem)`. Assert that selector/declaration; retain word wrapping, no hyphenation and route CSS ownership. |
| `tests/test_founder_beta_workflow_ux.py::test_pqv_spacing_is_not_over_compressed` | B | The dossier now uses grid gaps rather than old panel padding/margins. Assert current workspace/decision grid gaps and minimum touch targets; keep the recommendation-context compression guard. |
| `tests/test_league_switch_first_useful.py::test_no_football_modules_touched` | C | Local `main` is stale and included already-merged Trust changes. Compare the release branch against `origin/main`, the requested base; make git failures fail closed with `check=True`. Forbidden Trust paths remain identical. |
| `tests/test_legacy_color_cleanup.py::test_active_css_drops_known_legacy_sky_and_streamlit_blues` | B | `--color-position-wr: #7dd3fc` is an intentional semantic position token. Exempt only that exact declaration; all legacy accent literals remain prohibited elsewhere. |
| `tests/test_roster_aware_trade_alerts_ia.py::test_alert_injury_row_has_concise_non_repetitive_hierarchy` | B | Current accessible urgency label is `URGENT player alert`; assert exact casing. All hierarchy/content checks remain. |
| `tests/test_signal_intelligence_v1.py::test_see_all_timeline_includes_general_news` | C | Uncontrolled disk news joined the synthetic timeline and affected its bounded result. Stub only the independent disk-news input to empty; continue asserting both urgent and general-news entries and the News filter. |
| `tests/test_trade_hub_first_useful_result.py::test_no_football_logic_modules_modified_for_this_pr` | C | Same stale local-main comparison; use the actual remote base and fail closed on git errors. No forbidden path removed. |
| `tests/test_trade_hub_profiling.py::test_committed_golden_matches_fresh_deterministic_fixture[spec1]` | B | `9cfaf12` intentionally introduced Superflex QB-scarcity realism. Current 8-team Superflex raw/approved/displayed counts are 17/17/17, formerly 20/20/20. Update complete exact golden, not thresholds. |
| `tests/test_trade_hub_profiling.py::test_committed_golden_matches_fresh_deterministic_fixture[spec3]` | B | Same intentional realism change; 12-team primary counts are 8/8/8, formerly 10/10/10. Update complete exact golden; preserve Trust and ranking logic. |
| `tests/test_trust_cpu_optimization.py::test_real_public_player_dataset_is_exactly_equivalent` | C | Loader now reconciles 988 persisted rows to 1880 current-universe rows and writes its input. Hydrate a temporary copy, assert source hash unchanged and exact 1880 output count; preserve all eight exact equivalence checks. |
| `tests/test_trust_row_mapping_optimization.py::test_real_988_player_frame_is_field_for_field_equivalent` | C | Reuse the isolated hydrated fixture and assert 1880. Preserve full frame, dtype, diagnostics, fingerprints, column order and null-mask equivalence. Historical node ID retained. |
| `tests/test_valuation_archetypes.py::test_workspace_affordance_uses_native_action_and_canonical_modal` | B | Explanation action is now `How valuation works`; the separate selector owns the canonical lens. Assert native action/key, lens input/key, and canonical modal rather than removed tooltip copy. |
| `tests/test_valuation_authority.py::test_actual_keenan_cached_provider_value_runs_canonical_local_model` | E | Pin 2025/2024 golden seasons. Retain exact 1060 value, provider provenance, no-network guards, trade eligibility, and unchanged modeled peer value. |
| `tests/test_viewport_preservation.py::test_browser_in_place_actions_keep_region[390-844]` | C | Fixed 700ms wait raced final components.v2 viewport handler binding on cold load. Wait for `__dgViewportPreserveBound` and fonts before interaction; retain every viewport assertion and add before/after measurements on failure. |

Collection error: `tests/test_startup_latency_cleanup_234.py` — **C**. Optional Unix RSS telemetry was imported before its existing fail-soft boundary. Move the import inside `_rss_mb` so unsupported telemetry returns `None`; concurrency, isolation, timeout and load contracts run unchanged on Windows.

No failure is left lumped into an uninvestigated category. Final validation and remaining failures are recorded below.

## Evidence for intentional changes

- Substituting only pre-`9cfaf12` `evaluate_trade_market_realism` and `_trade_confidence_context` functions in an isolated diagnostic reproduced **both committed old goldens exactly**, including all fields and order. Current functions produce 17 and 8 ideas. The production implementation is unchanged.
- Starting from the committed 988-row database, canonical reconciliation produces Keenan value **1060 with 2025/2024 stats** and **884 with 2026/2025 stats**. The September season transition is intentional; pinning historical golden inputs is the repair.
- Chromium measured the current mobile PQV at 54.6px and compact trade portrait at 36px. Production styles already define these dimensions. No APP_CSS or other production CSS is edited.
- The optional WebKit branch in the same CSS test is aligned to the same current mobile dimension; it retains its pre-existing unavailable-engine behavior.

## Server-only AppTest boundary

`scripts/apptest_support.py::server_only_summary_tiles` is a scoped test context. It models only the summary-tile registration-unavailable `ValueError`, deliberately driving the real production HTML fallback. It is not imported by production. Other errors still propagate; component identity is restored on context exit. Two AppTest runs with fresh registries verify the HTML content and scoped restoration. A separate Chromium test executes the actual production component JavaScript, asserting exactly one trigger per click, Enter and Space, and none for a non-tappable tile. Existing mobile/Playwright validation remains present.

The budget script uses that context. No global production flag, component removal, blanket exception catch, extra provider/model call, rerun, or CSS expansion is introduced.

## Validation

Final results pending the complete run.
