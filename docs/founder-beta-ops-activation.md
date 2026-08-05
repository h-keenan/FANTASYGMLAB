# Founder Beta Operations & Production Activation

Operations activation report for FantasyGM Lab Founder Beta.

| Field | Value |
| --- | --- |
| Prompt baseline | `3065e315c7855f2546cc700e0b70d91c9247e9a3` |
| Scope | Operations / production activation — no football logic, valuations, rankings, Trust, recommendation ordering, Stripe charge mapping, Supabase schema, authentication rules, or UI redesign |
| Date | 2026-08-05 |
| Agent credentials | No Stripe, Supabase service-role, or Render API secrets in this environment |

## Launch decision

**Complete listed tasks first**

Public production is up on the expected build and guest surfaces look customer-ready, but
**Founder Beta is not cleared to accept paying customers** until every P0 Ops task below is
completed and evidenced in founder dashboards.

Live Stripe billing remains intentionally disabled. Stripe Test Mode dry-run on production
URLs was **not** completed here (no secrets / no webhook host).

## What was verified with evidence

### Public production surfaces (2026-08-05)

| Check | Result |
| --- | --- |
| `https://fantasygmlab.com/` → `https://www.fantasygmlab.com/` | HTTPS 200 |
| Streamlit health `/_stcore/health` | `ok` / 200 |
| Render app host `fantasygmlab.onrender.com` | 200 |
| App footer build | **`BUILD 3065E31 · MAIN`** (matches baseline) |
| Favicon / tab mark | Present (Streamlit/FGL) |
| Guest path | Continue as Guest works |
| Terms / Privacy / About | Load |
| Premium page (guest) | Loads; shows billing **not configured** copy |
| Multi-tab + soft refresh | Recover without visible crash |
| Stack traces / TODO / lorem in customer UI | None observed |
| Founder Beta branding | Present |
| GM Orb | Present |
| Notification Center sample alerts | Present (Founder Beta sample note expected) |
| Executive header | Present |

Probe script: `python3 scripts/founder_beta_ops_public_probe.py`

Screenshots: `/opt/cursor/artifacts/ops-activation/`

### Automated product validation (this branch)

| Check | Result |
| --- | --- |
| Focused ops / launch / Stripe / feedback contracts | covered by new + existing tests |
| `deployment_check.py` | passed (local packaging) |
| Performance budget | cold ~373 ms / warm ~65 ms / protobuf within budget |
| Trust context integrity | `valid: true` |
| Experimental route inventory | no missing/stale routes |
| Stripe checklist (local) | `Mode: missing_or_not_test` (expected — no secrets) |

### Code fix shipped in this PR (evidenced production issue)

Production guest session showed a customer-visible **Performance Report** expander. That UI is
gated by `DYNASTYGM_DEBUG_PERF`, so the Render Streamlit service currently has a debug flag
enabled (or equivalent secrets entry).

**Defense-in-depth:** on managed Render hosts, customer-unsafe debug/override tools now stay
off unless `DYNASTYGM_ALLOW_PROD_DEBUG` is explicitly set:

- `DYNASTYGM_DEBUG_PERF` (Performance Report)
- `DYNASTYGM_DEBUG_AUTH`
- `DYNASTYGM_PREMIUM_OVERRIDE`
- `DYNASTYGM_SHOW_DEV_DESTINATIONS`
- `DYNASTYGM_SHOW_EXPERIMENTAL` (destination visibility)

Founder must still **unset** those flags in Render. The code lock prevents accidental customer
exposure after this deploy.

## What could not be verified here (founder required)

| ID | Item | Why blocked | Required evidence |
| --- | --- | --- | --- |
| OPS-P0-1 | Apply `docs/supabase_entitlement_security_hardening.sql` | No Supabase dashboard/API access | SQL ran; client cannot self-grant premium |
| OPS-P0-2 | Apply `docs/supabase_feedback.sql` | No Supabase access | `feedback_reports` exists; RLS on |
| OPS-P0-3 | Confirm RLS active on profiles + feedback | No Supabase access | Policies visible in Table Editor |
| OPS-P0-4 | Streamlit has **no** `SUPABASE_SERVICE_ROLE_KEY` | No Render env access | Env list screenshot / audit |
| OPS-P0-5 | Unset `DYNASTYGM_DEBUG_PERF` (+ other debug flags) on Streamlit | No Render env access | Flag absent; Performance Report gone after redeploy |
| OPS-P0-6 | Stripe Test Mode prices + secrets on Streamlit | Premium copy proves checkout **not** configured | Guest/Premium shows test checkout when signed in |
| OPS-P0-7 | Deploy/reach Stripe webhook service `/health` | Default host returns **404** | `{"status":"ok"}` on real webhook URL |
| OPS-P0-8 | Stripe Test Mode lifecycle on production URLs | No Stripe secrets / webhook | Monthly + annual + portal + cancel + webhook + replay |
| OPS-P0-9 | Fresh Free + Premium customer walkthrough | Must not use founder accounts; needs email/auth | Matrix below completed |
| OPS-P0-10 | One feedback row in Supabase Table Editor | Needs auth + SQL | Row visible after submit |

### P1

