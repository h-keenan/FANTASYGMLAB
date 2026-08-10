# Startup Latency Cleanup + Production Load Validation (#234)

| Field | Value |
| --- | --- |
| Baseline | `621169c59b125cd3c4549a88912a45cc52a124b3` (#233) |
| Rollback | same as #233 merge parent / `#233` revert floor: `2c699c5d55e2a3de7b6afb96c57fc6606e5cd453` |
| Scope | Targeted provider coalesce, startup profile column trim, load harness, 45s fail-soft split — **no** football / fingerprint / TTL changes |

## A. Production package-MISS verification

Agents cannot set Render env vars. After this PR merges to `main`:

1. Set `DYNASTYGM_STARTUP=1` on the Streamlit Render service (temporary).
2. Confirm deploy SHA matches `main`.
3. Returning authenticated user, process-cold worker.
4. Capture complete `DYNASTYGM_STARTUP` log for one session.
5. Prove stage order:

```text
package MISS
→ game_plan_shared_context start/complete
→ trade inventory
→ briefing assembly
→ compose
→ package store
→ Game Plan ready
→ first useful
→ Dashboard complete / interactive stable
```

6. If the path cliffs before Game Plan ready → **P0**, stop latency claims.
7. Unset `DYNASTYGM_STARTUP` after capture.

Local proof (not production):

```bash
python scripts/verify_package_miss_path.py
```

## B. provider_leagues duplication

### Before (#233 production trace)

Three **post-READY** `provider_leagues` timings ≈ 195.6 + 166.4 + 66.0 ms ≈ **428 ms**.

Category `provider_leagues` collapses distinct Sleeper endpoints (`sleeper_league`, `sleeper_league_drafts`, `sleeper_draft`, `sleeper_draft_picks`, `sleeper_traded_picks`, `sleeper_matchups`).

### Callers (golden Dashboard package-MISS)

| Endpoint | Caller | When | Identical? |
| --- | --- | --- | --- |
| `sleeper_league` | `detect_league_value_settings` / maturity / draft picks | pre-dismiss + package path | Same league id — **lru coalesced** |
| `sleeper_league_drafts` | rookie draft context + Live Draft discovery | post-dismiss | Same — **lru coalesced** |
| `sleeper_draft` ×N | `_detect_*_draft_candidate` | package path | Was **duplicate fan-out** when stubs already had rounds/status |
| `sleeper_traded_picks` | `list_draft_pick_assets` | package path | Distinct — required |
| `sleeper_draft_picks` | rookie context winner | package path | Distinct when draft present |

### Fixes

1. **Stub-first draft candidates** — use league-drafts list metadata when rounds+status present; no N× `get_draft`.
2. **Move Live Draft discovery after Game Plan** on Dashboard — discovery only updates next topbar remount; must not own critical-path provider time before package MISS completes.
3. **Endpoint labels** on `provider_timing` for duplicate diagnosis (`endpoint` field + counters).
4. Regression budget: `MAX_PROVIDER_LEAGUES_CALLS_GOLDEN_STARTUP = 4` network league-family calls on the golden path (identical endpoints must be lru hits).

**Correctness:** no TTL inflation; football fingerprints unchanged.

## C. Profile fetch (~880 ms)

Breakdown (architecture):

| Slice | Owner |
| --- | --- |
| Request/network | Dominant on Render→Supabase (~hundreds of ms) |
| Query | Single `profiles` row by `user_id` |
| Parse/apply | Negligible |
| Entitlement | In-memory from profile — **no second network call** |
| Duplicates | Guarded by 60s session cache + `record_profile_fetch` |

**Optimization made:** startup fetch uses entitlement columns only (`include_billing=False`). Stripe billing columns load only on `force=True` (billing success / Premium).

**Not done (unsafe):** deferring profile past first useful — entitlement gates graduated features; must not invent client entitlement authority or trust stale Premium for billing.

**Auth / entitlement impact:** none — server profile row remains authority; billing columns still available when forced.

## D. Critical path (architecture-instrumented; not live production percentiles)

| Scenario | loading dismissed | first useful | Game Plan ready | Dashboard complete | interactive stable |
| --- | --- | --- | --- | --- | --- |
| Process cold / returning auth | auth+profile+entitlement+league+identity shell | post-dismiss football start | package HIT or MISS path | after compose/enrich | summary after dashboard |
| Process warm / session cold | auth restore dominates | shell then hydrate | process memo helps | shorter | shorter |
| Session warm | presentation | often package HIT | HIT | fast | fast |
| Package HIT | — | briefing from package | immediate | fast | fast |
| Package MISS | — | shared context→trade→brief→compose→store | after store | after enrich | after complete |

Stage ownership: auth storage handshake → profile → entitlement → league restore → providers → players → prepared frame → league context → trade inventory → briefing → compose → presentation/browser gap.

## E–F. Load / perceived-load harness

```bash
python scripts/test_realistic_session_load.py --concurrency 1,3,5,10,20
python scripts/test_perceived_load.py --concurrency 1,3,5,10
```

### LOCAL results (this agent, synthetic process-cache sessions)

| Workload | c | builders | fail | timeout | deadlock | p50 | p95 | max | wait p95 | leak |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| LOAD A same | 1 | 1 | 0 | 0 | 0 | ~8–156* | — | — | — | no |
| LOAD A same | 3–20 | **1** | 0 | 0 | 0 | ~8.1–8.5 | ~8.3–9.2 | ~8.3–9.2 | ≤1.2 | no |
| LOAD B distinct | 1–20 | **=c** | 0 | 0 | 0 | ~8.1–8.5 | ~8.3–8.6 | ~8.8 | ≤0.6 | no |

\*First cold harness sample can include interpreter warmup; steady samples are ~8 ms at `delay_ms=8`.

- **LOAD A** same signature stampede → one expensive build/signature, waiters complete, no deadlock/corruption/leak
- **LOAD B** distinct signatures → per-key parallelism, no global lock
- RSS ~122 MB stable; CPU not separately sampled beyond wall times
- Browser paint / websocket / CLS: **manual founder capture** (documented in harness JSON) — not fabricated

Environment: **LOCAL** (cloud agent VM). Not a loaded Render worker.

## G. 45s single-flight safety net

| Knob | Value | Role |
| --- | --- | --- |
| `SINGLEFLIGHT_WAIT_TIMEOUT_S` | **45s** | Hard abandoned-owner ceiling (unchanged constant) |
| `SINGLEFLIGHT_USER_VISIBLE_WAIT_S` | **12s** | Waiter acquire timeout (fail-soft / fallback) |
| `USER_VISIBLE_FAILSOFT_S` | **12s** | User-visible fail-soft marker |

Recommendation: keep hard ceiling at 45s; users must never sit on a 45s freeze — waiters surface at ~12s.

## H. No regressions

Preserved: football truth, fingerprint v2, package invalidation, trade trust serialization, guest→Free, Premium intent, graduated features, Decision Memory / GM Targets isolation, Share privacy, Player Explorer, Live Draft behavior, header/GM fixes, explicit rerun budget. No speculative TTL inflation. No background `st.session_state` mutation.
