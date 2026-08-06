# Cold Start Critical Path & First Usable Screen

P0 launch-blocker performance investigation and fixes.

| Field | Value |
| --- | --- |
| Baseline | `190f9533838a793f504de661a365e32de7ecccd2` |
| Scope | Startup orchestration only — no football, Trust, auth rules, entitlements, Stripe, Supabase schema, or Sleeper semantics changes |
| Date | 2026-08-06 |

## Launch verdict

**Application first-load: IMPROVED — READY AFTER OPS for awake service.**

The 15+ second production experience is **primarily Render cold-wake + multi-rerun auth orchestration + loading shell held until full page hydration**, not football analysis cost alone.

| Layer | Contribution to 15+ s | Action |
| --- | --- | --- |
| **Render free/sleep wake** | Often **majority** of wall time before Python starts | Operational — keep service awake or accept wake delay; quantify separately |
| **Process import** | ~1.5 s on fresh process | Deferred secondary modules remain future work; not changed wholesale here |
| **Auth bridge pending / reruns** | 3–5 full trees; could hang forever on pending | **Fixed:** hang timeout + versioned storage |
| **Loading shell until page end** | Shell blocked Trade Hub / League Intel / deep work | **Fixed:** dismiss at first usable paint |
| **Live Draft Sleeper discovery** | Network on critical path before chrome | **Fixed:** deferred after first usable |
| **Supabase profile (15 s timeout)** | Could stall startup | **Fixed:** 4 s startup timeout |
| **Health check on `/`** | Could keep spinning full app for probes | **Fixed:** `/_stcore/health` |

If production still shows ~15 s on a **sleeping** Render instance after this deploy, that remaining delay is **infrastructure cold wake**, not application critical-path work. Do not invent an application speedup for wake delay.

---

## Root causes

1. **Loading shell dismissed only after full route bodies** — `startup.complete()` ran after Dashboard / Trade Hub / League work. Users saw “Opening your workspace…” for the entire secondary hydration.
2. **Auth bridge `st.stop()` with no hang bound** — if browser storage never returned, shell stayed forever.
3. **Live Draft discovery** called Sleeper before first usable chrome.
4. **Profile REST timeout = 15 s** on the critical path.
5. **Render `healthCheckPath: /`** hit the full Streamlit app instead of `/_stcore/health`.
6. **Render sleep / cold boot** (when applicable) dominates wall clock before process start — separate from app time.

---

## First usable screen

### Signed-out
- FantasyGM Lab branding (hero / shell)
- Sign-in / create-account / guest import path
- Concise product context
- **Not blocked on:** Trade Hub, League Intelligence, news, Trust evidence, deep rankings

### Authenticated
- Executive shell + page title
- Active league identity (from session / restored context)
- Navigation
- Cached roster/player identity when available
- Lightweight workspace chrome
- Degraded caption if session/profile delayed
- **Not blocked on:** Trade Hub generation, League Intelligence, news, Trust evidence, career history, secondary recommendations

### Definition in code
Loading shell dismisses at `runtime_trace.mark("first_usable_paint")` immediately after topbar + mobile nav, **before** `if current_page == "dashboard"` and other route bodies.

---

## Critical vs deferred

### Critical (before first usable)
| Work | Status |
| --- | --- |
| Module import / session begin | Required |
| Public player snapshot / DB load | Required |
| Auth bridge (bounded) | Required; times out to guest shell |
| Profile lookup (4 s timeout) | Required for entitlement; fail-closed Free |
| Entitlement resolve | Required |
| Saved-league restore (explicit rerun when needed) | Required for identity |
| Active league identity | Required |
| Route restore + executive chrome | Required |

### Deferred (after first usable / on demand)
| Work | Status |
| --- | --- |
| Live Draft Sleeper discovery | Deferred; cached for next nav |
| Trade Hub board generation | Unchanged — after shell dismiss |
| League Intelligence / shared league context | Unchanged — after shell dismiss |
| News, dossier history, deep rankings | Unchanged — after shell dismiss |
| Deferred section gates | Existing gates retained |

