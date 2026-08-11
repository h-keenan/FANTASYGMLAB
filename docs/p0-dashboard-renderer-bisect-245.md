# P0 Dashboard renderer bisect (#245) — isolation only, not a fix

## Production evidence (post-#244)

- Visible: A, B, C, D
- Missing: E
- Conclusion: `render_home_dashboard()` enters and emits D, then does **not** return to the caller.

## Execution map (`render_home_dashboard`)

1. C / native element / D / **D0**
2. Optional **MINIMAL** body → D9 → return
3. Early gates (startup / ESPN / no league / no roster) → D9 → return
4. Prefs + roster load
5. **D1** → Game Plan package lookup/build (can hang here)
6. **D1_PACKAGE_READY** when package path finishes
7. `dashboard_workflow.render_dashboard_workflow`:
   - **D1_BEFORE_GAME_PLAN_RENDER** → Game Plan UI → **D2**
   - **D3** → What Changed → **D4**
   - **D5** → summary/intelligence tiles → **D6**
   - **D7** → Deep Analysis → **D8**
   - remaining (orientation / league pulse)
8. milestones → **D9** → visibility probe mount → return
9. Caller **E**

## Env switches

| Env | Effect |
|---|---|
| `FGL_P0_DASHBOARD_MINIMAL=1` | Keep auth/header/routing/orb; replace body with title + success + button + D9 |
| `FGL_P0_DASHBOARD_ENABLE_THROUGH=intro\|game_plan\|what_changed\|summary\|deep_analysis\|all` | Source-level binary reintroduction gate (default `all`) |
| `FGL_P0_DASHBOARD_BISECT=0` | Silence D0–D9 text markers |

## Audit notes (no silent swallow on workflow failure)

- No `st.stop` / `st.rerun` inside `render_home_dashboard`
- Workflow exception path now `st.exception(...)` + visible bisect marker (was silent `except Exception`)
- Probe mount wrapped in timed boundary after D9
- `st.container(key="dashboard_workflow")` + `.dashboard-workflow-shell` still present (not removed — bisect only)

## How to read production results

| Last visible marker | Meaning |
|---|---|
| D0 only (+ minimal success) | MINIMAL mode path / outcome A vs B |
| D1, not D1_PACKAGE_READY | Hang/fail inside Game Plan package build/lookup |
| D1_PACKAGE_READY, not D2 | Hang inside Game Plan UI render |
| D2–D3, not D4 | What Changed |
| D5, not D6 | Summary tiles |
| D7, not D8 | Deep Analysis |
| D9, not E | Probe / post-return caller path |
| E | Renderer returned |

**Do not treat pytest/harness as FIXED.** Founder must report which Di is last visible and whether MINIMAL mode shows success + E.
