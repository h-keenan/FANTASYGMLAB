-- College Football Prospect Scouting — crowdsourced draft-class signal
-- (mobile-first; feeds modules/trade_ideas.py's draft-class-strength calc).
-- Run in Supabase Dashboard -> SQL Editor after docs/supabase_accounts.sql.
--
-- Product shape (coridian_):
--   - SHARED primary system: any signed-in user can leave a scouting grade
--     on a prospect. All grades pool into one shared aggregate per
--     prospect/class — that shared aggregate, never one user's opinion, is
--     what can move draft-class strength (see modules/college_scouting.py).
--   - Personal watchlist layered on top (prospect_watchlist): plain
--     follow/unfollow, no scouting fields duplicated there.
--
-- NO FABRICATED DATA: there is no licensed college recruiting/draft feed
-- wired into this app yet. This migration deliberately seeds zero rows into
-- college_prospects — inventing fictional prospect names/schools would be
-- indistinguishable from real scouting subjects to the people using this
-- screen (see modules/college_scouting.py's "NO FABRICATED DATA" docstring
-- section). The table is real and migration-managed; it starts empty and
-- stays empty until a real prospect data source is loaded into it. Until
-- then, services/mobile_api_service.py's /v1/scouting/prospects returns an
-- empty prospect list and the mobile screen shows its existing "No
-- prospects yet" empty state — never invented rows.
--
-- RLS:
--   - college_prospects: read-only reference data. SELECT for any
--     authenticated user; no INSERT/UPDATE/DELETE policy at all — rows are
--     managed only by this migration (or a future admin tool), never by the
--     app. Not user data, so this is safe to leave world-readable-to-users.
--   - scouting_reports: SELECT is intentionally open to every authenticated
--     user (not just auth.uid() = user_id) — the whole point of this table
--     is a shared, crowdsourced pool; hiding other users' rows would make
--     the aggregate impossible to compute anywhere but a service-role job.
--     INSERT/UPDATE/DELETE remain restricted to the row's own user_id, same
--     as every other per-user table in this app.
--   - prospect_watchlist: fully private, auth.uid() = user_id on every
--     operation — same shape as docs/supabase_gm_targets.sql.
--
-- Until this migration is applied, the scouting/watchlist screens and the
-- crowd-strength signal all fail soft (empty lists / neutral 1.0x
-- multiplier), matching every other Supabase-backed feature in this app —
-- see services/mobile_api_service.py's /v1/scouting/* handlers and
-- modules/college_scouting.py's fetch_* functions.

create table if not exists public.college_prospects (
    id text primary key,
    name text not null,
    position text not null,
    school text not null,
    draft_year integer not null,
    created_at timestamptz not null default now()
);

alter table public.college_prospects enable row level security;

drop policy if exists college_prospects_select_all on public.college_prospects;
create policy college_prospects_select_all
on public.college_prospects for select
to authenticated
using (true);

-- No insert/update/delete policy — this table is migration-managed only.

comment on table public.college_prospects is
    'Shared college prospect catalog. No seed data — real recruiting/draft data only; see modules/college_scouting.py "NO FABRICATED DATA". Read-only to the app; RLS select-all, no app-writable policy.';

-- Intentionally no seed INSERT here. When a real prospect data source is
-- integrated, load real rows here (or via an admin tool) — only
-- fantasy-relevant positions (QB/RB/WR/TE) matter to this app, since it has
-- no IDP support and offensive tackles have no fantasy scoring value;
-- modules/college_scouting.py's SCOUTING_RELEVANT_POSITIONS filter also
-- drops any other position at read time as a backstop.

create table if not exists public.scouting_reports (
    user_id uuid not null references auth.users(id) on delete cascade,
    prospect_id text not null references public.college_prospects(id) on delete cascade,
    grade smallint not null,
    round_projection smallint,
    note text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (user_id, prospect_id),
    constraint scouting_reports_grade_check check (grade between 1 and 5),
    constraint scouting_reports_round_projection_check
        check (round_projection is null or round_projection between 1 and 7),
    constraint scouting_reports_note_length_check check (char_length(note) <= 280)
);

create index if not exists scouting_reports_prospect_idx
    on public.scouting_reports (prospect_id);

alter table public.scouting_reports enable row level security;

-- Deliberately NOT auth.uid() = user_id — see file header. Every signed-in
-- user can read every scouting report; that's the shared/crowdsourced pool.
drop policy if exists scouting_reports_select_all on public.scouting_reports;
create policy scouting_reports_select_all
on public.scouting_reports for select
to authenticated
using (true);

drop policy if exists scouting_reports_insert_own on public.scouting_reports;
create policy scouting_reports_insert_own
on public.scouting_reports for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists scouting_reports_update_own on public.scouting_reports;
create policy scouting_reports_update_own
on public.scouting_reports for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists scouting_reports_delete_own on public.scouting_reports;
create policy scouting_reports_delete_own
on public.scouting_reports for delete
to authenticated
using (auth.uid() = user_id);

-- No anon policies — anonymous users cannot access Scouting Reports.

comment on table public.scouting_reports is
    'Per-user college prospect scouting grade (1-5) + optional round projection/note. RLS: select open to all authenticated users (shared/crowdsourced pool by design); insert/update/delete auth.uid()=user_id only. Aggregated client- and server-side by modules/college_scouting.py — never a single opinion, always the pool.';

create table if not exists public.prospect_watchlist (
    user_id uuid not null references auth.users(id) on delete cascade,
    prospect_id text not null references public.college_prospects(id) on delete cascade,
    created_at timestamptz not null default now(),
    primary key (user_id, prospect_id)
);

alter table public.prospect_watchlist enable row level security;

drop policy if exists prospect_watchlist_select_own on public.prospect_watchlist;
create policy prospect_watchlist_select_own
on public.prospect_watchlist for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists prospect_watchlist_insert_own on public.prospect_watchlist;
create policy prospect_watchlist_insert_own
on public.prospect_watchlist for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists prospect_watchlist_delete_own on public.prospect_watchlist;
create policy prospect_watchlist_delete_own
on public.prospect_watchlist for delete
to authenticated
using (auth.uid() = user_id);

-- No UPDATE policy — follow/unfollow only, mutates via insert + delete.
-- No anon policies — anonymous users cannot access the watchlist.

comment on table public.prospect_watchlist is
    'Personal "follow this prospect" watchlist — no scouting fields here (those live in scouting_reports). RLS auth.uid()=user_id on every operation, same shape as docs/supabase_gm_targets.sql.';
