# Post-dismiss football hydration & widget-state ownership (#217)

## Problem

After #215/#216, global loading dismisses in ~2s. Remaining cost was post-dismiss:

- prepared valued+ranked frame miss (~1.5s)
- `ranks_ready` (~1.2–2.0s) dominated by building thousands of rank dataclasses
- optional valued shell enrichment (league summary) before Game Plan
- deferred auth save `st.rerun()` immediately at dismiss, forcing football onto the next run
- Streamlit widget dual-ownership warning on `player_trade_hub_target_player_*`

## Architecture after this PR

```text
shell + nav → loading_dismissed (~2s preserved)
  → players → valuation → ranks (vectorized attach) → prepared frame
  → football_context_ready
  → schedule public player refresh (process single-flight background; #238)
  → Dashboard Game Plan → game_plan_first_useful
  → valued shell chrome enrichment (deferred on Dashboard)
  → dashboard_football_ready
  → optional post-usable auth save remount (after football, once)
```

Stale Sleeper player refresh must never await on the football→Game Plan gap
(`docs/post-football-player-refresh-stall-238.md`).

## ranks_ready breakdown

`attach_canonical_ranks` no longer builds a full `CanonicalRankingTable` of dataclasses
to paint columns. Same methodology (eligibility → stable score sort → overall +
positional ranks). Timing parts (when `DYNASTYGM_STARTUP` enabled):

| Part | Meaning |
| --- | --- |
| `dataframe_copy_ms` | input copy |
| `score_prep_ms` | numeric score / id / position columns |
| `eligible_filter_ms` | eligibility mask |
| `sort_and_positional_ms` | ordering + OVR/POS ranks |
| `merge_assign_ms` | column attach |
| `total_ms` | wall for attach |

## Prepared-frame cache

1. Session memo (`#152`) — warm reruns
2. Process store — identical public+settings signature across Streamlit sessions in the same worker (no account/roster in key)
3. Diagnostics: `prepared_frame_cache_lookup`, `prepared_frame_build_start/complete`, miss reason on slow-op detail
4. `prepared_frame_cache_write` only on miss

## Post-dismiss runs

| Run (typical) | Owner |
| --- | --- |
| 2 | Shell + `loading_dismissed` + football hydrate + Game Plan (when no early remount) |
| later | One post-usable auth save remount (`post_usable_auth_save_rerun`) — football is cache hit |
| fragments | PQV / Trade Hub only; not startup hydration |

Auth save is marked at dismiss (`post_usable_auth_save_deferred`) and remounts **after** football/Game Plan so it cannot duplicate cold rank builds.

## Widget ownership

Pattern A for handoff-driven selects:

- init `st.session_state[key]` before widget
- omit `index=` / conflicting default

Fixed:

- `player_trade_hub_target_player_{league}`
- `{prefix}_return_explorer_player`
- `league_team_select_{league}`

League switch clears `player_trade_hub_target_player_` / `player_trade_hub_mode_` with focus keys.

## Explicit non-goals

No changes to valuation formulas, ranking formulas, recommendation generation/ordering, Trust, waivers, auth/entitlement rules, or Supabase schema.
