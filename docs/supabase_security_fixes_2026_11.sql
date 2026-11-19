-- Security fixes from docs/audits/2026-11-security-privacy-audit.md (2026-11-18).
-- FOR coridian_ TO REVIEW AND RUN BY HAND in the Supabase SQL Editor. NOT applied by the audit.
-- Every section is independent, idempotent (create or replace / drop if exists) and can be run on its own.
-- Read the "BEFORE YOU RUN" note on each section. Verification queries are at the bottom.

-- ===========================================================================
-- 1) HIGH (audit H2): remove the client-callable delete_user() RPC.
-- ---------------------------------------------------------------------------
-- public.delete_user() is SECURITY DEFINER and granted to `authenticated`, so any signed-in client can call
-- supabase.rpc('delete_user') and delete their auth user WITHOUT going through the delete-account edge function.
-- That skips: Stripe subscription cancellation (user deleted but still billed), Sign in with Apple revocation,
-- and the non-cascading row cleanup (feedback_reports, billing_webhook_events).
-- Both web-next (AuthContext) and mobile (accountDeletion.ts) now call the `delete-account` edge function, which
-- deletes the auth user with the service role, so the RPC is no longer needed by any client.
--
-- BEFORE YOU RUN: confirm the installed mobile build(s) in the field no longer call rpc('delete_user')
-- (grep in this repo shows no remaining caller). If an old build still does, its delete button will start failing
-- closed with a permission error until the user updates. That is the intended failure mode.

revoke execute on function public.delete_user() from authenticated;
revoke execute on function public.delete_user() from anon;
revoke execute on function public.delete_user() from public;
-- (service_role / postgres keep execute implicitly.)

-- ===========================================================================
-- 2) MEDIUM (audit M2): trade_outcomes server-owned columns must not be client-writable.
-- ---------------------------------------------------------------------------
-- RLS lets a user UPDATE their own trade_outcomes row, including result_summary / result_computed_at (written by
-- the server's grading job) and followup_pushed_at (written by the push sweep). The community "interesting trades"
-- feed (GET /v1/community/trades, service-role read) selects rows by outcome + result columns and shows them to
-- every signed-in user, so a client can fabricate a "result" and have it served to the whole community.
-- Same guard pattern as docs/supabase_server_owned_columns_guard.sql: postgres / supabase_admin / service_role pass.
--
-- BEFORE YOU RUN: confirm the grading job and push sweep run as service_role (they use the service-role key).

create or replace function public.protect_trade_outcomes_server_columns()
returns trigger
language plpgsql
as $$
declare
    privileged boolean;
begin
    privileged := current_user in ('postgres', 'supabase_admin', 'service_role');
    if privileged then
        return new;
    end if;

    if tg_op = 'INSERT' then
        new.result_summary := null;
        new.result_computed_at := null;
        new.followup_pushed_at := null;
        return new;
    end if;

    new.result_summary := old.result_summary;
    new.result_computed_at := old.result_computed_at;
    new.followup_pushed_at := old.followup_pushed_at;
    return new;
end;
$$;

drop trigger if exists trade_outcomes_protect_server_columns on public.trade_outcomes;
create trigger trade_outcomes_protect_server_columns
    before insert or update on public.trade_outcomes
    for each row execute function public.protect_trade_outcomes_server_columns();

-- ===========================================================================
-- 3) MEDIUM (audit M3): scouting_reports is readable in full by every signed-in user.
-- ---------------------------------------------------------------------------
-- Policy scouting_reports_select_all (using (true)) lets any authenticated client read every user's rows,
-- including user_id and the free-text `note`, straight from PostgREST. The product only needs the per-prospect
-- aggregate (and the caller's own row). Replace with own-row read + a SECURITY DEFINER aggregate function.
--
-- !! DO NOT RUN THIS SECTION UNTIL THE CODE CHANGE LANDS !! The API's scouting aggregate currently reads
-- scouting_reports with the caller's own token (modules/college_scouting.py). After you create the function below,
-- the API must be switched to call rpc/scouting_report_aggregates before select_all is dropped, or the aggregate
-- on the College Prospects screen goes empty. Steps: (a) run the create function part now, (b) ship the code,
-- (c) then run the policy swap.

create or replace function public.scouting_report_aggregates()
returns table (prospect_id text, report_count bigint, avg_grade numeric, avg_round numeric)
language sql
stable
security definer
set search_path = public
as $$
    select r.prospect_id::text,
           count(*)::bigint,
           round(avg(r.grade)::numeric, 1),
           round(avg(r.round_projection)::numeric, 1)
    from public.scouting_reports r
    group by r.prospect_id
$$;

revoke all on function public.scouting_report_aggregates() from public, anon;
grant execute on function public.scouting_report_aggregates() to authenticated;

-- (c) AFTER the code change ships:
-- drop policy if exists scouting_reports_select_all on public.scouting_reports;
-- create policy scouting_reports_select_own on public.scouting_reports
--     for select to authenticated using (auth.uid() = user_id);

-- ===========================================================================
-- 4) LOW (audit L1): bound anonymous feedback inserts.
-- ---------------------------------------------------------------------------
-- feedback_insert_guest lets the anon role insert rows with user_id null. Cap the free-text columns so the table
-- cannot be used as a free bulk store. Adjust column names to your live schema if they differ
-- (check: select column_name from information_schema.columns where table_name = 'feedback_reports').
-- Run only after confirming the column names; the DO block skips columns that do not exist.

do $$
declare
    col text;
begin
    foreach col in array array['message', 'body', 'comment', 'details', 'page', 'url']
    loop
        if exists (
            select 1 from information_schema.columns
            where table_schema = 'public' and table_name = 'feedback_reports' and column_name = col
              and data_type = 'text'
        ) then
            execute format(
                'alter table public.feedback_reports drop constraint if exists %I', 'feedback_reports_' || col || '_len'
            );
            execute format(
                'alter table public.feedback_reports add constraint %I check (char_length(%I) <= 4000) not valid',
                'feedback_reports_' || col || '_len', col
            );
        end if;
    end loop;
end
$$;

-- ===========================================================================
-- 5) LOW (audit L7): ESPN cookie ciphertext should not be readable back by the browser.
-- ---------------------------------------------------------------------------
-- espn_credentials has a FOR ALL owner policy, so a client (or an XSS payload running as the user) can SELECT its
-- own espn_s2_enc / swid_enc. They are Fernet ciphertext under a server-only key, so this is defense in depth only.
-- The API reads them with the user's token (modules/espn_credentials.py load()), so do NOT revoke select on the
-- table; instead leave this as-is until the API reads through service role. Documented here, not executed.

-- ===========================================================================
-- VERIFY (read-only)
-- ---------------------------------------------------------------------------
-- 1) delete_user no longer callable by clients (expect no 'authenticated'/'anon'/PUBLIC grantee):
--    select grantee, privilege_type from information_schema.routine_privileges
--    where routine_schema = 'public' and routine_name = 'delete_user';
-- 2) trigger present:
--    select tgname from pg_trigger where tgrelid = 'public.trade_outcomes'::regclass and not tgisinternal;
-- 3) every public table has RLS on (expect zero rows):
--    select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
--    where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity;
-- 4) policies that allow anon or use (true) (review each row):
--    select tablename, policyname, roles, cmd, qual from pg_policies
--    where schemaname = 'public' and (qual = 'true' or 'anon' = any(roles));
-- 5) client-visible SECURITY DEFINER functions (review grants):
--    select p.proname, p.proacl from pg_proc p join pg_namespace n on n.oid = p.pronamespace
--    where n.nspname = 'public' and p.prosecdef;
