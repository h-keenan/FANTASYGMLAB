-- Trade Outcomes — "did this trade happen?" follow-up loop (mobile).
-- Run in Supabase Dashboard -> SQL Editor after docs/supabase_accounts.sql.
--
-- Contract:
--   - One row per shared trade (image or text share from Trade Analyzer or
--     Trade Hub). trade_summary is a compact, already-computed snapshot for
--     redisplay (partner/send/receive/value edge) — never re-derived from
--     live rankings later, so history stays "as it was recommended at the
--     time" even if valuations change.
--   - RLS fail-closed: auth.uid() = user_id only, for select/insert/update.
--   - Mobile API uses the caller's own access token (anon key + user JWT)
--     for insert/select/update, matching services/mobile_api_service.py's
--     auth model elsewhere. The push-trigger sweep
--     (modules/push_triggers.py, scripts/run_push_trigger_sweep.py) runs
--     as its own Render Cron Job with the service-role key, which bypasses
--     RLS by design — it only ever sets followup_pushed_at, never outcome.
--   - No DELETE policy — outcome history is durable once recorded.
--
-- Until this migration is applied, the share flow still works (recording a
-- share fails closed, no crash) and the "did this happen?" surfaces just
-- stay empty rather than erroring.

create table if not exists public.trade_outcomes (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    league_id text not null,
    partner_team_name text not null default '',
    trade_summary jsonb not null default '{}'::jsonb,
    outcome text not null default 'pending',
    shared_at timestamptz not null default now(),
    outcome_recorded_at timestamptz,
    snoozed_until timestamptz,
    followup_pushed_at timestamptz,
    constraint trade_outcomes_outcome_check
        check (outcome in ('pending', 'yes', 'no', 'didnt_send'))
);

create index if not exists trade_outcomes_pending_idx
    on public.trade_outcomes (user_id, outcome, shared_at);

alter table public.trade_outcomes enable row level security;

drop policy if exists trade_outcomes_select_own on public.trade_outcomes;
create policy trade_outcomes_select_own
on public.trade_outcomes for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists trade_outcomes_insert_own on public.trade_outcomes;
create policy trade_outcomes_insert_own
on public.trade_outcomes for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists trade_outcomes_update_own on public.trade_outcomes;
create policy trade_outcomes_update_own
on public.trade_outcomes for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

-- No DELETE policy — this is durable Trade History once answered.
-- No anon policies — anonymous users cannot access Trade Outcomes.

comment on table public.trade_outcomes is
    'Shared-trade follow-up loop: pending -> yes/no/didnt_send. RLS auth.uid()=user_id; followup_pushed_at is set only by the service-role push-trigger sweep.';
