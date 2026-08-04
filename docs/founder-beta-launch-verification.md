# Founder Beta Launch Verification

Launch-readiness verification for FantasyGM Lab Founder Beta.
Baseline branch point: `607754cd003b67b463bdc1f986d684678a9d1fbe`.

## LC0 status (2026-08-04)

Launch Candidate Zero report: [`docs/founder-beta-lc0.md`](founder-beta-lc0.md).

Post-PR-#109 baseline measured: `2118bca3063075660768ab85200f4e52fdbb2a94`.

**Decision unchanged:** Ready after listed manual configuration (not yet ready to charge
real money). Automated suites are green; production SQL + Stripe test lifecycle + fresh
account walkthrough remain required.

## Explicit launch recommendation

**Ready after listed manual configuration** (not yet ready to charge real money).

Stripe test-mode, entitlement authority hardening, durable Supabase feedback,
logout session cleanup, and automated coverage are in this PR. Live Stripe
billing remains intentionally disabled.

## Fresh-account test matrix

| Persona / scenario | Expected result | Automated | Manual |
| --- | --- | --- | --- |
| Signed-out visitor | Landing + guest path; no stale auth chrome | partial | yes |
| New Free account | Sign-up → Free entitlement → import league | partial | yes |
| Returning Free account | Restore session; Free gates only | yes | yes |
| Newly upgraded Premium | Webhook → premium; full Trade Hub / Dashboard | yes | yes |
| Returning Premium | Profile entitlement survives refresh | yes | yes |
| Cancelled-but-still-active (`cancel_at_period_end`, status `active`) | Remains Premium until period end | yes | yes |
| Expired / deleted subscription | Downgrades to Free | yes | yes |
| Invalid / incomplete payment | Checkout fails without entitlement grant | yes | yes |
| Profile lookup failure | Fail closed to Free | yes | — |
| Temporary Stripe webhook delay | UI stays Free until webhook; refresh recovers | yes (skip/no-op) | yes |
| Temporary Supabase failure | Clear warning; no crash | partial | yes |
| No imported league | Onboarding / import path | yes | yes |
| Multiple leagues | Switcher updates identity without stale prior league | yes | yes |

## Stripe test-mode lifecycle

Verified in code/tests:

- monthly / annual checkout metadata and test-only secrets
- successful payment → premium
- failed payment → free
- duplicate checkout reduced via Stripe idempotency key
- customer portal helper
- cancel-at-period-end keeps premium while status is active
- subscription deleted / canceled / unpaid / incomplete_expired → free
- webhook signature verification + livemode rejection
- webhook replay re-PATCHes safely (no false 500 on past_due)
- past_due subscription update is a successful no-op (no auto-downgrade, no retry storm)
- service-role key remains webhook-service only

Run:

```bash
python3 scripts/stripe_test_mode_checklist.py
pytest tests/test_stripe_billing.py tests/test_launch_verification.py -q
```

## Feedback persistence decision

**Production destination:** Supabase table `public.feedback_reports`

SQL: `docs/supabase_feedback.sql`

**Why:** Render Streamlit disk is ephemeral. JSONL under `data/` does not survive redeploys.

**Local fallback:** JSONL remains for developer environments when Supabase is unavailable.

### Founder feedback review (no server files)

1. Open Supabase Dashboard for the production project.
2. Table Editor → `feedback_reports` (newest first), or run:

```sql
select report_id, created_at, category, message, status, app_build, context
from public.feedback_reports
order by created_at desc
limit 100;
```

3. Mark reviewed rows by updating `status` (for example `reviewed`) in the dashboard.

## Supabase / RLS findings

| Finding | Severity | Fix |
| --- | --- | --- |
| Client INSERT could self-grant premium | P0 | `docs/supabase_entitlement_security_hardening.sql` forces free on client insert |
| Webhook role missing from entitlement trigger allowlist | P0 | allow `service_role` for verified billing updates |
| Feedback ephemeral on Render | P0/P1 | `docs/supabase_feedback.sql` + app persist path |
| past_due caused webhook HTTP 500 | P1 | skip entitlement PATCH when status is indeterminate |
| Logout left prior league/username in session | P1 | `clear_auth_session` clears league chrome |

