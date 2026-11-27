-- Yahoo Fantasy OAuth tokens (per user) for imported Yahoo leagues.
-- Run this in Supabase Dashboard -> SQL Editor. Idempotent: safe to re-run.
-- No migration runner exists. Until it is applied, "Connect Yahoo" answers
-- "couldn't save your connection" instead of failing hard; nothing else breaks.
--
-- Token columns hold Fernet CIPHERTEXT produced by modules/yahoo_credentials.py
-- with the server-side YAHOO_CREDENTIAL_KEY (or, if unset, the existing
-- ESPN_CREDENTIAL_KEY). The database never sees a token in the clear and never
-- holds the key. Losing or rotating the key just asks users to reconnect Yahoo.
--
-- Same shape as docs/supabase_espn_credentials.sql (needs public.set_updated_at(),
-- created by docs/supabase_accounts.sql).

create table if not exists public.yahoo_credentials (
    user_id uuid primary key references auth.users(id) on delete cascade,
    refresh_token_enc text not null,
    access_token_enc text not null default '',
    access_expires_at bigint not null default 0,
    yahoo_guid text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.yahoo_credentials enable row level security;

drop policy if exists "yahoo_credentials_owner_all" on public.yahoo_credentials;
create policy "yahoo_credentials_owner_all"
    on public.yahoo_credentials
    for all
    to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

drop trigger if exists yahoo_credentials_set_updated_at on public.yahoo_credentials;
create trigger yahoo_credentials_set_updated_at
    before update on public.yahoo_credentials
    for each row execute function public.set_updated_at();
