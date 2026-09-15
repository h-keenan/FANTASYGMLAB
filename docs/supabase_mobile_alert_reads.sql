-- Mobile Alerts read-state (per-user, per-league, per-item).
-- Run in Supabase Dashboard -> SQL Editor after docs/supabase_accounts.sql.
--
-- Contract:
--   - Durable "I've seen this alert" marker, keyed by (user_id, league_id, alert_key)
--   - alert_key is a stable hash of the underlying news item's link — never the
--     raw article content or any football valuation output
--   - RLS fail-closed: auth.uid() = user_id only
--   - Mobile API uses the caller's own access token (anon key + user JWT), never
--     the service-role key — matches services/mobile_api_service.py's auth model
--   - Insert-only: "mark as read" is an idempotent insert; there is no "mark
--     unread" in v1, so no UPDATE/DELETE policy is needed yet
--   - ON DELETE CASCADE with auth.users covers account deletion
--
-- Until this migration is applied, GET /v1/leagues/{id}/alerts still works
-- (every item just reports read: false) and POST .../read fails closed
-- (503, not a crash) — see services/mobile_api_service.py.

create table if not exists public.mobile_alert_reads (
    user_id uuid not null references auth.users(id) on delete cascade,
    league_id text not null,
    alert_key text not null,
    read_at timestamptz not null default now(),
    primary key (user_id, league_id, alert_key)
);

create index if not exists mobile_alert_reads_lookup_idx
    on public.mobile_alert_reads (user_id, league_id);

alter table public.mobile_alert_reads enable row level security;

drop policy if exists mobile_alert_reads_select_own on public.mobile_alert_reads;
create policy mobile_alert_reads_select_own
on public.mobile_alert_reads for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists mobile_alert_reads_insert_own on public.mobile_alert_reads;
create policy mobile_alert_reads_insert_own
on public.mobile_alert_reads for insert
to authenticated
with check (auth.uid() = user_id);

-- No UPDATE/DELETE policy in v1 — read state is insert-only ("mark as read"),
-- there is no "mark unread" action yet.
-- No anon policies — anonymous users cannot access alert read-state.

comment on table public.mobile_alert_reads is
    'Mobile Alerts read markers. Identity rows only (no football output); RLS auth.uid()=user_id.';
