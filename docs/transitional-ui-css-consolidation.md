# Transitional UI / CSS Consolidation

Cleanup/refactor after PR #176 (`22e12050`). Presentation hygiene only — no football logic, rankings, valuations, Trust, Stripe, auth, or lifecycle changes.

## Transitional classes before / after

| Class | Before | After | Notes |
| --- | --- | --- | --- |
| `power-row` / `power-row-top` / `power-rank-pill` / `power-*` aliases | Dual-classed with `dg-ranked-*` | **Removed** | Markup and CSS use `dg-ranked-*` only |
| `power-logo-wrap` | Leaderboard / draft logos | **Removed** → `dg-ranked-logo` | |
| `power-board` | Board wrapper dual class | **Removed** → `dg-ranked-board` | |
| `power-track` / `power-fill` / `power-meta` | Dead / orphan CSS | **Removed** | No emitters |
| `intel-card` / `intelligence-grid` / `intel-*` | League intelligence | **Renamed** → `dg-intel-*` | Canonical ownership |
| `team-rank-card` / `team-rank-grid` | Team comparative ranks | **Removed** | Migrated to `render_summary_tiles` |
| `trade-idea-card-compact` | Alias / orphan selector | **Removed** | No markup emitters; Trade Hub uses `trade-idea-card` |
| `summary-tile-kicker` | Orphan selector in UX polish | **Removed** | Never emitted |
| `summary-tile` | Active metric tiles | **Retained (documented)** | Dual-classed with `dg-ui-card`; tap component depends on class |
| `analysis-card` | Active analysis cards | **Retained (documented)** | Dual-classed with `dg-ui-card` |
| `advice-card` / `prospect-card` | My Team surfaces | **Retained (documented)** | Dual-classed with `dg-ui-card` |
| `home-command-card` | Dashboard command tiles | **Retained (documented)** | Dual-classed; modal / weight semantics |

Target met: customer routes no longer rely on **undocumented** transitional styling. Remaining dual-class names are intentional product primitives with `dg-ui-card` ownership.

## CSS ownership map

| Concern | Canonical owner |
| --- | --- |
| Design tokens / primitives | `design_tokens`, `ui_primitive_styles` |
| Ranked leaderboards | `dg-ranked-*` rules in `app_styles` + `ranked_leaderboard_row_html` |
| League intelligence cards | `dg-intel-*` in `app_styles` + `render_league_intelligence_cards` |
| Metric tiles | `summary-tile` + `workspace_ui.render_summary_tiles` / `executive_table_ui.render_executive_metric_tiles` |
| Analysis / advice / prospect | Feature markup + shared card chrome via `dg-ui-card` + unify layer |
| Section headers | `ui_primitives.render_section_header` |
| Executive unify / late overrides | `executive_design_unify_styles` (last in `APP_CSS` chain before mobile interaction overlay) |
| Desktop layout density | `desktop_executive_layout_styles` |
| Founder consistency / quick-fix | `founder_beta_consistency_styles`, `founder_beta_quick_fix_styles` |

## Selectors removed (high signal)

- `.power-row`, `.power-row-top`, `.power-rank-pill`, `.power-logo-wrap`, `.power-board`, `.power-track`, `.power-fill`, `.power-meta`, and dual aliases paired with `dg-ranked-*`
- `.intel-card` / `.intelligence-grid` / `.intel-*` (renamed to `.dg-intel-*`)
- `.team-rank-card*`, `.team-rank-grid`
- `.trade-idea-card-compact`
- `.summary-tile-kicker`

## Override chains eliminated

1. **Ranked row dual-class cascade** — markup + CSS no longer list `power-row*` beside `dg-ranked-*`; one selector family remains.
2. **Team-rank → summary-tile** — removed dedicated team-rank chrome that was later normalized by unify / consistency layers; ranks now use the same summary-tile contract.
3. **Orphan accent kill** — dead `power-row::after` / `team-rank-card::after` entries removed from accent and unify selector lists (and corrupted `::after::after` artifacts from an intermediate cleanup pass repaired).
4. **Unify `::after` kill extended** — `analysis-card`, `advice-card`, `prospect-card`, `dg-intel-card`, `dg-ranked-row` join `home-command-card` / `summary-tile` so late accent bars stay suppressed without per-surface corrective rules.

## Markup migrations

- `ranked_leaderboard_row_html` / boards: pure `dg-ranked-*` + `dg-ui-card`
- League intelligence: `dg-intel-*` + `dg-ui-card`
- `render_team_rank_cards` → `workspace_ui.render_summary_tiles(..., compact=True, key_prefix="team_rank_cards")`
- `render_analysis_cards` / advice / prospect: add `dg-ui-card` dual class

## Table / disclosure decision

Customer executive tables already use `executive_table_ui.render_executive_table_disclosure` (summary cards first, full `st.dataframe` behind expander). **No rewrite** in this PR. Founder Ops/debug may still show practical framework tables.

## Helpers consolidated

- Team rank cards no longer maintain a parallel HTML/CSS card shell; they call the existing summary-tile helper.
- No new broad abstraction layers. No duplicate helper modules deleted beyond CSS selector debt.

## Files deleted

None. Temp local cleanup scripts (`scripts/_tmp_*.py`) are not committed.

## Protobuf / performance impact

Baseline after #176:

| Metric | Before (#176) | After (this PR) |
| --- | --- | --- |
| Cold protobuf | 517,384 | **514,768** (−2,616) |
| Warm protobuf | 472,989 | **470,373** (−2,616) |
| Warm server ms | ~66 | **~66.4** |
| Assembled `APP_CSS` chars | 425,436 | **422,846** (−2,590) |

Ceiling unchanged: **520,000** cold protobuf. Prefer deletions over new layers; do not raise the ceiling.

## Accessibility / lifecycle

- Focus styles, touch targets, dialog/popover behavior, and summary-tile tap semantics preserved (`tappable=False` for team ranks).
- No startup, cache, league-switch, or recommendation lifecycle changes.

## Remaining intentional style debt

- `summary-tile`, `analysis-card`, `advice-card`, `prospect-card`, `home-command-card` remain named product classes (documented dual-class with `dg-ui-card`).
- Stacked late override modules still exist (`interface_reimagining`, `founder_beta_*`, `desktop_executive`, unify, mobile overlay). Further merge is a separate maintainability pass.
- Base `APP_CSS` still emits decorative `::after` accents that unify suppresses — full deletion of those accent blocks is a follow-up once non-shell surfaces are proven unused.
- `CareerProfile` model without HTML helper remains (from #176).

## Validation

```bash
python -m compileall -q app.py modules scripts tests
python -m pytest -q
python scripts/check_founder_beta_performance_budget.py
git diff --check
```

Browser: Chromium responsive suite + mobile interaction suite via CI Delivery Validation; local harness smoke for Dashboard, Trade Hub, My Team, Waivers, League Overview, PQV, Premium, Alerts, GM Menu.
