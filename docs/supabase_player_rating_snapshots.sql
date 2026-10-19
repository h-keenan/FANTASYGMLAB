-- Player Rating History — daily 0-99 overall-rating snapshots per player,
-- for the external content-posting bot's rating-change-history endpoint.
-- Run in Supabase Dashboard -> SQL Editor.
--
-- Contract (see modules/player_rating_history.py for the write/read side,
-- .github/workflows/player-rating-snapshot.yml for the daily job that
-- writes it, and docs/external-api-contract.md for the
-- GET /v1/external/players/{id}/rating-history read contract):
--   - One row per (player_id, snapshot_date) — once per calendar day, not
--     a per-request timestamp. snapshot_date is a `date` (UTC), not a
--     timestamptz, by design: the whole point of this table is "what was
--     yesterday's rating vs today's," not a finer-grained time series.
--   - overall_rating is the exact same 0-99 badge every screen in this app
--     already shows (modules.player_quick_view.overall_ratings_for_pool),
--     computed once a day over the same canonical, no-league-context,
--     whole-universe-of-fantasy-relevant-players pool
--     services/fantasy_content.py's public content feed already builds —
--     never a second, independently-derived rating.
--   - Append-only time series. The daily sweep upserts
--     on_conflict (player_id, snapshot_date) so a same-day re-run is
--     idempotent (replaces today's rows with today's freshly computed
--     ratings), but it NEVER updates a prior day's row, and nothing in
--     this codebase ever deletes a row here.
--   - Real history only exists once this migration has been run AND the
--     scheduled job has actually executed for 2+ days. Before that, the
--     external rating-history endpoint honestly reports
--     status: "insufficient_history" with every comparison field null —
--     it never fabricates a baseline or a delta from nothing.
--   - Written only by the scheduled sweep (service-role key) and read only
--     by the external rating-history endpoint (also service-role, since
--     this is the shared global pool, not scoped to any one user's
--     league) — no authenticated/anon client ever touches this table
--     directly, so RLS is enabled defensively with no policies, same
--     pattern as docs/supabase_push_notification_log.sql.

create table if not exists public.player_rating_snapshots (
    player_id text not null,
    snapshot_date date not null,
    overall_rating integer not null,
    computed_at timestamptz not null default now(),
    primary key (player_id, snapshot_date),
    constraint player_rating_snapshots_rating_range_check
        check (overall_rating >= 0 and overall_rating <= 99)
);

alter table public.player_rating_snapshots enable row level security;

-- No policies: service_role bypasses RLS entirely, and this table is never
-- read or written by an authenticated/anon client.

comment on table public.player_rating_snapshots is
    'Daily 0-99 overall-rating snapshots per player, service_role-only. Append-only time series backing GET /v1/external/players/{id}/rating-history — see modules/player_rating_history.py.';
