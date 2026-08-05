# Founder Beta Workflow Correctness & UX Bug Fixes

| Field | Value |
| --- | --- |
| Baseline | `adf54bb` (latest `main` after Ops Activation #118; prompt cited `3065e31`) |
| Scope | Workflow / UX defect fixes only — no football logic, valuations, rankings, recommendation generation/ordering, Trust, auth, Stripe, Supabase schema, or Sleeper changes |
| Date | 2026-08-05 |

## Root causes found

1. **Trade Hub “one recommendation” (historical):** Category pills defaulted to Headline Recommendation (always 1 card) even when inventory was larger. Live UI already removed pills in #112; dead `render_trade_hub_section_filter` + orphan pill CSS remained and could be rewired by mistake.
2. **Secondary-heavy Free truncation:** Free preview keeps `primary[:2]` and drops all secondary. A board with **1 primary + N secondary** shows **1 card** under Free. Entitlement comparison now normalizes casing so `"Premium"` cannot accidentally Free-gate.
3. **Dashboard Next Move click tax:** Entitled additional recommendations (≤2) were hidden behind an expander with a duplicate `→` affordance, looking like missing inventory for Premium fixtures.
4. **Category badge fallback:** Cards without `_display_section` fell back to generic “Trade Board” instead of deriving the card category.
5. **PQV over-compression:** Executive compression forced `space-xs` dossier margins, hurting metric rhythm/readability.
6. **League switch stale trade dialog:** Open Trade Hub detail navigation was not cleared on league switch.

## UX bugs fixed

| Fix | Change |
| --- | --- |
| Remove category pills completely | Deleted `render_trade_hub_section_filter`; removed orphan pill CSS |
| Premium inventory honesty | Casefold entitlement; regression for 1 primary + N secondary |
| Category badges | Fallback to `trade_hub_display_section(idea)` |
| Dashboard Next Moves | ≤2 additional shown inline; larger stacks keep expander without `→` |
| PQV readability | Increased section/metric spacing; quieter Back-to-trade control |
| League switch | Close trade detail navigation with other transient state |
| Fixture harness | Annotate `_display_section` on Trade Hub fixture card |

## Explicit non-changes

No football logic, valuations, rankings, recommendation ordering, Trust calculations, authentication, Stripe, Supabase schema, or Sleeper integration changes.

## Remaining founder-reported issues

| Item | Status |
| --- | --- |
| Authentic production Premium board sometimes showing 1 idea after Trust truly leaves 1 | Expected scarcity — caption explains; not an entitlement hide |
| Authenticated league-switch latency on production | Needs credentialed measurement (Ops) |
| FQA-001–006 punch-list items | Unchanged review-only items in `docs/founder-qa-punch-list.md` |

## Rollback boundary

Revert this merge commit on `main`.
