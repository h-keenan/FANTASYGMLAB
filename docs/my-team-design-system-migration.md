# My Team Design System Migration

## Scope

This migration changes presentation only. The existing My Team route still
constructs roster membership, roles, lineup, Team Needs, advice, trades,
waivers, injuries, roster-limit decisions, ranks, and entitlement state before
calling `modules.my_team_ui.render_my_team_workspace`.

No calculation input, recommendation list, cache boundary, or entitlement rule
is changed.

## Information architecture

The primary workspace now presents:

1. Roster priorities
2. Team summary
3. Roster decisions
4. Starting lineup grouped by lineup role
5. Bench depth
6. Taxi and IR summary when populated
7. Team outlook
8. Existing Premium deep analysis

Projected starters are partitioned once into QB, RB, WR, TE, Flex, special
teams, and a safe fallback group. Each input row appears in exactly one group.
The partition changes display order only.

## Design System use

- Level-two and level-three hierarchy uses the canonical section-header
  primitive.
- Empty roster conditions use the canonical classified empty-state primitive.
- My Team compact player rows opt into the shared token-backed player-card
  treatment and canonical semantic status badge.
- The existing player-card renderer remains the single implementation.
- Every migrated card retains its existing deterministic Player Quick View key,
  source label, recommendation context, and lazy modal behavior.
- The card surface uses semantic tokens for surface, border, radius, elevation,
  focus, and minimum touch-target size.

The opt-in arguments default off, so other pages retain their current
presentation until their own controlled migration.

## Responsive and accessibility contracts

- Existing compact-card mobile flow remains single-column.
- Player cards retain native keyboard activation metadata and meaningful Quick
  View labels.
- Canonical focus rings and the 44px minimum touch target apply to migrated
  cards.
- Status remains visible as text and does not rely on color alone.
- Empty states use semantic headings and explicit condition-specific copy.
- Bench detail remains collapsed to limit initial mobile scroll length.

## Taxi and IR limitation

The presentation boundary receives existing Taxi and IR counts, not the
individual Sleeper assignment lists. This migration therefore displays a
summary only and does not infer membership. Adding individual exempt-roster
cards would require a separately reviewed data-boundary change.

## Validation boundary

Structural tests cover starter partitioning, empty states, token-backed card
opt-in, canonical status badges, unchanged Quick View keys, Free/Premium
branches, and preservation of existing rendering defaults.

The controlled in-app browser could not initialize in this environment, so
authenticated pixel screenshots were not captured. Desktop and mobile
contracts were validated structurally against existing responsive styles and
the fixture-backed renderer tests. A future visual pass should capture the My
Team route with synthetic authenticated fixtures at 1440x900, 390x844, and
360x800 before the next full page migration.
