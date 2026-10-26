-- News ingest store: items, append-only revision history, per-source health.
-- Run by hand in Supabase Dashboard -> SQL Editor (no migration runner exists;
-- the repo does not assume this has been applied).
--
-- Written only by scripts/ingest_news.py (service role, GitHub Action
-- .github/workflows/news-ingest.yml); read only by GET /v1/external/news
-- (service role). No anon/authenticated client touches these tables, so RLS is
-- enabled with no policies (same pattern as supabase_player_rating_snapshots.sql).
--
-- Until applied: the ingest job exits 2 (--require-durable) and the API falls
-- back to a local file, reporting `durable_store_unavailable_using_local_file`.
--
-- No foreign keys on purpose: revisions are written before items (so a failed
-- write never leaves an item pointing at a missing revision) in separate requests.
--
-- content_hash is a hash of the FEED-SUPPLIED title+summary, used only to
-- detect that the feed text changed. It is NOT a checked article document.

create table if not exists public.news_items (
    item_id text primary key,
    canonical_url text not null,
    title text not null,
    link text not null,
    published_ts double precision,
    source_key text not null,
    feed_url text not null,
    dedupe_key text,
    duplicate_of text,
    first_seen_at timestamptz not null default now(),
    latest_revision_id text,
    updated_at timestamptz not null default now()
);

create index if not exists news_items_first_seen_idx on public.news_items (first_seen_at desc);
create index if not exists news_items_duplicate_of_idx on public.news_items (duplicate_of);

create table if not exists public.news_item_revisions (
    seq bigint generated always as identity primary key,
    revision_id text not null unique,
    item_id text not null,
    previous_revision_id text,
    content_hash text not null,
    title text not null,
    summary text not null default '',
    link text not null,
    published_ts double precision,
    source_key text not null,
    feed_url text not null,
    created_at timestamptz not null default now()
);

create index if not exists news_item_revisions_item_idx on public.news_item_revisions (item_id);
create index if not exists news_item_revisions_created_idx on public.news_item_revisions (created_at);

create table if not exists public.news_source_health (
    source_key text primary key,
    feed_url text not null,
    last_attempt_at timestamptz,
    last_success_at timestamptz,
    last_error text,
    consecutive_failures integer not null default 0,
    last_item_count integer not null default 0,
    last_new_item_count integer not null default 0,
    updated_at timestamptz not null default now()
);

alter table public.news_items enable row level security;
alter table public.news_item_revisions enable row level security;
alter table public.news_source_health enable row level security;

comment on table public.news_items is 'One row per canonical article URL from the publisher RSS feeds. See modules/news_ingest.py.';
comment on table public.news_item_revisions is 'Append-only revision history; seq is the /v1/external/news cursor.';
comment on table public.news_source_health is 'Per-feed ingest health (last success, consecutive failures).';
