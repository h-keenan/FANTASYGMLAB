-- Database-level backstop for the Free-tier saved-league cap.
-- Run once in Supabase Dashboard -> SQL Editor. Safe to re-run.
--
-- Why: the API (POST /v1/leagues/save) already refuses a 2nd league for Free
-- accounts, but saved_leagues is writable by the user's own token under RLS, so
-- a direct Supabase client could skip the app check. This trigger enforces the
-- same cap in the database.
--
-- Rules (mirror modules/saved_leagues.py):
--   * Free: at most 1 saved league.
--   * Pro ('premium'/'pro') and Front Office: no database cap (the API applies
--     its own limits for those tiers).
--   * Re-saving a league the user already has (an upsert/update) is always allowed.
--   * Existing rows are never touched or deleted; only NEW inserts are checked.
--   * profiles.entitlement is already protected from client edits by
--     prevent_profile_entitlement_client_update(), so it can be trusted here.
--
-- To remove: drop trigger saved_leagues_enforce_free_cap on public.saved_leagues;
--            drop function public.enforce_saved_league_cap();

create or replace function public.enforce_saved_league_cap()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    tier text;
    existing_count integer;
begin
    -- Upsert of a league the user already holds is an update, not a new league.
    if exists (
        select 1 from public.saved_leagues
        where user_id = new.user_id and league_id = new.league_id
    ) then
        return new;
    end if;

    select coalesce(entitlement, 'free') into tier
    from public.profiles
    where user_id = new.user_id;

    if coalesce(tier, 'free') in ('premium', 'pro', 'front_office') then
        return new;
    end if;

    select count(*) into existing_count
    from public.saved_leagues
    where user_id = new.user_id;

    if existing_count >= 1 then
        raise exception 'Free accounts can save 1 league. Upgrade to add more.'
            using errcode = 'P0001';
    end if;

    return new;
end;
$$;

drop trigger if exists saved_leagues_enforce_free_cap on public.saved_leagues;
create trigger saved_leagues_enforce_free_cap
before insert on public.saved_leagues
for each row execute function public.enforce_saved_league_cap();
