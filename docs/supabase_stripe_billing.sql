-- DynastyGM optional Stripe billing fields for test-mode Founder Premium.
-- Run this only if you want the verified Stripe webhook backend to store
-- customer/subscription metadata for portal access and reconciliation.
-- Do not put service-role keys or private credentials in the app.

alter table public.profiles
    add column if not exists stripe_customer_id text,
    add column if not exists stripe_subscription_id text,
    add column if not exists stripe_subscription_status text,
    add column if not exists stripe_price_id text,
    add column if not exists premium_updated_at timestamptz;

comment on column public.profiles.stripe_customer_id is
    'Stripe customer id set by verified server-side webhook handling.';

comment on column public.profiles.stripe_subscription_id is
    'Stripe subscription id set by verified server-side webhook handling.';

comment on column public.profiles.stripe_subscription_status is
    'Stripe subscription status set by verified server-side webhook handling.';

comment on column public.profiles.stripe_price_id is
    'Stripe recurring price id set by verified server-side webhook handling.';

comment on column public.profiles.premium_updated_at is
    'Timestamp of the latest server-side Premium entitlement update.';
