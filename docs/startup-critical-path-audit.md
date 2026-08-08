# Startup Critical-Path Audit & Remediation

| Field | Value |
| --- | --- |
| Baseline | `511c0914635bfd38317c7770155e47eff32fa4dd` (#211) |
| Scope | Startup / presentation order only — no football, Trust, auth, entitlement, Stripe, or Sleeper semantics changes |
| Date | 2026-08-08 |

---

## Production BEFORE (returning authenticated, Render Starter awake)

From production `DYNASTYGM_STARTUP` logs (iPhone ~8 s perceived):

| Milestone | Elapsed |
| --- | ---: |
| Session restored | ~3016 ms |
| Profile loaded | ~3017 ms |
| Entitlements loaded | ~3018 ms |
| League restored | ~3019 ms |
| Loading dismissed | ~6514 ms |

Two application-owned windows:

1. **~0 → ~3.0 s** — shell mount, CSS, auth bridge (pending/stops/reruns), profile, entitlement, league resume/reruns. Milestones cluster because they complete on the final restore run after prior reruns consumed most of the wall clock.
2. **~3.0 → ~6.5 s** — work still on the critical path **after** `league_restored` and **before** `loading_dismissed`.

---

## Instrumented gap: league_restored → loading_dismissed

| Operation | Required for first useful chrome? | Action |
| --- | --- | --- |
| `resolve_active_league_context` / roster id | Yes | Keep |
| `ensure_players` / public frame | Yes (league selected) | Keep; already deferred when no league |
| Sidebar identity widgets | Mostly | Keep username/league |
| Sidebar scoring override forest + news | No | **Deferred while `startup.active`** |
| Duplicate `get_user_roster_id` in account panel | No | **Reuse `active_league_context`** |
| Prepared valued+ranked frame | Yes for Dashboard | Keep |
| Shell chrome via `cached_team_direction_summary` → intelligence | **No** | **Removed from chrome path** |
| Shell chrome via `cached_league_summary` + ranks | Yes (strategy/ranks) | Keep (lightweight) |
| Topbar + mobile nav | Yes | Keep |
| Live Draft discovery | No | Already after dismiss |
| Dashboard / Decision Memory / GM Targets / news | After dismiss | Unchanged order |

### Exact cause of ~3.5 s post-league gap (proven by code path)

Dominant avoidable cost: `_build_shell_chrome_bundle` + `cached_league_shell_context` called **`cached_team_direction_summary`**, which pulls **`cached_league_core_context` → `cached_league_intelligence_frame`** (transactions/injury/manager refine) before loading could dismiss — contradicting the shell docstring.

Secondary costs in the same window: cold `ensure_players`, prepared valued+ranked frame, heavy sidebar ForwardMsg (override selectboxes + news).

---

## Exact cause of first ~3 seconds

Not a single Supabase query. Wall clock is dominated by:

1. Startup shell + triple CSS inject on each restore rerun
2. Auth storage bridge pending (`st.stop` bounded) + restore → explicit `st.rerun()`
3. Profile (4 s timeout) + entitlement on the post-restore run
4. League auto-resume → another explicit `st.rerun()` when needed

`session_restored` / `profile_loaded` / `entitlements_loaded` / `league_restored` appearing within ~3 ms of each other means they finish on the **same final run**; the preceding reruns are what consumed ~3 s.

---

## Minimum viable startup state (loading may dismiss)

- Branded shell / hero
- Auth state (or degraded guest after hang bound)
- Entitlement (fail-closed)
- Selected league identity + roster id when authenticated
- Route + executive topbar / mobile nav
- Lightweight shell strategy/ranks from **league summary** (not intelligence)

Loading means: “unsafe to use.” It does **not** mean every Dashboard enrichment finished.

---

## Changes shipped

1. `cached_league_shell_context` uses `cached_league_summary` only (no direction/intelligence).
2. `_build_shell_chrome_bundle` uses shell context once; never calls `cached_team_direction_summary`.
3. While `startup.active`, skip sidebar scoring-override expander + Data/News tools.
4. Account panel reuses roster id from `active_league_context`.
5. New `DYNASTYGM_STARTUP` milestones: `players_ready`, `prepared_frame_ready`, `shell_chrome_ready`, `workspace_chrome_ready`.
6. Architectural tests in `tests/test_startup_critical_path_contracts.py`.

---

## How to read the new waterfall

```text
DYNASTYGM_STARTUP ... league_restored
DYNASTYGM_STARTUP ... players_ready
DYNASTYGM_STARTUP ... prepared_frame_ready
DYNASTYGM_STARTUP ... shell_chrome_ready
DYNASTYGM_STARTUP ... workspace_chrome_ready
DYNASTYGM_STARTUP ... loading_dismissed / first_usable_paint
```

Deltas between these labels account for the post-league gap. Re-check production after deploy.

---

## Verdict

**KEEP STREAMLIT — REMAINING BOTTLENECK: auth restore reruns + player/prepared-frame work before Game Plan**

Intelligence-on-chrome was the incorrect ~3.5 s owner. After this PR, re-measure production `loading_dismissed`. If returning authenticated users still exceed ~3 s to usable Dashboard, next targets are auth rerun consolidation (carefully) and Game Plan presentation from memoized briefing — still not migration.
