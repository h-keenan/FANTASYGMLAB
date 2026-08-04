-- DynastyGM MVP account tables.
-- Run this in Supabase Dashboard -> SQL Editor.
-- The app uses anon-key authenticated requests plus RLS. Do not use service-role keys in the app.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
    user_id uuid primary key references auth.users(id) on delete cascade,
    email text,
    display_name text,
    sleeper_username text,
    entitlement text not null default 'free' check (entitlement in ('free', 'premium')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.saved_leagues (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    sleeper_username text not null default '',
    league_id text not null,
    league_name text not null default '',
    owner_id text not null default '',
    roster_id text not null default '',
    team_id text not null default '',
    is_default boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, league_id)
);

create table if not exists public.user_settings (
    user_id uuid primary key references auth.users(id) on delete cascade,
    settings jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

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

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

drop trigger if exists profiles_prevent_entitlement_client_update on public.profiles;
drop trigger if exists profiles_enforce_entitlement_authority on public.profiles;
create trigger profiles_enforce_entitlement_authority
before insert or update on public.profiles
for each row execute function public.prevent_profile_entitlement_client_update();

drop trigger if exists saved_leagues_set_updated_at on public.saved_leagues;
create trigger saved_leagues_set_updated_at
before update on public.saved_leagues
for each row execute function public.set_updated_at();

drop trigger if exists user_settings_set_updated_at on public.user_settings;
create trigger user_settings_set_updated_at
before update on public.user_settings
for each row execute function public.set_updated_at();

create unique index if not exists saved_leagues_one_default_per_user
on public.saved_leagues (user_id)
where is_default;

alter table public.profiles enable row level security;
alter table public.saved_leagues enable row level security;
alter table public.user_settings enable row level security;

drop policy if exists profiles_select_own on public.profiles;
create policy profiles_select_own
on public.profiles for select
using (auth.uid() = user_id);

drop policy if exists profiles_insert_own on public.profiles;
create policy profiles_insert_own
on public.profiles for insert
with check (auth.uid() = user_id);

drop policy if exists profiles_update_own on public.profiles;
create policy profiles_update_own
on public.profiles for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists profiles_delete_own on public.profiles;
create policy profiles_delete_own
on public.profiles for delete
using (auth.uid() = user_id);

drop policy if exists saved_leagues_select_own on public.saved_leagues;
create policy saved_leagues_select_own
on public.saved_leagues for select
using (auth.uid() = user_id);

drop policy if exists saved_leagues_insert_own on public.saved_leagues;
create policy saved_leagues_insert_own
on public.saved_leagues for insert
with check (auth.uid() = user_id);

drop policy if exists saved_leagues_update_own on public.saved_leagues;
create policy saved_leagues_update_own
on public.saved_leagues for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists saved_leagues_delete_own on public.saved_leagues;
create policy saved_leagues_delete_own
on public.saved_leagues for delete
using (auth.uid() = user_id);

drop policy if exists user_settings_select_own on public.user_settings;
create policy user_settings_select_own
on public.user_settings for select
using (auth.uid() = user_id);

drop policy if exists user_settings_insert_own on public.user_settings;
create policy user_settings_insert_own
on public.user_settings for insert
with check (auth.uid() = user_id);

drop policy if exists user_settings_update_own on public.user_settings;
create policy user_settings_update_own
on public.user_settings for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists user_settings_delete_own on public.user_settings;
create policy user_settings_delete_own
on public.user_settings for delete
using (auth.uid() = user_id);
