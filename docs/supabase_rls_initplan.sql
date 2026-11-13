-- Perf audit 2026-11: RLS policies that call auth.uid() bare are re-evaluated for every row scanned; wrapping it as
-- (select auth.uid()) lets Postgres evaluate it once per statement (Supabase advisor "auth_rls_initplan"). Same
-- semantics, so no behavior change. Idempotent: rewrites only policies in schema public that still call it bare.
--
-- Apply by hand in the Supabase SQL Editor (no migration runner). NOT yet applied or tested against the live DB:
-- run it first on a branch/staging project, then compare `explain analyze` of a user-scoped select
-- (e.g. select * from sim_games where user_id = auth.uid() order by created_at desc) before/after.

do $$
declare
    pol record;
    new_using text;
    new_check text;
    stmt text;
begin
    for pol in
        select schemaname, tablename, policyname, qual, with_check
        from pg_policies
        where schemaname = 'public'
          and (coalesce(qual, '') ~ 'auth\.uid\(\)' or coalesce(with_check, '') ~ 'auth\.uid\(\)')
          and coalesce(qual, '') !~* 'select\s+auth\.uid' and coalesce(with_check, '') !~* 'select\s+auth\.uid'
    loop
        new_using := case when pol.qual is null then null
                          else regexp_replace(pol.qual, 'auth\.uid\(\)', '(select auth.uid())', 'g') end;
        new_check := case when pol.with_check is null then null
                          else regexp_replace(pol.with_check, 'auth\.uid\(\)', '(select auth.uid())', 'g') end;
        stmt := format('alter policy %I on %I.%I', pol.policyname, pol.schemaname, pol.tablename);
        if new_using is not null then stmt := stmt || ' using (' || new_using || ')'; end if;
        if new_check is not null then stmt := stmt || ' with check (' || new_check || ')'; end if;
        execute stmt;
    end loop;
end $$;
