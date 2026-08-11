# Product-wide UI/UX polish + performance / redundancy audit

Branch: `cursor/product-ui-perf-polish-71e1`
Rollback SHA: `d045a8666ed22b392c7fcb84ef4579e7b8b69f85` (#247 merge on `main`)

## Scope

Diagnose-first refinement. No football methodology, entitlement, Stripe,
auth-authority, cache-TTL, or experimental-graduation changes. Preserve
#244 scoped GM Orb `:has(>)` and #247 orb geometry forever.

## A — UI primitive inventory (production)

| Primitive | Semantic purpose | Helper | Primary CSS |
|---|---|---|---|
| Page context | Route identity strip | `app.py` page shell | `.dg-page-context`, `.dg-page-shell--*`, `.dg-page-meta` |
| Section header | Section hierarchy | `ui_primitives.render_section_header` | `.dg-ui-section-header`, `.dg-ui-eyebrow`, `.dg-ui-section-title`, `.dg-ui-section-subtitle` |
| Content card | Decision / supporting card | `ui_primitives.render_content_card` | `.dg-ui-card`, tone modifiers |
| Summary tile | Compact metrics | `workspace_ui.render_summary_tiles` | `.summary-tile.dg-ui-card` |
| Analysis card | Supporting analysis | `workspace_ui.render_analysis_cards` | `.analysis-card.dg-ui-card` |
| Decision panel | Strength / risk buckets | `workspace_ui` decision helpers | `.decision-panel`, `-body`, `-empty` |
| Home command | Dashboard destinations | home command renderers | `.home-command-card.dg-ui-card` |
| Quiet status | Empty / clear / discovery | feature UIs | `.dg-what-changed-quiet`, `.dg-daily-briefing-quiet`, `.dg-gm-targets-quiet`, `.dashboard-clear-state` |
| Streamlit CTA | Primary / secondary / tertiary | `st.container(key=dg_cta_*)` | polish `st-key-dg_cta_*` |
| Disclosure | Client details | `workspace_ui.client_disclosure_html` | `.dg-info-disclosure`, `.dg-client-disclosure` |
| Expander | Streamlit disclosure | `st.expander` | `div[data-testid="stExpander"]` (polish owner) |
| Badge / chip | Status | `status_badge_html` | `.dg-ui-badge--*` |
| Empty state | Recovery | `render_empty_state_panel` | `.dg-ui-empty-state` |
| Player row/card | Ranked / roster / FA | `football_assets` / `player_cards` | `.scan-card`, `.compact-player-row`, `.free-agent-card` |
| Surfaces | L0–L2 | CSS tokens | `.dg-surface-l0/l1/l2` |
| GM Orb | Floating nav | mobile overlay | scoped `:has(>)` + orb geometry |

### Canonical hierarchy (unchanged roles)

- L0 page/background → L1 surface → L2 raised
- Primary decision card > supporting card > status/quiet
- Primary CTA > secondary > tertiary/text
- Premium lock > ordinary note; warning > neutral

### UI primitives removed / consolidated

**Removed (proven never emitted):**
`.platform-shell-note`, `.platform-header*`, `.launch-shell` / `.launch-hero` /
`.launch-eyebrow` / `.launch-brand-*` / `.launch-step*` / `.launch-title` /
`.launch-value` / `.launch-league-list`, exact `.dg-page-shell` +
`.dg-page-glyph/copy/kicker/title/subtitle`, dead
`.home-command-label/note`, `.home-home-expander`, `.home-league-pulse-label`
(list member), `.decision-panel-row*`, `.news-feed`, dead
`.player-detail-back-row/launch-row/section-note`.

**Consolidated:** quiet-shell chrome → single
`MOBILE_VISUAL_POLISH_CSS` selector list including `.dg-gm-targets-quiet`.
Feature modules keep typography/layout deltas only.

**Preserved live:** `.launch-section-*`, `.launch-league-card/chip`,
`.dg-page-meta`, `.dg-page-context`, `.decision-panel-body`, `.news-card`,
home-command-card family, #244/#247.

### Typography / spacing / CTA / disclosure / header

| Area | Finding | Action this PR |
|---|---|---|
| Typography | Dual `--dg-*` + design tokens; micro rem ladder remains | Brand plate arcs → tokens; light plate stays `#f8fafc` |
| Spacing | Quiet shells re-declared padding/gap | DRY to polish tokens |
| CTA | `dg_cta_*` tiers already canonical; deep-analysis denser fork intentional | No rewrite |
| Disclosure | Multiple `stExpander` layers last-wins; polish owns chrome | Left intact (risk > reward) |
| Header | No defect after #247 | No redesign |

### Mobile / desktop

No layout redesign. CSS dead-weight removal only. Visual matrix still owned by
existing browser harnesses at `deviceScaleFactor=1` (100% zoom).

## B — Performance / redundancy

### Proven cleanups

| Change | Before | After | Correctness |
|---|---|---|---|
| Eager `weekly_report_ui` import | Always imported | Lazy on archived route | No behavior change while archived |
| Session `news` on league switch | Retained | Cleared via `LEAGUE_SWITCH_TRANSIENT_STATE_KEYS` | Avoids stale pool |
| Waivers roster map | Always `get_rosters` | Reduced `get_shared_league_context(include_intelligence=False)` then fallback | Same data; fewer call sites |
| `trade_receive_partner` | Not cleared on switch | In `TRADE_ANALYZER_PACKAGE_KEYS` | League-safe archived analyzer |
| Dead helpers | See inventory | Removed | Zero callers |

### Dead Python helpers removed

`_candidate_note_map`, `_safe_secret_flag`, `render_concept_band`,
`_read_text_asset`, `_count_jsonl`, `_draft_type`, `_slugify_name`,
`_lookup_secret` (premium/stripe×2), `_sum_keys`, `_badge_variant`,
`waiver_dynasty_context`, `waiver_opportunity_context`.

Deferred (football-module guard): `trade_ideas._pick_value`,
`_best_player_asset`.

### Reruns

Explicit production `st.rerun()` count remains **41** (budget ≤42). No proven
redundant rerun removed — auth/dialog/league/tap-grid/PQV fragment remounts
remain required.

### Provider calls by route (high confidence)

| Route | Duplicate finding |
|---|---|
| Dashboard | Game Plan uses `cached_league_context` — clean |
| My Team | Shared context then map — clean |
| Trade Hub | Reduced context — clean |
| Waivers | Fixed this PR (shared map first) |
| League Overview | Standings re-calls `get_rosters`/`get_league`; LRU-coalesced — schema fix deferred |
| PQV | News pool session→disk→fetch — clean when warm |

### Football / process-cache

No methodology changes. No fingerprint / single-flight ownership changes.
Duplicate football work not proven beyond existing cache ownership.

### APP_CSS

| Metric | Value |
|---|---|
| Before this polish branch (`main` #247) | ~415,165 |
| After dead-chrome cleanup | ~403,934 |
| Ceiling gate | < 418,220 |

### Experimental feature cost matrix (no graduation)

| Feature | Re-enable cost | Provider | Football | Startup | Nav | Premium |
|---|---|---|---|---|---|---|
| Decision Memory | moderate | Supabase history | no | low | none | Premium history |
| GM Targets | moderate | Supabase CRUD | observe ranks | low | conditional | free 3 / Prem 50 |
| Share | low–moderate | optional portrait | no | none until generate | none | free |
| Player Explorer | low (CORE) | local frame | filter | low CSS | CORE | free |
| Trade Analyzer | high (ARCHIVED) | context + curve | yes | none archived | dual trade | TBD |
| Weekly Report | moderate–high | cached report | maturity | lazy import | overlaps Dashboard | — |
| Teams | low (→ Overview) | same | same | none | duplicate | — |
| Tendencies | moderate–high | tx history | classifier | Hub path | clutter | trust risk |

### Load / Slow-4G / perceived

This pass does not claim new multi-session or Slow-4G measurements. Use prior
baselines in `docs/startup-latency-cleanup-234.md`,
`docs/app-wide-performance-audit.md`, and local AppTest budget script for
server cold/warm + protobuf.

## Remaining debt

**UI:** expander last-wins layers; micro rem ladder; deep-analysis CTA denser
fork; PQV parallel heading tokens.

**Perf:** League Overview standings context schema; optional below-fold deferrals.

**Code:** `trade_ideas` dead wrappers; more orphan scan/FA/trade-explain CSS
families (emitter-proven, deferred for blast-radius).

## Top 5 next optimizations

1. Expose rosters/league on shared context to drop Overview LRU re-calls.
2. Continue orphan CSS purge (scan-card / free-agent-main / trade-explain).
3. Single `stExpander` chrome owner — delete superseded layers.
4. Map 0.42–0.71rem ladder → badge/caption tokens.
5. Dedicated football-guard-approved dead-wrapper cleanup in `trade_ideas`.

## VERDICT

**NEEDS MORE WORK** for full “READY” bar (visible multi-viewport screenshot
proof + measured perceived-load matrix), but this PR ships **proven** dead CSS
+ dead Python + one Waivers provider call-site consolidation without weakening
correctness or #244/#247 contracts.
