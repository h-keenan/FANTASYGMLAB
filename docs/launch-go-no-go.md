# Launch Go / No-Go (#227)

Baseline: main after #226 (`e4454eb`). Audit PR: #227.

**Overall verdict: CONDITIONAL GO**

Code-side launch blockers found in this pass were fixed (P1). Remaining blockers are **Ops / production configuration** (Stripe live readiness, Supabase migrations for optional experiments, GitHub Actions billing) — not application crashes or data-leak defects reproducible in repository validation.

**Rollback:** `git revert` the #227 merge commit on `main`, or reset to `e4454eb` before #227. Scope is presentation/state/analytics/docs/tests only.

---

## Surface status

| Area | Status | Notes |
| --- | --- | --- |
| Guest journey | PASS | Value before signup; soft prompts continuity-only |
| Free account journey | PASS | Save/resume contracts intact |
| Guest → account continuity | PASS | Resume + account-default-wins (#224) |
| Returning auth | PASS WITH DOCUMENTED DEBT | Depends on Supabase secrets in deploy |
| Account isolation | PASS | Logout clears guest + Premium intent (#227) |
| League isolation | PASS | League-switch clearing + FAAB/role prefixes |
| Dashboard | PASS | Game Plan Free path; Pulse lock after value |
| My Team | PASS | Core free; Deep Analysis Premium |
| Trade Hub | PASS | Free ≤2; Premium board |
| Waivers | PASS | FAAB sort guarded when score column missing (#227) |
| League Overview | PASS | Core |
| PQV | PASS | No default Premium banner |
| Live Draft | PASS | CONDITIONAL; active-draft only |
| Premium gating | PASS | Canonical Upgrade CTA; experiments not included-now |
| Guest → Premium intent | PASS | Auth first; intent preserved |
| Stripe checkout handoff | PASS | Explicit CTA only; no auto-session after auth |
| Checkout success/cancel | PASS | Memo clear on success; cancel analytics normalized |
| Entitlement refresh | PASS | Memo cleared on billing success |
| Provider failures | PASS WITH DOCUMENTED DEBT | Fail-soft patterns; not every provider mock in this PR |
| Empty states | PASS WITH DOCUMENTED DEBT | Major routes covered by existing UI contracts |
| Cache serialization | PASS | TradeTrustContext + #221/#222 suites |
| Game Plan fingerprint | PASS | Existing hardening tests |
| After-READY recomputation | PASS WITH DOCUMENTED DEBT | Contracts in interaction/cache suites; not re-instrumented end-to-end here |
| Startup | PASS | Cold AppTest ~535 ms server; process-cold football still expected once |
| Warm navigation | PASS | Warm AppTest ~57 ms; fixture Dashboard ~101 ms |
| Header | PASS WITH DOCUMENTED DEBT | Geometry contracts; no screenshot pass this PR |
| Desktop UI | PASS WITH DOCUMENTED DEBT | Deterministic AppTest/protobuf only |
| Mobile UI | PASS WITH DOCUMENTED DEBT | CI mobile-ui billing-skipped; no local screenshots |
| Analytics | PASS | Alias normalize on write (#227); PII + Stripe id blocks |
| Privacy/security basics | PASS | No tokens in analytics allowlist; logout isolation |
| Experimental defaults | PASS | Kill switches OFF; archived never in nav |
| Archived routes | PASS | Dead Startup/ESPN CTAs removed (#227); Player Detail → PQV |
| Production configuration | BLOCKED (Ops) | Live Stripe / webhook / secrets checklist remains |

---

## Findings closed in #227

| ID | Severity | Fix |
| --- | --- | --- |
| LQA-1 | P1 | Startup/ESPN quick actions → CORE destinations only |
| LQA-2 | P1 | `track_premium_event` normalizes aliases before `track_event` |
| LQA-3 | P1 | Logout + account-bound keys clear Premium checkout intent |
| LQA-4 | P1 | Waivers FAAB sort guards missing `score_field` column |
| LQA-5 | P1 | Block Stripe-shaped analytics prop keys |

## Remaining P0

None in application code.

## Remaining P1 (Ops / infra)

1. Stripe Founder Beta live/test Ops activation (`docs/founder-beta-ops-activation.md`) if charging real Founders.  
2. GitHub Actions Delivery Validation / mobile-ui billing skip — cannot treat CI green as launch gate.  
3. Optional experiment Supabase migrations only if Ops enables DM/GM Targets.

## P2 post-launch debt

- Stale narrative in older experimental ROI audit body vs #226 registry.  
- Legacy `news` / `player_detail` route bodies retained behind ARCHIVED gate.  
- Cancel checkout leaves intent until logout (resume-friendly; documented).  
- Deeper provider-fault AppTest matrix beyond current contracts.  
- Visual screenshot harness when CI/browser available.

---

## Measured budgets (local)

| Metric | Value |
| --- | --- |
| Cold protobuf | 518,988 |
| Warm protobuf | 474,705 |
| Cold server ms | ~535 |
| Warm server ms | ~57 |
| Explicit reruns | 42 |
| APP_CSS chars | 422,111 |
| Full pytest | run in PR validation |

---

## Exact next step

**PR #228 — PRODUCTION CONFIGURATION + LAUNCH CHECKLIST**  
Ops secrets, Stripe webhook/host, Render env confirmation, and a human production smoke of guest → Free → Premium checkout in the deploy environment.
