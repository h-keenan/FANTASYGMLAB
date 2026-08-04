-- FantasyGM Lab entitlement authority hardening (additive / migration-safe).
-- Run in Supabase Dashboard -> SQL Editor after docs/supabase_accounts.sql
-- and docs/supabase_profile_entitlement.sql.
--
-- Fixes:
-- 1) Client INSERT can no longer self-grant premium.
-- 2) Verified Stripe webhook (role service_role) may update entitlement.
-- Client UPDATE of entitlement remains blocked.

create or replace function public.prevent_profile_entitlement_client_update()
returns trigger
language plpgsql
as $$
declare
    privileged boolean;
begin
    privileged := current_user in ('postgres', 'supabase_admin', 'service_role');
    if tg_op = 'INSERT' then
        if not privileged then
            new.entitlement := 'free';
        end if;
        return new;
    end if;
    if not privileged
       and new.entitlement is distinct from old.entitlement then
        raise exception 'Profile entitlement is managed outside the client app.';
    end if;
    return new;
end;
$$;

drop trigger if exists profiles_prevent_entitlement_client_update on public.profiles;
drop trigger if exists profiles_enforce_entitlement_authority on public.profiles;
create trigger profiles_enforce_entitlement_authority
before insert or update on public.profiles
for each row execute function public.prevent_profile_entitlement_client_update();

comment on function public.prevent_profile_entitlement_client_update() is
    'Forces free entitlement on client inserts and blocks client entitlement updates. service_role/postgres/supabase_admin may change entitlement for verified billing webhooks.';
