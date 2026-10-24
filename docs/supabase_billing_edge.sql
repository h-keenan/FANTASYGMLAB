-- FantasyDesk billing on Supabase Edge Functions (additive, manual).
-- Run by hand in Supabase Dashboard -> SQL Editor (no migration runner exists).
-- Safe to re-run. Prerequisites (already applied in production):
--   docs/supabase_accounts.sql, docs/supabase_profile_entitlement.sql,
--   docs/supabase_entitlement_security_hardening.sql,
--   docs/supabase_premium_tiers_migration.sql, docs/supabase_stripe_billing.sql,
--   docs/supabase_revenuecat_billing.sql, docs/supabase_free_trial.sql.
--
-- What this adds: ONE table, the durable idempotency log the Edge Function
-- webhooks use (replaces the Python services' process-local 6h event-id
-- cache, which a stateless Edge runtime cannot have). Nothing existing is
-- altered: public.profiles stays the entitlement source of truth that the
-- FastAPI API and web/mobile already read.
--
-- Writes: service_role ONLY (the Edge Functions' injected service-role key,
-- which bypasses RLS). RLS is enabled with NO policies and all privileges are
-- revoked from anon/authenticated, so no client can read or write it.

create table if not exists public.billing_webhook_events (
    provider text not null check (provider in ('stripe', 'revenuecat')),
    event_id text not null,
    event_type text not null default '',
    user_id text not null default '',
    outcome text not null default '',        -- applied | skipped_no_entitlement | skipped_non_uuid_user
    entitlement text not null default '',    -- free | premium | front_office | ''
    reason text not null default '',
    trial_transition text not null default '', -- started | converted | canceled | '' (analytics backfill)
    received_at timestamptz not null default now(),
    primary key (provider, event_id)
);

alter table public.billing_webhook_events enable row level security;

revoke all on table public.billing_webhook_events from anon, authenticated;
grant select, insert on table public.billing_webhook_events to service_role;

comment on table public.billing_webhook_events is
    'Idempotency + audit log of processed Stripe/RevenueCat webhook events. Written only by the billing Edge Functions (service_role). No client policies by design.';

create index if not exists billing_webhook_events_received_at_idx
    on public.billing_webhook_events (received_at desc);

-- Optional housekeeping (run manually if the table grows; keep >= 30 days so
-- provider retry windows are always covered):
--   delete from public.billing_webhook_events where received_at < now() - interval '90 days';
