# Dashboard executive action layer (#201)

| Field | Value |
| --- | --- |
| Baseline | `b2cd2be4e1d6df81c787b73a3622a06e5390e737` (post #199/#200) |
| Scope | Hierarchy, dedupe, handoff clarity, first-viewport density |
| Explicit non-changes | Recommendation generation/scoring/ordering, Trade/waiver math, Trust, valuations, entitlements rules |

## Before inventory

| Section | Purpose | Disposition |
| --- | --- | --- |
| Today's Game Plan | Curated ≤5 actions from organized inventory | **KEEP** (sole primary action surface) |
| What Changed | Recent decision transitions | **KEEP** (secondary) |
| Immediate Action | Roster pressure / injury tiles + quiet clear-state | **MERGE** into Game Plan Watch / quiet plan |
| Your Next Move | Duplicate of Game Plan Top Priority | **REMOVE** when Game Plan present |
| Additional recommendations | Leftover tiles after primary | **DEMOTE** — skip when already in Game Plan |
| League Insights | Trade/waiver market tiles | **DEMOTE** expander (after suppress) |
| Team Snapshot | Record / health / age | **DEMOTE** expander |
| Orientation | First-use teaching | **KEEP** |
| Deep Analysis | Destination jumps | **KEEP** |
| League Pulse | Deferred league posture | **KEEP** expander |

## Final hierarchy

1. **Today's Game Plan** — Top Priority (visually dominant first item) + supporting plan items
2. **What Changed** — up to 2–3 transitions; Decision Memory discovery when entitled
3. **Supporting context** — League Insights + Team Snapshot (collapsed)
4. **Orientation** (when applicable)
5. **Deep Analysis** + League Pulse expander

Fallback (no Game Plan renderer): retain Immediate Action + primary board for startup/edge paths.

## Primary-action terminology

**Chosen: Top Priority** (category inside Today's Game Plan).

Why: Game Plan already composes `CATEGORY_TOP_PRIORITY` from `briefing.primary` using existing organize order. A second “Immediate Action” / “Your Next Move” board duplicated the same inventory and competed for first-viewport attention.

Urgent roster pressure / injury remain in the plan as **Watch** items from `briefing.immediate` — not a parallel primary system.

## Contracts

### Today's Game Plan
- Source: `compose_daily_gm_briefing(organize_dashboard_items(...))`
- Cap: existing `MAX_BRIEFING_ITEMS` (5)
- Dedupe: `recommendation_id` + headline fingerprint (unchanged)
- First item = Top Priority; presentation accent only
- Destinations: Trade Hub / Waivers / My Team / League Overview via existing `_tile_destination` + tile `route_key`

### What Changed
- Distinct question: material transitions since prior state
- Default ≤ `MAX_DASHBOARD_EVENTS` existing cap
- Quiet when empty; never equals Game Plan visual weight

### Handoff matrix

| Inventory | Destination | Provenance |
| --- | --- | --- |
| Trade | `trade_hub` + focus player | `recommendation_id` + narrative |
| Waiver | `waivers` (+ player row / PQV) | `recommendation_id` + narrative |
| Need / pressure / injury | `my_team` | label context |
| League movement | Trade Hub or League Overview | existing destination map |

## Free / Premium / experimental

- Free: truncated inventory upstream; Game Plan from truncated list; Premium lock after Game Plan for deeper moves.
- Premium: full inventory → Game Plan; Insights/Snapshot available collapsed.
- Decision Memory / GM Targets / Share: do not enter first viewport; Memory discovery stays under What Changed.

## Performance / protobuf

Remove duplicate Immediate / Next Move / always-on Insights+Snapshot chrome before adding accent CSS (scoped to `DAILY_GM_BRIEFING_CSS`). No new providers. No football recomputation.

## Mobile validation note

Team Snapshot summary tiles are collapsed by default. `scripts/validate_mobile_ui.py` metric comparison capture must expand **Team Snapshot** before clicking `.summary-tile-tappable` tiles (Average Age / Starter Strength).
