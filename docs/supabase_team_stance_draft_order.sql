-- Team Situation: store the user's draft-order rule next to the stance.
-- Run in Supabase Dashboard -> SQL Editor after docs/supabase_team_stance.sql.
-- Idempotent: safe to run more than once.
--
-- Why: the Commissioner page's "How is your draft order set?" answer
-- (Not sure / Worst record / Lottery) lived only in component state, so it
-- reset on every visit. It is the same kind of per-(user, league) declaration
-- as the stance, so it is stored on the same row, with the same RLS
-- (auth.uid() = user_id) and the same upsert-on-conflict (user_id, league_id)
-- write path. No new table, no new policy.
--
-- Contract:
--   - draft_order_rule: 'unknown' (default) | 'record' | 'lottery'
--     (modules.league_integrity.DRAFT_RULES)
--   - stance becomes nullable: a user can declare a draft-order rule without
--     ever declaring a Team Situation. A null stance reads back as "" (unset),
--     exactly like a missing row (modules.team_stance.normalize_stance).
--   - The existing check (stance in rebuilding/competing/balanced) still
--     applies to every non-null value.
--
-- Until this migration is applied the endpoints fail soft: the rule reads
-- back as 'unknown' and a save reports not_available.

alter table public.team_stance
    alter column stance drop not null;

alter table public.team_stance
    add column if not exists draft_order_rule text not null default 'unknown';

alter table public.team_stance
    drop constraint if exists team_stance_draft_order_rule_check;
alter table public.team_stance
    add constraint team_stance_draft_order_rule_check
    check (draft_order_rule in ('unknown', 'record', 'lottery'));

comment on column public.team_stance.draft_order_rule is
    'User-declared draft-order rule for this league (unknown/record/lottery). Only changes how a flagged team is described on the Commissioner page, never lineup math.';
