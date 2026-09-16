-- Dedup log for the automated push-trigger sweep (modules/push_triggers.py).
-- Run in Supabase Dashboard -> SQL Editor after docs/supabase_push_tokens.sql.
--
-- Contract:
--   - One row per (user_id, recommendation_id) actually pushed. The sweep
--     checks for an existing row before sending and inserts one right after
--     a successful send, so the same recommendation is never pushed twice.
--     An item naturally re-qualifies once its recommendation_id changes
--     (roster/league state actually changed enough to produce a new id).
--   - Written only by the push-trigger sweep job (service_role), which runs
--     outside any user's session — no user-facing RLS policy is needed and
--     none is granted (no authenticated/anon access at all).
--   - Unbounded growth is fine at this scale; if it ever matters, rows older
--     than a few weeks can be deleted on a schedule — not required for the
--     "basic" trigger this backs.

create table if not exists public.push_notification_log (
    user_id uuid not null references auth.users(id) on delete cascade,
    recommendation_id text not null,
    league_id text not null default '',
    sent_at timestamptz not null default now(),
    primary key (user_id, recommendation_id)
);

alter table public.push_notification_log enable row level security;

-- No policies: service_role bypasses RLS entirely, and this table is never
-- read or written by an authenticated/anon client.

comment on table public.push_notification_log is
    'Dedup log for the automated push-trigger sweep — one row per (user_id, recommendation_id) actually pushed, service_role-only.';
