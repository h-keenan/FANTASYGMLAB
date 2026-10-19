-- Community Trade Feed reactions — emoji-only, no comments/replies, by
-- design (so this feature needs no moderation layer). Run in Supabase
-- Dashboard -> SQL Editor after docs/supabase_trade_outcomes.sql.
--
-- Contract:
--   - One row per (outcome, user, emoji) — a user can react with more than
--     one of the fixed emoji to the same trade, but never twice with the
--     SAME emoji (the unique constraint below; toggled by insert + delete,
--     same "no UPDATE policy" shape as docs/supabase_college_scouting.sql's
--     prospect_watchlist).
--   - outcome_id references trade_outcomes directly. This table does NOT
--     carry (and must never carry) partner_team_name, league_id, or
--     anything else identity-adjacent — only which trade_outcomes row and
--     which emoji. See modules/community_trades.py's module docstring for
--     the full anonymization reasoning this feature follows.
--   - RLS fail-closed: auth.uid() = user_id for every operation, including
--     SELECT. This is NOT a shared/crowdsourced-read table like
--     scouting_reports — a client-side `select true` policy here would
--     expose a raw user_id -> outcome_id reaction mapping to any signed-in
--     client, and would make it impossible to hide a reaction on a trade
--     whose owner has since opted out of the Community Trade Feed. Reaction
--     COUNTS (never raw rows) are read cross-user only by
--     services/mobile_api_service.py's GET /v1/community/trades, via
--     modules/community_trades.py's own service-role access — the same
--     "service role is the only cross-user read path" pattern
--     docs/supabase_trade_outcomes.sql's own trade_outcomes table requires
--     for this same feature (see that module's docstring).
--   - A reaction write always uses the caller's own access token (never
--     service role) — RLS auth.uid() = user_id is sufficient and correct
--     for "add/remove my own reaction."
--
-- Until this migration is applied, reacting fails soft (ok: False, no
-- crash) and the Community Trade Feed simply shows zero reaction counts,
-- matching every other not-yet-migrated Supabase table in this app.

create table if not exists public.community_trade_reactions (
    id uuid primary key default gen_random_uuid(),
    outcome_id uuid not null references public.trade_outcomes(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    emoji text not null,
    created_at timestamptz not null default now(),
    constraint community_trade_reactions_emoji_check
        check (emoji in ('🔥', '😂', '😱', '💀', '📈')),
    constraint community_trade_reactions_unique_per_user_emoji
        unique (outcome_id, user_id, emoji)
);

create index if not exists community_trade_reactions_outcome_idx
    on public.community_trade_reactions (outcome_id);

alter table public.community_trade_reactions enable row level security;

drop policy if exists community_trade_reactions_select_own on public.community_trade_reactions;
create policy community_trade_reactions_select_own
on public.community_trade_reactions for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists community_trade_reactions_insert_own on public.community_trade_reactions;
create policy community_trade_reactions_insert_own
on public.community_trade_reactions for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists community_trade_reactions_delete_own on public.community_trade_reactions;
create policy community_trade_reactions_delete_own
on public.community_trade_reactions for delete
to authenticated
using (auth.uid() = user_id);

-- No UPDATE policy — react/un-react only, mutates via insert + delete.
-- No anon policies — anonymous users cannot access Community Trade
-- Feed reactions.

comment on table public.community_trade_reactions is
    'Community Trade Feed emoji reactions (fixed set, no comments/replies). RLS auth.uid()=user_id on every operation, including SELECT — cross-user aggregate counts are read only by modules/community_trades.py''s own service-role access, never via a client-side select-all policy.';