Analysis **results** are unchanged; only **when** secondary work runs relative to shell dismiss.

---

## Before / after timelines (application time, awake process)

AppTest / local measurements are **not** production browser times. Approximate application-side critical path:

| Milestone | Before (structural) | After |
| --- | --- | --- |
| Loading shell exit | End of full page hydration | Immediately after chrome (`first_usable_paint`) |
| Auth pending hang | Unbounded `st.stop()` | ≤ 2 stops or ≤ 2.5 s → guest shell |
| Profile network | 15 s timeout | 4 s on startup |
| Live Draft discovery | Before chrome | After first usable |
| Streamlit health | Full `/` | `/_stcore/health` |

| Target | Status |
| --- | --- |
| Branded shell visible &lt; 1.5 s (awake) | **infrastructure-dependent** + import; shell mounts first in `main` |
| First interactive signed-out &lt; 2 s (awake) | **met** on local AppTest budgets when cache warm; production browser **unmeasured** here |
| First usable authenticated shell &lt; 3 s (awake) | **improved**; depends on auth reruns + network |
| Complete Dashboard &lt; 5 s | **missed / external-dependent** when Sleeper/Supabase slow |
| No indefinite loader | **met** (hang protection) |
| No false Free flash | **preserved** (fail-closed unchanged) |
| No stale prior-account content | **improved** (auth storage v2 + legacy migrate) |

---

## Browser / local state findings

| Finding | Resolution |
| --- | --- |
| Durable auth in `localStorage` (`dynastygm_supabase_auth`) | Versioned to `dynastygm_supabase_auth_v2`; legacy key migrated once then removed |
| Resume hooks on focus/pageshow | Retained; hang protection prevents infinite shell |
| Stale route/league | Not indiscriminately cleared; league invalidation still fails closed |

Private browsing previously felt faster because it skipped durable-auth pending/rerun cascades.

---

## Render-specific audit

| Item | Finding |
| --- | --- |
| Start command | `streamlit run app.py ...` (unchanged) |
| Health check | Changed Streamlit service to `/_stcore/health` |
| Service plan / sleep | **Not provisioned automatically.** If Free/sleeping, wake delay is unavoidable infrastructure time |
| Recommendation | Keep production web service awake for Founder Beta, or accept wake as separate SLA; measure with Render metrics |

**Render time vs app time:** Report wake separately. Application changes cannot remove process-sleep delay.

---

## Work moved off critical path

1. Loading shell held through secondary route bodies → dismiss at first usable
2. Live Draft Sleeper discovery → after first usable
3. Auth pending unbounded stop → bounded timeout
4. Profile 15 s → 4 s startup timeout
5. Health probe full app → stcore health

---

## Rerun / network / protobuf

| Metric | Change |
| --- | --- |
| Auth/league explicit reruns | Preserved (required for restore correctness) |
| Auth pending stops | Capped at 2 before proceeding |
| Startup Supabase profile timeout | 15 s → 4 s |
| Sleeper calls before first usable | Live Draft discovery removed from pre-chrome path |
| Protobuf/CSS payload | Unchanged in this PR (budget still within CI limits) |

---

## Explicit confirmation

No changes to football logic, valuations, rankings, recommendation generation/ordering, Trust, authentication **rules**, entitlement **rules**, Stripe behavior, Supabase **schema**, or Sleeper **semantics**.

Changed: startup orchestration, hang bounds, health check path, auth **storage key version**, presentation timing of shell dismiss.

---

## Rollback boundary

`190f9533838a793f504de661a365e32de7ecccd2`

---

## Remaining bottlenecks

1. Render cold wake (operational)
2. Eager import wall (~1.5 s) — future deferred-import pass with evidence
3. Auth restore still requires 1–2 explicit reruns (correctness)
4. Full Dashboard hydration still depends on Sleeper/Supabase latency
5. Production browser timings still require founder instrumentation on awake service
