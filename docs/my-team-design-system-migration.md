# My Team Design System Migration

## Scope

This migration changes presentation only. The existing My Team route still
constructs roster membership, roles, lineup, Team Needs, advice, trades,
waivers, injuries, roster-limit decisions, ranks, and entitlement state before
calling `modules.my_team_ui.render_my_team_workspace`.

No calculation input, recommendation list, cache boundary, or entitlement rule
is changed. Premium Deep Analysis content is gated to match the documented
Free/Premium matrix.

See `docs/my-team-roster-workspace-audit.md` for the #194 hierarchy pass.

## Information architecture

The primary workspace presents:

1. Roster priorities
2. Roster decisions (Core Assets first; secondary decisions collapsed)
3. Starting lineup grouped by lineup role
4. Bench depth (Premium detail collapsed)
5. Roster Snapshot (position rooms + franchise context; single Health Outlook)
6. Taxi and IR caption when populated
7. Collapsed front-office context + Premium deep analysis

Projected starters are partitioned once into QB, RB, WR, TE, Flex, special
teams, and a safe fallback group. Each input row appears in exactly one group.
The partition changes display order only.

## Design System use

- Level-two and level-three hierarchy uses the canonical section-header
  primitive.
- Empty roster conditions use the canonical classified empty-state primitive.
- My Team compact player rows opt into the shared token-backed player-card
  treatment and canonical semantic status badge.
- Core Assets, starters, and Premium bench notes use
  `canonical_player_ranking.format_compact_rank`.
- The existing player-card renderer remains the single implementation.
- Every migrated card retains its existing deterministic Player Quick View key,
  source label, recommendation context, and lazy modal behavior.

## Responsive and accessibility contracts

- Existing compact-card mobile flow remains single-column.
- Player cards retain native keyboard activation metadata and meaningful Quick
  View labels.
- Canonical focus rings and the 44px minimum touch target apply to migrated
  cards.
- Bench detail remains collapsed to limit initial mobile scroll length.

## Taxi and IR limitation

The presentation boundary receives existing Taxi and IR counts, not the
individual Sleeper assignment lists. This migration therefore displays a
summary caption only and does not infer membership.

## Validation boundary

Structural tests cover starter partitioning, empty states, token-backed card
opt-in, canonical status badges, unchanged Quick View keys, Free/Premium
branches, and section order after the roster-workspace hierarchy pass.
