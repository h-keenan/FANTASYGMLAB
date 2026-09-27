-- Trade Outcomes — quiet "did it actually work?" result columns.
-- Run in Supabase Dashboard -> SQL Editor after docs/supabase_trade_outcomes.sql.
--
-- Why a separate follow-up file rather than editing that migration in
-- place: same pattern as docs/supabase_gm_targets_untouchable.sql following
-- docs/supabase_gm_targets.sql — this is additive, applied to whatever
-- state the table is already in.
--
-- Contract addition (see modules/trade_outcome_results.py for the compute
-- side and services/mobile_api_service.py's GET /v1/trade-outcomes/history
-- for the read side):
--   - result_summary jsonb — null until computed; a small object describing
--     whichever real signals were available (production PPR points since
--     the trade, value_score trend) and, only when a real signal cleared a
--     conservative threshold, a verdict + confidence. Never a forced/fake
--     verdict — see modules/trade_outcome_results.py's docstring.
--   - result_computed_at timestamptz — set once, whether or not a verdict
--     was reached, so a row that can never be resolved (e.g. shared before
--     this feature existed, so trade_summary carries no player_id) isn't
--     retried by the sweep forever.
--   - Both are written only by the service-role result sweep (bypasses RLS
--     by design, same as followup_pushed_at already does) — no new RLS
--     policy needed, the existing select-own policy already covers reading
--     these two columns back.

alter table public.trade_outcomes
    add column if not exists result_summary jsonb,
    add column if not exists result_computed_at timestamptz;

create index if not exists trade_outcomes_result_pending_idx
    on public.trade_outcomes (outcome, outcome_recorded_at, result_computed_at);

comment on column public.trade_outcomes.result_summary is
    'Computed by modules.trade_outcome_results (service-role only): real production/value-score signal since the trade, and a verdict only when a real threshold was cleared. Null until computed or when insufficient real signal exists.';

comment on column public.trade_outcomes.result_computed_at is
    'Set once by the result sweep, whether or not a verdict was reached — prevents re-evaluating a permanently-inconclusive row every sweep.';
