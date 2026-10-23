# 3-day free trial of Pro: owner setup

Code is shipped; nothing below is configured by the code. Product decision: 3 days
free, Pro only, one trial per account, payment method required up front.

## What the code does
- Web (Stripe Checkout): `subscription_data.trial_period_days = STRIPE_TRIAL_DAYS`
  (default 3, `0` disables, applies to Pro only, not Front Office), payment method
  collected up front, and `trial_settings.end_behavior.missing_payment_method = cancel`
  so a trial with no usable card cancels instead of converting to free access.
- One trial per account: no trial if the profile already has Stripe/RevenueCat
  history, or Stripe shows any earlier subscription for the same email. Any lookup
  failure means no trial.
- Webhooks: `trialing` grants Pro; `active` keeps it; `canceled`/`unpaid`/payment
  failure/`trialing` with a `trial_end` in the past revoke. The trial end date is
  stored in `profiles.trial_ends_at` (optional, see step 4) and shown on Account.
- Mobile: the paywall shows trial copy only when RevenueCat reports the user
  eligible for the store intro offer (`checkTrialOrIntroductoryPriceEligibility`)
  and the product actually has a free intro offer.

## Owner steps
1. Stripe (Dashboard, per mode): no price change needed. Trial length comes from the
   API call. Optional env on the API service: `STRIPE_TRIAL_DAYS=3` (omit for default).
   Confirm the webhook is subscribed to `customer.subscription.created`,
   `customer.subscription.updated`, `customer.subscription.deleted`,
   `checkout.session.completed`, `invoice.payment_succeeded`, `invoice.payment_failed`
   (`docs/billing-go-live-checklist.md`). In Customer portal settings, allow
   cancellation (so people can cancel during the trial).
2. App Store Connect: Subscriptions -> your Pro group -> each Pro product (monthly,
   annual) -> Subscription Prices -> Introductory Offers -> Create: Type "Free",
   Duration "3 Days", territories all, start date today. Apple allows one intro offer per
   subscription group per Apple ID, which enforces one trial per account on iOS.
3. Google Play Console: Monetize -> Subscriptions -> the Pro subscription -> Base plan
   -> Add offer -> Eligibility "New customer acquisition", Phase 1 "Free trial",
   Duration 3 days, then Save and Activate. Play enforces one use per Google account.
4. Supabase SQL Editor: run `docs/supabase_free_trial.sql` (adds `profiles.trial_ends_at`).
   Skipping it is safe; only the "Trial ends" line is lost.
5. RevenueCat: Products -> confirm both store products are attached to the
   `premium` entitlement (the entitlement is active for the whole trial; RevenueCat
   marks it `period_type = TRIAL`). Webhook events used: `INITIAL_PURCHASE`
   (period_type TRIAL = trial started), `RENEWAL` with `is_trial_conversion = true`
   (converted), `CANCELLATION` / `EXPIRATION` of a TRIAL period (canceled). No new
   event types need enabling. Offerings need no change: eligibility and the intro
   price are read from the store products.
6. Verify in test/sandbox before live: Stripe test card 4242 -> subscription shows
   `trialing`, Account shows the end date; cancel -> access ends at trial end.
   iOS sandbox / Play license-testing accounts for the store flows.

## Analytics (privacy-safe, existing pipeline)
- `trial_started` (existing canonical event, Stripe webhook).
- `feature_use` with `feature=trial`, `action=converted|canceled`
  (Stripe and RevenueCat webhooks; `action=started` from RevenueCat). Only the hashed
  account key and platform are attached.

## Not changed
Free-tier ledger and paywall audit behavior (`modules/free_tier_ledger.py`,
`docs/paywall-audit-2026-10.md`).
