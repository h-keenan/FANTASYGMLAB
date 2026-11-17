-- Automated prospect ingest columns (scripts/run_college_prospect_ingest.py).
-- Run once in Supabase SQL Editor after docs/supabase_college_scouting.sql.
-- Idempotent. Until applied, the ingest upserts base columns only and skips
-- post-draft retirement; the app keeps working (fail-soft).
-- Rows are never deleted: drafted prospects are flagged and hidden, because a
-- delete would cascade to users' scouting_reports / prospect_watchlist.

alter table public.college_prospects add column if not exists source text;
alter table public.college_prospects add column if not exists source_url text;
alter table public.college_prospects add column if not exists ingested_at timestamptz;
alter table public.college_prospects add column if not exists drafted boolean not null default false;
alter table public.college_prospects add column if not exists nfl_team text;
alter table public.college_prospects add column if not exists draft_round smallint;
alter table public.college_prospects add column if not exists draft_pick smallint;
alter table public.college_prospects add column if not exists nfl_gsis_id text;
alter table public.college_prospects add column if not exists sleeper_player_id text;
