# DynastyGM Visual Identity — Phase 1

## Direction

DynastyGM now uses a monochrome, rectilinear visual foundation intended to read
as football front-office software: compact, deliberate, and information-first.
Color is reserved for semantic meaning. The implementation changes shared
presentation contracts only; it does not change page content or behavior.

## Shared contract

- Surfaces use graphite layers, one-pixel borders, and square geometry.
- Elevation is restrained and communicates hierarchy rather than decoration.
- Controls use uppercase compact labels, 44px minimum targets, and visible focus.
- Section headers use consistent bottom rules and tighter vertical rhythm.
- Tables use tabular numerals, compact uppercase headers, and subtle row bands.
- Existing modals retain their interaction contract with square panels and
  professional header bands.
- Reduced-motion preferences remove nonessential animation.

## Player cards and prestige

Current player-card renderers now resolve presentation through one prestige
mapping while preserving their existing user-facing labels:

| Prestige | Current labels |
| --- | --- |
| Elite | Cornerstone, Untouchable, Core Asset, Elite |
| Starter | Star, Core Starter, Starter |
| Contributor | Contributor |
| Development | Rising, Young Stash, Trade Target, Best Available, Priority Add |
| Depth | Depth, Hold, Watch List, Trade Candidate, Injury Replacement |
| Replacement | Drop Candidate, Deprioritized |

The shared stylesheet gives scan cards, compact roster rows, and explorer cards
the same border, surface, hover, avatar, typography, and prestige treatment.
Football statuses such as injury, opportunity, warning, Premium, and Trust keep
their semantic accents.

## Consistency audit

The audit found three primary causes of drift:

1. semantic tokens permitted rounded SaaS geometry;
2. legacy page CSS reintroduced gradients and large shadows after shared styles;
3. player statuses used page-specific tone colors without a common prestige axis.

Phase 1 corrects those at the final shared stylesheet boundary. It intentionally
does not rewrite thousands of legacy declarations because the final shared layer
provides one authoritative production result and keeps rollback isolated.

Remaining exceptions should be migrated only when their owning feature is
already being changed. Decorative marketing and legal/public surfaces were not
given new business content or structure.

## Validation boundary

Structural tests verify token ownership, stylesheet order, prestige mapping,
responsive targets, focus, reduced motion, tables, dialogs, and absence of
production logic changes. Representative browser checks cover desktop and mobile
where the fixture-backed local application can reach the relevant state.
