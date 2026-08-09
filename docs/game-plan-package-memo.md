# Game Plan package memo (PR #219)

## Problem

Production session `5bb127d1` (post-#218):

| Milestone | Elapsed |
|---|---|
| loading_dismissed | ~2.6s |
| football_context_ready | ~4.5s |
| game_plan_first_useful | ~12.2s |

Football→Game Plan gap ≈ **7.7s**, owned primarily by:

1. `game_plan_shared_league_context` ≈ **3.28s**
2. `game_plan_trade_inventory` ≈ **2.9–5.3s** (also re-entered on post-ready UI reruns)
3. Compose/render remainder ≈ **1.2s**

## Old dependency pipeline

```
prepared valued/ranked frame          CANONICAL FOOTBALL
  → get_shared_league_context()         LEAGUE CONTEXT (default include_intelligence=True)
  → refresh_authenticated_preferences   USER PREFERENCE (session-memoed)
  → team metrics / needs / waivers      LEAGUE CONTEXT + CANONICAL FOOTBALL
  → cached_dashboard_trade_headline     RECOMMENDATION INVENTORY (max_ideas=2 → cached_trade_ideas)
  → enforce + manager tendencies        SECONDARY ENRICHMENT (same inventory)
  → organize_dashboard_items            PRESENTATION inventory
  → compose_daily_gm_briefing           PRESENTATION composition
  → Streamlit render                    PRESENTATION
```

Why shared context stayed expensive after football was ready:

- Dashboard called `get_shared_league_context()` with **default `include_intelligence=True`**, rebuilding full League Insights / refined direction even though Trade Hub already uses `include_intelligence=False`.
- `@st.cache_data` still **hashes large `df_players`** on every call; “cache hit” is not free.
- Session shared-context memo existed but Game Plan still re-entered generation + trade hashing on ordinary Dashboard remounts (Alerts / GM / PQV / auth remount).

## New architecture

```
cheap prefs + roster ids + roles
  → Game Plan package fingerprint
  → session package lookup
       HIT  → restore DailyGmBriefing + DashboardBriefing + snapshot
              → render (presentation only)
       MISS → get_shared_league_context(**GAME_PLAN_CONTEXT_FLAGS)
              → trade headline inventory (once)
              → compose
              → store package
              → render
```

`modules/game_plan_package.py` owns the structured memo. Widgets are never memoized.

### Intelligence decision

`GAME_PLAN_CONTEXT_FLAGS = (False, True, True, True)`:

- `include_intelligence=False` — no full League Insights on Game Plan path
- roster map / trust / maturity remain on

League Pulse loads full intelligence **on demand** when the deferred gate is opened.

### Fingerprint (invalidates only on real truth)

- account user id
- league id / roster id
- prepared frame signature
- score field / league settings key
- team strategy / role map / untouchables
- entitlement
- lifecycle digest / roster state version
- startup mode / pick multiplier

Does **not** invalidate on Alerts, GM menu, PQV, static disclosure, or unrelated widgets.

### Trade inventory ownership

- Generator of record remains `cached_trade_ideas` / `build_trade_ideas`.
- Dashboard headline uses `cached_dashboard_trade_headline` (`max_ideas=2`).
- Trade Hub presentation uses a larger board (`max_ideas=8`).
- Game Plan package memo ensures Dashboard does not regenerate inventory on warm remounts when the fingerprint is unchanged.
- No alternate trade algorithm.

### Compose memo

`compose_daily_gm_briefing` keeps a small process memo keyed by briefing zone fingerprints + context. Package memo remains the Dashboard warm path owner.

## Invalidation

| Event | Behavior |
|---|---|
| League switch | `clear_league_scoped_prepared_memos` → clear package |
| Account switch / logout | `clear_account_bound_transient_state` / prepared clear → clear package |
| Roster / settings / roles / strategy / entitlement change | fingerprint miss → rebuild once |
| Alerts / GM / PQV / disclosure | fingerprint unchanged → hit |

## Milestones

- `game_plan_package_cache_lookup`
- `game_plan_context_ready`
- `game_plan_trade_inventory_ready`
- `game_plan_composed`
- `game_plan_package_ready`
- `game_plan_first_useful` (uses preserved `startup_session_origin` after `startup.complete()`)

## Production verification

With `DYNASTYGM_STARTUP=1`:

1. Three returning-auth Dashboard starts
2. Three Dashboard → My Team → Dashboard warm revisits
3. Alerts / GM / PQV after load

Expect: no repeated `game_plan_trade_inventory` / shared-context rebuild when fingerprint unchanged. Then disable diagnostics.

## Scope

Performance / caching / ownership only. No valuation, ranks, Trust, ordering, entitlement, auth, or lifecycle rule changes.
