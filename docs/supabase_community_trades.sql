-- Opt-in shared trades for the Community feed. Run in Supabase Dashboard ->
-- SQL Editor (manual; no migration runner). Safe to re-run.
--
-- A user explicitly shares a trade they ran in the Trade Analyzer
-- ("Share to community", off by default). Rows hold only what the user chose
-- to publish: the traded assets, our grade, a short "why", and an optional
-- display name (null = "Anonymous"). No league id, no team names.
--
-- Contract:
--   - Any signed-in user can read rows that are not hidden.
--   - Owner inserts / deletes their own rows. No UPDATE policy.
--   - Any signed-in user can report a row (one report per user per row).
--     A SECURITY DEFINER trigger counts reports and sets hidden = true once
--     the count reaches 3, so reporters never need write access to the trade.
--
-- Until applied, the API reports the feature as unavailable and clients hide
-- the toggle and the feed.

create table if not exists public.community_shared_trades (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    display_name text check (display_name is null or char_length(display_name) <= 24),
    send jsonb not null default '[]'::jsonb,
    receive jsonb not null default '[]'::jsonb,
    grade text not null check (char_length(grade) <= 24),
    band text not null default '' check (char_length(band) <= 32),
    why text not null default '' check (char_length(why) <= 280),
    report_count integer not null default 0,
    hidden boolean not null default false,
    created_at timestamptz not null default now()
);

create index if not exists community_shared_trades_feed_idx
    on public.community_shared_trades (created_at desc) where hidden = false;
create index if not exists community_shared_trades_user_idx
    on public.community_shared_trades (user_id, created_at desc);

alter table public.community_shared_trades enable row level security;

drop policy if exists community_shared_trades_select_visible on public.community_shared_trades;
create policy community_shared_trades_select_visible
on public.community_shared_trades for select
to authenticated
using (hidden = false or auth.uid() = user_id);

drop policy if exists community_shared_trades_insert_own on public.community_shared_trades;
create policy community_shared_trades_insert_own
on public.community_shared_trades for insert
to authenticated
with check (auth.uid() = user_id and hidden = false and report_count = 0);

drop policy if exists community_shared_trades_delete_own on public.community_shared_trades;
create policy community_shared_trades_delete_own
on public.community_shared_trades for delete
to authenticated
using (auth.uid() = user_id);

create table if not exists public.community_shared_trade_reports (
    id uuid primary key default gen_random_uuid(),
    trade_id uuid not null references public.community_shared_trades(id) on delete cascade,
    reporter_id uuid not null references auth.users(id) on delete cascade,
    reason text not null default '' check (char_length(reason) <= 120),
    created_at timestamptz not null default now(),
    constraint community_shared_trade_reports_unique unique (trade_id, reporter_id)
);

alter table public.community_shared_trade_reports enable row level security;

drop policy if exists community_shared_trade_reports_insert_own on public.community_shared_trade_reports;
create policy community_shared_trade_reports_insert_own
on public.community_shared_trade_reports for insert
to authenticated
with check (auth.uid() = reporter_id);

drop policy if exists community_shared_trade_reports_select_own on public.community_shared_trade_reports;
create policy community_shared_trade_reports_select_own
on public.community_shared_trade_reports for select
to authenticated
using (auth.uid() = reporter_id);

create or replace function public.community_shared_trade_apply_report()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    update public.community_shared_trades
    set report_count = report_count + 1,
        hidden = (report_count + 1) >= 3
    where id = new.trade_id;
    return new;
end;
$$;

drop trigger if exists community_shared_trade_reports_after_insert on public.community_shared_trade_reports;
create trigger community_shared_trade_reports_after_insert
after insert on public.community_shared_trade_reports
for each row execute function public.community_shared_trade_apply_report();

comment on table public.community_shared_trades is
    'Opt-in Community feed trades. Hidden automatically at 3 reports. Owner can delete.';
