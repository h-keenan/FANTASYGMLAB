-- Fantasy Sim storage (MVP). Run by hand in Supabase Dashboard -> SQL Editor.
-- There is no migration runner: do not assume this has been applied.
--
-- Contract:
--   - Three sim_* tables, no foreign keys into any real table except auth.users.
--   - RLS fail-closed: auth.uid() = user_id for every operation (the API talks
--     to PostgREST with the caller's own JWT, never service_role).
--   - ON DELETE CASCADE with auth.users covers account deletion.
--   - Until applied, /v1/sim/* answers 200 {"reason": "sim_storage_unavailable"}
--     (the code tolerates the tables being missing). Feature flag: SIM_ENABLED.
--   - Retention: sim_prune_old_worlds() deletes worlds untouched for 90 days.
--     It is not scheduled; run it manually or from a cron of your choice.

create table if not exists public.sim_worlds (
    id uuid primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    source_league_id text not null,
    league_name text not null default '',
    mode text not null default 'remaining',
    seed bigint not null,
    engine_version text not null,
    status text not null default 'ready',
    strategy jsonb not null default '{}'::jsonb,
    grade_letter text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists sim_worlds_user_created_idx
    on public.sim_worlds (user_id, created_at desc);

-- Frozen inputs: a world replays identically after real values refresh.
create table if not exists public.sim_snapshots (
    world_id uuid primary key references public.sim_worlds(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    payload jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists public.sim_results (
    world_id uuid primary key references public.sim_worlds(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    payload jsonb not null,
    created_at timestamptz not null default now()
);

alter table public.sim_worlds enable row level security;
alter table public.sim_snapshots enable row level security;
alter table public.sim_results enable row level security;

do $$
declare
    t text;
begin
    foreach t in array array['sim_worlds', 'sim_snapshots', 'sim_results'] loop
        execute format('drop policy if exists %I on public.%I', t || '_select_own', t);
        execute format('create policy %I on public.%I for select to authenticated using (auth.uid() = user_id)', t || '_select_own', t);
        execute format('drop policy if exists %I on public.%I', t || '_insert_own', t);
        execute format('create policy %I on public.%I for insert to authenticated with check (auth.uid() = user_id)', t || '_insert_own', t);
        execute format('drop policy if exists %I on public.%I', t || '_update_own', t);
        execute format('create policy %I on public.%I for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id)', t || '_update_own', t);
        execute format('drop policy if exists %I on public.%I', t || '_delete_own', t);
        execute format('create policy %I on public.%I for delete to authenticated using (auth.uid() = user_id)', t || '_delete_own', t);
    end loop;
end
$$;

-- No anon policies: anonymous users cannot touch sim data.

create or replace function public.sim_prune_old_worlds()
returns integer
language sql
security definer
set search_path = public
as $$
    with gone as (
        delete from public.sim_worlds where updated_at < now() - interval '90 days' returning 1
    )
    select count(*)::integer from gone;
$$;

revoke all on function public.sim_prune_old_worlds() from public, anon, authenticated;

comment on table public.sim_worlds is
    'Fantasy Sim worlds (isolated feature). Own rows only; never joined to real league/valuation tables.';
