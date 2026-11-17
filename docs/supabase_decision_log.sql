-- Decision Log: every recommendation a user saw (waiver add, start/sit,
-- stance advice, trade idea) and what they did about it.
-- Run in Supabase Dashboard -> SQL Editor after docs/supabase_accounts.sql.
--
-- Contract (see modules/decision_log.py):
--   - One row per (user_id, rec_key). rec_key is the recommendation's own
--     stable id where one exists (trade idea id, "waiver:<league>:<player>"),
--     so a re-shown recommendation updates the same row instead of piling up.
--   - action: shown -> accepted | ignored | opposite. "opposite" = the user
--     did the reverse of the advice (started the player we said to sit).
--   - snapshot jsonb: what was recommended AT THE TIME (recommended_ids,
--     alternative_ids, label, confidence). Never re-derived later.
--   - result jsonb / graded_at are written only by the service-role grading
--     sweep (scripts/run_trade_outcome_result_sweep.py), same pattern as
--     trade_outcomes.result_summary. Users cannot write them (column grants).
--   - RLS fail-closed: auth.uid() = user_id for select/insert/update. No
--     DELETE policy (durable history; cascades when the account is deleted).
--
-- Until applied, the API fails soft: recording returns ok:false, the track
-- record simply has no decision-log rows, trade results still work.

create table if not exists public.decision_log (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    league_id text not null default '',
    kind text not null,
    rec_key text not null,
    action text not null default 'shown',
    confidence text not null default '',
    snapshot jsonb not null default '{}'::jsonb,
    shown_at timestamptz not null default now(),
    acted_at timestamptz,
    result jsonb,
    graded_at timestamptz,
    constraint decision_log_kind_check
        check (kind in ('trade_idea', 'waiver_add', 'start_sit', 'stance')),
    constraint decision_log_action_check
        check (action in ('shown', 'accepted', 'ignored', 'opposite')),
    constraint decision_log_user_rec_unique unique (user_id, rec_key)
);

create index if not exists decision_log_user_idx
    on public.decision_log (user_id, shown_at desc);
create index if not exists decision_log_ungraded_idx
    on public.decision_log (shown_at) where graded_at is null;

alter table public.decision_log enable row level security;

drop policy if exists decision_log_select_own on public.decision_log;
create policy decision_log_select_own on public.decision_log
for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists decision_log_insert_own on public.decision_log;
create policy decision_log_insert_own on public.decision_log
for insert to authenticated with check ((select auth.uid()) = user_id);

drop policy if exists decision_log_update_own on public.decision_log;
create policy decision_log_update_own on public.decision_log
for update to authenticated
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

-- Users may not write the server-computed grade.
revoke insert (result, graded_at) on public.decision_log from authenticated;
revoke update (result, graded_at) on public.decision_log from authenticated;

comment on table public.decision_log is
    'Recommendations shown to a user and what they did (accepted/ignored/opposite). RLS auth.uid()=user_id; result/graded_at are service-role only.';
