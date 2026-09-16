-- Mobile push notification token registry (Expo push tokens).
-- Run in Supabase Dashboard -> SQL Editor after docs/supabase_accounts.sql.
--
-- Contract:
--   - One row per device token; primary key is the token itself (not
--     user_id) so re-logging in as a different account on the same device
--     reassigns the row via upsert instead of creating a duplicate.
--   - RLS fail-closed: auth.uid() = user_id only.
--   - Streamlit/mobile use anon key + user JWT (no service_role) to read
--     back their own tokens; only a trusted backend (service_role, used
--     only server-side to call Expo's push API) reads across users.
--   - The mobile app unregisters its token on sign-out so a shared/reused
--     device doesn't keep delivering pushes meant for the previous account.
--
-- Kill switch (app): none yet — registration fails soft (no crash, no
-- writes) until this migration is applied.

create table if not exists public.push_tokens (
    expo_push_token text primary key,
    user_id uuid not null references auth.users(id) on delete cascade,
    platform text not null default '',
    device_name text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists push_tokens_user_idx
    on public.push_tokens (user_id, updated_at desc);

alter table public.push_tokens enable row level security;

drop policy if exists push_tokens_select_own on public.push_tokens;
create policy push_tokens_select_own
on public.push_tokens for select
to authenticated
using (auth.uid() = user_id);

drop policy if exists push_tokens_insert_own on public.push_tokens;
create policy push_tokens_insert_own
on public.push_tokens for insert
to authenticated
with check (auth.uid() = user_id);

drop policy if exists push_tokens_update_own on public.push_tokens;
create policy push_tokens_update_own
on public.push_tokens for update
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists push_tokens_delete_own on public.push_tokens;
create policy push_tokens_delete_own
on public.push_tokens for delete
to authenticated
using (auth.uid() = user_id);

-- No anon policies — anonymous users cannot register or read tokens.

comment on table public.push_tokens is
    'Expo push tokens for the mobile app. Token is the primary key so device reassignment across accounts upserts cleanly; RLS auth.uid()=user_id.';
