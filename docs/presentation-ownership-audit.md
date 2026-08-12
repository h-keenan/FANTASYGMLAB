# Presentation ownership audit (pre-launch)

Scope: ownership reduction only — no redesign, valuation, providers, auth,
entitlements, or Streamlit migration. Base: post-#268 `main`.

## Verdict

**PRESENTATION OWNERSHIP NEEDS MORE WORK**

This pass removes proven-dead render helpers, exact-duplicate midfile CSS, and
superseded late-override orb geometry. Late cascade layers remain for sheet
chrome, buttons, and midfile legacy body — future UI changes can still require
override archaeology.

### Metrics (post-#268 base `cb2b3f7` → this PR)

| Metric | Before | After |
|---|---:|---:|
| APP_CSS chars | 363238 | 360326 |
| Diff (branch vs main) | — | +220 / −374 |
| Style modules | 28 | 28 |
| Override-only modules removed | — | 0 (shrunk, not deleted) |
| Dead render helpers removed | — | 9 symbols |
| Full pytest | — | 2389 passed |
| Protobuf cold/warm | — | 462173 / 417890 |
| server_ms cold/warm | — | 118.6 / 31.1 |
| Explicit reruns | — | 41 |
| Provider impact | — | none |

## Canonical ownership map

| CONCERN | CANONICAL OWNER | COMPETING OWNERS | STATUS | ACTION |
|---|---|---|---|---|
| Design tokens | `DESIGN_TOKEN_CSS` | — | Clean | keep |
| UI primitives | `UI_PRIMITIVE_CSS` | midfile remnants | Mostly clean | keep |
| CTA / disclosure buttons | `COMPONENT_FAMILY_CSS` | midfile, COMMAND_CENTER, INTERFACE, UX_POLISH | Contested | prune globals later |
| Dense list rows | `DENSE_LIST_CSS` | — | Clean | keep |
| Modal / dialog chrome | `UI_MODAL_CSS` + QUICK_FIX dialog | QUICK_FIX `stDialog` | Dual | keep; fold later |
| Midfile legacy body | `_APP_CSS_MIDFILE` | many late layers | Legacy | delete exact dups only |
| Executive shell | `APPLICATION_SHELL_CSS` | polish opacity | Clean | keep |
| Command cells / popovers | `EXECUTIVE_COMMAND_HEADER_CSS` | — | Clean (#267) | keep late inject |
| Content width / gutters | `DESKTOP_EXECUTIVE_LAYOUT_CSS` | INTERFACE, CONSISTENCY, VISUAL_HIERARCHY (partial) | Improved | DESKTOP sole desktop pad owner |
| GM orb geometry (#244) | `MOBILE_INTERACTION_OVERLAY_CSS` | QUICK_FIX orb look (superseded), DESKTOP (removed this pass) | Improved | keep overlay last |
| GM sheet chrome | QUICK_FIX + DESKTOP sheet rules | both still active | Contested | consolidate into overlay |
| Brand mark / Founder | `BRAND_IDENTITY_CSS` | — | Clean | keep |
| Dashboard workflow | `DASHBOARD_WORKFLOW_CSS` | DESKTOP grids (DESKTOP wins) | Improved | removed grid dupes |
| Visual hierarchy scan | `VISUAL_HIERARCHY_CSS` | UNIFY, CONSISTENCY | Contested | removed `.block-container` pad |
| Waivers presentation | `WAIVERS_PRESENTATION_CSS` | — | Clean | keep |
| Trade detail | `TRADE_DETAIL_CSS` | — | Clean | keep |
| Player quick view | `PLAYER_QUICK_VIEW_CSS` | midfile quick-view | Dual | keep |
| Legal / footer links | shell / brand (post-#267) | — | Clean | keep |
| Header geometry | shell + command header | — | Clean (#267) | keep |

## Module classification

| Module | Class |
|---|---|
| `design_tokens` / `ui_primitive_styles` / `component_family_styles` / `dense_list_styles` / `ui_modal_styles` | A CANONICAL |
| `application_shell_styles` / `executive_command_header_styles` | A CANONICAL |
| `desktop_executive_layout_styles` | A CANONICAL (width/grid) + residual sheet chrome |
| `mobile_interaction_overlay_styles` | A CANONICAL (orb) / Streamlit overlay |
| `mobile_workflow_styles` / `mobile_visual_polish_styles` | B RESPONSIVE / D FEATURE |
| `waivers_presentation_styles` / `trade_detail_styles` / `player_quick_view_styles` / `football_asset_styles` / `league_intelligence_styles` / `brand_identity_styles` / `dashboard_workflow_styles` | D FEATURE-SPECIFIC |
| `marketing_landing_styles` | D FEATURE-SPECIFIC (route-scoped) |
| midfile `_APP_CSS_MIDFILE` | F LEGACY |
| `interface_reimagining_styles` / `founder_beta_quick_fix_styles` / `founder_beta_consistency_styles` / `visual_hierarchy_styles` / `visual_identity_styles` (COMMAND_CENTER) / `executive_design_unify_styles` / `ux_polish_styles` | G OVERRIDE-ONLY (partial unique rules remain) |
| Empty `SAFE_VISIBILITY_CSS` | H DEAD — removed |

## Removals this pass

### Dead CSS
- `SAFE_VISIBILITY_CSS = ""`
- Midfile exact duplicate clip-path card rule
- Midfile exact duplicate pill + tag chrome block
- Dashboard workflow duplicate home-command/summary grid rules
- Redundant mobile polish expander/`dg_cta` min-height media (kept deep-analysis nav)
- Visual hierarchy desktop `.block-container` padding (DESKTOP owns)
- Desktop executive orb-trigger rules superseded by overlay

### Dead render helpers
- `premium.render_premium_badge`
- `workspace_ui.render_team_identity_card` / `render_home_command_hero` / `render_home_status_strip`
- `app` wrappers/aliases for the above plus `_normalize_trade_html`, `_render_trade_html`, `_render_player_scan_tap_grid`
- `waivers_ui.render_waivers_page_header`

### Intentionally kept (not dead)
- Dual `_format_score` / `_format_rank` (both live callers)
- `format_compact_rank` canonical contract
- QUICK_FIX GM sheet chrome (`CURRENT`, chevrons, founder nav width)
- DESKTOP sheet animation / typography (still wins some properties over QUICK_FIX)
- Graduated / dormant experimental features

## Feature flags

No impossible/dead registry branches removed. Graduated routes (Live Draft,
Player Explorer, GM Targets, Decision Memory, share cards) remain live.
Intentionally dormant experiments (valuation archetypes, manager tendencies,
ESPN limited import) kept.

## Risky Streamlit selectors (`:has`)

| Owner | Selector | Scope | Regression |
|---|---|---|---|
| `MOBILE_INTERACTION_OVERLAY_CSS` | `stVerticalBlock:has(> … .mobile-gm-floating-trigger-marker)` | direct-child | `test_gm_orb_viewport_ui_polish` (#244) |
| `MOBILE_INTERACTION_OVERLAY_CSS` | `stVerticalBlock:has(> … .mobile-gm-sheet-marker)` | direct-child | same |
| DESKTOP / QUICK_FIX | sheet `:has(> …)` | direct-child | preserve |
| Forbidden | unscoped `:has(.mobile-gm-floating-trigger-marker)` | collapses root | asserted absent |

## Remaining debt (highest risk)

1. GM sheet chrome still split DESKTOP ↔ QUICK_FIX ↔ overlay z-index
2. Global button ownership across midfile / COMMAND_CENTER / INTERFACE / family
3. Midfile `::after` accents killed by UNIFY (emit-then-kill)
4. INTERFACE / CONSISTENCY residual `.block-container` padding at mobile breakpoints
5. Dual live `_format_score` / `_format_rank` copies (rewire, don’t delete cold)
