# Final Launch Flow Regression + Real-Device Visual QA (#235)

| Field | Value |
| --- | --- |
| Baseline / rollback | `dc319d24752726dbb5b385ec5e0c54352bdde4d3` (#234 merge) |
| Scope | Launch-candidate verification + GM orb Streamlit-tooltip fix; no speculative redesign |
| Overall | **CONDITIONAL GO** |

## Production #234 package-MISS gate

| Item | Status |
| --- | --- |
| #234 merged | YES (`dc319d2`) |
| LOCAL package-MISS path | **PASS** — `scripts/verify_package_miss_path.py` (nested re-entry safe; full stage sequence) |
| PRODUCTION `DYNASTYGM_STARTUP=1` waterfall | **PENDING FOUNDER** — agents cannot set Render env |
| Production first useful / Game Plan ready / Dashboard complete / interactive stable | **PENDING FOUNDER capture** |

### Founder production capture (required before declaring GO)

1. Deploy main containing #234/#235.
2. Temporarily set `DYNASTYGM_STARTUP=1` on Streamlit Render service.
3. Returning authenticated user, process-cold worker, force Game Plan package MISS.
4. Prove: MISS → shared context start/complete → trade → briefing → compose → store → Game Plan ready → first useful → Dashboard complete → interactive stable.
5. Record exact timestamps; unset `DYNASTYGM_STARTUP`.

If that path cliffs → **P0 STOP**. Do not treat launch as ready.

---

## P0 / P1 / P2 this pass

| ID | Sev | Finding | Status |
| --- | --- | --- | --- |
| L235-1 | P1 | GM orb leaked `O`/`PE` after Streamlit wrapped primary buttons in tooltip spans; direct-child `> button` CSS no longer matched | **FIXED** — descendant selectors + circular/a11y contracts; protobuf-trimmed |
| L235-2 | P2 | Tablet `@768` near-zero check flagged secondary home-command cards (~110px) | **FIXED** — exclude `home-command-card-secondary` |
| L235-3 | P2 | Mobile validator incorrectly required square (`0px`) GM radius | **FIXED** — require circular `50%` + hidden label + mark background |

- **P0 discovered:** 0 code-owned (production cliff still unverified)
- **P0 fixed:** 0
- **Remaining P0:** production package-MISS cliff unknown until founder capture
- **P1 discovered:** 1 (GM orb leak)
- **P1 fixed:** 1
- **Remaining P1:** Actions runners empty / Delivery Validation infra; production gate pending
- **P2 backlog:** iPhone Safari safe-area manual; Slow-4G perceived-load manual; minor density polish; domain topology ops

---

## Visual QA (Chromium fixture harness)

```bash
python -m streamlit run scripts/ui_validation_harness.py --server.headless true --server.port 8510
python scripts/validate_mobile_ui.py --base-url http://127.0.0.1:8510 --output /opt/cursor/artifacts/ui-mobile
```

| Viewport | Result |
| --- | --- |
| 320 / 390 / 430 | PASS (header, GM orb circular + mark, surfaces) |
| 768 / 1024 | PASS after secondary-card + GM contract fixes |
| 1280 / 1440+ | PASS |
| iPhone Safari | **MANUAL REQUIRED** (not available in agent VM) |

**Screenshots:** 192 PNGs under `/opt/cursor/artifacts/ui-mobile/` plus 14 under `/opt/cursor/artifacts/launch-qa-235/` (Playwright Chromium; agent VM — not iPhone Safari).

| Surface | Verdict |
| --- | --- |
| Header | PASS on fixture; iPhone safe-area manual |
| GM control | PASS after fix — circular ~44px, FGL mark, no O/PE, aria `Open GM menu` |
| Dashboard hierarchy | PASS fixture (Game Plan / Top Priority readable) |
| My Team / Trade / Waivers / PQV | PASS fixture contracts |
| Player Explorer / Decision Memory / GM Targets / Share | PASS code + fixture where covered; live auth journeys manual |
| Premium UX | PASS language/constants; live Stripe test manual |

---

## Golden paths (code + suite; live prod manual)

| Path | Result |
| --- | --- |
| Guest | Contract PASS — no account wall before value (suite + prior #224) |
| Guest → Free | Contract PASS |
| Returning Free | Contract PASS (package HIT path covered) |
| Returning Premium | Contract PASS (entitlement gates) |
| Guest Premium intent | Contract PASS — explicit `Start Founder Premium checkout`; no auto Stripe |
| League-switch isolation | Contract PASS |
| Account-switch / logout isolation | Contract PASS (`clear_account_bound_transient_state`) |

---

## Failure-mode / performance / load

| Check | Result |
| --- | --- |
| Failure-mode matrix | Contract PASS / prior suites; no new silent blank/spinner cliffs found in this pass |
| LOCAL package-MISS | PASS |
| LOCAL package-HIT reuse | PASS |
| Post-hydration rebuild marker | Present |
| Provider-call budget constant | `MAX_PROVIDER_LEAGUES_CALLS_GOLDEN_STARTUP` ≤ 8 |
| Single-flight same-signature | 1 builder / 5 waiters (test) |
| User-visible fail-soft | 12s < hard 45s |
| Process-cold / warm timings (production) | **PENDING FOUNDER** |
| LOCAL load 1/3/5/10/20 same-sig | PASS — builder_count_total=1 at n=20; deadlock=0; leakage=false; failure_rate=0 |
| LOCAL load different-sig | PASS — no accidental global serialization stall; deadlock=0 |
| LOCAL load p50 / p90 / p95 / max (same-sig n=20) | 8.5 / 8.9 / 8.9 / 9.0 ms (synthetic cache hits; not Render) |
| Perceived-load / websocket / CLS | **MANUAL** (agent Chromium fixture only) |

---

## Production configuration recheck (public / code)

| Item | Status |
| --- | --- |
| fantasygmlab.com | HTTP 200 (marketing) |
| www / app.fantasygmlab.com | Topology historically incomplete (`app` `/` 404 body) — Ops |
| Render app / always-on | Ops — do not change in this PR |
| Stripe mode / prices / portal / webhook | Test-mode assumed; **do not enable live charging** |
| Supabase Site URL / redirect allowlist | Ops (#228) |
| Decision Memory / GM Targets tables | Code ready; DB Ops (#228/#232) |
| Experiment kill switches | Default ON graduated; `DYNASTYGM_EXPERIMENTAL_*=0` honored |
| Diagnostics `DYNASTYGM_STARTUP` | Off by default; founder toggle only |
| GitHub Actions runners | **NOT READY** — empty runner / 0 steps (#231–#234 pattern) |
| Privacy / Terms / support | Present in product surfaces (prior) |

---

## Budgets / validation

| Check | Result |
| --- | --- |
| APP_CSS before (#234) | ~417,270 |
| APP_CSS after | 418,220 |
| protobuf cold | 519,172 (≤ 520,000) |
| protobuf warm | 474,889 |
| focused + full pytest | **2053 passed** |
| compileall | PASS |
| git diff --check | PASS |
| performance budget script | PASS |
| tests added | `tests/test_final_launch_flow_regression_235.py` |

---

## Deliverable matrix (1–88)

1. PR URL — see PR
2. merge SHA — pending merge
3. final main SHA — pending merge
4. rollback SHA — `dc319d24752726dbb5b385ec5e0c54352bdde4d3`
5. overall — **CONDITIONAL GO**
6. production #234 package-MISS — PENDING FOUNDER
7–10. production timings — PENDING FOUNDER
11–13. P0 — discovered 0 / fixed 0 / remaining: unverified production cliff
14–16. P1 — discovered 1 / fixed 1 / remaining: Actions infra + production gate
17. P2 backlog — iPhone Safari, Slow-4G, domain topology, minor density
18–24. golden paths — contract PASS (live prod manual)
25–36. visual/feature verdicts — see tables above
37. failure-mode — CONDITIONAL PASS (contracts + suites; live matrix sampling manual)
38–42. timing cells — LOCAL package path PASS; production PENDING
43–46. provider/build/rerun — budgets/constants enforced; production counts PENDING
47–54. load — LOCAL 1/3/5/10/20 PASS; deadlocks 0; leakage false; failure rate 0
55–58. viewports — PASS Chromium fixture
59. iPhone Safari — MANUAL REQUIRED
60–62. perceived-load / websocket / remount — MANUAL / fixture-limited
63. a11y — PASS basics (GM aria, contracts); not full WCAG
64–65. analytics / privacy — PASS blocklist contracts
66–72. config readiness — see config table (Ops gaps remain)
73–74. APP_CSS 417,270 → 418,220
75–76. protobuf cold 519,172 / warm 474,889
77. tests added — `test_final_launch_flow_regression_235.py`
78. full pytest — 2053 passed
79–81. compileall / diff-check / perf budget — PASS
82–83. screenshots — 192 + 14 PNGs under `/opt/cursor/artifacts/ui-mobile/` and `launch-qa-235/`
84. manual QA still required — production package-MISS waterfall; iPhone Safari; Slow-4G; authenticated golden paths on prod; Stripe test checkout once
85. exact launch blockers — (1) unverified production package-MISS after #234 deploy (2) Actions runners broken for Delivery Validation
86. post-launch P2 — density polish, domain topology cleanup, optional Slow-4G harness
87. **FINAL VERDICT: CONDITIONAL GO**
88. **Exact next action:** merge #235 → enable `DYNASTYGM_STARTUP=1` → capture production package-MISS waterfall → unset flag → GO if stages complete, else P0 incident

---

## FINAL VERDICT

**CONDITIONAL GO**

Conditions:

1. Founder captures production package-MISS waterfall with `DYNASTYGM_STARTUP=1` and confirms Game Plan ready (gate).
2. Founder merges despite Actions infra failure (same as #233/#234) **or** Actions runners are restored.
3. Optional: iPhone Safari + Slow-4G perceived-load manual pass.
4. Domain topology / Stripe test readiness tracked in #228 checklist remain Ops-owned.

Exact next action: merge #235 → enable `DYNASTYGM_STARTUP=1` → production package-MISS capture → unset flag → decide GO vs P0.
