# My Team roster workspace audit

| Field | Value |
| --- | --- |
| Baseline | `409a003b9c3d22c09e9bcb050a7f90877aa751d0` |
| Scope | Information architecture + presentation + decision density |
| Explicit non-changes | Valuations, canonical ranks, recommendation generation/order, Trade Hub/waiver math, Trust, auth, entitlements rules (presentation gating aligned to docs), Sleeper semantics |

## Before section inventory

| Section | Question | Important? | Dup? | Decision-useful? | Treatment |
| --- | --- | --- | --- | --- | --- |
| Page shell + continuity | Where am I? | Yes | Low | Orienting | Keep; tighten subtitle |
| Roster Priorities | What needs attention now? | Yes | Partial vs advice | Primary | Keep first |
| Roster Decisions / Core Assets | Which players matter most? | Yes | Low | Primary | Keep |
| Protected / trade-hold-drop | What can move/cut? | Yes | Limit alert when over | Primary (Premium) | Keep collapsed |
| Team Summary | Strength/weak/health? | Yes | Health + rooms | Medium | Merge |
| Starting Lineup | What does roster look like? | Yes | Deep tables | Primary | Promote earlier |
| Bench | Depth? | Yes | Deep tables | Medium | Keep collapsed Premium |
| Taxi & IR tiles | Exempt slots? | Sometimes | Roster Status note | Low | Compact caption |
| Team Outlook | Franchise posture? | Yes | Health + archetype | Medium | Merge into Snapshot |
| Front-Office Advice | Narrative playbook? | Medium | Restates Next Move | Medium | Demote expander |
| Deep Analysis | Manual overrides/tables? | Support | Rooms/archetype | Mixed | Premium-only body |

## Final hierarchy

1. **Roster Priorities** — Next Move, status, injury, need, trade, waiver (or Roster Pressure when over limit)
2. **Roster Decisions** — Core Assets (canonical compact ranks) → collapsed secondary decisions
3. **Starting Lineup** — projected groups with compact OVR/pos ranks
4. **Bench** — Premium key backups (collapsed) or lock
5. **Roster Snapshot** — single band: starter unit, weak/strong rooms, strategy, power, franchise, archetype, one Health Outlook
6. **Taxi/IR** — caption only when counts > 0 (no fake membership lists)
7. **Front-office context** — collapsed existing advice cards
8. **Deep Analysis** — Premium: strategy/untouchables, roles, outlooks, Draft Watch, tables, handoffs

## First screen

| Width | Before | After |
| --- | --- | --- |
| 390 | Shell + priorities tiles; lineup late | Same priorities first; lineup earlier than merged snapshot |
| 1440 | Priorities + start of decisions | Priorities → decisions → lineup before franchise tiles |

## Player-row contract

| Surface | Rank | Value | Affordance |
| --- | --- | --- | --- |
| Core Assets | `format_compact_rank` canonical | `value_score` | PQV |
| Starters | `format_compact_rank` canonical (added) | `value_score` | PQV |
| Bench (Premium) | `format_compact_rank` canonical (added) | `value_score` | PQV |
| Trade/Hold/Drop | Decision reason notes | `value_score` | PQV + narrative |

No local rank math. Scoring-format attachment remains on prepared `df_players`.

## Recommendation / GM Targets / Free–Premium

- Recommendations: existing `select_my_team_primary_recommendation`, trade/waiver narratives, advice builder — unchanged.
- GM Targets: still PQV-only; no per-row target chrome.
- Free: Priorities, Core Assets, lineup, Snapshot, collapsed advice.
- Premium: secondary decisions, bench detail, Deep Analysis body (roles/tables/watchlists). Entitlement leak fixed: Free no longer receives Edit Roles / tables outside the lock.

## Redundancy removed

- Duplicate Health Outlook tile (Summary + Outlook → one)
- Separate Team Summary + Team Outlook headers → **Roster Snapshot**
- Taxi/IR summary-tile band → caption
- Always-open Front-Office Advice band → collapsed expander
- Deep Analysis Strengths/Weaknesses/Risk cards + archetype summary (covered by Snapshot)

## Primitives

| Primitive | Status |
| --- | --- |
| home-command-card priorities | Retained |
| summary-tile snapshot | Retained (one band) |
| advice-card | Retained, demoted |
| prospect-card Draft Watch | Retained Premium |
| design_system scan cards | Retained |
| st.dataframe deep tables | Retained Premium disclosures |

## Gaps intentionally not changed

1. Starters/bench remain **projected** via `suggest_optimal_lineup`, not Sleeper starter slots.
2. Taxi/IR **counts only** — no membership lists without a data-boundary PR.
3. No new position-grade or roster-balance model.
4. Free still cannot edit strategy/untouchables without Premium Deep Analysis (existing contract).

## Performance

Presentation-only; no new providers. Expect flat-to-slightly-lower payload from removing duplicate tiles/cards. Fill measured APP_CSS / protobuf in the PR report.

## Remaining debt

- Continuity bar copy still generic.
- Role editor UX still dense inside Deep Analysis.
- Wide desktop still single-column scan (no separate wide layout).
- Individual Taxi/IR player cards blocked on data boundary.
