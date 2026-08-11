# P0 blank Dashboard — GM orb CSS collapse (#244)

## Verdict

**FIXED** — unscoped GM-orb `:has()` collapsed the root Streamlit main content
block into the fixed 44px orb.

## Offender

| Field | Value |
|---|---|
| File | `modules/mobile_interaction_overlay_styles.py` |
| Selector (broken) | `div[data-testid="stVerticalBlock"]:has(.mobile-gm-floating-trigger-marker)` |
| Why | Descendant `:has()` matches **every ancestor** vertical block that contains the orb marker, including the root main content `stVerticalBlock` |
| Effect | `position:fixed; width/height:44px; overflow:hidden` on the root block — page becomes dark background + tiny GM control |
| Load order | Concatenated **last** in `APP_CSS`, so it overrides earlier correctly-scoped GM rules |

## Why #243 canaries were invisible

A–E were native `st.write` / `st.button` under the same root vertical block as the GM orb. Safe-render could force `height:auto` / `overflow:visible` but did **not** clear `position:fixed` + `width:44px`, so canaries were crushed into the corner orb box (and button-child rules zeroed button labels under the same unscoped ancestor match).

## Fix

Scope every GM orb / sheet block rule to direct-child form:

`div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-floating-trigger-marker)`

Same for `.mobile-gm-sheet-marker`. Orb chrome behavior preserved; root main content no longer matches.

## Isolation artifacts

- `FGL_P0_NATIVE_RENDER=1` early bypass in `app.py` / `modules/p0_native_render_bypass.py`
- `scripts/prove_gm_orb_css_collapse_244.py` — broken vs scoped CSS DOM proof
- `scripts/validate_dashboard_visibility_244.py` — harness + full APP_CSS + GM orb on dashboard
- Dashboard UI harness now mounts the GM orb so CI cannot miss this class of bug

## First breaking layer

`gm_orb` / `mobile_interaction_css` — specifically the **unscoped** `:has(.mobile-gm-floating-trigger-marker)` rule inside `MOBILE_INTERACTION_OVERLAY_CSS` (loaded with APP_CSS).
