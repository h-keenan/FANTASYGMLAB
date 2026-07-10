-- DynastyGM premium entitlement migration.
-- Run this in Supabase Dashboard -> SQL Editor after the account tables exist.
-- The app reads public.profiles.entitlement with the authenticated anon-key session.
-- Do not put service-role keys or private credentials in the app.

alter table public.profiles
    add column if not exists entitlement text not null default 'free';

update public.profiles
set entitlement = 'free'
where entitlement is null or entitlement not in ('free', 'premium');

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'profiles_entitlement_check'
          and conrelid = 'public.profiles'::regclass
    ) then
        alter table public.profiles
            add constraint profiles_entitlement_check
            check (entitlement in ('free', 'premium'));
    end if;
end $$;

comment on column public.profiles.entitlement is
    'DynastyGM account entitlement. Allowed values: free, premium.';

create or replace function public.prevent_profile_entitlement_client_update()
returns trigger
language plpgsql
as $$
begin
    if current_user not in ('postgres', 'supabase_admin')
       and new.entitlement is distinct from old.entitlement then
        raise exception 'Profile entitlement is managed outside the client app.';
    end if;
    return new;
end;
$$;

drop trigger if exists profiles_prevent_entitlement_client_update on public.profiles;
create trigger profiles_prevent_entitlement_client_update
before update on public.profiles
for each row execute function public.prevent_profile_entitlement_client_update();
