-- ESPN login cookies (espn_s2 + SWID) for private ESPN leagues.
-- Run this in Supabase Dashboard -> SQL Editor. No migration runner exists.
--
-- Both columns hold Fernet CIPHERTEXT produced by modules/espn_credentials.py
-- with the server-side ESPN_CREDENTIAL_KEY. The database never sees a cookie
-- in the clear and never holds the key. Generate the key once with:
--   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
-- and set it as ESPN_CREDENTIAL_KEY on the API server. Losing or rotating the
-- key just means users are asked to reconnect ESPN.

create table if not exists public.espn_credentials (
    user_id uuid primary key references auth.users(id) on delete cascade,
    espn_s2_enc text not null,
    swid_enc text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.espn_credentials enable row level security;

drop policy if exists "espn_credentials_owner_all" on public.espn_credentials;
create policy "espn_credentials_owner_all"
    on public.espn_credentials
    for all
    to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

drop trigger if exists espn_credentials_set_updated_at on public.espn_credentials;
create trigger espn_credentials_set_updated_at
    before update on public.espn_credentials
    for each row execute function public.set_updated_at();
