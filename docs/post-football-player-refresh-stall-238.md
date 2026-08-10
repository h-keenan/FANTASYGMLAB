# Post-football player refresh stall (#238)

## Incident

Production GO after #237 failed for a returning-user Dashboard. Correlated
`DYNASTYGM_STARTUP=1` sessions:

| Session | Role |
| --- | --- |
| `f3773561` | Primary — never reached Game Plan |
| `cf2e4880` | Interleaved — also paid `sleeper_players_fetch` after shell ready |

For `f3773561` the last successful milestones were:

`loading_dismissed` → `players_ready` → `prepared_frame_ready` → `football_context_ready`

Then a synchronous `provider_players` / `sleeper_players_fetch` (~9079 ms) ran
**before** Game Plan package lookup. Runs 3–8 followed (`post_usable_auth_save_queued`
/ `durable_auth_save_pending`) without `game_plan_first_useful`.

This is **not** the #233 package-MISS deadlock.

## Root cause

`ensure_players_for_startup` correctly served the persisted SQLite frame and armed
`PLAYERS_REFRESH_PENDING_KEY` when `sleeper_players.json` was stale (#215 SWR).

`maybe_refresh_players_after_shell` then **awaited** `build_players_table(refresh=True)`
on the request thread immediately after `football_context_ready` and **before**
`render_home_dashboard`. That blocked Game Plan entry and interacted badly with
Streamlit reruns while post-usable auth save remained queued.

## Fix

1. **STARTUP PLAYER FRAME** — persisted/cached frame remains first-useful.
2. **REFRESH PLAYER FRAME** — process-scoped single-flight background owner
   (`modules/players_refresh_flight.py`); followers keep last-known-good; failure
   preserves prior frame; cooldown prevents re-arm storms.
3. Request path after football only **schedules** refresh (`background=True`).
4. Auth save deferral is one-shot (do not re-arm `POST_USABLE_SAVE_AFTER_FOOTBALL_KEY`).
5. Diagnostics: `dashboard_game_plan_entry`, fingerprint + package lookup start/complete.
6. Summaries emit per trigger (`loading_dismissed`, `game_plan_first_useful`,
   `interactive_stable`) without treating the dismiss summary as final.
7. Dashboard post-football fail-soft deadline when Game Plan never becomes useful.

## Production re-verify

With `DYNASTYGM_STARTUP=1`, returning user + selected league + Dashboard:

```text
loading_dismissed
→ players_ready
→ football_context_ready
→ dashboard_game_plan_entry
→ game_plan_package_lookup_*
→ game_plan_first_useful / fail-soft
→ dashboard_football_ready
→ interactive_stable summary
```

If stale refresh occurs, prove it is `deferred_bg` / `refresh_owner` /
`coalesced_follower` and does **not** sit on the football→Game Plan gap.
Then disable diagnostics.
