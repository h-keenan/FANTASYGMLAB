-- Live projection forward log + weekly scoring reports. Additive only.
-- Run in Supabase Dashboard -> SQL Editor. Written/read by the service role only
-- (modules/live_projection_log.py, scripts/run_live_projection_scoring.py).
-- RLS on, NO policies (no anon / authenticated access), same pattern as
-- docs/supabase_roster_pct_snapshots.sql. Rows older than ~400 days (about one season)
-- are pruned by the weekly scoring job.

create table if not exists public.live_projection_snapshots (
    league_id text not null,
    season integer not null,
    week integer not null,
    roster_a text not null,
    roster_b text not null,
    -- '' = the matchup-level row (win probability); otherwise one starter.
    player_id text not null default '',
    -- real game clock in 5-game-minute steps: 0..11, 12 = overtime, 99 = final.
    clock_bucket smallint not null,
    side text not null,
    position text,
    remaining double precision,
    actual double precision,
    projection double precision,
    projected_final double precision,
    win_prob_a double precision,
    total_a double precision,
    total_b double precision,
    snapshot_at timestamptz not null default now(),
    primary key (league_id, season, week, roster_a, roster_b, player_id, clock_bucket),
    constraint live_projection_snapshots_side_check check (side in ('a', 'b', 'm')),
    constraint live_projection_snapshots_bucket_check check (clock_bucket between 0 and 12 or clock_bucket = 99),
    constraint live_projection_snapshots_wp_check check (win_prob_a is null or (win_prob_a >= 0 and win_prob_a <= 1))
);

create index if not exists live_projection_snapshots_at_idx
    on public.live_projection_snapshots (snapshot_at);
create index if not exists live_projection_snapshots_week_idx
    on public.live_projection_snapshots (season, week);

alter table public.live_projection_snapshots enable row level security;

create table if not exists public.live_projection_reports (
    season integer not null,
    week integer not null,
    scored_at timestamptz not null default now(),
    metrics jsonb not null,
    primary key (season, week)
);

alter table public.live_projection_reports enable row level security;

comment on table public.live_projection_snapshots is
    'Per-starter live projected final and per-matchup win probability, one row per 5 game-minutes of real clock; service_role-only. See modules/live_projection_log.py.';
comment on table public.live_projection_reports is
    'Weekly score of live_projection_snapshots against final results (MAE/bias/Brier/reliability); service_role-only.';
