# Analytics metric definitions and Sheets exporter contract (Phase 1, 2026-11)

Code: `modules/analytics_metrics.py` (definitions), `modules/account_acquisition.py` (per-account record),
`modules/founder_analytics.build_report` (exposes them), `docs/supabase_account_acquisition_2026_11.sql` (owner-run DB change).
Evidence labels: **[code]** = inferred from reading the repo; **[prod]** = confirmed by production data. Nothing here
was confirmed by production data (no prod DB was queried); the owner checks at the end close that gap.

## Definitions (one shared implementation)

Rows first drop `environment = test`, then the single-page bot heuristic (`founder_analytics._filter_bot_like_sessions`).

| Metric | Definition |
|---|---|
| person | Account key (keyed hash `user_key`/`account_hash`) if present, else `anon_id` resolved through an anon->account link map built from rows carrying both (stitching). An anon id linked to more than one account (shared browser, salt rotation) is left unstitched. `session_key` is never a person. |
| unique_visitors / active_users | Distinct persons with any event in the window. Includes guests and sample-league visitors. |
| DAU / WAU / MAU | `unique_visitors` over trailing 1 / 7 / 30 UTC calendar days ending today. |
| sessions | Distinct real `session_key` (web, 30-min TTL). Rows without one (mobile, legacy): one per person per UTC day. |
| registered_users | Persons with an account key who were not guest-only. Pre-2026-11 rows have no `account_kind`; they count as registered and are also reported as `legacy_unclassified_users` (so registered is an upper bound until those age out). |
| guest_users | Persons whose only account activity is `account_kind=guest` (anonymous Supabase session). A guest who upgrades keeps the same user id and moves to registered. |
| engaged_users | Persons with >=1 `MEANINGFUL_ENGAGEMENT_EVENTS` event or a non-demo `feature_use` (not onboarding). Sample-league (`demo=true`) events never count as engaged. |
| signups | Distinct persons with `signup_completed` (first occurrence wins), broken down by `signup_method` (email / google / apple). |
| account_kind | Derived SERVER-side from the verified token on `/v1/e` (`visitor` / `guest` / `registered`); a client-sent value is overwritten. |

Why the old MAU was unreliable **[code]**: (1) `_identity_key` preferred the per-visit `session_key` over `anon_id`,
so a returning anonymous visitor became a new "user" each session; (2) no anon->account stitching in the DAU/WAU/MAU
path; (3) a hard 20,000-row read cap silently dropped the OLDEST rows of any larger window (MAU first, WAU unaffected);
(4) test rows and bot-shaped single page views were not removed in `retention_summary`. All four are fixed.
Which of these (plus the 2026-10-27 bot filtering and the 2026-11-21 hash-salt change) explains 544 -> 273 is **not
confirmed by prod data**; recompute with `window=all` (below) to see the like-for-like series.

## Truncation
`launch_analytics.max_read_rows()` (env `ANALYTICS_MAX_READ_ROWS`, default 200,000, ceiling 1,000,000) replaces the
20,000 constant. A read that hits the cap sets `read_truncated: true` in the report and adds a WARNING to
`partial_notes`; it is never silent. For very large volumes move aggregation into SQL (not done here: it needs an
owner-run function and the stitching rule above does not translate to a single query).

## Report fields (GET `/v1/founder/analytics?window=<24h|7d|30d|all>`)
- `audience`: `{as_of, dau, wau, mau, windows:{dau,wau,mau:{unique_visitors, registered_users, guest_users, anonymous_visitors, engaged_users, sessions, legacy_unclassified_users}}, signups, definitions}`; with `window=all` also `history[]` (60 days, one object per day with `dau, wau, mau, sessions, registered_dau, guest_dau, engaged_dau, engaged_mau`, all recomputed with the same rules, so history and today are like-for-like).
- `sample_league_funnel`: `{viewers, engaged, cta_clicked, signed_up_after_view, view_to_signup_pct}`.
- `try_link_funnel`: no-signup ad try links (`/try/<topic>`, events `feature_use feature=try_link`, `action` viewed | cta_click, `item_kind` = topic, always `demo=true`): `{viewers, cta_clicked, signed_up_after_view, view_to_signup_pct, by_topic}`; each person counts under the topic they viewed first. Demo views are never engagement.
- `signup_reconciliation`: events vs real accounts (`account_acquisition`): `signup_events_distinct, accounts_created_registered, accounts_created_guest, accounts_by_method, unlogged_signups`; `available:false` until the SQL file is applied.
- `read_truncated`, and the existing keys (`sessions`, `anonymous_users`, `hashed_accounts` are kept for compatibility but are NOT the stitched definition; exporters should switch to `audience`).
- `retention_summary()` (`dau/wau/mau`, `unique_users`, D1/D7/D30) now uses the stitched person id and excludes test rows.

## Identity stitching and privacy
No new identifier is introduced. Stitching only joins values already stored (anon_id <-> keyed account hash) from rows
that carry both, inside the server process; nothing raw leaves it. The keyed hashing (`ANALYTICS_HASH_SALT`) is
unchanged. Note: if the salt was set/changed mid-window, one person has two account keys; they are only joined when
they share an anon id with exactly one key (ambiguous anon ids stay split, a conservative choice).

