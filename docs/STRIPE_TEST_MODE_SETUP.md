# Stripe Test-Mode Billing Setup

DynastyGM supports a test-mode Stripe foundation for Founder Premium. Live billing is not enabled by this setup, and the app should keep working when Stripe configuration is missing.

## Required Test Secrets

Set these in environment variables or Streamlit secrets. Do not commit real values.

- `STRIPE_SECRET_KEY`: Stripe test secret key, beginning with `sk_test_`.
- `STRIPE_WEBHOOK_SECRET`: Stripe test webhook signing secret, beginning with `whsec_`.
- `STRIPE_PRICE_MONTHLY`: Monthly recurring test price id from Stripe.
- `STRIPE_PRICE_ANNUAL`: Annual recurring test price id from Stripe.

Optional:

- `STRIPE_CUSTOMER_PORTAL_RETURN_URL`
- `STRIPE_CHECKOUT_SUCCESS_URL`
- `STRIPE_CHECKOUT_CANCEL_URL`

If required checkout configuration is missing, the Premium page shows billing as unavailable instead of rendering a fake checkout.

## Creating Test Prices

1. In the Stripe Dashboard, make sure the workspace is in test mode.
2. Create a Founder Premium product.
3. Add one recurring monthly test price.
4. Add one recurring annual test price.
5. Put those test price ids in `STRIPE_PRICE_MONTHLY` and `STRIPE_PRICE_ANNUAL`.

Do not use live price ids until a separate live billing review is complete.

## Checkout Flow

Checkout is available only when Stripe test config is present and the user is logged in. Checkout session metadata includes:

- `supabase_user_id`
- `plan_interval`

The client does not grant Premium after checkout. Premium entitlement must still come from a verified server-side webhook or manual Supabase grant.

## Webhook Entitlement Flow

The helpers in `modules/stripe_billing.py` and `modules/stripe_webhook.py` verify Stripe webhook signatures, reject live-mode events, map subscription events to entitlement updates, and patch Supabase with a server-side key:

- active/trialing checkout or subscription events map to `profiles.entitlement = 'premium'`
- canceled/inactive/unpaid/payment-failed states map to `profiles.entitlement = 'free'`

For live billing, handle webhooks in a server-side endpoint such as a Supabase Edge Function or separate backend. Streamlit should not be treated as the final production webhook endpoint unless the deployment has a reviewed secure public route.

Webhook handling must:

1. Verify the Stripe signature with `STRIPE_WEBHOOK_SECRET`.
2. Read `supabase_user_id` from Stripe metadata.
3. Update `public.profiles.entitlement` server-side.
4. Never expose Stripe secrets or tokens to the client.
5. Never let normal user settings writes modify entitlement.

The webhook backend needs these server-only secrets:

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

Do not put `SUPABASE_SERVICE_ROLE_KEY` in Streamlit frontend output, client JavaScript, or any user-editable setting.

## Optional Supabase Billing Fields

Run `docs/supabase_stripe_billing.sql` if you want the webhook to store Stripe ids for portal access and reconciliation:

- `stripe_customer_id`
- `stripe_subscription_id`
- `stripe_subscription_status`
- `stripe_price_id`
- `premium_updated_at`

The app tolerates these columns being absent. If they exist and the authenticated profile fetch can read them, Premium users with `stripe_customer_id` can use the test-mode customer portal helper.

## Local Test Flow

1. Create monthly and annual recurring test prices in Stripe.
2. Set the test secrets listed above.
3. Start the app and sign in.
4. Open Premium and create a Stripe test checkout.
5. In another terminal, forward Stripe test webhooks to your backend endpoint:

```bash
stripe listen --forward-to http://localhost:8000/stripe-webhook
```

6. Complete checkout with a Stripe test card.
7. Confirm the webhook receives `checkout.session.completed` or `customer.subscription.updated`.
8. Confirm `public.profiles.entitlement` changes to `premium`.
9. Reopen DynastyGM and confirm the Premium locks disappear.
10. Cancel the subscription in Stripe or send a deleted event.
11. Confirm `public.profiles.entitlement` changes back to `free`.
12. Test the customer portal before any live billing review.

The exact webhook URL depends on the backend or Supabase Edge Function you deploy. The core rule is that the endpoint must verify the Stripe signature before updating Supabase.

## Customer Portal and Cancellation

Before live billing, configure Stripe Customer Portal so users can manage or cancel subscriptions without contacting support. The app includes a portal session helper, but portal access depends on Stripe customer id availability and test configuration.

Store only the minimum Stripe identifiers needed for portal access and reconciliation, such as a customer id or subscription id. Do not store card or payment details in Supabase.

## Free Trial

Trial support is optional. If enabled later, the trial length and renewal behavior must be explicit in the Premium page copy before live billing is enabled.

## Live Billing Checklist

Do not enable live billing until all of these are complete:

- Live Stripe keys and prices are configured outside source control.
- Webhook endpoint is deployed server-side and signature verification is tested.
- Entitlement updates are idempotent and audited.
- Customer Portal cancellation is tested.
- Premium page copy states pricing, trial, renewal, and cancellation terms clearly.
- Future features remain labeled as possible/planned, not guaranteed.
- No client-side path can self-upgrade `profiles.entitlement`.
- RLS policies still prevent users from modifying their own entitlement.
- Sleeper/ESPN/NFL unaffiliated disclaimers remain visible where appropriate.
