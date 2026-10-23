-- FantasyDesk free trial: display-only trial end date.
-- Run by hand in Supabase Dashboard -> SQL Editor (no migration runner exists).
-- Safe to skip: both billing webhooks retry without this column if it is
-- missing, so entitlement still flows; only the "trial ends on ..." line in the
-- account screen needs it.

alter table public.profiles
    add column if not exists trial_ends_at timestamptz;

comment on column public.profiles.trial_ends_at is
    'End of an in-progress free trial (Stripe trial_end / RevenueCat expiration of a TRIAL period). Set and cleared by verified billing webhooks. Display only: never the source of entitlement.';
