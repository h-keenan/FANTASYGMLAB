# Mobile header overlap + account-control latency (production RCA)

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-08-12 |
| Production host | `https://app.fantasygmlab.com` |
| Rollback SHA | `6b62d2d9b104ee7c7b212cedc72dc18539a95046` (`main` tip / #272) |
| Fix branch | `cursor/mobile-header-auth-latency-71e1` |

## A. Mobile header — root cause

### Production DOM (390px Chromium, real Streamlit) — BEFORE

| Control | Live `stPopoverButton` count | Notes |
| --- | ---: | --- |
| SELECT | **2** | One inside `stTooltipHoverTarget`, one sibling |
| ALERTS | **1** | No `help=` |
| YOU | **2** | Same tooltip duplicate pattern |

SELECT’s second button sat at `left=134` — the same box as ALERTS — producing the overlapping SELECT/ALERTS glyph collision. YOU’s duplicate sat at `left=377` (outside the 390 viewport).

Artifact: `/opt/cursor/artifacts/prod-header-auth-forensics.json`,
screenshots `prod-header-before-{390,430}-top.png`.

### Why

1. `st.popover(..., help=...)` on League/Select and You makes Streamlit emit **two** `stPopoverButton` nodes inside one `stPopover`.
2. Canonical owner CSS set `[data-testid=stPopover] { display:flex }` **without** `flex-direction:column`, so siblings laid out in a **row**.
3. Tooltip accommodation used `min-width: 100%` on tooltip wrappers, so each duplicate claimed a full command-cell width and spilled into the next column.

Alerts (no `help=`) had a single button — only Select/You collided.

### Why 390 harness passed

Harness/CSS ownership tests asserted `help=` **presence** and tooltip fill rules; they did not assert **one live visible button per command** against real Streamlit popover+tooltip DOM on a 390 viewport. Synthetic fixtures did not reproduce the dual-button collision.

### Fix (canonical owner — not a late global override)

1. **Remove `help=`** from League/Select and You popovers (`app.py`); keep copy as `st.caption` inside the sheet.
2. In `EXECUTIVE_COMMAND_HEADER_CSS` (scoped owner, not APP_CSS): `flex-direction: column` on rail popovers; hide residual sibling `stPopoverButton`; drop `min-width: 100%` tooltip fill (`min-width: 0`).

No new global CSS override layer. `APP_CSS` length unchanged at **350891**. Header CSS remains a separate late inject from the header renderer.

### Local Streamlit AFTER (real app, not harness)

| Control | Live `stPopoverButton` count | Left edges (390) |
| --- | ---: | --- |
| SELECT | **1** | ~13 |
| ALERTS | **1** | ~134 |
| YOU | **1** | ~256 |

No overlapping boxes. Screenshots: `local-header-after-{390,430}-{top,rail}.png`.

## B. Account-control latency — root cause

### Critical path (unsigned, no league) — BEFORE

1. Streamlit bootstrap / Render cold start (when applicable)
2. Auth storage bridge → up to **`AUTH_STORAGE_CLIENT_DEADLINE_MS` (3000)** `st.stop()` wait
3. Profile/entitlement (no-op when signed out)
4. League restore (no-op)
5. **Sidebar widget forest** + shell chrome + notifications + topbar
6. Only then `render_home_launch_screen` → Create account / Guest

Account CTAs waited on **sidebar + shell + notifications**, not on Sleeper/valuation/news directly — but those steps sat on the same run before launch UI.

Cold Chromium on `app.` ~2.3–3.2s when warm edge; iPhone Safari ~8–10s matches auth pending + heavy pre-launch work.

Blocking network for guest CTAs: auth-storage iframe deadline (empty storage should resolve earlier; hung clients paid full 3s). No required Sleeper/valuation/news calls for unsigned+no-league, but sidebar still ran first.

Reruns before usable CTAs (guest, empty storage): typically **1** script run after bridge; wall clock dominated by bridge deadline + pre-CTA chrome.

### Fix

1. After auth/league settle, if unsigned + no league: **dismiss loading** and render marketing + `render_mobile_auth_entry` **before sidebar**.
2. Lower client auth storage deadline **3000 → 1500 ms** (empty storage still emits immediately; hung iframe wakes sooner).
3. Launch screen skips duplicate account entry when early path already ran (`_early_launch_account_rendered` / `skip_account_entry`).

No spinner-only “fix”.

### Local AFTER timing (unsigned, no league)

- `loading_dismissed` with `early_guest_launch: true` ~**16 ms** script elapsed after `league_restored`
- `account_controls_ready` ~**21 ms** script elapsed
- Reruns before account controls usable: **0** additional (same run as auth settle)

Production cold/warm before/after wall times: re-measure on `app.` after deploy (see PR artifacts).

## CSS / protobuf

| Metric | Before | After |
| --- | ---: | ---: |
| `len(APP_CSS)` | 350891 | 350891 (unchanged) |
| `len(EXECUTIVE_COMMAND_HEADER_CSS)` | ~18.5k | **18740** |
| Header CSS inside APP_CSS | no | no |
| New global CSS layer | — | **none** |

Protobuf / headroom: `tests/test_css_protobuf_headroom.py` (`len(APP_CSS) < 390_000`).

## Validation

- Focused header/auth/startup contracts + full pytest
- `python3 -m compileall`
- `git diff --check`