## Sign-up tracking
- Web (`web-next/src/lib/signupTracking.ts`, AuthContext) and mobile (`mobile/src/lib/accountEvents.ts`, AuthContext) emit `signup_completed` with `signup_method` for email (incl. confirm-by-link), Google and Apple, and `guest_session_started` for guest sessions, once per account per device (local marker). A guest upgrade yields `signup_completed` once. **[code]**
- Reconciliation: `account_acquisition` rows come from the verified GoTrue user (real `created_at`, provider, `is_anonymous`) the first time an account sends any event; `signup_reconciliation.unlogged_signups` is the gap.

## Attribution
- Web keeps FIRST touch (`utm_*`, `referrer_host`, click id kind+value) and LAST touch (`lt_utm_source/medium/campaign`, `lt_referrer_host`, `lt_click_id`) in localStorage and sends both on every event. A referrer-only first touch no longer blocks a later UTM/click-id touch (upgraded); a plain referrer never displaces a campaign last touch.
- Persisted per account in `account_acquisition` (first touch + last touch at registration). Mobile has no UTM/install attribution (only `?ref=` referral codes); out of scope here.

## Sample league
`/sample-league` still sends nothing except `feature_use feature=sample_league action=viewed|tab|connect_cta` with `demo=true` (`trackSampleLeague`). `viewed` is once per browser session; `tab` carries `item_kind`. Conversion = viewer with a later `signup_completed` (same stitched person).

## Mobile analytics: end-to-end verification (static, **[code]**)
1. `mobile/src/lib/analytics.ts`: `resolveAnalyticsEnabled(env, __DEV__)`; unset -> ON in production builds, OFF in dev; `0` is the kill switch. `.env.example` and the App.tsx comment previously said the opposite (fixed).
2. Events POST to the API base URL `/v1/e` with the Supabase bearer token and `anon_id`; props limited to `analyticsCore.ALLOWED_PROP_KEYS`.
3. Server `/v1/e` requires `DYNASTYGM_LAUNCH_ANALYTICS=1` (default off in `analytics_enabled()`), then bot filter, `TRACKED_EVENTS`, `platform in {web,ios,android}`.
4. **Defect found and fixed:** the generic bot list contains `okhttp`, which is React Native Android's default User-Agent, so Android events were very likely dropped as bots. Now a self-declared `platform=android|ios` event with an okhttp/CFNetwork UA is accepted (`is_bot_user_agent_for_platform`); crawlers and curl-style clients still are not.
5. `mobile/fastlane/app_privacy_details.json` already declares Product Interaction (analytics, linked to user).
6. Mobile sends no `session_id`, so mobile sessions use the person-per-day approximation.
Whether a shipped binary actually sends events, and the real ingestion volume, are **not confirmed** (needs prod data).

## Owner steps
1. Run `docs/supabase_account_acquisition_2026_11.sql` in the Supabase SQL editor (idempotent). Until then everything degrades: no per-account rows, reconciliation reports `available:false`.
2. Optional env: `ANALYTICS_MAX_READ_ROWS` (default 200000). Confirm `DYNASTYGM_LAUNCH_ANALYTICS=1` and whether `ANALYTICS_HASH_SALT` is set (and since when).
3. Deploy the API, web-next and the next mobile build (the mobile signup/guest events and the Android fix only take effect on a new build; the okhttp server fix works for already-shipped builds).
4. Prod checks (inferred -> confirmed): `select count(*) from analytics_events where ts > extract(epoch from now() - interval '30 days')` (> 20000 confirms the old cap hypothesis); daily rows by `props->>'platform'` since 2026-11-22 (iOS/Android ingestion); `select signup_method, count(*) from account_acquisition group by 1` after a few days.

## What the separate private Sheets exporter must change
The exporter is not in this repo, so this is the exact contract to update (do not read `analytics_events` directly for these):
1. Read `GET /v1/founder/analytics?window=all` (founder auth as today) once per run. Use `audience.dau / wau / mau` (not `anonymous_users`, `hashed_accounts` or its own distinct-count over `session_key`/`anon_id`).
2. Add columns: `unique_visitors`, `registered_users`, `guest_users`, `engaged_users`, `sessions` (from `audience.windows.<dau|wau|mau>`), `legacy_unclassified_users`, `signups` (`audience.signups.distinct_signups`) with a method breakdown (`by_method`), and `signup_reconciliation.unlogged_signups`.
3. Re-baseline history: overwrite the historical DAU/WAU/MAU rows from `audience.history[]` (same definitions for every day) and mark the old series as "legacy definition"; do not splice old and new MAU.
4. If it reads raw rows, it must exclude `environment='test'`, stitch anon->account as above, and stop using `session_key` as an identity; prefer not to.
5. Read `read_truncated`; if true, write the value but flag the cell (a floor).
6. Attribution: read `account_acquisition` (service role) for signups by `utm_campaign`/`utm_source`/`signup_method`, and join to `profiles` / `billing_webhook_events` on `user_id` (impossible via `analytics_events`, whose keys are hashed).
7. Sample-league tile from `sample_league_funnel`.
