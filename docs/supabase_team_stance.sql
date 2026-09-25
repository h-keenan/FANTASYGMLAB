-- Team Situation (Decision Memory v1 — explicit GM stance declaration).
-- Run in Supabase Dashboard -> SQL Editor after docs/supabase_accounts.sql.
--
-- NAME COLLISION NOTE: unrelated to docs/supabase_decision_memory.sql, which
-- backs modules.decision_memory (a recommendation-change-history log). This
-- table backs modules.team_stance: a single manual, user-declared value —
-- "Rebuilding" / "Competing" / "Balanced" — never inferred, never a history.
--
-- Contract (mirrors docs/supabase_gm_targets.sql):
--   - Durable per-user, per-league row — one stance per (user_id, league_id)
--   - Identity is (user_id, league_id) — never store football output here
--   - RLS fail-closed: auth.uid() = user_id only
--   - Streamlit/mobile use anon key + user JWT (no service_role)
--   - Includes the UPDATE policy from day one (unlike gm_targets' v1) because
--     the only write path here is upsert-on-conflict (user_id, league_id) —
--     a user changing their stance is always an UPDATE under the hood, not
--     an add/remove-only preference list.
--
-- Kill switch (app): DYNASTYGM_EXPERIMENTAL_TEAM_STANCE=1 (default ON)
-- Until this migration is applied, the app fails safely (no crash, no writes,
-- stance reads back as "" / unset).
--
-- Presentation only: this stance never feeds modules.rankings, value_score,
-- or any composite scoring — see modules.trade_ideas.apply_team_stance_framing
-- for the one place it is allowed to touch anything (rationale TEXT).
--
-- "Protect" tags are NOT stored here — modules.gm_targets.gm_targets.untouchable
-- already is that concept; this table intentionally has no player column.

create table if not exists public.team_stance (
    user_id uuid not null references auth.users(id) on delete cascade,
    league_id text not null,
    stance text not null check (stance in ('rebuilding', 'competing', 'balanced')),
    updated_at timestamptz not null default now(),
    primary key (user_id, league_id)
);

alter table public.team_stance enable row level security;

drop policy if exists team_stance_select_own on public.team_stance;
create policy team_stance_select_own
on public.team_stance for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists team_stance_insert_own on public.team_stance;
create policy team_stance_insert_own
on public.team_stance for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists team_stance_update_own on public.team_stance;
create policy team_stance_update_own
on public.team_stance for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists team_stance_delete_own on public.team_stance;
create policy team_stance_delete_own
on public.team_stance for delete
to authenticated
using (auth.uid() = user_id);

-- No anon policies — anonymous users cannot access Team Situation.

comment on table public.team_stance is
    'User-declared team stance (Rebuilding/Competing/Balanced) per league. Presentation-only bias on trade-idea rationale text; never valuation or rankings input. RLS auth.uid()=user_id.';