| ID | Item |
| --- | --- |
| OPS-P1-1 | Live Stripe billing review (separate from Test Mode) |
| OPS-P1-2 | Customer Portal cancel-at-period-end observed on production |
| OPS-P1-3 | External provider freshness vs live Sleeper |
| OPS-P1-4 | Support / contact email published (currently absent on Privacy) |
| OPS-P1-5 | Branded Open Graph / social preview assets |
| OPS-P1-6 | Confirm production webhook hostname in docs after deploy |

## Stripe Test Mode dry-run results

| Scenario | Result |
| --- | --- |
| Local checklist script | Configured: **false** / Mode: `missing_or_not_test` |
| Monthly checkout on production | **Not run** — billing not configured in guest Premium UI |
| Annual checkout | **Not run** |
| Customer Portal | **Not run** |
| Cancellation / renewal / webhook / replay / failure / refund / invoice | **Not run** |
| Automated Stripe unit/contract tests | Pass in repo (no live network) |

Manual sequence remains: `python3 scripts/stripe_test_mode_checklist.py` +
`docs/STRIPE_TEST_MODE_SETUP.md`.

## Real customer simulation

| Persona | Result |
| --- | --- |
| Guest (production Chromium) | Pass — import/onboarding chrome, no crash |
| Free account (fresh) | **Not run** — requires email confirmation + founder ops |
| Premium (fresh via test checkout) | **Not run** — Stripe not configured on production |
| Private / second login / league switch authenticated | **Not run** |
| Mobile + desktop guest | Pass (responsive + desktop screenshots) |

## Production monitoring notes

| Signal | Observation |
| --- | --- |
| Render / Supabase / Stripe logs | **Not accessible** in this environment |
| Browser console on guest load | Streamlit client errors/warnings present (typical websocket/chrome noise); no customer-visible stack traces |
| Billing configuration | Premium page states checkout appears once billing is enabled — treat as **Stripe secrets missing or incomplete** on Streamlit |
| Webhook service | Guessed Render hostname 404 — treat as **undeployed or custom hostname unknown** |
| Analytics | Optional (`DYNASTYGM_LAUNCH_ANALYTICS`); wiring verified in code; production emission not observed |

## Release package checklist

| Item | Status |
| --- | --- |
| Founder Beta branding | Verified on production |
| Premium page | Verified (billing gated / not configured) |
| Feedback entry | Present in product chrome (auth path not exercised live) |
| Notification Center | Sample alerts (Founder Beta) |
| Executive Header | Verified |
| GM Orb | Verified |
| Loading / Streamlit init | Acceptable cold wait; no blank permanent failure |
| Experimental labels | ESPN experimental labeled; experimental destinations code-locked on managed hosts |
| Developer / debug / placeholder / TODO customer copy | No TODO/stack traces; Performance Report was a debug leak → code-locked |
| Privacy / Terms | Present |
| Support email | **Gap** |

## Marketing readiness

See [`docs/founder-beta-marketing-readiness.md`](founder-beta-marketing-readiness.md). Gaps only — no marketing implementation in this PR.

## Operations checklist (founder)

Copy and check off in order:

1. [ ] Supabase: run entitlement hardening SQL
2. [ ] Supabase: run feedback SQL; confirm RLS
3. [ ] Render Streamlit: confirm **no** service-role key
4. [ ] Render Streamlit: unset `DYNASTYGM_DEBUG_PERF`, `DYNASTYGM_DEBUG_AUTH`, `DYNASTYGM_PREMIUM_OVERRIDE`, `DYNASTYGM_SHOW_EXPERIMENTAL`, `DYNASTYGM_SHOW_DEV_DESTINATIONS`, `DYNASTYGM_RUNTIME_TRACE`
5. [ ] Render Streamlit: set Stripe **test** secrets + price ids + return URLs; `APP_BASE_URL=https://fantasygmlab.com`
6. [ ] Render: deploy webhook service; confirm `/health`; put signing secret only on webhook
7. [ ] Stripe Test Mode: endpoint events per `docs/STRIPE_TEST_MODE_SETUP.md`
8. [ ] Fresh Free account walkthrough (not founder)
9. [ ] Fresh Premium via test checkout → entitlement premium → portal cancel → free/policy
10. [ ] Submit feedback → row in `feedback_reports`
11. [ ] Redeploy after this PR; confirm footer SHA and **no** Performance Report
12. [ ] Only then consider live-billing review (`docs/STRIPE_TEST_MODE_SETUP.md` live section)

## Rollback boundary

- Product rollback: revert this merge commit on `main` (Render auto-deploy).
- Debug lock rollback: unset is unnecessary if flags already correct; escape hatch is `DYNASTYGM_ALLOW_PROD_DEBUG`.
- SQL migrations remain additive; do not drop tables to roll back.
- No football / valuation / ranking / Trust / recommendation-order changes in this PR.

## Explicit recommendation

**Complete listed tasks first.**

Do **not** launch Founder Beta paid intake until OPS-P0-1 through OPS-P0-10 are evidenced.
After those tasks, re-run the public probe + Stripe checklist and upgrade the decision to
Ready to charge (Test Mode only) or a separate live-billing review for real money.
