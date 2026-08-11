# P0 render canary diagnostic (not a Dashboard fix)

Binary visibility experiment for production. Native Streamlit `st.write` /
`st.button` only. Safe-render CSS ON by default (`FGL_P0_SAFE_RENDER=0` to
disable). **Do not treat Python milestones or local harnesses as proof of paint.**

## Canary map (production path)

| ID | Label | Location |
|---|---|---|
| A | `FGL_P0_A_AFTER_AUTH` (+ `FGL_P0_CANARY_AFTER_AUTH` + `FGL_P0_TEST_BUTTON`) | `app.py` after `startup.complete()` / loading dismiss (~16176) |
| B | `FGL_P0_B_BEFORE_ROUTE` | `app.py` immediately before `render_home_dashboard(...)` |
| C | `FGL_P0_C_DASHBOARD_ENTER` | first lines of `render_home_dashboard` |
| D | `FGL_P0_D_FIRST_ELEMENT_RETURNED` | after first native `st.write` inside dashboard |
| E | `FGL_P0_E_DASHBOARD_RETURNED` | immediately after `render_home_dashboard` returns |

## Loading shell / main-content visibility owners

| Mechanism | File | Effect |
|---|---|---|
| Startup shell mount / dismiss | `modules/startup_coordinator.py` `_SHELL_CSS`, `begin`/`complete`/`abort` | Fixed fullscreen `.dg-startup-shell` (`z-index: 2147483000`, `inset:0`, `position:fixed`) covers the app until `placeholder.empty()` |
| Shell hides brand hero | same, `body:has(.dg-startup-shell) .app-hero { display:none }` | Hero hidden while shell present |
| First usable dismiss | `app.py` ~16146–16154 | `loading_dismissed` + `startup.complete()` |
| Safety dismiss | `app.py` ~20687–20695 | late `startup.complete()` if still active |
| P0 safe-render | `modules/p0_render_canary.py` | Forces shell hidden; forces main Streamlit containers visible |
| Prior safe-visibility (opt-in) | `modules/dashboard_visibility.py` `FGL_SAFE_VISIBILITY_MODE` | Similar overrides behind `html[data-fgl-safe-visibility]` |

## CSS/JS that can hide or cover main Streamlit content

**Overlay / cover**

- `modules/startup_coordinator.py` `.dg-startup-shell` — fixed full-viewport overlay
- `modules/dashboard_visibility.py` JS — may remove stale `.dg-startup-shell` after paint (watchdog); does not emit A–E

**Streamlit chrome / containers (`modules/app_styles.py`)**

- `[data-testid="stHeader"] { display:none }` (~6432)
- Toolbar / status / deploy / menu `display:none` (~10132–10139)
- Mobile `@media (max-width:900px)`: `overflow-x: clip` on `.stApp` / `stMain` / `stMainBlockContainer` (~10163–10170)
- Dialog-open: GM / feedback controls `visibility:hidden` (~10192–10196)

**GM Orb (explains invisible orb *label* text, not Dashboard body)**

- `modules/mobile_interaction_overlay_styles.py` — button children `color:transparent`, `font-size:0`, `opacity:0`, `visibility:hidden` on related blocks
- `modules/founder_beta_quick_fix_styles.py`, `modules/desktop_executive_layout_styles.py` — same orb pattern

**Other product `display:none` / opacity** (component-scoped, not global main blanking)

- Large APP_CSS product-card rules; `modules/ux_polish_styles.py` sheet/dialog control hiding; `modules/mobile_visual_polish_styles.py` quick-nav hide; executive/marketing `body:has(...) .app-hero { display:none }`

## Paths that can prevent or erase canaries

| Path | Effect |
|---|---|
| `st.stop()` while auth pending (`app.py` ~15232) | Never reaches A–E; loading shell still active |
| `st.stop()` when player frame empty (`app.py` ~16202) | A visible; B–E never emit this run |
| Exception before `render_home_dashboard` | A (and maybe not B); no C–E |
| Exception inside dashboard after C/D | A–D possible; E missing |
| Early `return` inside dashboard after C/D | C/D still emitted; E still runs after return |
| `startup.complete()` → `placeholder.empty()` | Clears shell placeholder only; does not clear main-flow canaries |
| Later `st.rerun()` | New run must re-emit canaries; prior DOM replaced by Streamlit remount |

**Not claimed fixed.** Production report = which of A/B/C/D/E are physically visible after the loading screen disappears.
