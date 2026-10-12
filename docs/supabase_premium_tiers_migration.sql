-- DynastyGM 3-tier pricing migration (Scout / GM Pro / Front Office).
-- Run this in Supabase Dashboard -> SQL Editor after docs/supabase_accounts.sql,
-- docs/supabase_profile_entitlement.sql, and
-- docs/supabase_entitlement_security_hardening.sql already exist.
--
-- `docs/supabase_accounts.sql`'s `create table if not exists` only applies
-- this wider check constraint to a brand-new install; an already-deployed
-- `profiles` table keeps its original ('free', 'premium') constraint until
-- this file is run against it. Additive and safe to re-run.
--
-- Does not change the entitlement authority trigger
-- (prevent_profile_entitlement_client_update) — only verified server-side
-- writes (service_role / the Stripe webhook) can ever set 'pro' or
-- 'front_office'; that guard already exists from the earlier migrations
-- above and is untouched here.
--
-- 'premium' remains a valid, actively-written value: it is the legacy
-- name the webhook still writes for GM Pro (see modules/premium.py's
-- module docstring for why that storage decision was made — mobile's own
-- raw `entitlement == "premium"` checks must not regress). 'pro' is
-- accepted too, for forward-compatibility if a future webhook revision
-- ever writes it directly instead.

do $$
begin
    if exists (
        select 1 from pg_constraint
        where conname = 'profiles_entitlement_check'
          and conrelid = 'public.profiles'::regclass
    ) then
        alter table public.profiles drop constraint profiles_entitlement_check;
    end if;
    alter table public.profiles
        add constraint profiles_entitlement_check
        check (entitlement in ('free', 'premium', 'pro', 'front_office'));
end $$;

comment on column public.profiles.entitlement is
    'DynastyGM account entitlement. Allowed values: free, premium (legacy name for pro), pro, front_office.';
