# Executive header responsive geometry

| Field | Value |
| --- | --- |
| Baseline | `da23e67dea9b2fffa488157631893868d9b8cf33` (pre-#185) |
| Geometry landings | #185 (rail width), #186 (chevron column), this contract pass |
| Scope | Presentation-only header / command-bar width composition |
| Explicit non-changes | Football, rankings, valuations, Trust, auth, entitlements, Stripe, Supabase, Sleeper, FGL Arc Monogram artwork |

## Root cause

The League / Alerts / You chevron starvation was **not** a bad Material icon style.

Desktop command rail was locked to a fixed `22.5rem` strip (`max-width: 22.5rem`) while the shell grid gave remaining space to identity (`minmax(0, 1fr) auto`). Three equal Streamlit columns then width-starved “Switch League” + `expand_more`. Button `overflow: hidden` clipped the framework chevron. Mobile wrapped the same equal cells without reclaiming full row width intentionally.

## Before geometry

| Breakpoint | Identity | Commands |
| --- | --- | --- |
| ≥761 | Took leftover after fixed rail | Fixed `22.5rem` / min `16.5rem` |
| ≤760 | Full width row 1 | Full width row 2, equal thirds, first-cell left border doubled the edge |
| Trigger | `inline-flex` + shared overflow | Label + chevron competed; long labels won |

## Responsive contract

Two groups:

1. **Identity (left / top)** — FGL Arc Monogram, page title, War Room / league ellipsis, Founder Beta (subordinate, `max-width: 9.75rem` in shell title row).
2. **Commands (right / second row)** — Switch League, Alerts, You.

Shell owner: `application_shell_styles.py` (+ chrome in `visual_hierarchy_styles.py`).
Command width / trigger / chevron / separator owner: `executive_command_header_styles.py`.

## Breakpoint behavior

| Width | Behavior |
| --- | --- |
| ≤430 | Second-row commands; tighter padding / letter-spacing; chevron column preserved |
| ≤760 | Identity stacks above commands; commands are a full-width proportional row; row top border; first command has no left border |
| ≥761 | Single band: `grid-template-columns: minmax(0, 1fr) minmax(min(100%, 28rem), 1fr)` so the rail shares available width |
| 1024–1920 | Same contract; rail grows with the shell instead of leaving unused space while squeezing controls |

## Command sizing

Streamlit column weights (`COMMAND_COLUMN_WEIGHTS`):

| Cell | Weight |
| --- | ---: |
| League | 1.15 |
| Alerts | 1.15 |
| You | 0.95 |

Trigger labels (compact): **League** / **Alerts** / **You** with help text **Switch league** on the league cell.

Heights remain `var(--touch-target-min)` (44px) from #144. No `translateY`, negative margins, or League-only height forks.

## Long-content behavior

| Fixture | Behavior |
| --- | --- |
| League identity short / normal / long | Identity `.dg-executive-shell__league` ellipsis; commands unchanged |
| Switch League | Label may ellipsis inside reserved text track |
| Alerts / Alerts (1) / (12) / (99) | Stable trigger width |
| Alerts (100+) | Presented as `Alerts (99+)` |
| You | Remains the short account affordance (no email stuffing) |

Harness surface: `?surface=header-geometry` (defaults to long league + Alerts (12)).
Query overrides: `header_league=short|normal|long`, `header_alerts=0|1|12|120`.

## Chevron

Canonical trigger grid:

`grid-template-columns: minmax(0, 1fr) 0.75rem`

Text track may ellipsis; Material `expand_more` / SVG owns column 2 (`grid-column: 2`, fixed 0.75rem). Scoped only under `st-key-executive_command_actions`.

## CSS ownership

| Concern | Owner |
| --- | --- |
| Shell grid / identity padding / Founder Beta max-width | `application_shell_styles.py` |
| Shell chrome borders | `visual_hierarchy_styles.py` (no command widths) |
| Command rail, cells, chevrons, separators, mobile row | `executive_command_header_styles.py` |
| Compact Founder Beta mark/copy in title row | `executive_design_unify_styles.py` |
| Overlay / GM stacking | `mobile_interaction_overlay_styles.py` (#150/#153) |

Obsolete fixed rail widths (`22.5rem` / `16.5rem`) are removed — do not reintroduce in late override layers.

## Performance

Measured on this contract pass (`check_founder_beta_performance_budget.py`):

| Metric | Value |
| --- | ---: |
| APP_CSS bytes | ~424,396 |
| EXECUTIVE_COMMAND_HEADER_CSS bytes | ~16,058 |
| Cold protobuf | ~518,981 |
| Warm protobuf | ~474,698 |
| Cold server ms | ~1886 |
| Warm server ms | ~86 |

Ceiling remains 520,000 protobuf bytes. No football/rerun changes.

## Remaining limitations

1. Streamlit still owns popover markup (`expand_more` ligature / nested wrappers); we only allocate tracks.
2. Column weights are proportional hints — exact px widths still depend on Streamlit’s flex column implementation.
3. Extremely long identity league names ellipsis; the Switch League trigger copy stays the action label, not the full league name.
4. Dropdown anchoring remains framework-owned; overlay z-index contracts from #150/#153 still apply.
