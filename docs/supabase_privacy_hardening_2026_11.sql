-- Privacy hardening (audit L1, L6). Additive and idempotent. Run in the Supabase SQL editor.
--
-- ORDER: deploy the API first and make sure SUPABASE_SERVICE_ROLE_KEY is set on the API
-- (modules/espn_credentials.py then reads/writes through the service role). Run section 2 only after that,
-- otherwise saved ESPN connections stop loading until the key is set.

-- 1) L1: bound anonymous feedback (size + global guest insert rate).
do $$
declare
    col text;
    lim int;
begin
    for col, lim in select * from (values ('message', 4000), ('email', 320), ('category', 64), ('feedback_type', 64), ('app_build', 40)) as t(c, l)
    loop
        if exists (select 1 from information_schema.columns
                   where table_schema = 'public' and table_name = 'feedback_reports' and column_name = col and data_type = 'text') then
            execute format('alter table public.feedback_reports drop constraint if exists %I', 'feedback_reports_' || col || '_len');
            execute format('alter table public.feedback_reports add constraint %I check (char_length(%I) <= %s) not valid',
                           'feedback_reports_' || col || '_len', col, lim);
        end if;
    end loop;
end
$$;

alter table public.feedback_reports drop constraint if exists feedback_reports_context_size;
alter table public.feedback_reports
    add constraint feedback_reports_context_size check (pg_column_size(context) <= 8000) not valid;

create or replace function public.feedback_guest_throttle() returns trigger
language plpgsql as $fn$
begin
    if new.user_id is null and (
        select count(*) from public.feedback_reports
        where user_id is null and created_at > now() - interval '1 minute'
    ) >= 60 then
        raise exception 'feedback rate limit' using errcode = '54000';
    end if;
    return new;
end
$fn$;

drop trigger if exists feedback_guest_throttle on public.feedback_reports;
create trigger feedback_guest_throttle
    before insert on public.feedback_reports
    for each row execute function public.feedback_guest_throttle();

-- 2) L6: the browser session must not read espn_credentials back. No policy = deny for anon/authenticated;
--    the API uses the service role.
drop policy if exists "espn_credentials_owner_all" on public.espn_credentials;
revoke all on public.espn_credentials from anon, authenticated;
