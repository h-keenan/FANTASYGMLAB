-- Account deletion hardening. Additive and idempotent. Run by hand in the Supabase SQL editor.
-- Prerequisites: docs/supabase_accounts.sql, supabase_stripe_billing.sql, supabase_revenuecat_billing.sql,
-- supabase_billing_edge.sql, supabase_analytics_events.sql, supabase_feedback.sql.
-- Then redeploy the edge function:  supabase functions deploy delete-account
--
-- Policy: delete personal data and referral links; KEEP payment/subscription records but anonymized
-- (no name, no email, no user id); anonymize analytics; and make sure no deletion path can silently skip
-- cancelling the subscription.

-- 1) Billing snapshot kept after deletion. Service role only. No name, no email.
create table if not exists public.deleted_account_billing (
    id bigint generated always as identity primary key,
    user_ref text not null,                      -- sha256('billing-ref:' || user_id); not reversible without the id
    stripe_customer_id text,
    stripe_subscription_id text,
    stripe_subscription_status text,
    stripe_price_id text,
    revenuecat_app_user_id text,
    entitlement text,
    deleted_at timestamptz not null default now(),
    -- true when a live Stripe subscription may still exist: ops must cancel it by hand if
    -- stripe_cancel_confirmed is still false.
    needs_stripe_cancel boolean not null default false,
    stripe_cancel_confirmed boolean not null default false,
    stripe_customer_anonymized boolean not null default false,
    handled_at timestamptz
);

create index if not exists deleted_account_billing_user_ref_idx on public.deleted_account_billing (user_ref);
create index if not exists deleted_account_billing_unhandled_idx
    on public.deleted_account_billing (deleted_at) where needs_stripe_cancel and not stripe_cancel_confirmed;

alter table public.deleted_account_billing enable row level security;
revoke all on table public.deleted_account_billing from anon, authenticated;
grant select, insert, update on table public.deleted_account_billing to service_role;

comment on table public.deleted_account_billing is
    'Anonymized payment/subscription records kept after account deletion. Rows with needs_stripe_cancel and not stripe_cancel_confirmed are deletions that bypassed the delete-account function: cancel the Stripe subscription manually.';

-- 2) Whatever deletes the account (edge function, the old delete_user RPC, the dashboard), the profile row is
--    removed by cascade, and this trigger records any billing it held and flags it for cancellation.
create or replace function public.capture_billing_on_profile_delete()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    has_billing boolean;
begin
    has_billing := coalesce(old.stripe_customer_id, '') <> ''
        or coalesce(old.stripe_subscription_id, '') <> ''
        or coalesce(old.revenuecat_app_user_id, '') <> '';
    if has_billing then
        insert into public.deleted_account_billing (
            user_ref, stripe_customer_id, stripe_subscription_id, stripe_subscription_status, stripe_price_id,
            revenuecat_app_user_id, entitlement, needs_stripe_cancel
        ) values (
            encode(sha256(convert_to('billing-ref:' || old.user_id::text, 'UTF8')), 'hex'),
            nullif(old.stripe_customer_id, ''), nullif(old.stripe_subscription_id, ''),
            old.stripe_subscription_status, old.stripe_price_id,
            nullif(old.revenuecat_app_user_id, ''), old.entitlement,
            coalesce(old.stripe_customer_id, '') <> '' or coalesce(old.stripe_subscription_id, '') <> ''
        );
    end if;
    return old;
end;
$$;

revoke all on function public.capture_billing_on_profile_delete() from public, anon, authenticated;

drop trigger if exists profiles_capture_billing_on_delete on public.profiles;
create trigger profiles_capture_billing_on_delete
    before delete on public.profiles
    for each row execute function public.capture_billing_on_profile_delete();

-- 3) Anonymize the records that are kept. Called by the delete-account edge function (service role) just
--    before the auth user is removed. Idempotent.
create or replace function public.anonymize_deleted_user(
    p_user_id uuid,
    p_analytics_hashes text[] default '{}',
    p_feedback_hashes text[] default '{}'
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    uid text := p_user_id::text;
    tombstone text := 'deleted:' || left(encode(sha256(convert_to('referral:' || uid, 'UTF8')), 'hex'), 12);
    referrers int := 0;
    referred int := 0;
begin
    -- Referrers: keep the count (idempotency + comp already granted) but replace the deleted user's id.
    update public.user_settings us
       set settings = jsonb_set(
               us.settings,
               '{referral_program,referred_user_ids}',
               (select coalesce(jsonb_agg(case when e = to_jsonb(uid) then to_jsonb(tombstone) else e end), '[]'::jsonb)
                  from jsonb_array_elements(us.settings -> 'referral_program' -> 'referred_user_ids') e)
           )
     where jsonb_typeof(us.settings -> 'referral_program' -> 'referred_user_ids') = 'array'
       and (us.settings -> 'referral_program' -> 'referred_user_ids') ? uid;
    get diagnostics referrers = row_count;

    -- Users this person referred: drop the link back to the deleted referrer.
    update public.user_settings us
       set settings = jsonb_set(us.settings, '{referral_attribution,referrer_user_id}', '""'::jsonb)
     where us.settings -> 'referral_attribution' ->> 'referrer_user_id' = uid;
    get diagnostics referred = row_count;

    -- Payment records stay; the user id on them does not.
    update public.billing_webhook_events set user_id = '' where user_id = uid;

    -- Analytics: unlink rows from the account (and the device/session ids that tie them together).
    if coalesce(array_length(p_analytics_hashes, 1), 0) > 0 then
        update public.analytics_events
           set user_key = '', account_hash = '', anon_id = '', session_key = ''
         where account_hash = any(p_analytics_hashes) or user_key = any(p_analytics_hashes);
    end if;

    -- Feedback: delete rows that carry the id, strip the account hash from anonymous ones.
    delete from public.feedback_reports where user_id = p_user_id;
    if coalesce(array_length(p_feedback_hashes, 1), 0) > 0 then
        update public.feedback_reports
           set context = context - 'account_hash'
         where context ->> 'account_hash' = any(p_feedback_hashes);
    end if;

    return jsonb_build_object('referrers_updated', referrers, 'referred_updated', referred);
end;
$$;

revoke all on function public.anonymize_deleted_user(uuid, text[], text[]) from public, anon, authenticated;
grant execute on function public.anonymize_deleted_user(uuid, text[], text[]) to service_role;

-- 4) The old client-callable RPC skipped Stripe entirely. Close it (audit H2). The trigger in (2) is the backstop
--    for any other path.
do $$
begin
    if exists (select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace
               where n.nspname = 'public' and p.proname = 'delete_user') then
        execute 'revoke all on function public.delete_user() from public, anon, authenticated';
    end if;
end
$$;

-- Ops check: deletions that may still be billing.
--   select * from public.deleted_account_billing where needs_stripe_cancel and not stripe_cancel_confirmed;
