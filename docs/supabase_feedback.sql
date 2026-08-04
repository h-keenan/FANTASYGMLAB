-- FantasyGM Lab durable feedback reports (additive / migration-safe).
-- Run in Supabase Dashboard -> SQL Editor after docs/supabase_accounts.sql.
--
-- Why: Render's Streamlit filesystem is ephemeral. JSONL under data/ does not
-- survive redeploys. This table is the production Founder Beta destination.
--
-- Founder review: open Supabase Dashboard -> Table Editor -> feedback_reports
-- (or SQL: select * from public.feedback_reports order by created_at desc).
-- No service-role key is required in the Streamlit app.

create table if not exists public.feedback_reports (
    report_id uuid primary key,
    created_at timestamptz not null default now(),
    user_id uuid references auth.users(id) on delete set null,
    feedback_type text not null default 'global',
    category text not null default '',
    message text not null default '',
    email text not null default '',
    can_contact boolean not null default false,
    status text not null default 'new',
    app_build text not null default '',
    context jsonb not null default '{}'::jsonb
);

create index if not exists feedback_reports_created_at_idx
    on public.feedback_reports (created_at desc);

create index if not exists feedback_reports_user_id_idx
    on public.feedback_reports (user_id);

create index if not exists feedback_reports_status_idx
    on public.feedback_reports (status);

alter table public.feedback_reports enable row level security;

drop policy if exists feedback_select_own on public.feedback_reports;
create policy feedback_select_own
on public.feedback_reports for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists feedback_insert_own on public.feedback_reports;
create policy feedback_insert_own
on public.feedback_reports for insert
to authenticated
with check (auth.uid() = user_id);

-- Guests may submit feedback without an account. Rows stay anonymous (user_id null).
drop policy if exists feedback_insert_guest on public.feedback_reports;
create policy feedback_insert_guest
on public.feedback_reports for insert
to anon
with check (user_id is null);

-- No update/delete policies for clients. Founders review via Supabase Dashboard.
comment on table public.feedback_reports is
    'Founder Beta customer feedback. Clients insert own/guest rows; founders review in Supabase Dashboard.';
