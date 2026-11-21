-- Scouting reports + shared trades: authors are shown by display name only, and only if they opt in; nobody can
-- read another user's user_id through PostgREST (audit M7). Additive and idempotent. Run by hand in the SQL editor.
--
-- ORDER: deploy the API with this change first (it reads the views below and falls back to the tables while they
-- do not exist). Run this file after. Running it before the deploy only degrades the old API's shared aggregate
-- until the deploy lands.

-- 1) Scouting reports -------------------------------------------------------------------------------------------
alter table public.scouting_reports add column if not exists anonymous boolean not null default true;

-- No user_id. author_display_name is null for anonymous reports. Runs as the view owner, so it can read every row
-- even after the table is restricted to its owner below.
create or replace view public.scouting_reports_public as
select
    r.prospect_id,
    r.grade,
    r.round_projection,
    r.note,
    case when r.anonymous then null else nullif(p.display_name, '') end as author_display_name
from public.scouting_reports r
left join public.profiles p on p.user_id = r.user_id;

revoke all on public.scouting_reports_public from anon;
grant select on public.scouting_reports_public to authenticated;

-- Raw rows (with user_id) are now readable only by their author.
drop policy if exists scouting_reports_select_all on public.scouting_reports;
drop policy if exists scouting_reports_select_own on public.scouting_reports;
create policy scouting_reports_select_own on public.scouting_reports
    for select to authenticated using (auth.uid() = user_id);

-- 2) Community shared trades ------------------------------------------------------------------------------------
-- display_name is already null for anonymous posts (set by the API). The feed view has no user_id; `mine` is
-- computed per caller.
create or replace view public.community_shared_trades_feed as
select
    t.id, t.display_name, t.send, t.receive, t.grade, t.band, t.why, t.hidden, t.created_at,
    (t.user_id = auth.uid()) as mine
from public.community_shared_trades t
where t.hidden = false or t.user_id = auth.uid();

revoke all on public.community_shared_trades_feed from anon;
grant select on public.community_shared_trades_feed to authenticated;

drop policy if exists community_shared_trades_select_visible on public.community_shared_trades;
drop policy if exists community_shared_trades_select_own on public.community_shared_trades;
create policy community_shared_trades_select_own on public.community_shared_trades
    for select to authenticated using (auth.uid() = user_id);

-- Check (should return no rows for a non-owner session):
--   select user_id from public.scouting_reports where user_id <> auth.uid() limit 1;
