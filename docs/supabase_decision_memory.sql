-- Experimental Decision Memory (Founder Beta / Premium).
-- Run in Supabase Dashboard -> SQL Editor after docs/supabase_accounts.sql.
--
-- Contract:
--   - Durable material DecisionChangeEvent rows + per-league comparison baselines
--   - RLS fail-closed: auth.uid() = user_id only
--   - Streamlit uses anon key + user JWT (no service_role)
--   - Unique (user_id, event_id) makes multi-tab / rerun inserts idempotent
--   - ON DELETE CASCADE with auth.users covers account deletion
--
-- Kill switch (app): DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY=1
-- Until this migration is applied, the app fails safely (no crash, no writes).

create table if not exists public.decision_memory_events (
    user_id uuid not null references auth.users(id) on delete cascade,
    event_id text not null,
    league_id text not null,
    roster_id text not null default '',
    recommendation_id text not null default '',
    event_type text not null default '',
    transition text not null default '',
    reason_code text not null default '',
    category text not null default '',
    target_label text not null default '',
    player_id text not null default '',
    destination text not null default '',
    previous_state jsonb not null default '{}'::jsonb,
    current_state jsonb not null default '{}'::jsonb,
    previous_priority integer,
    current_priority integer,
    priority_band text not null default '',
    confidence_band text not null default '',
    scoring_format text not null default '',
    valuation_lens text not null default '',
    summary_headline text not null default '',
    summary_detail text not null default '',
    why_label text not null default '',
    created_at timestamptz not null default now(),
    primary key (user_id, event_id)
);

create index if not exists decision_memory_events_league_created_idx
    on public.decision_memory_events (user_id, league_id, created_at desc);

create index if not exists decision_memory_events_created_idx
    on public.decision_memory_events (user_id, created_at desc);

create table if not exists public.decision_memory_baselines (
    user_id uuid not null references auth.users(id) on delete cascade,
    league_id text not null,
    roster_id text not null default '',
    context_fingerprint text not null default '',
    scoring_format text not null default '',
    valuation_lens text not null default '',
    material_signatures jsonb not null default '{}'::jsonb,
    prior_snapshots jsonb not null default '{}'::jsonb,
    top_recommendation_id text not null default '',
    updated_at timestamptz not null default now(),
    primary key (user_id, league_id)
);

create index if not exists decision_memory_baselines_updated_idx
    on public.decision_memory_baselines (user_id, updated_at desc);

alter table public.decision_memory_events enable row level security;
alter table public.decision_memory_baselines enable row level security;

-- Events: own rows only
drop policy if exists decision_memory_events_select_own on public.decision_memory_events;
create policy decision_memory_events_select_own
on public.decision_memory_events for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists decision_memory_events_insert_own on public.decision_memory_events;
create policy decision_memory_events_insert_own
on public.decision_memory_events for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists decision_memory_events_update_own on public.decision_memory_events;
create policy decision_memory_events_update_own
on public.decision_memory_events for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists decision_memory_events_delete_own on public.decision_memory_events;
create policy decision_memory_events_delete_own
on public.decision_memory_events for delete
to authenticated
using (auth.uid() = user_id);

-- Baselines: own rows only
drop policy if exists decision_memory_baselines_select_own on public.decision_memory_baselines;
create policy decision_memory_baselines_select_own
on public.decision_memory_baselines for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists decision_memory_baselines_insert_own on public.decision_memory_baselines;
create policy decision_memory_baselines_insert_own
on public.decision_memory_baselines for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists decision_memory_baselines_update_own on public.decision_memory_baselines;
create policy decision_memory_baselines_update_own
on public.decision_memory_baselines for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists decision_memory_baselines_delete_own on public.decision_memory_baselines;
create policy decision_memory_baselines_delete_own
on public.decision_memory_baselines for delete
to authenticated
using (auth.uid() = user_id);

-- No anon policies — anonymous users cannot access Decision Memory.

comment on table public.decision_memory_events is
    'Experimental Premium Decision Memory events. Material transitions only; RLS auth.uid()=user_id.';
comment on table public.decision_memory_baselines is
    'Per-league durable comparison baselines for Decision Memory. Never delete the current baseline for lifecycle correctness.';
