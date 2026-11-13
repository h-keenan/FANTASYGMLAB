-- League roster snapshots: weekly ids-only snapshots of every saved league's
-- rosters (starters / bench / IR / taxi) + the traded-pick ledger, for the
-- Fantasy Sim "start of this season" mode and season recaps.
-- Run in Supabase Dashboard -> SQL Editor. Idempotent: safe to re-run.
--
-- Contract (see modules/league_roster_snapshots.py,
-- .github/workflows/league-roster-snapshot.yml, docs/data-capture.md):
--   - One row per (league_id, season, week, slot). slot is 'post_waivers'
--     (Wed) or 'pre_kickoff' (Sun). week is the NFL week, 0 off-season.
--   - rosters / picks are the compact documents; when a league is identical to
--     its previous snapshot IN THE SAME SEASON the row has unchanged = true and
--     rosters/picks NULL (readers carry the earlier document forward). Dedupe
--     never crosses a season, so dropping old seasons cannot orphan a row.
--   - No user_id, username, email or token is stored: only the Sleeper league
--     id, Sleeper roster/owner ids and player ids.
--   - Written and read ONLY with the service-role key (the scheduled sweep and
--     backend readers). RLS is enabled with NO policies and every privilege is
--     revoked from anon/authenticated, so clients cannot read or write it.
--   - Retention: public.prune_league_roster_snapshots(keep_seasons) deletes
--     seasons older than the window and snapshots of leagues that no account
--     has saved for 120+ days (so account deletion eventually removes a
--     league's history once its last saver is gone). The weekly job calls it.

create table if not exists public.league_roster_snapshots (
    league_id text not null,
    season integer not null,
    week integer not null,
    slot text not null,
    captured_at timestamptz not null default now(),
    content_hash text not null,
    unchanged boolean not null default false,
    league_status text not null default '',
    rosters jsonb,
    picks jsonb,
    primary key (league_id, season, week, slot),
    constraint league_roster_snapshots_slot_check
        check (slot in ('post_waivers', 'pre_kickoff')),
    constraint league_roster_snapshots_week_check
        check (week >= 0 and week <= 25),
    constraint league_roster_snapshots_season_check
        check (season >= 2000 and season <= 2100),
    constraint league_roster_snapshots_unchanged_check
        check ((unchanged and rosters is null) or (not unchanged and rosters is not null))
);

create index if not exists league_roster_snapshots_captured_idx
    on public.league_roster_snapshots (captured_at);

alter table public.league_roster_snapshots enable row level security;

-- Fail closed: no policies, and no table privileges for client roles.
-- service_role bypasses RLS and keeps its own grants.
revoke all on table public.league_roster_snapshots from anon, authenticated;

-- Drop-and-recreate the old 1-arg signature if an earlier version of this file
-- was applied, so re-running never leaves two overloads behind.
drop function if exists public.prune_league_roster_snapshots(integer);

create or replace function public.prune_league_roster_snapshots(
    keep_seasons integer default 3,
    orphan_grace_days integer default 120
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    newest integer;
    old_seasons bigint := 0;
    orphans bigint := 0;
begin
    if keep_seasons is null or keep_seasons < 1 then
        raise exception 'keep_seasons must be >= 1';
    end if;
    if orphan_grace_days is null or orphan_grace_days < 0 then
        raise exception 'orphan_grace_days must be >= 0';
    end if;

    select max(season) into newest from public.league_roster_snapshots;
    if newest is null then
        return jsonb_build_object('old_seasons', 0, 'unsaved_leagues', 0);
    end if;

    delete from public.league_roster_snapshots
    where season <= newest - keep_seasons;
    get diagnostics old_seasons = row_count;

    -- Leagues no account has saved any more. Once a league id is no longer in
    -- saved_leagues the sweep stops writing it, so every one of its rows ages
    -- past the grace window (default 120 days: long enough that a league whose
    -- id Sleeper rolled over keeps last season's history for recaps) and is
    -- then removed. This is how an account deletion eventually clears a league
    -- nobody else saved.
    delete from public.league_roster_snapshots s
    where s.captured_at < now() - make_interval(days => orphan_grace_days)
      and not exists (
        select 1 from public.saved_leagues l where l.league_id = s.league_id
      );
    get diagnostics orphans = row_count;

    return jsonb_build_object('old_seasons', old_seasons, 'unsaved_leagues', orphans);
end;
$$;

revoke all on function public.prune_league_roster_snapshots(integer, integer) from public;
revoke all on function public.prune_league_roster_snapshots(integer, integer) from anon, authenticated;
grant execute on function public.prune_league_roster_snapshots(integer, integer) to service_role;

comment on table public.league_roster_snapshots is
    'Weekly ids-only roster snapshots per saved league (service_role only). See modules/league_roster_snapshots.py and docs/data-capture.md.';
