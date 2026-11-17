-- College prospect stats + profile (powers the prospect detail sheet: Stats and Profile tabs).
-- Run once in Supabase SQL Editor AFTER docs/supabase_college_scouting.sql
-- (and docs/supabase_college_prospects_ingest.sql). Idempotent: safe to re-run.
--
-- Written weekly by .github/workflows/college-prospect-ingest.yml
-- (modules/college_prospect_ingest.py, service role). Read by the API with the
-- caller's own JWT, so RLS gives SELECT to any authenticated user and nothing else.
--
-- NO FABRICATED DATA: every number here comes from College Football Data
-- (collegefootballdata.com); `source` / `source_url` cite it per row. Fantasy
-- points shown in the app are derived from these CFBD stat lines at read time and
-- labelled as such. Until this migration is applied the ingest skips the stats
-- step and the sheet shows "No college stats yet" (fail-soft); nothing breaks.
--
-- One row per prospect (1:1 with college_prospects). Rows are never deleted by the
-- job; deleting a prospect cascades here.
--   seasons   jsonb  [{season, team, passing:{..}, rushing:{..}, receiving:{..}}, ...] newest first
--   advanced  jsonb  {season, ppa:{avg_all, avg_pass, avg_rush, total_all, ...}, usage:{overall, pass, rush, ...}}
--   game_log  jsonb  {season, games:[{week, opponent, passing:{..}, rushing:{..}, receiving:{..}}, ...]}
--   recruiting jsonb {year, stars, rating, national_rank, position_rank, state_rank, city, state, school}

create table if not exists public.college_prospect_stats (
    prospect_id text primary key references public.college_prospects (id) on delete cascade,
    cfbd_player_id text,
    stats_season integer,
    class_year smallint,
    height_in smallint,
    weight_lb smallint,
    hometown text,
    school_logo_url text,
    seasons jsonb not null default '[]'::jsonb,
    advanced jsonb,
    game_log jsonb,
    recruiting jsonb,
    source text,
    source_url text,
    ingested_at timestamptz not null default now()
);

alter table public.college_prospect_stats enable row level security;

drop policy if exists college_prospect_stats_select_authenticated on public.college_prospect_stats;
create policy college_prospect_stats_select_authenticated
on public.college_prospect_stats for select
to authenticated
using (true);

-- No INSERT/UPDATE/DELETE policy: only the service-role ingest job writes.
