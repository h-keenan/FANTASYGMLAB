-- Push safety: per-device timezone for quiet hours.
-- Run by hand in Supabase Dashboard -> SQL Editor (no migration runner).
--
-- Graceful degradation when NOT applied:
--   - POST /v1/push/register retries without the timezone column, so token
--     registration keeps working.
--   - The sweep's timezone read errors and every user is treated as
--     America/New_York for quiet hours (22:00-08:00).
-- The weekly cap needs no SQL: it counts push_notification_log rows by
-- distinct sent_at in the last 7 days (a batched push is one insert).
-- Per-category toggles (team_situation, trade_followup, lineup_lock,
-- waiver_reminder; the last two need no SQL) live in the existing
-- user_settings.settings.push_categories JSON; no schema change.

alter table public.push_tokens
    add column if not exists timezone text not null default '';

comment on column public.push_tokens.timezone is
    'IANA timezone reported by the device (e.g. America/Chicago); empty = unknown, sweep assumes America/New_York.';

-- Helps the cap count query.
create index if not exists push_notification_log_user_sent_idx
    on public.push_notification_log (user_id, sent_at desc);
