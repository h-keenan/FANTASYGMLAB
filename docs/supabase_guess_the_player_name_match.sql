-- "Who is who?" name-match mini-game streak (per-user, durable).
-- Run in Supabase Dashboard -> SQL Editor after docs/supabase_accounts.sql.
--
-- coridian_, 2026-10-19 (Discord pitch): a SECOND daily mini-game alongside
-- "Whose stats are these?" (docs/supabase_guess_the_player.sql) — "you get
-- two players and one player is, you know, a known name that's good, and
-- then one player is kind of an unknown name who maybe has better stats
-- than the known name, and so you pick and choose who is who." A distinct
-- game with its own difficulty/feel, so it gets its OWN streak table here
-- rather than sharing docs/supabase_guess_the_player.sql's
-- guess_the_player_streaks — the two streaks must never mix.
--
-- Contract (identical shape to guess_the_player_streaks, just a separate
-- table/game):
--   - One row per user (primary key user_id) — upserted via PostgREST
--     (on_conflict=user_id, Prefer: resolution=merge-duplicates), not
--     insert-only like mobile_alert_reads.
--   - last_pick_id + last_result make one POST
--     .../guess-the-player/name-match/answer for the SAME day's pick
--     idempotent: a repeat submission for a pick_id already recorded here
--     returns the stored result instead of re-scoring (so
--     reloading/re-submitting can never inflate a streak).
--   - RLS fail-closed: auth.uid() = user_id only, same as every other
--     per-user table in docs/supabase_accounts.sql.
--   - Mobile API uses the caller's own access token (anon key + user JWT),
--     never the service-role key — matches services/mobile_api_service.py's
--     auth model.
--   - ON DELETE CASCADE with auth.users covers account deletion
--     (docs/supabase_delete_account.sql).
--
-- Until this migration is applied, GET /v1/guess-the-player/name-match
-- still works (streak always reports 0/0) and POST .../name-match/answer
-- fails closed (200, ok: false) rather than crashing — see
-- services/mobile_api_service.py.

create table if not exists public.guess_the_player_name_match_streaks (
    user_id uuid primary key references auth.users(id) on delete cascade,
    current_streak integer not null default 0,
    best_streak integer not null default 0,
    last_pick_id text not null default '',
    last_result text not null default '' check (last_result in ('', 'correct', 'incorrect')),
    updated_at timestamptz not null default now()
);

drop trigger if exists guess_the_player_name_match_streaks_set_updated_at on public.guess_the_player_name_match_streaks;
create trigger guess_the_player_name_match_streaks_set_updated_at
before update on public.guess_the_player_name_match_streaks
for each row execute function public.set_updated_at();

alter table public.guess_the_player_name_match_streaks enable row level security;

drop policy if exists guess_the_player_name_match_streaks_select_own on public.guess_the_player_name_match_streaks;
create policy guess_the_player_name_match_streaks_select_own
on public.guess_the_player_name_match_streaks for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists guess_the_player_name_match_streaks_insert_own on public.guess_the_player_name_match_streaks;
create policy guess_the_player_name_match_streaks_insert_own
on public.guess_the_player_name_match_streaks for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists guess_the_player_name_match_streaks_update_own on public.guess_the_player_name_match_streaks;
create policy guess_the_player_name_match_streaks_update_own
on public.guess_the_player_name_match_streaks for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

-- No delete policy — a streak resets to 0 by losing, never by row
-- deletion; account deletion cascades regardless of RLS.
-- No anon policies — anonymous users cannot access streak state.

comment on table public.guess_the_player_name_match_streaks is
    'Who is who? name-match mini-game streak, one row per user. Separate from guess_the_player_streaks (different game). RLS auth.uid()=user_id.';
