# Billing and entitlements on Supabase (Edge Functions + Postgres)

Decision (Zach, 2026-10-24): the self-hosted server box no longer processes
payments or entitlements. Stripe and RevenueCat webhooks, checkout, and the
billing portal run as Supabase Edge Functions. Provider keys live ONLY as
Supabase function secrets.

Status: **Phase 1 = code only, nothing deployed.** The Python services stay in
the repo as the rollback path and are marked deprecated.

## Architecture

```
Stripe  --webhook-->  stripe-webhook         --service role-->  public.profiles (entitlement, stripe_*, trial_ends_at)
RevenueCat --webhook-> revenuecat-webhook    --service role-->  public.profiles (entitlement, revenuecat_*, trial_ends_at)
                       (both also write public.billing_webhook_events = idempotency/audit log)

web / mobile --Supabase JWT--> create-checkout-session --> Stripe Checkout (embedded)
web / mobile --Supabase JWT--> billing-portal-session  --> Stripe Billing Portal

FastAPI (require_league_access, tiers, founder/free codes) and web/mobile
keep READING public.profiles.entitlement exactly as today. Untouched.
```

Source of truth is unchanged: `public.profiles.entitlement` (`free` | `premium`
= GM Pro, legacy name | `front_office`; a trial is stored as Pro/`premium`).
The existing trigger (`docs/supabase_entitlement_security_hardening.sql`) already
restricts entitlement writes to `service_role`/`postgres`; Edge Functions use the
platform-injected service-role key, so no policy changes are needed.

Layout: `supabase/functions/{stripe-webhook,revenuecat-webhook,create-checkout-session,billing-portal-session}/`
(each `index.ts` = `Deno.serve` wrapper, `handler.ts` = testable logic) and
`supabase/functions/_shared/` (pure logic, fetch-based Supabase/Stripe/RevenueCat
clients, tests). No npm/SDK dependencies: Stripe and RevenueCat are called over
REST with `fetch`, signatures are verified with WebCrypto.

### Idempotency
Durable, by provider event id, in `public.billing_webhook_events`
(PK `(provider, event_id)`). A processed event returns 200 `skipped/duplicate`
without touching `profiles`. An event is recorded only after the profile update
succeeded (or the event legitimately needs no update), so a failed update returns
500 and the provider retries. Independently, the profile PATCH keeps the original
atomic out-of-order guard (`stripe_event_created_at` / `revenuecat_event_created_at`
`or=` filter), so replays and reordered events cannot regress state.

### Tiers and trial
Free / Pro (`premium`) / Front Office (`front_office`). Trial: one constant,
`TRIAL_DAYS = 3` in `supabase/functions/_shared/config.ts` (optional
`STRIPE_TRIAL_DAYS` secret overrides; `0` disables). Pro only, one per account,
Stripe-native (`trial_period_days`, cancel if no payment method at trial end),
stored as Pro with `trial_ends_at`. Trial -> unpaid/past_due/canceled => `free`;
trial -> active => stays Pro; a stale `trialing` event whose `trial_end` has
passed resolves `free`.

## Secrets (names only; set with `supabase secrets set`)

Auto-injected by Supabase (do not set): `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`.

Stripe: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_BILLING_MODE` (`test`|`live`),
`STRIPE_PRICE_PRO_MONTHLY`, `STRIPE_PRICE_PRO_ANNUAL`, `STRIPE_PRICE_PRO_ANNUAL_LAUNCH_WEEK` (optional),
`STRIPE_PRICE_FRONT_OFFICE_ANNUAL` (optional), `STRIPE_TRIAL_DAYS` (optional).
(Legacy `STRIPE_PRICE_MONTHLY`/`STRIPE_PRICE_ANNUAL` still accepted as fallbacks.)

RevenueCat: `REVENUECAT_WEBHOOK_AUTH_TOKEN`, `REVENUECAT_SECRET_KEY`, `REVENUECAT_PROJECT_ID`,
`REVENUECAT_BILLING_MODE` (`test`|`live`), `REVENUECAT_ENTITLEMENT_LOOKUP_KEY` (optional, default `premium`),
`REVENUECAT_FRONT_OFFICE_ENTITLEMENT_LOOKUP_KEY` (optional, default `front_office`).

App: `APP_BASE_URL` (post-payment return origin, e.g. the production web origin),
`CORS_ALLOWED_ORIGINS` (optional, comma-separated extra origins besides `APP_BASE_URL`).

Never put any value in the repo, docs, `.env` files, or web/mobile bundles.

## Deploy (Phase 2, needs Zach)

```bash
# one-time
supabase login
supabase link --project-ref <PROJECT_REF>        # set project_id in supabase/config.toml too

