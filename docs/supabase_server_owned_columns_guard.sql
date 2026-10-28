-- Server-owned column guard (security hardening, additive / migration-safe).
-- Run in Supabase Dashboard -> SQL Editor AFTER docs/supabase_accounts.sql,
-- docs/supabase_entitlement_security_hardening.sql and
-- docs/supabase_free_trial.sql / docs/supabase_revenuecat_billing.sql.
-- There is no migration runner: apply by hand, then verify with the checks at
-- the bottom. Re-running is safe (create or replace / drop if exists).
--
-- WHY (found in docs/LOGIC-AND-BASES-AUDIT-2026-10-28.md, P0):
--
-- 1) Free -> Pro self-grant through user_settings.
--    modules/premium.py effective_entitlement() upgrades a Free account to Pro
--    when user_settings.settings -> 'referral_program' ->> 'comp_until' is in
--    the future (modules/referrals.py comp_is_active). The RLS policy
--    user_settings_update_own lets a signed-in user PATCH their OWN settings
--    row with their own JWT and the public anon key, so any user can write
--    comp_until = '2099-01-01' and get Pro for free. The referral credit is
--    written only by the service role (modules/referrals.py
--    grant_referral_credit), so clients never need to write that key.
--
-- 2) Billing identifiers on profiles are client-writable.
--    The existing trigger only protects the `entitlement` column. A user can
--    still PATCH their own profiles row's stripe_customer_id,
--    stripe_subscription_id, revenuecat_* and trial_ends_at. The
--    billing-portal-session Edge Function opens the Stripe portal for
--    profiles.stripe_customer_id, so pointing it at another customer's id
--    would open that customer's portal. These columns are written only by the
--    verified webhooks (service role).
--
-- Both guards use the same privilege test as the existing hardening:
-- postgres, supabase_admin and service_role (the webhooks, the referral
-- credit, the sweeps) pass untouched; everyone else is constrained.
--
-- Client behavior after this migration:
--   * user_settings: any client write that includes or omits 'referral_program'
--     keeps the stored server value (or none). Other keys behave as before.
--   * profiles: a client UPDATE that changes any server-owned column raises
--     'Profile billing fields are managed outside the client app.'; client
--     INSERTs get those columns reset to null. Upserts that do not send these
--     columns (the app's account_store.upsert_profile) are unaffected.

-- ---------------------------------------------------------------------------
-- 1) user_settings.settings -> 'referral_program' is server-owned.

create or replace function public.protect_user_settings_server_keys()
returns trigger
language plpgsql
as $$
declare
    privileged boolean;
    cleaned jsonb;
begin
    privileged := current_user in ('postgres', 'supabase_admin', 'service_role');
    if privileged then
        return new;
    end if;

    cleaned := coalesce(new.settings, '{}'::jsonb) - 'referral_program';
    if tg_op = 'UPDATE' and old.settings ? 'referral_program' then
        cleaned := cleaned || jsonb_build_object('referral_program', old.settings -> 'referral_program');
    end if;
    new.settings := cleaned;
    return new;
end;
$$;

drop trigger if exists user_settings_protect_server_keys on public.user_settings;
create trigger user_settings_protect_server_keys
before insert or update on public.user_settings
for each row execute function public.protect_user_settings_server_keys();

comment on function public.protect_user_settings_server_keys() is
    'Strips client writes to settings.referral_program (server-owned reward state that effective_entitlement trusts). service_role/postgres/supabase_admin are exempt.';

-- ---------------------------------------------------------------------------
-- 2) profiles billing columns are server-owned (extends the entitlement guard).

create or replace function public.prevent_profile_entitlement_client_update()
returns trigger
language plpgsql
as $$
declare
    privileged boolean;
begin
    privileged := current_user in ('postgres', 'supabase_admin', 'service_role');
    if privileged then
        return new;
    end if;

    if tg_op = 'INSERT' then
        new.entitlement := 'free';
        new.stripe_customer_id := null;
        new.stripe_subscription_id := null;
        new.stripe_subscription_status := null;
        new.stripe_price_id := null;
        new.premium_updated_at := null;
        new.stripe_event_id := null;
        new.stripe_event_created_at := null;
        new.revenuecat_app_user_id := null;
        new.revenuecat_event_id := null;
        new.revenuecat_event_type := null;
        new.revenuecat_environment := null;
        new.revenuecat_event_created_at := null;
        new.trial_ends_at := null;
        return new;
    end if;

    if new.entitlement is distinct from old.entitlement then
        raise exception 'Profile entitlement is managed outside the client app.';
    end if;
    if new.stripe_customer_id is distinct from old.stripe_customer_id
       or new.stripe_subscription_id is distinct from old.stripe_subscription_id
       or new.stripe_subscription_status is distinct from old.stripe_subscription_status
       or new.stripe_price_id is distinct from old.stripe_price_id
       or new.premium_updated_at is distinct from old.premium_updated_at
       or new.stripe_event_id is distinct from old.stripe_event_id
       or new.stripe_event_created_at is distinct from old.stripe_event_created_at
       or new.revenuecat_app_user_id is distinct from old.revenuecat_app_user_id
       or new.revenuecat_event_id is distinct from old.revenuecat_event_id
       or new.revenuecat_event_type is distinct from old.revenuecat_event_type
       or new.revenuecat_environment is distinct from old.revenuecat_environment
       or new.revenuecat_event_created_at is distinct from old.revenuecat_event_created_at
       or new.trial_ends_at is distinct from old.trial_ends_at then
        raise exception 'Profile billing fields are managed outside the client app.';
    end if;
    return new;
end;
$$;

-- The trigger itself already exists from the entitlement hardening file;
-- re-create it so this file is self-contained.
drop trigger if exists profiles_prevent_entitlement_client_update on public.profiles;
drop trigger if exists profiles_enforce_entitlement_authority on public.profiles;
create trigger profiles_enforce_entitlement_authority
before insert or update on public.profiles
for each row execute function public.prevent_profile_entitlement_client_update();

comment on function public.prevent_profile_entitlement_client_update() is
    'Forces free entitlement and null billing identifiers on client inserts; blocks client updates to entitlement and Stripe/RevenueCat/trial columns. service_role/postgres/supabase_admin (verified webhooks) are exempt.';

-- ---------------------------------------------------------------------------
-- Verify (run as a signed-in test user via the client SDK, NOT in the SQL
-- editor, which runs as postgres and bypasses the guards):
--   1. supabase.from('user_settings').update({settings: {referral_program: {comp_until: '2099-01-01T00:00:00Z'}}})
--      then GET /v1/me: entitlement must still be 'free'.
--   2. supabase.from('profiles').update({stripe_customer_id: 'cus_x'}) must fail.
--   3. Normal flows still work: link a Sleeper username, save a league, change a
--      preference, complete a Stripe test checkout and see the webhook upgrade.
--
-- Rollback: re-run docs/supabase_entitlement_security_hardening.sql (restores
-- the entitlement-only function) and `drop trigger user_settings_protect_server_keys
-- on public.user_settings;`.
