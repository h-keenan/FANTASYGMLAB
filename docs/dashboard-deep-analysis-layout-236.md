# Dashboard Deep Analysis layout regression (#236)

| Field | Value |
| --- | --- |
| Baseline / rollback | `a1431b0` (#235 merge) |
| Scope | Presentation/layout only — Deep Analysis nav compact + interactive |
| Not in scope | Football, Premium gates, routing semantics, redesign |

## Render owner

1. `modules/dashboard_workflow.py` — `render_section_header("Deep Analysis")` then `render_quick_actions([...])`
2. `app.py` — `render_home_quick_actions` → `workspace_ui.render_home_quick_actions`
3. `modules/workspace_ui.py` — `st.container(key="dashboard_deep_analysis_nav")` + 2×2 `st.columns` + secondary buttons
4. Styles — `modules/mobile_visual_polish_styles.py` (injected after `APP_CSS` in `app.py`)

## Root cause

#231 intended “compact tertiary nav,” but production DOM + polish interacted badly:

1. **Empty shell markdown** — `st.markdown("<div class='home-quick-actions-shell dg-cta-tertiary'>")` rendered an **empty** element *above* the buttons (not wrapping them).
2. **Dual border owner** — polish applied `background` + `border` to **both** `st-key-dashboard_deep_analysis_nav` and `.home-quick-actions-shell` → outer panel + inner empty bordered slab / top double-border artifact + vertical dead space.
3. **Affordance stripped** — `dg_cta_tertiary_*` + nav button rules forced `background:transparent; border:0` → labels read as floating text inside the giant box.
4. **Streamlit column wrap** — emotion CSS `@media (max-width:640px) { min-width: calc(100% - 1.5rem) }` forced each `stColumn` full-width, stacking the intended 2×2 into four full-width slabs (~202px nav height vs ~114px after fix).

#235 did not introduce this; it failed to catch it.

## Why #235 QA missed it

`scripts/ui_validation_harness.py` replaced Deep Analysis with a **synthetic single button** (`fixture_dashboard_deep_analysis`) and did **not** inject `MOBILE_VISUAL_POLISH_CSS`. Screenshots/contracts never exercised the real empty-shell + dual-border + tertiary-strip DOM.

## Fix

- Remove empty shell markdown.
- Use `dg_cta_secondary_deep_*` keys (bordered raised tiles, still secondary to Game Plan).
- Polish: one L1 border on the nav container; `height/min-height: auto/0` on wrappers; hide legacy `.home-quick-actions-shell`; interactive tile treatment; descendant `button` selectors (tooltip-safe).
- Harness: render real `render_home_quick_actions` + inject polish CSS.
- Regression suite: `tests/test_dashboard_deep_analysis_layout_236.py` (includes AppTest for four labels).

## Structure

| | Before | After |
| --- | --- | --- |
| Desktop/mobile DOM | heading → empty bordered shell → 2×2 tertiary text buttons inside oversized dual-border panel | heading → single compact L1 panel → 2×2 secondary tiles |
| Routes | League Overview→`rankings`, My Team→`my_team`, Trade Hub→`trade_hub`, Draft Center→`draft_summary` | unchanged |

## Measured fixture geometry (after)

| Viewport | Nav box | Layout | Button |
| --- | --- | --- | --- |
| 320 | ~296×114 | 2×2 | 44px, bordered, radius 4 |
| 390 / 430 | ~366–406×114 | 2×2 | 44px |
| 1280 | ~725×114 | 2×2 | 44px |

Screenshots (FIXTURE, not production Streamlit iframe): `/opt/cursor/artifacts/deep-analysis-236/FIXTURE-deep-analysis-nav-*.png`

## Performance

Presentation-only. No provider / football / rerun changes.

| Metric | Value |
| --- | --- |
| APP_CSS before → after | 418,220 → 418,220 (unchanged; polish is separate inject) |
| polish CSS | ~3,287 → 4,115 |
| protobuf cold / warm | 520,000 / 475,717 |
| provider / football / rerun impact | none |