# 1. SQL: run docs/supabase_billing_edge.sql in the Dashboard SQL Editor (additive; one table)

# 2. secrets (values typed by Zach; never pasted into chat/repo)
supabase secrets set STRIPE_SECRET_KEY=... STRIPE_WEBHOOK_SECRET=... STRIPE_BILLING_MODE=test ...
supabase secrets list                            # names + digests only

# 3. functions (config.toml already sets verify_jwt per function)
supabase functions deploy stripe-webhook --no-verify-jwt
supabase functions deploy revenuecat-webhook --no-verify-jwt
supabase functions deploy create-checkout-session
supabase functions deploy billing-portal-session
```

Function URLs: `https://<PROJECT_REF>.supabase.co/functions/v1/<name>`.

## Tests

```bash
deno test supabase/functions/_shared/          # supported runner (also a CI job)
# no Deno? same suite under bun:
cd supabase/functions/_shared && bun test --preload ./bun_shim.ts
```
Covers signature verification (valid/tampered/wrong secret/stale/rotated), idempotency, every
handled Stripe event type, trial transitions, price allowlist, RevenueCat mapping/auth/dedupe,
checkout (JWT auth, verified-email prefill, customer reuse, trial rules, return_url, price
selection, launch week) and portal. Python regression tests (`pytest`) are unchanged.

## Cutover checklist (CUTOVER CHECKLIST)

Do TEST mode end to end first, then repeat for live.

