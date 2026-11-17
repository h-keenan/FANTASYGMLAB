-- Let a dynasty Sim store its off-season as status = 'offseason'.
-- Apply by hand in the Supabase SQL editor. Idempotent; it only replaces the CHECK constraint and never touches rows.
-- Until it is applied the app keeps working: it stores 'in_season' and derives the off-season from game state.

alter table public.sim_games drop constraint if exists sim_games_status_check;

alter table public.sim_games
    add constraint sim_games_status_check
    check (status in ('drafting', 'in_season', 'playoffs', 'offseason', 'complete'));
