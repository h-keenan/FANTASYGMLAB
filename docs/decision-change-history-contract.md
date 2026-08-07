# Decision Change History Contract

Presentation and lifecycle-derived history only. Does **not** change football
logic, valuations, rankings, recommendation generation/scoring/ordering, Trust,
freshness rules from #149, authentication, entitlements, Stripe, Supabase schema,
Sleeper semantics, caching contracts, or business rules.

## Product boundary

| Surface | Question | Job |
| --- | --- | --- |
| **Today's Game Plan** | What should I do now? | Curated current priorities |
| **Inbox** | What activity should I know about? | Activity / action alerts |
| **What Changed** | Why does my decision board look different? | Material recommendation **transitions** |

These three surfaces must not become duplicates.

- Inbox remains **activity/action-oriented** (e.g. “Add Brashard Smith”).
- What Changed remains **transition-oriented** (e.g. “Brashard Smith became your top waiver priority” / “is no longer available”).
- Avoid paired copy that only says “Recommendation changed” on both surfaces.

## Event schema

`DecisionChangeEvent` (`modules/decision_change_history.py`):

- `event_id`, `recommendation_id`, `league_id`, `roster_id`, `timestamp`
- `lifecycle_transition` (`prior_state->next_state`)
- `reason` (machine-readable from PR #149)
- `category`, `target_label`, `player_id`, `destination`
- `previous_state` / `current_state` (slim structured snapshots)
- `previous_priority` / `current_priority`
- `previous_confidence_band` / `current_confidence_band`
- `scoring_format`, `valuation_lens`
- `summary_headline`, `summary_detail`, `why_label` (deterministic presentation)

Canonical truth is structured fields — not arbitrary rendered prose.

## Lifecycle → event mapping

Consumes `recommendation_lifecycle.compare_inventory_signatures()` only.

| InventoryChange | History event |
| --- | --- |
| `priority_changed` | Top priority changed |
| `recommendation_changed` + new id | New recommendation / opportunity |
| `recommendation_changed` + action/confidence fields | Action changed / strengthened / softened |
| `recommendation_resolved` | Recommendation / waiver / roster need resolved |

Context reasons from `sync_lifecycle_on_context_change` inform **Why?** labels
(roster, availability, scoring, valuation) without inventing football causation.

### Deliberately ignored

- Identical reruns / refreshes with identical material signatures
- Navigation, opening PQV / Inbox / menus
- Cache refresh with identical content
- Cosmetic/copy/presentation-only movement
- Every OVR rank tick (no new rank-change scoring)
- First inventory observation (baseline seed only — no history spam)

## Dedupe rules

- Event id = hash(league, recommendation_id, reason, next_state, material_signature)
- Duplicate sync of the same transition does not append again
- New-recommendation rows suppressed when a priority-changed event already covers the new #1
- Cap: 24 session events; Dashboard shows ≤3

## Deterministic summary rules

Summaries are generated from structured diffs only (no LLM):

- Top priority changed → target + optional prior target
- Waiver opportunity resolved → “no longer available”
- Recommendation action changed → prior action → current action
- Recommendation strengthened/softened → confidence band labels
- Roster need resolved → need no longer immediate

If cause cannot be established: `Underlying recommendation context changed.`

## Deep-link behavior

Where a destination exists, CTAs reopen **current** workspace truth:

| Category | Destination |
| --- | --- |
| Trades | Trade Hub |
| Waivers | Waivers |
| Player / injury | Player Quick View (when player_id present) else My Team |
| League | League Overview |

Historical recommendation narratives are **not** rebound. `_open_decision_change_event`
passes `recommendation_narrative=None` so stale advice is never resurrected as current.

## Dashboard hierarchy

1. Today's Game Plan (primary)
2. **What Changed** (secondary) ← this feature
3. Your Next Move …
4. Remaining workflow zones

Quiet empty state:

> No meaningful decision changes since your current session began.

Full history: `st.dialog("Decision history")` grouped Today / Earlier.

## Inbox relationship

Coexistence is allowed when questions differ:

- Inbox: “Add Brashard Smith”
- What Changed: “Brashard Smith became your top waiver priority” / resolved

Forbidden duplication: both saying only “Recommendation changed.”

## Persistence decision

**Session-scoped Founder Beta only.** No Supabase schema in this PR.

Cleared on:

- logout / account switch (`session_integrity` + `clear_lifecycle_session_state`)
- league switch (`_clear_league_switch_transient_state` + lifecycle league change)

### Future durable-history proposal (not implemented)

If founders need cross-session recall, propose a later table such as
`decision_change_events(account_id, league_id, roster_id, event_id, recommendation_id,
reason, transition, payload_json, created_at)` with TTL retention. Require product
evidence before migrating production.

## Mobile contract

At ≤430px:

- Compact meta + one-line detail
- No giant explanation block
- No nested scroll trap / horizontal overflow
- CTAs ≥44px
- Respects #150 overlay layering (page content; history dialog uses modal layer)

## Performance impact

- Consumes diffs already computed in `publish_activity_inventory`
- No recommendation / valuation / ranking / Trade Hub / waiver recomputation
- No Sleeper/Supabase calls for history
- CSS is route-scoped (`DECISION_CHANGE_HISTORY_CSS`) — not added to global `APP_CSS`

## Terminology findings

Overlapping labels observed (do not redesign in this PR):

| Term | Role today | Simplification lean |
| --- | --- | --- |
| Today's Game Plan | Current priorities | Keep |
| Your Next Move | Primary tile zone | Consider folding into Game Plan later |
| What Changed | Decision transitions | Keep |
| Inbox / Alerts | Activity | Keep “Inbox” as product noun |
| Immediate Action | Urgent roster issues | Keep for urgency band |
| League Intelligence | Supporting intel | Keep secondary |
| Recommendation / Priority | Internal vs presentation | Prefer “priority” in founder copy |

## Explicit confirmation

No football logic, Trust, auth, Stripe, Supabase schema, Sleeper, ranking math,
recommendation generation/scoring/ordering, or #149 lifecycle semantics were changed
beyond consuming inventory diffs and clearing session history keys.
