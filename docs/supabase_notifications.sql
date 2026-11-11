-- Notification pipeline: delivery audit, Expo receipts, open metrics.
-- Run by hand in Supabase Dashboard -> SQL Editor (no migration runner).
-- See docs/notifications.md for the whole design.
--
-- OPTIONAL. Nothing breaks if this is never applied:
--   * the push sweep only writes/reads notification_events when the repo
--     variable NOTIFICATION_EVENTS=1 is set (set it AFTER running this), and
--     it switches itself off for the run if the table turns out to be missing;
--   * POST /v1/notifications/opened is a silent no-op without the table;
--   * dedupe and the weekly cap still come from push_notification_log
--     (docs/supabase_push_notification_log.sql), which this does not replace;
--   * user-facing preferences (quiet hours, weekly cap, per-league mute,
--     digest) live in user_settings.settings.notification_prefs and need no SQL.

create table if not exists public.notification_events (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    batch_id uuid not null,                       -- one push may carry several items
    league_id text not null default '',
    category text not null default '',
    dedupe_key text not null default '',          -- same id push_notification_log uses
    state text not null default 'sent'
        check (state in ('sent', 'delivered', 'opened', 'failed')),
    title text not null default '',
    body text not null default '',
    deep_link text not null default '',
    tickets jsonb not null default '[]'::jsonb,   -- [{token, id}] for receipt polling
    error text not null default '',               -- Expo error code / failure reason
    created_at timestamptz not null default now(),
    sent_at timestamptz,
    receipt_checked_at timestamptz,
    opened_at timestamptz
);

create index if not exists notification_events_user_created_idx
    on public.notification_events (user_id, created_at desc);
create index if not exists notification_events_batch_idx
    on public.notification_events (batch_id);
-- The receipt poller's scan.
create index if not exists notification_events_receipt_idx
    on public.notification_events (sent_at)
    where state = 'sent' and receipt_checked_at is null;

alter table public.notification_events enable row level security;

-- Users may read their own events (future in-app inbox) and mark them opened.
-- The sweep writes with the service role, which bypasses RLS.
drop policy if exists notification_events_select_own on public.notification_events;
create policy notification_events_select_own on public.notification_events
    for select using (auth.uid() = user_id);

drop policy if exists notification_events_update_own on public.notification_events;
create policy notification_events_update_own on public.notification_events
    for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

comment on table public.notification_events is
    'One row per item in a delivered/failed push: receipts, failures, opens. Written by the push sweep (service_role); dedupe/cap still use push_notification_log.';

-- Retention: events older than ~90 days are not needed. Run occasionally:
--   delete from public.notification_events where created_at < now() - interval '90 days';
