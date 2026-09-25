-- Durable product analytics event log (modules/launch_analytics.py write path,
-- modules/founder_analytics.py read path for the Founder Analytics dashboard).
-- Run in Supabase Dashboard -> SQL Editor. Independent of docs/supabase_accounts.sql
-- (no foreign key onto profiles/auth.users — see "Identity" below).
--
-- Contract:
--   - Storage-backend migration only. This does not change what gets
--     tracked (modules.launch_analytics.TRACKED_EVENTS / DECISION_EVENTS /
--     PREMIUM_EVENTS are unchanged) — only where events are durably stored.
--   - One row per analytics event, written by modules.launch_analytics.track_event
--     on a background thread (best-effort, fire-and-forget — never blocks
--     the caller, never raises). The existing host-local JSONL
--     (data/launch_analytics.jsonl) is written independently and remains a
--     fail-open cache/fallback: if this table is missing, unreachable, or
--     write fails, analytics keeps working exactly as it does today
--     (JSONL-only). Nothing regresses when Supabase is down.
--   - Identity: session_key/anon_id (pseudonymous session id) and
--     user_key/account_hash (sha256'd account id — never a raw user id,
--     never an email) are the same values already computed in
--     modules.launch_analytics.hash_account_id / anonymous_id before this
--     table ever sees them. Analytics events fire for guest/anonymous
--     sessions as often as authenticated ones, and Founder Analytics reads
--     must see every account's events (not just one), so this is
--     intentionally NOT an auth.uid()-scoped per-user table — there is no
--     foreign key to auth.users and no per-user RLS policy (see below).
--   - props is the same allowlisted, PII-scrubbed JSON object
--     modules.launch_analytics._safe_props already produces for the JSONL
--     line (BLOCKED_PROP_KEYS/ALLOWED_PROP_KEYS enforced before either
--     write path ever sees it) — this table adds no new fields to what is
--     tracked or retained.
--   - Access: service_role only, from the backend process
--     (modules/launch_analytics.py for writes, modules/founder_analytics.py
--     for reads) — never a user's own JWT, never a client-side call. RLS is
--     enabled with NO policies (matches docs/supabase_push_notification_log.sql):
--     service_role bypasses RLS entirely; no authenticated/anon access is
--     granted or intended.
--   - Retention: modules.launch_analytics.prune_expired_events already
--     prunes the local JSONL at RETENTION_DAYS (120d); this table has no
--     automatic prune yet (left for a later pass, same "basic first"
--     posture as docs/supabase_push_notification_log.sql) — unbounded
--     growth at Founder Beta scale is fine (see VOLUME_MODEL in
--     modules/launch_analytics.py), a scheduled delete-older-than job can
--     be added later without any app-code change.
--
-- Until this migration is applied, analytics keeps working exactly as it
-- does today — the write-through and the Founder Analytics read both fail
-- soft to host-local JSONL only.

create table if not exists public.analytics_events (
    id bigint generated always as identity primary key,
    event text not null,
    event_version integer not null default 2,
    ts double precision not null,
    occurred_at timestamptz not null default now(),
    build text not null default '',
    environment text not null default '',
    session_key text not null default '',
    anon_id text not null default '',
    user_key text not null default '',
    account_hash text not null default '',
    props jsonb not null default '{}'::jsonb,
    inserted_at timestamptz not null default now()
);

-- Window queries (Founder Analytics WINDOWS: 24h/7d/30d/all) filter/sort on ts.
create index if not exists analytics_events_ts_idx
    on public.analytics_events (ts);

-- Per-event-type aggregation (feature adoption, health/error rollups) scoped
-- to a time window.
create index if not exists analytics_events_event_ts_idx
    on public.analytics_events (event, ts);

alter table public.analytics_events enable row level security;

-- No policies: service_role bypasses RLS entirely, and this table is never
-- read or written by an authenticated/anon client (see "Access" above).

comment on table public.analytics_events is
    'Durable product analytics event log (write-through from modules.launch_analytics.track_event), service_role-only; host-local JSONL remains a fail-open fallback/cache. Does not change what is tracked — storage backend only.';
