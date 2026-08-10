# Auth storage restore variance & Game Plan timing (#218)

## Production evidence (post-#217)

| Session | `auth_storage_requested` → `received` | `loading_dismissed` | Game Plan (wall) |
| --- | ---: | ---: | ---: |
| Fast `7cb9473a` | ~1.3s | ~1.95s | ~3.48s |
| Slow `8828ba78` | ~7.0s | ~7.76s | ~12.58s |
| Slow `b741f9e8` | ~6.4s | ~7.22s | ~11.20s |

Football hydration after dismiss is ~10ms when prepared-frame process reuse hits.
Shell summary is ~30ms and is **not** the bottleneck.

`game_plan_first_useful.elapsed_ms` was wrongly ~0 because `startup.complete()`
cleared `STARTUP_TIMING_STARTED_KEY` and the milestone re-seeded origin to “now”.
**Fixed:** complete no longer clears the timing origin for the startup session.

## Browser-storage handshake (hard platform boundary)

```text
Python mark_component_mount_start
  → mount Components v2 `supabase_auth_storage_bridge`
  → JS entry (performance.now)
  → localStorage read (+ legacy migrate)
  → setTriggerValue(stored|status) + _handshake diag
  → Streamlit schedules script rerun
  → Python record_payload_received / restore_auth_payload
```

There is **no** Python sleep/poll loop. Hang protection allows at most one
`st.stop()`; the browser component must emit within **3 s** (`startup_deadline`)
so Streamlit remounts (#242). Slow sessions that still logged
`auth_storage_received` at ~7–56 s waited on **Streamlit’s component
mount → trigger → rerun** without a client wake-up — fixed by the deadline emit.

### Diagnostics (`DYNASTYGM_STARTUP` when enabled)

`kind=auth_storage_handshake` fields:

| Field | Meaning |
| --- | --- |
| `python_first_pending_ms` | Mount → first empty return |
| `python_mount_to_receive_ms` | Mount → payload receive (Python clock) |
| `request_to_receive_wall_ms` | Wall clock request → receive |
| `js_entry_ms` | JS module entry offset |
| `localStorage_read_ms` | `getItem` (+ legacy) duration |
| `js_emit_ms` | Entry → `setTriggerValue` |
| `frontend_to_python_ms` | JS emit wall → Python receive wall |
| `visibility` / `hidden` | Tab visibility at emit |
| `pending_returns` | Empty component returns before payload |
| `python_apply_ms` | `restore_auth_payload` (+ optional refresh) |

A ~1.3s vs ~7s restore should show which of: JS entry delay, localStorage read,
emit, or frontend→Python/rerun gap dominates.

### Clock domains (comparable fields only)

| Field | Clock |
| --- | --- |
| `python_first_pending_ms` / `python_mount_to_receive_ms` | `time.perf_counter` deltas |
| `js_entry_ms` / `localStorage_read_ms` / `js_emit_ms` | Browser `performance.now` relative durations |
| `emit_wall_ms` / `frontend_to_python_ms` | Wall-clock ms (`Date.now` / `time.time()*1000`) |
| `request_to_receive_wall_ms` | Wall-clock from first Python mount mark to payload receive |

**Do not subtract across clock domains.** Wall fields are comparable to each other;
perf_counter fields are comparable to each other. Handshake logs include a
`clock_domains` map. Auth behavior is unchanged.

## Is localStorage still a hard startup prerequisite?

**Yes for a cold Streamlit session with no in-memory auth.**

Safe fast path already exists and is preserved:

- If `session_state` already has a user id (`hasSession=true`), JS skips token
  restore and Python does not wait for `stored`.
- Identical fingerprint restore skips workspace wipe / re-queue.

There is **no** auth cookie or server-readable durable identity today. Adding one
would be a separate security design (logout, expiry, multi-tab, account switch)
and was **not** implemented here to avoid risky auth shortcuts.

## Game Plan post-football owners

Named slow-ops / milestones after `football_context_ready`:

1. `game_plan_shared_league_context` — `get_shared_league_context()` at Dashboard entry
2. `game_plan_prefs` — authenticated preference refresh
3. `game_plan_league_context` — fallback `cached_league_context` inside dashboard
4. `game_plan_trade_inventory` — headline trades + enforce + tendencies
5. `game_plan_compose` — `compose_daily_gm_briefing`
6. `game_plan_first_useful` — after Today’s Game Plan DOM marker (correct origin)

No recommendation methodology changes.

## Post-ready script runs

`startup_run` rows now include `run_cause`, e.g.:

| Cause | Meaning |
| --- | --- |
| `auth_storage_pending` | Waiting on browser storage |
| `startup_shell` / `startup_football_or_route` | Pre-complete hydration |
| `post_usable_auth_save` | Deferred durable save remount (#217) |
| `league_switch` / `player_quick_view` | Interactive |
| `post_ready_interactive` | Other post-READY remounts (widgets/fragments) |

## Production verification

1. Enable `DYNASTYGM_STARTUP=1`.
2. Capture ≥3 returning-auth sessions (include at least one slow storage case).
3. Confirm `game_plan_first_useful.elapsed_ms` ≈ wall time from session start (not ~0).
4. Diff `auth_storage_handshake` rows for fast vs slow.
5. Confirm `loading_dismissed` still precedes players/prepared.
6. Disable `DYNASTYGM_STARTUP`.