1. [ ] Zach: confirm Supabase project ref and that Edge Functions are enabled (Pro plan not required).
2. [ ] Run `docs/supabase_billing_edge.sql`. Confirm `docs/supabase_stripe_billing.sql`, `supabase_revenuecat_billing.sql`, `supabase_free_trial.sql`, `supabase_premium_tiers_migration.sql` were applied earlier (nothing assumes this; check the columns exist).
3. [ ] Set secrets (test-mode values first). Deploy the four functions.
4. [ ] Stripe Dashboard (test mode): add a NEW webhook endpoint `https://<ref>.supabase.co/functions/v1/stripe-webhook`; events: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_succeeded`, `invoice.payment_failed`. Copy its signing secret into `STRIPE_WEBHOOK_SECRET`. Keep the old Render/box endpoint enabled but see step 7.
5. [ ] Smoke test (test mode): Stripe CLI `stripe trigger customer.subscription.created` is not enough (no `supabase_user_id`); run one real test checkout through `create-checkout-session` with test card 4242..., confirm `profiles.entitlement='premium'`, `trial_ends_at` set, one row in `billing_webhook_events`. Resend the same event from the Stripe Dashboard: expect `skipped/duplicate`, no change. Cancel in the portal: expect `free` at period end / immediately on delete.
6. [ ] RevenueCat dashboard: set webhook URL to `.../functions/v1/revenuecat-webhook`, Authorization header value = `REVENUECAT_WEBHOOK_AUTH_TOKEN`; send RC's "Test" event (expect 200, skipped); do one sandbox purchase and confirm `profiles.entitlement`.
7. [ ] LIVE cutover window (low traffic): set `STRIPE_BILLING_MODE=live` + live key/prices/webhook secret and `REVENUECAT_BILLING_MODE=live`; add the live Stripe endpoint; in the SAME window disable (not delete) the old Stripe and RevenueCat webhook endpoints so only one system writes `profiles`. (Both writing is safe thanks to the ordering guard, but pick one to avoid double analytics/confusion.)
8. [ ] Repoint clients (Phase 2 code): web-next and mobile call `create-checkout-session` / `billing-portal-session` with the user's Supabase JWT instead of FastAPI `/v1/billing/checkout|portal`. Until then FastAPI still serves checkout/portal and needs its Stripe key (see "Not ported").
9. [ ] Verify live: real $-charge (refund after) or a 100%-off promo code; watch function logs (`supabase functions logs stripe-webhook`) for 24h.
10. [ ] After a stable window: remove Stripe/RevenueCat/service-role secrets from the box and from the old Render services; then retire the Python services (separate PR).

## Rollback plan

Nothing in Phase 1 changes production. After cutover, rollback = re-enable the old
Stripe/RevenueCat webhook endpoints (Python services still deployed and the code
still in the repo), disable the Supabase endpoints in the provider dashboards, and
leave FastAPI checkout/portal as is. Data is compatible both ways (same `profiles`
columns); `billing_webhook_events` is additive and can stay. Do not delete the Python
services or box secrets until step 10 is complete.

## What was ported, and what was not

Ported faithfully (from `modules/stripe_billing.py`, `stripe_webhook.py`, `revenuecat_billing.py`, `revenuecat_webhook.py`, `services/*_webhook_service.py`, `services/mobile_api_service.py` checkout/portal):

- Stripe signature verification (HMAC-SHA256, 300 s tolerance, multiple `v1`), livemode vs `STRIPE_BILLING_MODE` check, `whsec_` and `sk_<mode>_` checks, live-requires-prices check
- Event mapping: active set (`checkout.session.completed`, `subscription.created/updated`, `invoice.payment_succeeded`), `subscription.deleted`, `invoice.payment_failed`, `canceled/unpaid/incomplete_expired`, `cancel_at_period_end` reason tag, expired-trial guard, trial transitions (started/converted/canceled), trialing -> past_due/unpaid/canceled => free, Front Office price => `front_office`, user-id resolution order, price-id extraction order, invoice status quirks
- Profile payload fields, `trial_ends_at` set/clear rule, `trial_ends_at` column-missing retry, billing-column-missing error text, atomic ordering guard (grant needs strictly newer; revocation may tie), past-due/blank entitlement => no write
- Live-mode price allowlist (monthly, annual, launch-week, Front Office); in test mode no allowlist, as before
- HTTP contract: statuses (400 missing/bad signature, 500 on update failure so Stripe retries) and response JSON shape
- RevenueCat: Authorization compare (constant time), TEST/environment-mismatch/missing-user skips, fresh active-entitlements read from RevenueCat API (404 => free), lookup keys with defaults, front_office > premium > free, TRIAL fields and transitions, store -> platform map, ordering guard, response shape
- Checkout: price by (tier, interval) failing closed, Launch Week window (Oct 12-18 2026 CT), trial rules (Pro only, `trial_period_days`, cancel on missing payment method, forfeited by profile history, prior Stripe subscription for the email, or any lookup error), embedded/hosted modes, metadata, `client_reference_id`, promo codes, `payment_method_collection=always`, idempotency key, return path safety (`_safe_return_path`)
- Portal: customer id from the user's own profile, 404 if none, `/premium` return

Deliberate differences (improvements; review them):
- Idempotency is durable (table) instead of a 6 h process-local cache.
- Checkout reuses `profiles.stripe_customer_id` when present (was: new customer per session via `customer_email`); otherwise prefills the email from the verified JWT. A client-supplied email is never used.
- Idempotency key gets a param fingerprint suffix (a reused key with different params would 400 at Stripe).
- Non-UUID user ids: Stripe => 400 "user id" error; RevenueCat anonymous ids (`$RCAnonymousID:...`) => 200 skipped (previously a PATCH error and endless retries). Guards the PostgREST filter against injection.
- RevenueCat API read failure => 502 (was 400); still retried by RevenueCat.
- The Stripe webhook function does not require `STRIPE_SECRET_KEY` to verify signatures (fewer secrets needed there); if set it must match the mode.
- `STRIPE_CHECKOUT_*_URL` / `STRIPE_CUSTOMER_PORTAL_RETURN_URL` secrets are not read (the FastAPI caller always overrode them); `APP_BASE_URL` + path is used.

NOT ported (needs a decision or Phase 2):
- Python launch analytics (`trial_started`, `subscribed`, `churned`, `feature_use trial`) fired from the webhook. The Edge Function stores `trial_transition`, `reason`, `entitlement` per event in `billing_webhook_events` so these can be backfilled/derived; real-time `track_event` is gone until reimplemented.
- `GET /v1/billing/plans` (live Price display + publishable key + trial-eligibility copy) still lives in FastAPI/`modules/stripe_billing.py` and still needs a Stripe key on the box. A `billing-plans` function is the follow-up if the box must hold no Stripe key at all.
- Clients still call FastAPI for checkout/portal until Phase 2 repoints them.
- Premium lifecycle bits outside webhooks (founder/free codes, `require_league_access`) are intentionally untouched and keep reading `profiles`.

## Unverified in Phase 1

- Nothing was run against live Stripe, RevenueCat or Supabase. Deno was not installed on the authoring machine; the suite was run under Bun (same code, assertion shim) and type-checked with `tsc --strict`. The `deno test` CI job is the first Deno execution.
- Stripe API request encoding and Embedded Checkout params are built to Stripe's documented form format but not exercised against Stripe.
- PostgREST `or=(...)` filter behaviour is a straight port of the existing, previously-working Python filter; not re-tested against a live DB.
- `supabase/config.toml` needs the real `project_id`; `verify_jwt` settings should be confirmed on first deploy.
