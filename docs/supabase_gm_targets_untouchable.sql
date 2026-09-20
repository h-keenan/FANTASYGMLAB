-- GM Targets: add an "untouchable" flag (#232 follow-up).
-- Run in Supabase Dashboard -> SQL Editor after docs/supabase_gm_targets.sql.
--
-- Why: GM Targets was a passive watchlist with no way to tell the trade
-- engine "never ship this player away." This adds a per-target boolean the
-- caller can toggle after the row already exists, so it also adds the one
-- RLS policy the original migration deliberately left out (v1 was
-- delete+insert only; toggling an existing row's flag needs an update path).
--
-- Contract addition:
--   - untouchable boolean, default false — same identity/RLS rules as the
--     rest of the row (auth.uid() = user_id)
--   - Toggling reuses the existing upsert-on-conflict write path (Postgres
--     INSERT ... ON CONFLICT DO UPDATE), which requires UPDATE privileges
--     on the conflict path even though the app never issues a bare UPDATE
--   - Trade idea generation treats an untouchable target as a hard-blocked
--     outgoing asset (modules.trade_ideas._is_core_or_protected_starter),
--     the same mechanism that already protects a team's core starters

alter table public.gm_targets
    add column if not exists untouchable boolean not null default false;

drop policy if exists gm_targets_update_own on public.gm_targets;
create policy gm_targets_update_own
on public.gm_targets for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

comment on column public.gm_targets.untouchable is
    'User-set: never surface this player in an outgoing (send) trade package.';
