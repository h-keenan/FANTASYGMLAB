# Executive Visual System Finalization

## Scope

Presentation only. Baseline `d4cdb55` (post PR #128).

No football logic, rankings, valuations, Trust, recommendation generation or
ordering, authentication, entitlements, Stripe, Supabase, caching, or business
rules.

## Inconsistencies fixed

### Command bar
- Shell vertical padding collapsed so the FGL tile aligns to the 44px control band
- Founder badge min-height matched to `--touch-target-min`

### Portrait system
- Replaced legacy black `#020617` radial avatar fills with slate surface gradient
- Removed circular multi-shadow chrome on shared `.trade-avatar` / `.player-avatar` /
  `.free-agent-avatar` classes
- Slightly larger shared headshot scale (`1.18` / compact `1.22`)

### Dashboard executive flow
Reorder (actions before analysis):

1. Your Next Move (primary recommendation)
2. League Intelligence (top waiver / trade signals)
3. Immediate Action (urgent alerts / roster pressure)
4. Team Snapshot
5. Deep Analysis / League Pulse (supporting)

### Typography
Section/card hierarchy remains token-backed via the unify layer
(`--type-page-title` for primary sections).

### Trade Hub cards
Eye flow: Headline → Package → Players → Value delta → Confidence

- Title before category badge
- Package block before impact row
- Stronger player names; quieter confidence badge and fit/market chips
- Slate gradient portraits in the summary iframe
- Mobile ≤430: keep 2.75rem (44px) avatars; hide category, side labels,
  why line, value-delta label, and brand chrome so card height stays ≤360px

### Visual rhythm / debt
- Legacy avatar gradients and round shadows removed where shared
- Flat executive shell band spacing

## Rollback

Revert the merge commit on `main` (boundary: `d4cdb55`).
