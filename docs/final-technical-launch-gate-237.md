# Final Technical Launch Gate (#237)

| Field | Value |
| --- | --- |
| Baseline / rollback | `3890b69f871d302641728f05796068037c80bc75` (#236 merge) |
| #235 merge | `a1431b0cc83a875bbaba36c57dac886f4f116a51` |
| #236 merge | `3890b69f871d302641728f05796068037c80bc75` |
| Scope | Production package-MISS proof protocol + startup summary ownership + protobuf headroom |
| Not in scope | Features, experiments, redesign, TTL/fingerprint changes |

## A. Baseline on main (pre-#237 edits)

| Metric | Value |
| --- | --- |
| main SHA | `3890b69` |
| APP_CSS | 418,220 |
| polish | 4,115 |
| protobuf cold | **520,000** (zero headroom) |
| protobuf warm | 475,717 |
| explicit reruns | 42 |

## B. Production package-MISS gate

| Item | Status |
| --- | --- |
| Agents can set Render `DYNASTYGM_STARTUP=1` | **NO** |
| Production correlated waterfall captured this pass | **NO — PENDING FOUNDER** |
| LOCAL package-MISS path (`verify_package_miss_path.py`) | **PASS** |

### Founder capture protocol (required for GO)

1. Deploy main containing #236/#237.
2. Temporarily set `DYNASTYGM_STARTUP=1` on Streamlit Render service.
3. Returning authenticated user, process-cold worker, Dashboard, force Game Plan package MISS.
4. Capture one `startup_session_id` waterfall through Game Plan ready → Dashboard complete → interactive stable.
5. Unset `DYNASTYGM_STARTUP`.
6. If cliff after MISS → **P0 STOP**.

## C. Startup summary ownership fix

`slowest_stage` now prefers exclusive **owner** stages (`profile_fetch`, `league_restore`, `league_context`, `trade_inventory`, `briefing_assembly`, `compose`, …) and ignores tiny non-owner slices such as `auth_payload_applied` 1.4ms.

Also added:

- `package_store_ms`
- `accounted_ms`
- `unexplained_ms` (wall − exclusive accounted; no nested provider double-count)
- `slowest_stage_semantics: owner_exclusive`

## D. Protobuf headroom

| | BEFORE (#236 main) | AFTER (#237) |
| --- | --- | --- |
| cold | 520,000 | **511,897** |
| warm | 475,717 | **467,614** |
| headroom (hard 520k) | 0 | **8,103** |
| preferred ≤515k | FAIL | **PASS** |
| APP_CSS | 418,220 | **411,059** |

### Reductions (safe)

1. Removed obsolete `.home-quick-*` rules (empty shell no longer used after #236).
2. Removed dead `home-quick-action-note` mobile-workflow rule.
3. Stripped documentation CSS comments from concatenated style modules (no selector/behavior change).

Largest remaining cold contributors remain global `APP_CSS` inject + polish (Streamlit ForwardMsg floor).

## E. Experiments

**NO** experiment behavior changes. Defaults unchanged; kill switches honored.

## F. Load harness

Re-run `scripts/test_realistic_session_load.py` after changes — LOCAL only.

## G. FINAL VERDICT

**CONDITIONAL GO**

Application correctness for package-MISS remains locally proven (#233/#234 + LOCAL verify). Production waterfall with `DYNASTYGM_STARTUP=1` is still founder-owned. Protobuf headroom restored under preferred ceiling.

### Conditions

1. Founder captures production package-MISS waterfall and confirms Game Plan ready (gate).
2. Founder merge despite Actions empty-runner infra (same as #233–#236) **or** runners restored.
3. Optional: production visual glance for Deep Analysis / GM orb / header after deploy.
4. Ops: Stripe/Supabase/DNS remain external.

### Exact next action

Merge #237 → enable `DYNASTYGM_STARTUP=1` → capture production package-MISS → unset → **GO** if complete, else **P0**.
