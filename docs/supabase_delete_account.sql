-- Self-service account deletion (Apple App Store Guideline 5.1.1(v): an app
-- that supports account creation must also support in-app account
-- deletion, not just sign-out).
-- Run in Supabase Dashboard -> SQL Editor after docs/supabase_accounts.sql.
--
-- Contract:
--   - A user can delete only their OWN row. auth.uid() reads the caller's
--     own JWT claims regardless of the function's SECURITY DEFINER
--     privilege — it is not influenced by who owns the function — so this
--     is safe to expose to every authenticated user without any additional
--     ownership check.
--   - SECURITY DEFINER is required because a normal authenticated-role
--     grant cannot DELETE from auth.users directly; the function runs with
--     the privileges of its owner (a superuser-equivalent role in
--     Supabase) for exactly this one bounded operation, not for anything
--     else the client can influence.
--   - Deleting the auth.users row cascades to every app table with
--     `references auth.users(id) on delete cascade` — profiles,
--     gm_targets, saved_leagues, mobile_alert_reads, trade_outcomes, etc.
--     No mobile-api or service-role code path is needed; the mobile app
--     calls this directly via `supabase.rpc('delete_user')` using the
--     user's own session, the same way it already calls any other RPC.
--   - REVOKE from PUBLIC / anon: only a signed-in (authenticated) user may
--     call this, and only for themselves.
--
-- Until this migration is applied, the mobile app's "Delete Account" flow
-- fails closed (a clear error, not a crash) rather than silently no-op'ing.

create or replace function public.delete_user()
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  delete from auth.users where id = auth.uid();
end;
$$;

revoke all on function public.delete_user() from public;
revoke all on function public.delete_user() from anon;
grant execute on function public.delete_user() to authenticated;

comment on function public.delete_user() is
    'Deletes the calling user''s own auth.users row (and everything that cascades from it). auth.uid()-scoped — cannot delete another user.';
