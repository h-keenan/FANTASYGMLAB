# Dashboard browser visibility / parent-DOM probe (#241)

## Incident after #240

Production sessions `c88de577` / `e89aca1c` proved Python render completes:

- `dashboard_game_plan_emit_complete`
- `dashboard_python_render_complete`
- `final_app_render_return`
- `post_usable_auth_save_flushed` (same run, no remount)

Yet users still saw no Dashboard, and **no** `browser_dashboard_visible` ack reached
server logs.

## Root cause (probe false negative + overlay risk)

1. The #240 visibility probe was a Streamlit `components.v2` widget. Its JS ran
   inside the **component iframe** and queried `document` — not the parent
   Streamlit app document where Dashboard markers live. Production therefore
   never emitted a browser ack even when Python finished.
2. Server `loading_dismissed` / `startup.complete()` is not proof the browser
   dropped `.dg-startup-shell` (fixed, z-index `2147483000`). A stale shell can
   keep covering the app after Python render.

This pass does **not** change football, fingerprints, auth persistence, or
package caches.

## Fix

1. Probe observes `window.parent.document` (same pattern as navigation scroll).
2. MutationObserver on the top-level app for marker/shell/block-container churn.
3. Overlay watchdog: when `[data-fgl-dashboard-useful]` exists, forcibly dismiss
   only `.dg-startup-shell` nodes (never dialogs/modals).
4. One stable `setTriggerValue('visibility_ack', …)` (no `Date.now` identity)
   so Python logs `browser_dashboard_visible` once per startup session.
5. Diagnostics canary `DASHBOARD_CANARY_<session>` via plain `st.text`.
6. Optional `FGL_SAFE_VISIBILITY_MODE=1` CSS overrides (with `DYNASTYGM_STARTUP=1`).

## Acceptance

Browser matrix must prove markers + Game Plan + non-zero dimensions + overlay
absent + ≥5s stability. Production still requires a returning-user browser
session with `DYNASTYGM_STARTUP=1` to confirm server-side ack.
