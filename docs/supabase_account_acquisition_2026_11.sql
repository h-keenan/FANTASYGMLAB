-- Per-account acquisition record (Phase 1 analytics accuracy, 2026-11).
-- OWNER RUNS THIS BY HAND in Supabase Dashboard -> SQL Editor. Idempotent: safe to re-run.
--
-- What it is: ONE row per Supabase auth user holding the real account creation time, sign-up
-- method (email | google | apple | guest), guest-vs-registered state, and FIRST-touch (utm_*,
-- referrer_host, click id) plus LAST-touch (lt_*) acquisition attribution.
-- Written by modules/account_acquisition.py (service_role, from POST /v1/e) the first time an
-- account sends an analytics event; read by modules/founder_analytics.py for signup reconciliation.
--
-- Why: analytics_events stores only a KEYED HASH of the user id (ANALYTICS_HASH_SALT), so it can
-- never be joined to profiles / billing_webhook_events. This table keys on the raw user_id, so
-- signups, trials and revenue can be cut by acquisition source in SQL without exposing the hash.
--
-- Privacy / security:
--   * RLS enabled. service_role (the backend) bypasses RLS and is the only writer.
--   * A signed-in user may SELECT only their own row; no client INSERT/UPDATE/DELETE policy exists.
--   * Rows are deleted with the account (ON DELETE CASCADE), so account deletion removes them.
--   * No emails, names, IPs or raw URLs: only sanitized tokens the client already sends in analytics.
--   * Billing, entitlements and profiles are NOT touched.
--
-- Until this is applied the app keeps working: the backend write fails soft (retries every 10
-- minutes) and the Founder report shows "reconciliation unavailable".

create table if not exists public.account_acquisition (
    user_id            uuid primary key references auth.users (id) on delete cascade,
    account_created_at timestamptz,
    first_seen_at      timestamptz not null default now(),
    registered_at      timestamptz,
    is_guest           boolean not null default false,
    signup_method      text not null default 'unknown',
    platform           text not null default '',
    -- first touch
    utm_source         text,
    utm_medium         text,
    utm_campaign       text,
    utm_content        text,
    utm_term           text,
    referrer_host      text,
    click_id           text,
    click_id_value     text,
    -- last touch (at signup / registration)
    lt_utm_source      text,
    lt_utm_medium      text,
    lt_utm_campaign    text,
    lt_referrer_host   text,
    lt_click_id        text
);

create index if not exists account_acquisition_first_seen_idx
    on public.account_acquisition (first_seen_at);
create index if not exists account_acquisition_campaign_idx
    on public.account_acquisition (utm_campaign)
    where utm_campaign is not null;

alter table public.account_acquisition enable row level security;

drop policy if exists account_acquisition_select_own on public.account_acquisition;
create policy account_acquisition_select_own
    on public.account_acquisition for select
    to authenticated
    using ((select auth.uid()) = user_id);

comment on table public.account_acquisition is
    'One row per auth user: real signup method/time, guest vs registered, first+last touch attribution. service_role writes only; owner may read own row.';

-- Example owner queries (service role / SQL editor):
--   signups by campaign:  select utm_campaign, signup_method, count(*) from account_acquisition
--                         where not is_guest group by 1, 2 order by 3 desc;
--   attribution -> paid:  select a.utm_campaign, count(*) from account_acquisition a
--                         join profiles p on p.user_id = a.user_id
--                         where p.entitlement in ('premium','front_office') group by 1;