**Manual SQL to run before paid beta (order):**

1. `docs/supabase_accounts.sql` (if not already)
2. `docs/supabase_profile_entitlement.sql` (if not already)
3. `docs/supabase_stripe_billing.sql` (if not already)
4. `docs/supabase_entitlement_security_hardening.sql` (**required**)
5. `docs/supabase_feedback.sql` (**required**)

## Free / Premium matrix

| Surface | Free | Premium |
| --- | --- | --- |
| Dashboard Next Moves | Limited preview | Full stack |
| Trade Hub | Preview ideas + upgrade lock | Full board |
| Waivers | Priority adds | Full stash / watch / FAAB |
| Premium page | Checkout CTA | Manage Billing / portal |
| Entitlement source | Server profile only | Server profile only |

Premium changes **access only**, never football facts, valuations, rankings, or recommendation generation.

## Experimental / production env checklist

| Variable | Streamlit | Webhook | Launch value |
| --- | --- | --- | --- |
| `SUPABASE_URL` | required | required | production project URL |
| `SUPABASE_ANON_KEY` | required | — | anon key only |
| `SUPABASE_SERVICE_ROLE_KEY` | **must be unset** | required | webhook service only |
| `STRIPE_SECRET_KEY` | `sk_test_…` | `sk_test_…` | test only |
| `STRIPE_WEBHOOK_SECRET` | unset | `whsec_…` | webhook service only |
| `STRIPE_PRICE_MONTHLY` / `ANNUAL` | test prices | — | test prices |
| `STRIPE_*_URL` / `APP_BASE_URL` | required | — | https://fantasygmlab.com |
| `DYNASTYGM_BUILD` | set to deploy SHA | optional | Render commit SHA |
| `DYNASTYGM_SHOW_EXPERIMENTAL` | **unset/false** | — | off |
| `DYNASTYGM_SHOW_DEV_DESTINATIONS` | unset | — | off |
| `DYNASTYGM_DEBUG_UI` | unset | — | off |
| `DYNASTYGM_DEBUG_AUTH` | unset | — | off |
| `DYNASTYGM_PREMIUM_OVERRIDE` | unset | — | off |
| `DYNASTYGM_DEBUG_PERF` | unset | — | off |
| `DYNASTYGM_RUNTIME_TRACE` | unset | — | off |
| `DYNASTYGM_LAUNCH_ANALYTICS` | optional `1` | — | off by default |
| `DYNASTYGM_FEEDBACK_PATH` | local fallback only | — | optional |

Live Stripe keys (`sk_live_`, live price ids) must remain unused until a separate live-billing review.

## Analytics readiness

Minimal optional event boundary: `modules/launch_analytics.py`.

Enable with `DYNASTYGM_LAUNCH_ANALYTICS=1`. Events: landing visit, account created, league imported, Dashboard reached, Trade Hub opened, Player Quick View opened, Premium checkout started/completed, feedback submitted.

If not enabled, post-launch setup is: set the flag or wire the same event names to a privacy-conscious provider. Not a launch blocker.

## Manual steps still required before charging real money

1. Apply entitlement hardening + feedback SQL in production Supabase.
2. Confirm Render Streamlit has **no** service-role key.
3. Complete Stripe test-mode checklist end-to-end on production URLs.
4. Confirm Customer Portal cancel-at-period-end behavior in Stripe Dashboard.
5. Separate live-billing review (`docs/STRIPE_TEST_MODE_SETUP.md` live checklist).
6. Fresh Free + Premium account walkthrough on production (not founder/dev accounts).
7. Submit one feedback report and confirm it appears in Supabase Table Editor.

## Rollback boundary

Revert the launch-verification merge commit. SQL migrations are additive; entitlement trigger can be re-applied from the previous SQL docs if needed. No football/valuation/recommendation logic is modified.
