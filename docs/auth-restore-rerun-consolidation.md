# Auth restore rerun consolidation (#214)

## Problem

Production returning-authenticated startups showed repeated:

- Session restored (~1.5s, ~1.8s, ~2.0s, then ~3.9s)
- Profile loaded / Entitlements loaded twice
- League restored only on the late clustered run

A later warm pass completed shell + workspace in ~151 ms. Football work was not
the irreducible cost — the auth / browser-storage / Streamlit rerun cascade was.

## Old auth restore state machine

```text
Run N:   mount storage component → STORAGE_PENDING → st.stop()
Run N+1: stored payload → apply auth → queue durable save → st.rerun()
Run N+2: command=save → profile fetch → entitlement → league resume → st.rerun()
Run N+3: hasSession skip-read → profile cache → entitlement recompute → shell → dismiss
(+ optional component status remounts)
```

Conceptual phases revisited on every remount:

```text
AUTH_STORAGE_PENDING
  → AUTH_RESTORED → DURABLE_SAVE_PENDING
  → PROFILE_PENDING
  → ENTITLEMENT_READY
  → LEAGUE_RESTORE_PENDING
  → PAGE_BUILDING
  → INTERACTIVE
```

`session_restored` was logged unconditionally after every bridge render, so
pending stops and save remounts inflated the milestone waterfall.

## Root causes of each pre-ready rerun

| Run | Why it started | Cost |
| --- | --- | --- |
| Pending stop | Browser component has no value yet — **required** | Wait for storage |
| Post-restore `st.rerun()` | Separate durable save from apply | Full main() rebuild before profile |
| Post-league `st.rerun()` | Defensive widget rebuild after resume | Full main() after league already set |
| Save/status remounts | Component `setTriggerValue` | Extra Session restored logs + entitlement recompute |

## New auth restore state machine

```text
UNINITIALIZED
  → STORAGE_PENDING          (at most one effective storage read request)
  → AUTH_RESOLVED            (guest empty, restored, identical, or already signed-in)
  → PROFILE_RESOLVED
  → ENTITLEMENT_RESOLVED
  → LEAGUE_RESTORED
  → READY / shell_commit / loading_dismissed
  → optional post-usable durable save rerun (warm, after first paint)
```

Phases advance monotonically. Presentation reruns do not return to
`STORAGE_PENDING` once auth is resolved.

## Identical auth payload behavior

Fingerprint = `sha256(user_id|access|refresh|expires_at)` (not logged).

If the same fingerprint is already applied for the current user:

- do not clear workspace
- do not refetch profile
- do not re-queue durable save
- do not treat the event as a new `restored=True` transition

## Account-switch behavior

Different `user_id` still triggers full #145 hygiene:

- clear account-bound transient state
- clear selected league / username / entitlement memo
- clear profile/auto-resume guards
- clear restore lifecycle memo

## Expired token behavior

Failed refresh:

- queues durable auth clear
- clears restore lifecycle memo
- does not reuse stale entitlement/profile memo for speed

## Profile / entitlement ownership

| Concern | Owner | Startup rule |
| --- | --- | --- |
| Profile network | `_refresh_supabase_account_profile` | ≤1 fetch / user / 60s; counted |
| Entitlement | `refresh_current_user_entitlement` | memoized per user for identical restore runs; fail-closed via `premium.effective_entitlement` |
| League resume | `_maybe_auto_resume_supabase_league` | runs in the same script run after auth+profile; no forced rerun |

Auth identity is the dependency for entitlement, saved league, and profile.
Profile display is not a prerequisite for league restore once identity+token are
valid — league restore still runs after profile attempt in serial order for
safety (no threads).

## Loading dismissal contract

Dismiss only when:

1. Auth identity settled (restored, identical, guest, or hang-timeout guest)
2. Entitlement resolved (fail-closed free unless profile proves premium)
3. League restore attempted (selected or none)
4. Minimum shell chrome committed (`shell_commit` / `shell_chrome_ready`)

Do **not** wait for:

- durable localStorage save completion
- secondary route hydration
- full League Intelligence
- repeated identical storage remounts

## Shell gap findings (prepared_frame → shell_chrome)

Instrumented:

- `startup_draft_context_lookup`
- `workspace_shell_context_generation` (existing)
- `shell_chrome_bundle_build`

Cold first-pass ~1.1s in this region is predominantly shell league summary /
startup draft context after football frame — not auth. Auth consolidation must
land first; remaining owner is shell summary construction, not restore loops.

## Multi-tab

Durable browser auth (`localStorage`) may be shared across tabs. Streamlit
`session_state` is per tab. This PR does not add cross-tab sync. Each tab runs
its own restore lifecycle; identical payload rules prevent unsafe wipe only
within one Streamlit session.

## Before / after (structural)

| Metric | Before | After (target) |
| --- | --- | --- |
| Script runs before auth_ready | 3–5 | 1–2 (pending stop + settle) |
| Session restored milestones | many | ≤1 / startup session |
| Browser storage requests | remount-driven | ≤1 effective read / session |
| Profile fetches | 1 net, many calls | ≤1 fetch |
| Entitlement resolves | every completed run | memoized while identity stable |
| Auth `st.rerun` before profile | yes | removed |
| League `st.rerun` | yes | removed |
| Durable save rerun | before first-useful | after `loading_dismissed` |

## Remaining Streamlit limits

- One required `st.stop()` while storage is pending
- One optional warm post-usable save rerun for token persistence
- CSS / ForwardMsg serialization still remounts on every run
- Shell summary cold cost remains after auth is fixed

## Verdict direction

KEEP STREAMLIT — AUTH STARTUP FIXED when production medians show
`loading_dismissed` under ~3s for returning authenticated sessions on a warm
Render Starter service. If auth runs collapse but shell gap remains ~1s+, next
bottleneck owner is shell league summary / draft context — not auth.
