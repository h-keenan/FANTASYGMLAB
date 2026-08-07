# Experimental GM Targets — product & engineering contract

| Field | Value |
| --- | --- |
| Customer name | **GM Targets** |
| Label | **Experimental** |
| Supporting copy | Keep an eye on players you're considering buying, selling, adding, or monitoring. |
| Kill switch | `DYNASTYGM_EXPERIMENTAL_GM_TARGETS=1` (default **off**) |
| Entitlement | Premium + Experimental |
| Cap | **50 targets per league** (app-enforced; no silent eviction) |
| Baseline | after PR #161 (`d0f08fdca4e76a16dd3819a2525503a9fd415228`) |

## Product purpose

Answers: **“What is happening with the players I care about?”**

GM Targets is **user preference / observation**, not recommendation input.
Being watched must never increase value, ranking, recommendation score, Trade Hub
priority, waiver priority, Trust, confidence, or notification importance.

## Architecture

```
PQV / workspace Add|Remove
  → modules/gm_targets.py (preference CRUD + session ID cache)
  → Supabase gm_targets (user_id, league_id, player_id)
Display enrichment (read-only):
  → canonical ranks (#141/#143)
  → shared roster ownership map
  → existing recommendation narrative / activity inventory
  → existing DecisionChangeEvent (material change indicator)
```

No `gm_target_recommendation_score`. No football cache invalidation on add/remove.

## Schema

Migration: `docs/supabase_gm_targets.sql` (manual Ops apply — never from Streamlit).

### `gm_targets`

| Column | Notes |
| --- | --- |
| `user_id` | FK `auth.users` ON DELETE CASCADE |
| `league_id` | League scope |
| `player_id` | Stable Sleeper id (normalized string) |
| `source_surface` | Optional provenance (`player_quick_view`, …) |
| `created_at` | Default `now()` |
| PK | `(user_id, league_id, player_id)` |

Do **not** store name, team, ranks, values, recommendations, or ownership.

## RLS

| Op | Policy |
| --- | --- |
| SELECT / INSERT / DELETE | `auth.uid() = user_id` to `authenticated` |
| UPDATE | Not required in v1 |
| anon | **None** |

Client-provided `user_id` is still constrained by RLS.

## Kill switch

| State | Behavior |
| --- | --- |
| Off (default) | No customer UI, no reads, no writes; durable rows intact |
| On + Free | One restrained discovery on GM Targets destination; no persistence |
| On + Premium | Add/remove, durable list, enrichment |

## Entitlement

| Actor | Behavior |
| --- | --- |
| Guest | No discovery |
| Free + on | Discovery only on GM Targets page (not littered across PQV/Trade/Waivers) |
| Premium + on | Full feature |

Preserve #161: Free core jobs (Game Plan, What Changed, previews) remain ungated.

## Target identity & league scope

- Identity: `(user_id, league_id, player_id)` — never player name.
- Same player may be targeted in League A and not League B.
- League switch clears session cache immediately; durable rows retained per league.
- Account logout/switch clears session cache only.

## Workspace location

Experimental destination **`gm_targets`** under ROSTER (GM Menu / Where to go when kill switch on).
Not added to mobile primary orbs.

## Surfaces supporting Add/Remove

| Surface | Control |
| --- | --- |
| Player Quick View | Canonical full-width Add / Remove |
| GM Targets workspace | Remove + Open player |
| Trade Hub / Waivers / My Team / Players | Via existing PQV (no per-card bookmark clutter) |

## Presentation ordering (not a score)

1. Currently actionable canonical recommendation
2. Material change present
3. Canonical OVR ascending (missing last)
4. Recently added (`created_ts` desc)
5. `player_id` tie-break

## Canonical enrichment

| Field | Source |
| --- | --- |
| Ranks | `canonical_player_ranking.format_compact_rank` + scoring format |
| Ownership | Shared `roster_player_map` / my roster ids — no per-target provider calls |
| Recommendation | Bound narrative or activity-inbox record only; empty → “No current action” |
| Material change | Existing `DecisionChangeEvent` for `player_id` — **no new events** |

User intent (target) and FantasyGM Lab recommendation may disagree — that is intentional.

## Decision Memory relationship

| Feature | Question |
| --- | --- |
| GM Targets | Who am I watching **now**? |
| Decision Memory | What materially changed **over time**? |

Targets do not write Decision Memory. Removing a target does not delete history.

## Notifications relationship

v1 shows status/change **inside GM Targets only**.
Being watched does not make an event notification-worthy.
Future alerting may subscribe to independently material canonical events — document only.

## Performance

| Concern | Contract |
| --- | --- |
| Critical path | Not on shell / Dashboard primary / Trade Hub #1 / PQV first-useful |
| Membership | One league list fetch → session ID set for PQV |
| Add/remove | Preference CRUD only; no football recomputation |
| Protobuf | Must not raise 520KB budget; CSS route-scoped |

## Privacy / deletion

| Topic | Behavior |
| --- | --- |
| Stored | `user_id`, `league_id`, `player_id`, optional `source_surface`, `created_at` |
| Cap | 50/league; customer message at cap; no silent eviction |
| Retention | Until user removes, account deletion cascade, or future explicit policy |
| Logout | Session cache only |

## Known limitations / future

- No user notes in v1
- No target-driven notification spam
- No cross-league aggregate view
- Alerting possible later if canonical material events already qualify

## Ops activation

1. Run `docs/supabase_gm_targets.sql` in Supabase SQL Editor.
2. Set Render `DYNASTYGM_EXPERIMENTAL_GM_TARGETS=1`.
3. Confirm Premium can add/remove and open GM Targets.
4. Confirm Free sees discovery only on the GM Targets destination.
5. Confirm kill switch off hides UI and stops writes.

## Rollback boundary

Disable kill switch or revert this PR’s modules/UI/docs/tests.
Durable `gm_targets` rows remain until Ops drops the table.
Does not roll back Decision Memory, rankings, or Stripe.
