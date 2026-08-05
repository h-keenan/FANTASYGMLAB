# Rerun & render stability audit

## Scope

Engineering stability only. No football logic, rankings, valuations,
recommendation ordering, Trust, auth, Stripe, or Supabase schema changes.
No UI redesign.

Baseline: `9d0a197` (latest `main` after #123/#124). Task baseline `2c025df`
was older; this audit started from current main.

## Method

1. Static inventory via `scripts/audit_founder_beta_performance.py`
2. Site review of every `st.rerun()` against the single-rerun navigation contract
3. Controlled AppTest measurement via `scripts/measure_handoff_reruns.py`
   (`DYNASTYGM_RUNTIME_TRACE=1`, 10 samples)
4. Full pytest + Founder Beta performance budget gate

## Finding (measured)

Dashboard Quick Actions and several workspace/premium handoff buttons still used
the pre-fix pattern:

1. Streamlit widget click starts an automatic script run
2. Button body queues the route and calls `st.rerun()`
3. Destination renders on a **second** explicit rerun

Desktop sidebar / mobile GM destinations already commit in `on_click` with
**zero** explicit rerun events (`docs/single-navigation-rerun.md`).

### Quick-action harness (10 samples)

| Mode | Explicit rerun events (median) | Route correct |
| --- | ---: | --- |
| Legacy `queue` + `st.rerun()` | **1.0** | my_team |
| Fixed `on_click` + `commit` | **0.0** | my_team |

Wall times on this micro-harness are noise-scale (~6–7 ms); the meaningful
result is the eliminated second script run on every handoff click.

## Changes

| Surface | Before | After |
| --- | --- | --- |
| Dashboard Quick Actions | body `queue` + `st.rerun()` | `on_click=_commit_platform_destination` |
| Workspace / trade handoffs | body `queue` + `st.rerun()` | `on_click` commit |
| Premium lock / profile Open Premium | body `queue` + `st.rerun()` | `on_click` commit |
| Live Draft → Trade Hub | body sets page + `st.rerun()` | `on_click` commit helper |

Explicit `st.rerun()` inventory: **42 → 36** (auth, league switch, Player Detail,
and other true state transitions retained; Live Draft keeps a callback-less
fallback for isolated harnesses).

## Non-changes (audited, left alone)

- Desktop/mobile destination nav (already single-rerun)
- Notification CTAs (already `on_click` without explicit rerun)
- Auth restore / league auto-resume cascades (required)
- Player Detail / Trade Hub focus handoffs that mutate overlay state before
  destination load
- CSS inject-once (invalid under Streamlit redraw; prior measurement showed only
  ~10–13 ms server delta when removing CSS entirely)
- Unconditional session assignments such as `league_value_settings` /
  `current_page` (cheap; no measured rerun impact)

## Remaining bottlenecks

- Cold public player construction / protobuf size (budget-bound, not rerun waste)
- Authenticated Sleeper/Supabase network paths (not exercised with credentials)
- True state-transition reruns (auth, league switch, detail overlays)

## Reproduction

```bash
DYNASTYGM_RUNTIME_TRACE=1 python3 scripts/measure_handoff_reruns.py --samples 10
python3 scripts/audit_founder_beta_performance.py
python3 scripts/check_founder_beta_performance_budget.py
```
