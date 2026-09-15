-- FantasyGM Lab RevenueCat billing fields (mobile IAP + RC Billing web).
-- Run this before enabling the verified RevenueCat webhook backend.
-- Mirrors docs/supabase_stripe_billing.sql. See
-- docs/supabase_entitlement_security_hardening.sql for the trigger that
-- restricts entitlement writes to service_role — that trigger already covers
-- this webhook, no change needed there.

alter table public.profiles
    add column if not exists revenuecat_app_user_id text,
    add column if not exists revenuecat_event_id text,
    add column if not exists revenuecat_event_type text,
    add column if not exists revenuecat_environment text,
    add column if not exists revenuecat_event_created_at timestamptz,
    add column if not exists premium_updated_at timestamptz;

comment on column public.profiles.revenuecat_app_user_id is
    'RevenueCat app_user_id set by verified server-side webhook handling (the Supabase user id, once signed in).';

comment on column public.profiles.revenuecat_event_id is
    'Latest verified RevenueCat event applied to the entitlement.';

comment on column public.profiles.revenuecat_event_type is
    'RevenueCat event type (INITIAL_PURCHASE, RENEWAL, EXPIRATION, ...) from the latest verified event.';

comment on column public.profiles.revenuecat_environment is
    'RevenueCat event environment (SANDBOX or PRODUCTION) from the latest verified event.';

comment on column public.profiles.revenuecat_event_created_at is
    'Ordering guard that prevents older webhook events from replacing newer entitlement state.';
