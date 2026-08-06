# Executive Surface Modernization & Legacy UI Elimination

Presentation-only rollout completing the Executive Design System across customer-facing surfaces.

| Field | Value |
| --- | --- |
| Baseline | `d487bcdd9d1b31e7cea2c5a27a92826050a7a233` |
| Scope | Presentation only — zero football, Trust, auth, Stripe, Supabase, Sleeper, or workflow changes |
| Target | Customer-visible legacy UI = **0 undocumented** |

## Verdict

Every customer-facing route now uses the Executive Design System for section headers, summary cards, metric tiles, and table disclosure. Raw Streamlit `st.metric` and primary `st.dataframe` views are eliminated from customer paths. Full tabular detail remains available behind disclosure with no information removed.

**Remaining legacy count (customer-visible): 0**

Diagnostic-only paths (debug UI, founder-only tooling, unmatched-pick diagnostics) retain dataframe exports by design.

---

## Legacy Surface Inventory

### Before

| Pattern | Locations | Customer impact |
| --- | --- | --- |
| Legacy `section-header` markup | All routes via `workspace_ui.render_section_header` | Inconsistent typography vs command shell |
| Primary `st.dataframe` tables | League Archetypes, Manager Tendencies, League intel detail | Spreadsheet-first cognitive load |
| `st.metric` tiles | Draft Center capital dashboards | Native Streamlit chrome |
| Raw dataframe in Live Draft pick history | `live_draft_ui._render_team_boards` | Legacy table inside expander |
| `Detailed Table View` expanders | My Team, League team pages, Waivers | Dataframe-only disclosure |
| Transitional card classes without `dg-ui-card` | `summary-tile`, `team-rank-card`, `power-row` | Structurally legacy despite CSS unification |

### After

| Pattern | Resolution |
| --- | --- |
| Section headers | `workspace_ui.render_section_header` delegates to `ui_primitives.dg-ui-section-header` |
| Primary tables | `modules/executive_table_ui.py` — summary cards first, full table on disclosure |
| Metrics | `render_executive_metric_tiles()` using `dg-ui-card` rows |
| Live Draft boards | Executive pick summary cards + full dataframe only when nested disclosure allows |
| Detail expanders | Executive row summaries + preserved full dataframe (`include_expander=False` inside outer expanders) |
| Card shells | `dg-ui-card` added to `summary-tile`, `team-rank-card`, `power-row` |

---

## Surface-by-surface changes

| Surface | Change |
| --- | --- |
| **League Overview** | Manager Tendencies, Archetypes, and intelligence detail use executive table disclosure; power rows carry `dg-ui-card`; team rank cards structurally migrated |
| **Live Draft** | Pick history, score breakdown, and team summaries use executive table rows |
| **Draft Center** | Capital insight metrics use executive metric tiles; review-mode available board uses executive disclosure |
| **Waivers** | Detailed table expander leads with executive row summaries |
| **My Team / League team pages** | Full-detail expanders show executive summaries before preserved tables |
| **Dashboard / Trade Hub / PQV** | Already on executive shell from prior passes — unchanged logic |

---

## Consistency Matrix

| Surface | Section headers | Summary cards | Badges | Tables | Desktop grid | Mobile 320–430 |
| --- | --- | --- | --- | --- | --- | --- |
| Dashboard | ✓ dg-ui | ✓ dg-ui-card tiles | ✓ | N/A (cards) | ✓ | ✓ |
| Trade Hub | ✓ | ✓ trade-summary-card | ✓ | N/A | ✓ | ✓ |
| My Team | ✓ | ✓ scan cards | ✓ | ✓ disclosure | ✓ | ✓ |
| Waivers | ✓ | ✓ free-agent cards | ✓ | ✓ disclosure | ✓ | ✓ |
| League Overview | ✓ | ✓ power-board + tiles | ✓ | ✓ disclosure | ✓ | ✓ |
| Live Draft | ✓ | ✓ ranking rows | ✓ | ✓ executive rows | ✓ | ✓ |
| Player Quick View | ✓ | ✓ dossier cards | ✓ | ✓ stat rows | ✓ | ✓ |
| Notifications | ✓ | ✓ dg-notification-item | ✓ | N/A | ✓ | ✓ |
| Founder Ops | ✓ | ✓ health cards | ✓ | N/A | ✓ | ✓ |

---

## New module

**`modules/executive_table_ui.py`**

- `executive_table_row_html()` — single executive row card
- `executive_table_summary_html()` — responsive summary grid
- `render_executive_table_disclosure()` — summary first, full detail on disclosure
- `render_executive_metric_tiles()` — replaces `st.metric` clusters

CSS additions in `modules/ui_primitive_styles.py`: `.dg-ui-table-summary`, `.dg-ui-table-row`, `.dg-ui-metric-grid`.

---

## app.py impact

Presentation-only edits in League Overview sections (Rankings, Manager Tendencies, Archetypes), draft exclusion feed, and import of `executive_table_ui`. No football, entitlement, auth, or recommendation logic changed.

---

## Visual QA

Chromium harness: `scripts/validate_mobile_ui.py` at **320, 390, 430, 768, 1024, 1440**.

Screenshots captured in CI artifact `artifacts/ui-mobile/` for:

- Dashboard, Trade Hub, League, Waivers, My Team, Live Draft, Player Quick View, Navigation

---

## Rollback boundary

Revert merge commit on `main`. No schema, billing, or football-logic migrations.

---

## Explicit confirmation

**No changes** to football logic, valuations, rankings, Trust, recommendation generation, recommendation ordering, authentication, entitlements, Stripe, Supabase, Sleeper integration, workflow continuity, canonical narratives, context synchronization, or business rules.

Presentation, CSS, HTML structure, and customer-facing table/metric disclosure only.
