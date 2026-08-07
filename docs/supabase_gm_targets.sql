-- Experimental GM Targets (Founder Beta / Premium).
-- Run in Supabase Dashboard -> SQL Editor after docs/supabase_accounts.sql.
--
-- Contract:
--   - Durable league-scoped player preference rows (user watch intent)
--   - Identity is (user_id, league_id, player_id) — never store football output
--   - RLS fail-closed: auth.uid() = user_id only
--   - Streamlit uses anon key + user JWT (no service_role)
--   - Unique primary key makes multi-tab / rerun inserts idempotent
--   - ON DELETE CASCADE with auth.users covers account deletion
--
-- Kill switch (app): DYNASTYGM_EXPERIMENTAL_GM_TARGETS=1
-- Until this migration is applied, the app fails safely (no crash, no writes).
-- Do not execute this migration automatically from Streamlit.

create table if not exists public.gm_targets (
    user_id uuid not null references auth.users(id) on delete cascade,
    league_id text not null,
    player_id text not null,
    source_surface text not null default '',
    created_at timestamptz not null default now(),
    primary key (user_id, league_id, player_id)
);

create index if not exists gm_targets_league_created_idx
    on public.gm_targets (user_id, league_id, created_at desc);

alter table public.gm_targets enable row level security;

drop policy if exists gm_targets_select_own on public.gm_targets;
create policy gm_targets_select_own
on public.gm_targets for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists gm_targets_insert_own on public.gm_targets;
create policy gm_targets_insert_own
on public.gm_targets for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists gm_targets_delete_own on public.gm_targets;
create policy gm_targets_delete_own
on public.gm_targets for delete
to authenticated
using (auth.uid() = user_id);

-- No UPDATE policy — v1 mutates via delete + insert only.
-- No anon policies — anonymous users cannot access GM Targets.

comment on table public.gm_targets is
    'Experimental Premium GM Targets. Preference rows only; RLS auth.uid()=user_id. Cap enforced in app (50/league).';
