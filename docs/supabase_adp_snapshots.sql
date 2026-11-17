-- ADP snapshots (rookie + dynasty/startup) from Fantasy Football Calculator.
-- Run in Supabase Dashboard -> SQL Editor. Idempotent: safe to re-run.
--
-- Written daily by the rookie-adp-snapshot GitHub Actions workflow (service role,
-- modules/rookie_adp.py); read by the API (also service role, fail-soft) and readable
-- by authenticated clients. One row per (source, format, snapshot_date, ffc_player_id),
-- so a same-day re-run replaces that day's rows and past days are never touched
-- (append-only history for trends). Empty FFC windows write nothing.
--   format: 'rookie_1qb' | 'dynasty_1qb'  (no superflex source is approved yet)
--   REAL ADP ONLY. Modeled 'Est. SF' ADP is computed at read time and is never stored here.
--   sleeper_id is NULL when the name could not be mapped exactly; never guessed.
-- Source/licence notes: docs/audits/2026-11-rookie-adp-sources.md

create table if not exists public.adp_snapshots (
    source text not null default 'ffc',
    format text not null,
    qb_format text not null default '1qb',
    snapshot_date date not null,
    ffc_player_id text not null,
    sleeper_id text,
    name text not null,
    position text not null,
    team text,
    adp numeric not null,
    adp_formatted text,
    times_drafted integer,
    high numeric,
    low numeric,
    stdev numeric,
    teams integer,
    total_drafts integer,
    window_start date,
    window_end date,
    fetched_at timestamptz not null default now(),
    primary key (source, format, snapshot_date, ffc_player_id),
    constraint adp_snapshots_format_check check (format in ('rookie_1qb', 'dynasty_1qb')),
    constraint adp_snapshots_qb_format_check check (qb_format = '1qb'),
    constraint adp_snapshots_adp_check check (adp > 0)
);

create index if not exists adp_snapshots_format_player_idx
    on public.adp_snapshots (format, sleeper_id, snapshot_date desc);
create index if not exists adp_snapshots_format_date_idx
    on public.adp_snapshots (format, snapshot_date desc);

alter table public.adp_snapshots enable row level security;

-- Public market data, no per-user content: any signed-in user may read.
-- Writes: service_role only (bypasses RLS); no insert/update/delete policies.
drop policy if exists adp_snapshots_read_authenticated on public.adp_snapshots;
create policy adp_snapshots_read_authenticated
    on public.adp_snapshots
    for select
    to authenticated
    using (true);

comment on table public.adp_snapshots is
    'Daily rookie / dynasty ADP snapshots from Fantasy Football Calculator (credit on screen). Written by the rookie-adp-snapshot workflow; see modules/rookie_adp.py.';
