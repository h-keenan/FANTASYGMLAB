-- Roster % snapshots: one row per (player_id, source, snapshot_date).
-- Run in Supabase Dashboard -> SQL Editor. Additive only.
-- Written by the daily job (scripts/run_roster_pct_snapshot.py, service-role),
-- read by modules.roster_pct_history.get_roster_pct_trend. Rows older than
-- ~400 days are pruned by the same job. RLS on, no policies (service-role only),
-- same pattern as docs/supabase_player_rating_snapshots.sql.

create table if not exists public.roster_pct_snapshots (
    player_id text not null,
    source text not null,
    snapshot_date date not null,
    roster_pct double precision not null,
    sleeper_trending_adds integer,
    computed_at timestamptz not null default now(),
    primary key (player_id, source, snapshot_date),
    constraint roster_pct_snapshots_pct_range_check
        check (roster_pct >= 0 and roster_pct <= 100)
);

create index if not exists roster_pct_snapshots_date_idx
    on public.roster_pct_snapshots (snapshot_date);

alter table public.roster_pct_snapshots enable row level security;

comment on table public.roster_pct_snapshots is
    'Daily public roster % (and Sleeper 24h trending adds when available) per player, service_role-only. See modules/roster_pct_history.py.';
