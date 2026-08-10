# Auth storage startup stall (#242)

## Incident

Production session `83e6049f` waited **56,091 ms** between
`auth_storage_requested` and `auth_storage_received`. Same deployment sessions
completed auth storage in ~1.4–1.7 s. Users experienced this as “Dashboard never
loads.” Session `4799495d` later proved Dashboard DOM visibility can succeed
after #241 — this stall is **auth bootstrap starvation**, not Game Plan/CSS.

## Root cause

Python mounts `supabase_auth_storage_bridge`, sees no component value yet, sets
`pending`, and calls **`st.stop()` once**. Streamlit does **not** remount the
script until the browser component calls `setTriggerValue`.

Hang protection (`AUTH_PENDING_MAX_STOPS` / `AUTH_PENDING_MAX_MS`) only evaluates
on a **subsequent** script run. If the iframe/JS is delayed (tab backgrounded,
websocket queue, component mount starvation), there is no second run — Python
waits indefinitely for the emit. A 56 s gap is the wall time until JS finally
ran and emitted `stored`.

`frontend_to_python_ms` vs `request_to_receive_wall_ms` can disagree because they
mix wall clocks across browser/server; logs now include `wall_vs_frontend_delta_ms`
and explicit `clock_domains`.

## Fix

1. **Client deadline (3 s, capped at 5 s):** JS installs `setTimeout` that emits
   `stored` (if localStorage present) or `status` with `reason=startup_deadline`
   even if `initial_read` never completes — waking Streamlit.
2. **One `st.stop()` only** (`AUTH_PENDING_MAX_STOPS=1`). A second pending return
   continues as guest and arms late reconcile.
3. **Late reconcile:** timed-out / deadline paths arm
   `AUTH_LATE_RECONCILE_ARMED_KEY`. A later `stored` payload restores auth once
   without clearing a potentially valid durable session solely for lateness.
4. **Correlation:** shared `request_id` + `browser_instance_id` (sessionStorage)
   on handshake / startup_run rows.

## Not changed

Football, Game Plan, package fingerprint, Dashboard presentation, entitlements.

## Production gate

Returning-user loads with `DYNASTYGM_STARTUP=1`: auth storage wait max &lt; 5 s,
no 30–60 s stalls, `browser_dashboard_visible` still received. Local harness
alone is **not** sufficient to mark FIXED.
