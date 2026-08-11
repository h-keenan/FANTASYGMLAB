# P0 Dashboard rendering closed (#246)

## Verdict

**P0 DASHBOARD RENDERING CLOSED** after production #245 proved A–E + full Dashboard
paint, preserving the #244 GM-orb `:has()` scope fix, and removing temporary
#243–#245 diagnostic UI.

## #244 selector retained

`div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .mobile-gm-floating-trigger-marker)`

(and the matching sheet-marker direct-child form) in
`modules/mobile_interaction_overlay_styles.py`, concatenated last in `APP_CSS`.

## Removed (investigation-only)

- `modules/p0_render_canary.py`, `p0_dashboard_bisect.py`, `p0_native_render_bypass.py`
- Visible `FGL_P0_*` / `DASHBOARD_CANARY_*` Streamlit UI
- `FGL_P0_DASHBOARD_MINIMAL` / `ENABLE_THROUGH` / native-render / safe-render CSS
- Soft-deadline caption left on the ready Dashboard

## Retained under `DYNASTYGM_STARTUP=1`

- Python startup / Dashboard milestones (`log_startup_milestone`,
  `log_python_render_milestone`)
- Parent-DOM visibility probe + overlay watchdog (no visible canary text)
- Server-only visibility token (no `st.text`)

## Verification

- `tests/test_gm_orb_css_collapse_244.py` — full `APP_CSS` scoped-selector regression
- `scripts/validate_dashboard_clean_246.py` — 1280 / 430 / 390 / 320 clean paint
- `scripts/prove_gm_orb_css_collapse_244.py` — broken vs scoped CSS proof
