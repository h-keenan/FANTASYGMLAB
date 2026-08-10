# Dashboard visibility / Streamlit presentation (#240)

## Incident

Production `b1987155` proved football/cache layers are healthy after #239:

- `game_plan_first_useful` ≈ 5.44s
- `dashboard_football_ready` ≈ 5.59s
- package fingerprint stable (`b5b3b981`) with HIT on remounts

Yet the browser still did not show a loading Dashboard. Immediately after
`dashboard_football_ready`, production logged `post_usable_auth_save_rerun`
(~4ms later), then presentation runs 3–5.

## Root cause

1. **Destructive remount:** after Dashboard Python render, `main()` called
   `st.rerun()` to flush durable auth to `localStorage`. Streamlit tears down the
   just-emitted Dashboard deltas before the browser can commit a stable paint.
2. **Auth component trigger storm:** the storage component emitted
   `setTriggerValue(..., { ts: Date.now() })` on save/clear and on every settled
   `hasSession` read — timestamped triggers force additional Streamlit remounts
   (`post_ready_interactive`) after useful content.

Runs 3–5 were owned by that remount + timestamped auth-component callbacks, not
by football/package recomputation (fingerprint stayed HIT).

This is a presentation/lifecycle failure, not a football-cache miss.

## CSS / overlay audit

| Mechanism | Role | Visibility risk |
|---|---|---|
| `.dg-startup-shell` fixed, `z-index: 2147483000` | Startup overlay | Can hide Dashboard while present |
| `body:has(.dg-startup-shell) .app-hero { display: none }` | Hides hero while shell mounted | Cleared when `startup.complete()` empties placeholder |
| `placeholder.empty()` in `complete()` | Removes shell DOM | Required so `:has(.dg-startup-shell)` clears |
| Hidden marker divs (`data-fgl-dashboard-*`) | Diagnostics only | `hidden` + `aria-hidden` — not user content |
| Auth storage / visibility probe components | 1×1 widgets | Must not call `setTriggerValue` after useful paint |

Content can be present in the DOM but invisible while the startup shell remains.
Production evidence pointed to remount erasure, not a stuck overlay alone.

## Fix

1. Replace post-football `st.rerun()` with same-run
   `account_ui.flush_durable_auth_persistence()` (`post_usable_auth_save_flushed`).
2. Auth storage JS: save/clear/settled-session paths **do not** call
   `setTriggerValue`.
3. Dashboard presentation milestones from `dashboard_render_start` through
   `final_app_render_return`, plus `data-fgl-dashboard-*` markers.
4. Browser visibility probe (`modules/dashboard_visibility.py`) logs
   `browser_dashboard_visible` to the console only (no remount trigger).
5. Playwright matrix: desktop / 390px / Slow-4G fixture harness.

## Python → browser boundary milestones

| Milestone | Meaning |
|---|---|
| `dashboard_football_ready` | Football/package path ready — **not** visible |
| `dashboard_render_start` | `render_home_dashboard` entry |
| `dashboard_header_complete` | Workflow shell emitted |
| `dashboard_game_plan_emit_start/complete` | Game Plan widget/HTML emission |
| `dashboard_what_changed_complete` | What Changed section |
| `dashboard_summary_tiles_complete` | Snapshot/summary tiles path |
| `dashboard_deep_analysis_complete` | Deep Analysis nav |
| `dashboard_sections_complete` | Remaining sections + complete marker |
| `dashboard_render_function_return` | Python function return |
| `dashboard_python_render_complete` | Probe mount / Python render complete |
| `post_usable_auth_save_flushed` | Durable auth persisted **without** remount |
| `final_app_render_return` | `main()` finished this run |
| `browser_dashboard_visible` | Browser console ack (DOM + overlay absent) |

## Acceptance proof

- Python render completes through `dashboard_render_function_return`
- Browser receives `data-fgl-dashboard-useful` / complete markers
- Startup overlay absent
- Durable auth flush does not remount
- Markers remain stable ≥1.5s
- Package HIT behavior from #239 preserved
- No repeated football work after READY
