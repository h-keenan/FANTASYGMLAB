# League Overview product clarity audit

| Field | Value |
| --- | --- |
| Baseline | `2accab7baddcffe6a1e86cb2aeb0f3e5039a38a2` |
| Scope | Presentation, information architecture, terminology, proven-redundant UI |
| Explicit non-changes | Football math, rankings formulas, franchise/draft valuation, recommendation generation/order, Trade Hub, Waivers, Trust, auth, Stripe, Supabase, Sleeper, FGL artwork |

## Before section inventory

| Section | User question | Distinct? | Actionable? | Primary / support | Primitive | First-time clear? | Duplicated? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Standings | Where does my team stand by results? | Yes | Orienting | Primary | `dg-ranked-*` | Yes | No |
| Power Rankings | Who is strongest now? | Yes | Orienting | Primary | `dg-ranked-*` | Mostly | Secondary ranks repeated every row |
| About these metrics | What do these boards mean? | Support | Education | Support | concept-band expander | Yes | N/A |
| Highlight tiles (Best Starter / Bench / Health / Draft) | Who leads niche metrics? | Partial | Weak | Support | summary-tile | Mixed | Yes — overlapped intel cards + boards |
| Franchise Value (collapsed) | Where is dynasty value? | Yes | Orienting | Primary (hidden) | expander + ranked | Buried | Franchise also on Power secondary |
| Post-Draft Roster Read | What does a new startup look like? | Yes (startup only) | Orienting | Support | summary-tile | Yes | Startup-only |
| League Intelligence cards | Who owns extremes? | Partial | Weak alone | Support | `dg-intel-*` | Name unclear | Draft extremes + highlight tiles |
| League Decision Signals | What needs attention? | Yes | Strongest | Primary (misplaced after cards) | analysis-card | Better as Insights | Pick-Rich/Poor vs draft board |
| Full intelligence table | Raw transparency | Yes | Debug/audit | Support | executive disclosure | Name unclear | Re-lists board ranks |

## Terminology decision

| Field | Value |
| --- | --- |
| Old customer name | League Intelligence |
| Candidates | League Insights, League Pulse, League Movement, Market Watch, Around Your League |
| Chosen | **League Insights** |
| Reason | The Overview surface is posture/pressure plus league extremes — not a news feed and not “intelligence” as a product category. “Insights” matches what the section contains without sounding abstract. |

Related renames (customer-facing only):

| Surface | Before | After |
| --- | --- | --- |
| Overview section | League Intelligence | League Insights |
| Overview decision band | League Decision Signals | Folded under League Insights (Primary signals) |
| Overview disclosure | League intelligence detail / Full league intelligence table | Full team metrics |
| Dashboard briefing | League Intelligence | League Insights |
| News page header | League Intelligence | News (matches nav) |
| PQV source label from news | League Intelligence | News |

Internal modules (`league_intelligence*`, `league_intelligence_frame`) remain for compatibility.

## Final hierarchy

1. **Standings** — Where do I stand?
2. **Power Rankings** — Who is strongest?
3. **Franchise Value** — Where is the dynasty value? (promoted; no longer collapsed)
4. **Draft Capital** — Who owns future capital? (first-class board)
5. **How to read these boards** — short disclosure (was “About these metrics”)
6. **League Insights** — What is worth noticing?
   - Primary: decision cards (Pressure / Stuck Middle / Partner Types)
   - Supporting: leader extremes (draft Most/Least omitted; covered by Draft Capital board)
7. **Full team metrics** — optional transparency table

Startup leagues still show **Post-Draft Roster Read** instead of Insights when evidence maturity is `NEW_STARTUP`.

## Redundant content removed

- Overview highlight tiles (Best Starter Core, Deepest Bench, Health Drag, Best Draft Leverage)
- Collapsed Franchise expander wrapper (board is primary)
- Pick-Rich / Pick-Poor decision cards (answered by Draft Capital board)
- Most / Least Draft Capital leader cards on Overview (same)
- Duplicate “League Decision Signals” section header (merged into Insights)

## Primitives

| Primitive | Decision |
| --- | --- |
| `dg-ranked-*` / standings board | Retain — canonical league boards |
| `dg-intel-*` leader cards | Retain — supporting extremes under Insights |
| `analysis-card` | Retain — primary Insights signals |
| `summary-tile` on Overview Rankings | Removed for highlight strip; retained app-wide (startup read, other pages) |
| `concept-band` | Retain — board literacy expander |
| `st.info` standings empty | Replaced with `render_empty_state_panel` |
| advice-card / prospect-card | Not used on Overview Rankings — leave alone |

## CSS / ownership

| Concern | Owner |
| --- | --- |
| Ranked boards + intel cards | `modules/app_styles.py` |
| News feed items | `league_intelligence_styles.py` (+ late polish elsewhere) |
| Shell / header | unchanged |

Changes this pass:

- Board / intel `max-width` `72rem` → `min(100%, 90rem)` for wide desktop without a new layout system
- `.dg-intel-card--supporting` for secondary extremes
- No new late override module

## Empty states

- Standings unavailable / not ready → classified empty-state panel with recovery guidance
- Insights with no decision cards → empty-state panel
- News feed empty states unchanged

## Mobile / wide behavior

- Mobile: ranked secondary still wraps under identity; boards omit the board’s own primary rank from the secondary line to cut noise
- Wide: boards/insight grids can use up to 90rem instead of a 72rem river

## Current-team treatment

Unchanged canonical `dg-ranked-row--current` / intel current accent across Standings, Power, Franchise, Draft Capital, and insight cards.

## Performance

Measured after this pass (`check_founder_beta_performance_budget.py`):

| Metric | Notes |
| --- | ---: |
| APP_CSS | Expect flat-to-slightly-up from supporting class + max-width text |
| Protobuf | Should stay under 520,000; Overview HTML may grow slightly from promoting Franchise + Draft boards while losing highlight tiles |
| Provider calls | None added |
| Football recomputation | None |

Fill exact before/after numbers in the PR final report from the local budget run.

Local APP_CSS after this pass: **424,469** bytes (pre-change ~424,396).

## Screenshots

CI Chromium suite covers League Overview at 320–1920 via `scripts/validate_mobile_ui.py` surface `league`, plus dashboard/trade/my-team/waivers smoke markers.

## Intentional remaining debt

1. News feed still uses internal `league_intelligence*` module names and `.dg-intelligence-*` CSS.
2. Nav group label **INTELLIGENCE** remains for News / Archetypes / Tendencies.
3. Leader cards still share `dg-intel-*` class names (not renamed — CSS churn without UX gain).
4. Teams / Draft sibling tabs under the same route gate were not redesigned.
5. Streamlit expander/table disclosure chrome remains framework-owned.
