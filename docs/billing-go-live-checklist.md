# Billing go-live checklist (Stripe + RevenueCat webhook services)

Status as of 2026-10-23 (verified over SSH by the team, values never printed):
both webhook containers, `/opt/fantasygmlab/.env`, `production.json` and
`baseline.json` agree: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
`REVENUECAT_SECRET_KEY`, `REVENUECAT_PROJECT_ID`, `REVENUECAT_WEBHOOK_AUTH_TOKEN`
all have length 0, and `STRIPE_BILLING_MODE` / `REVENUECAT_BILLING_MODE` are
`test`. The services were built and deployed for test mode
(`docs/STRIPE_TEST_MODE_SETUP.md`, "do not enable live Stripe billing") and the
live cutover was never completed. Until it is, purchases cannot grant Pro
through these services (they fail closed). The mobile API has its own separate
Stripe credentials; they are not a substitute.

Never paste secret values into chat, tickets or docs. Check lengths and
prefixes only.

## 1. Stripe (live mode)
- [ ] Dashboard in **live** mode: copy the secret key (`sk_live_…`).
- [ ] Confirm live prices exist and match `STRIPE_PRICE_MONTHLY` / `STRIPE_PRICE_ANNUAL`
      (Pro $3.99/mo, $19.99/yr; Front Office $99.99/yr per the 2026-10-22 decision).
- [ ] Add a live webhook endpoint: `https://<STRIPE_WEBHOOK_DOMAIN>/stripe/webhook`
      with events `checkout.session.completed`, `customer.subscription.created`,
      `customer.subscription.updated`, `customer.subscription.deleted`,
      `invoice.payment_succeeded`, `invoice.payment_failed`
      (see `docs/stripe-webhook-service-contract.md`). Copy its signing secret (`whsec_…`).
- [ ] The service rejects events whose `livemode` does not match
      `STRIPE_BILLING_MODE`, so set it to live together with the keys.

## 2. RevenueCat
- [ ] Copy the secret API key and the project ID.
- [ ] Webhook URL `https://<REVENUECAT_WEBHOOK_DOMAIN>/revenuecat/webhook` with an
      Authorization header; use that same token as `REVENUECAT_WEBHOOK_AUTH_TOKEN`.
- [ ] Products/entitlements map to the store products (App Store / Play prices are a
      separate owner decision).

## 3. Apply everywhere (all four must agree)
- [ ] `/opt/fantasygmlab/.env`
- [ ] `/var/lib/fantasygmlab/releases/production.json`
- [ ] `/var/lib/fantasygmlab/releases/baseline.json`
- [ ] Recreate both webhook containers so they pick the values up.

## 4. Verify (no real money)
- [ ] In each container print per-variable length (and prefix for Stripe only):
      Stripe key `sk_live_`, signing secret `whsec_`, modes `live`, no zero lengths.
- [ ] `GET /health` and `GET /ready` return 200 on both services
      (`/ready` checks billing readiness independently of liveness).
- [ ] Unsigned `POST /stripe/webhook` returns 4xx, not 404.
- [ ] Stripe "Send test webhook" and a RevenueCat test event both return 200.
- [ ] One real low-value purchase on a test account: entitlement flips to Pro,
      then cancel/refund and confirm it reverts.

## 5. After go-live
- [ ] Set the store prices (owner approval) and confirm the paywall copy matches.
- [ ] Watch the webhook logs for rejected events (livemode mismatch, bad signature).
