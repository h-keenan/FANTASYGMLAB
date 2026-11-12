-- Fantasy Sim: the GM Game storage. Run by hand in Supabase Dashboard -> SQL Editor.
-- There is no migration runner: do not assume this has been applied.
-- Safe to re-run (every statement is idempotent).
--
-- Contract (same rules as docs/supabase_sim.sql):
--   - Three sim_* tables, no foreign keys into any real table except auth.users.
--   - RLS fail-closed: auth.uid() = user_id for every operation (the API talks
--     to PostgREST with the caller's own JWT, never service_role). Inserts into
--     the child tables also require that the game belongs to the caller, so
--     nobody can squat a (game_id, seq) of someone else's game.
--   - sim_games.snapshot is the frozen player pool + teams + schedule, copied
--     at creation and never refreshed. sim_events is the append-only source of
--     truth; sim_week_checkpoints is a rebuildable cache.
--   - Until applied, /v1/sim/games* answers 200 {"reason": "sim_storage_unavailable"}.
--   - Retention: sim_prune_old_games() deletes games untouched for 90 days (not
--     scheduled; run it by hand or from a cron of your choice).

create table if not exists public.sim_games (
    id uuid primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    seed bigint not null,
    engine_version text not null,
    scoring_model text not null default '',
    settings jsonb not null default '{}'::jsonb,
    status text not null default 'drafting',
    current_week integer not null default 0,
    difficulty text not null default 'normal',
    snapshot jsonb not null,
    result jsonb,
    grade_letter text,
    event_count integer not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Re-run safety for later column additions.
alter table public.sim_games add column if not exists scoring_model text not null default '';
alter table public.sim_games add column if not exists result jsonb;
alter table public.sim_games add column if not exists grade_letter text;
alter table public.sim_games add column if not exists event_count integer not null default 0;

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'sim_games_status_check') then
        alter table public.sim_games
            add constraint sim_games_status_check
            check (status in ('drafting', 'in_season', 'playoffs', 'complete'));
    end if;
end
$$;

create index if not exists sim_games_user_created_idx
    on public.sim_games (user_id, created_at desc);

-- Append-only decision/outcome log. (game_id, seq) is the primary key, which is
-- also the optimistic-concurrency guard: two racing writers cannot both insert
-- the same seq, the loser gets a conflict and retries.
create table if not exists public.sim_events (
    game_id uuid not null references public.sim_games(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    seq integer not null,
    week integer not null default 0,
    actor text not null,
    type text not null,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    primary key (game_id, seq)
);

-- Folded state at the start of a week (cache; events stay the source of truth).
create table if not exists public.sim_week_checkpoints (
    game_id uuid not null references public.sim_games(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    week integer not null,
    event_seq integer not null,
    state jsonb not null,
    created_at timestamptz not null default now(),
    primary key (game_id, week)
);

alter table public.sim_games enable row level security;
alter table public.sim_events enable row level security;
alter table public.sim_week_checkpoints enable row level security;

do $$
declare
    t text;
begin
    foreach t in array array['sim_games', 'sim_events', 'sim_week_checkpoints'] loop
        execute format('drop policy if exists %I on public.%I', t || '_select_own', t);
        execute format('create policy %I on public.%I for select to authenticated using (auth.uid() = user_id)', t || '_select_own', t);
        execute format('drop policy if exists %I on public.%I', t || '_delete_own', t);
        execute format('create policy %I on public.%I for delete to authenticated using (auth.uid() = user_id)', t || '_delete_own', t);
    end loop;
end
$$;

-- sim_games: the caller owns the row.
drop policy if exists sim_games_insert_own on public.sim_games;
create policy sim_games_insert_own on public.sim_games
    for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists sim_games_update_own on public.sim_games;
create policy sim_games_update_own on public.sim_games
    for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Child tables: the caller must own both the row and the parent game.
do $$
declare
    t text;
begin
    foreach t in array array['sim_events', 'sim_week_checkpoints'] loop
        execute format('drop policy if exists %I on public.%I', t || '_insert_own', t);
        execute format(
            'create policy %I on public.%I for insert to authenticated with check ('
            || 'auth.uid() = user_id and exists (select 1 from public.sim_games g where g.id = game_id and g.user_id = auth.uid()))',
            t || '_insert_own', t);
        execute format('drop policy if exists %I on public.%I', t || '_update_own', t);
        execute format(
            'create policy %I on public.%I for update to authenticated using (auth.uid() = user_id) '
            || 'with check (auth.uid() = user_id and exists (select 1 from public.sim_games g where g.id = game_id and g.user_id = auth.uid()))',
            t || '_update_own', t);
    end loop;
end
$$;

-- No anon policies: anonymous users cannot touch sim data.

create or replace function public.sim_prune_old_games()
returns integer
language sql
security definer
set search_path = public
as $$
    with gone as (
        delete from public.sim_games where updated_at < now() - interval '90 days' returning 1
    )
    select count(*)::integer from gone;
$$;

revoke all on function public.sim_prune_old_games() from public, anon, authenticated;

comment on table public.sim_games is
    'Fantasy Sim GM game saves (isolated feature). Own rows only; never joined to real league/valuation tables.';
