-- "Guess the Player" mini-game streak (per-user, durable).
-- Run in Supabase Dashboard -> SQL Editor after docs/supabase_accounts.sql.
--
-- coridian_, 2026-10-19 (confirmed spec, via Discord): "tracking a record
-- or a streak would be cool" for the Dashboard "Whose stats are these?"
-- card. One row per user (not per-pick) — current_streak/best_streak are
-- durable counters, updated in place on every answer.
--
-- Contract:
--   - One row per user (primary key user_id), like docs/supabase_accounts.sql's
--     profiles/user_settings tables — upserted via PostgREST
--     (on_conflict=user_id, Prefer: resolution=merge-duplicates), not
--     insert-only like mobile_alert_reads.
--   - last_pick_id + last_result make one POST .../guess-the-player/answer
--     for the SAME day's pick idempotent: a repeat submission for a
--     pick_id already recorded here returns the stored result instead of
--     re-scoring (so reloading/re-submitting can never inflate a streak).
--   - RLS fail-closed: auth.uid() = user_id only, same as every other
--     per-user table in docs/supabase_accounts.sql.
--   - Mobile API uses the caller's own access token (anon key + user JWT),
--     never the service-role key — matches services/mobile_api_service.py's
--     auth model.
--   - ON DELETE CASCADE with auth.users covers account deletion
--     (docs/supabase_delete_account.sql).
--
-- Until this migration is applied, GET /v1/guess-the-player still works
-- (streak always reports 0/0) and POST .../answer fails closed (200,
-- ok: false) rather than crashing — see services/mobile_api_service.py.

create table if not exists public.guess_the_player_streaks (
    user_id uuid primary key references auth.users(id) on delete cascade,
    current_streak integer not null default 0,
    best_streak integer not null default 0,
    last_pick_id text not null default '',
    last_result text not null default '' check (last_result in ('', 'correct', 'incorrect')),
    updated_at timestamptz not null default now()
);

drop trigger if exists guess_the_player_streaks_set_updated_at on public.guess_the_player_streaks;
create trigger guess_the_player_streaks_set_updated_at
before update on public.guess_the_player_streaks
for each row execute function public.set_updated_at();

alter table public.guess_the_player_streaks enable row level security;

drop policy if exists guess_the_player_streaks_select_own on public.guess_the_player_streaks;
create policy guess_the_player_streaks_select_own
on public.guess_the_player_streaks for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists guess_the_player_streaks_insert_own on public.guess_the_player_streaks;
create policy guess_the_player_streaks_insert_own
on public.guess_the_player_streaks for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists guess_the_player_streaks_update_own on public.guess_the_player_streaks;
create policy guess_the_player_streaks_update_own
on public.guess_the_player_streaks for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

-- No delete policy — a streak resets to 0 by losing, never by row
-- deletion; account deletion cascades regardless of RLS.
-- No anon policies — anonymous users cannot access streak state.

comment on table public.guess_the_player_streaks is
    'Guess the Player mini-game streak, one row per user. RLS auth.uid()=user_id.';
