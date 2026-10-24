-- Games: league Pick'em picks. Run in Supabase Dashboard -> SQL Editor
-- (manual; no migration runner). Safe to re-run.
--
-- One row per user per league matchup per week. Only the pick is stored;
-- results are graded from real Sleeper scores when read, so nothing here can
-- drift from the truth. No money, no prizes.
--
-- Contract:
--   - A signed-in user can read, insert, update and delete only their own rows.
--   - Members never read each other's rows (that would reveal picks before the
--     weekly lock). The season leaderboard is built server-side with the
--     service role and returns graded totals only.
--   - The API checks league membership, the current week and the lock before
--     it writes; RLS only guarantees ownership.
--
-- Until applied, the API reports Pick'em as unavailable and clients show a
-- short "coming soon" state. The Season Simulator needs no tables.

create table if not exists public.games_pickem_picks (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    league_id text not null check (char_length(league_id) <= 64),
    season text not null check (char_length(season) <= 8),
    week integer not null check (week between 1 and 30),
    matchup_id text not null check (char_length(matchup_id) <= 16),
    picked_roster_id text not null check (char_length(picked_roster_id) <= 16),
    picker_roster_id text not null check (char_length(picker_roster_id) <= 16),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, league_id, season, week, matchup_id)
);

create index if not exists games_pickem_picks_league_idx
    on public.games_pickem_picks (league_id, season, week);

alter table public.games_pickem_picks enable row level security;

drop policy if exists games_pickem_picks_select_own on public.games_pickem_picks;
create policy games_pickem_picks_select_own
on public.games_pickem_picks for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists games_pickem_picks_insert_own on public.games_pickem_picks;
create policy games_pickem_picks_insert_own
on public.games_pickem_picks for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists games_pickem_picks_update_own on public.games_pickem_picks;
create policy games_pickem_picks_update_own
on public.games_pickem_picks for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists games_pickem_picks_delete_own on public.games_pickem_picks;
create policy games_pickem_picks_delete_own
on public.games_pickem_picks for delete
to authenticated
using (auth.uid() = user_id);
