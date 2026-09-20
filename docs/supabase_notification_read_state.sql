-- Notification Center durable read/dismiss state (roadmap P1: "Durable
-- Alerts state" — read/dismiss should survive across devices/sessions).
-- Run in Supabase Dashboard -> SQL Editor after docs/supabase_accounts.sql.
--
-- Contract:
--   - modules/notification_center.py's read/dismiss tracking is otherwise
--     Streamlit-session-only (lost on refresh/new device) — this table is
--     an additive durability layer, not a replacement. Session behavior for
--     signed-out/guest users is unchanged.
--   - Row identity: (user_id, league_id, notification_id) — notification_id
--     is the same stable alias modules.notification_center.attention_aliases
--     already produces; never a football/valuation value.
--   - dismissed defaults false: a row's mere existence means "read"; an
--     explicit dismiss sets dismissed=true. mark_notification_read's own
--     upsert never includes the `dismissed` column, so it can't regress an
--     already-dismissed row back to false.
--   - RLS fail-closed: auth.uid() = user_id only. No anon policies.
--   - UPDATE policy is required (not just insert): re-marking an existing
--     row's `dismissed` flag is an upsert-on-conflict, which needs UPDATE
--     privileges under RLS even though the app never issues a bare UPDATE.
--   - ON DELETE CASCADE with auth.users covers account deletion.
--
-- Until this migration is applied, read/dismiss state keeps working exactly
-- as it does today (Streamlit session only) — hydration and the durable
-- write-through both fail soft.

create table if not exists public.notification_read_state (
    user_id uuid not null references auth.users(id) on delete cascade,
    league_id text not null,
    notification_id text not null,
    dismissed boolean not null default false,
    updated_at timestamptz not null default now(),
    primary key (user_id, league_id, notification_id)
);

create index if not exists notification_read_state_lookup_idx
    on public.notification_read_state (user_id, league_id);

alter table public.notification_read_state enable row level security;

drop policy if exists notification_read_state_select_own on public.notification_read_state;
create policy notification_read_state_select_own
on public.notification_read_state for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists notification_read_state_insert_own on public.notification_read_state;
create policy notification_read_state_insert_own
on public.notification_read_state for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists notification_read_state_update_own on public.notification_read_state;
create policy notification_read_state_update_own
on public.notification_read_state for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

-- No DELETE policy — dismissed state degrades to session-only if a row is
-- ever manually removed, never a crash.
-- No anon policies — anonymous/guest sessions stay session-only by design.

comment on table public.notification_read_state is
    'Durable read/dismiss markers for the Notification Center. Identity + one flag only; RLS auth.uid()=user_id.';
