# Security and privacy audit, 2026-11-18

Scope: Supabase RLS on every table in `docs/supabase_*.sql`, service-role key exposure, every `/v1` route (auth,
ownership, Pro gates, rate limits, `/v1/external`, `/v1/public`, `/v1/content`), account-deletion completeness, PII in
logs, and CORS / redirects / webhook verification.

Method and limits: static review of the repo at `origin/main` (backend `services/` + `modules/`, `web-next/`,
`mobile/`, `supabase/functions/`, `docs/supabase_*.sql`). The live database cannot be queried, so RLS findings describe
what the checked-in SQL does, not what is deployed; the verification queries at the bottom of
`docs/supabase_security_fixes_2026_11.sql` confirm the live state. No `.env` or `local_secrets/` file was opened and no
secret value was read.

Result in one line: no Critical findings. The structure is sound (every table has RLS, every `/v1` route that touches
user data goes through `require_user` and user-JWT PostgREST so RLS does the ownership check, webhooks verify
signatures with constant-time compares, no service-role key reaches a client bundle). Two High items, both needing a
human decision or SQL; several Medium items.

"Who must act": **code** = an engineer (done here where marked FIXED), **coridian_ SQL** = run by hand in the Supabase
SQL editor (`docs/supabase_security_fixes_2026_11.sql`), **Zach** = secrets, billing, or provider dashboards.

## Summary table

| # | Sev | Title | Who | Status |
|---|-----|-------|-----|--------|
| H1 | High | Rate limiter bypass: rotating the `Authorization` header mints a fresh bucket | code | FIXED (#2171) |
| H2 | High | `public.delete_user()` RPC is client-callable and bypasses Stripe cancel / Apple revoke | coridian_ SQL | open, SQL provided |
| M1 | Medium | Backend Sentry could ship ESPN cookies / bearer tokens / emails in request bodies | code | FIXED (#2172) |
| M2 | Medium | `trade_outcomes` server-owned columns are client-writable, feeding the community trade feed | coridian_ SQL | open, SQL provided |
| M3 | Medium | PostgREST filter built by string interpolation of path/query values | code | FIXED (#2173) |
| M4 | Medium | Referral Pro comp can be farmed with anonymous guest accounts | Zach + code (escalated) | open, not touched |
| M5 | Medium | Delete-account gaps (RevenueCat, Stripe customer, analytics, referrer links, free-trial resets) | Zach + code (escalated) | open, not touched |
| M6 | Medium | `X-Forwarded-For` first hop is trusted for rate-limit identity | Zach (proxy) / code | open |
| M7 | Medium | `scouting_reports` and `community_shared_trades` expose other users' `user_id` and free text | coridian_ product decision | open |
| L1 | Low | Anonymous feedback insert is unbounded | coridian_ SQL | open, SQL provided |
| L2 | Low | `user_id` appears in 5 backend log lines | code (policy) | open |
| L3 | Low | Free ad-unlock is an honor system (no server-side ad verification) | product | open |
| L4 | Low | No Content-Security-Policy on web-next | code | open |
| L5 | Low | `/health` publishes build SHA and deploy time to anonymous callers | code (policy) | open |
| L6 | Low | `espn_credentials` ciphertext is readable back by the browser session | code + SQL | open |
| L7 | Low | Analytics account hash uses a static, public salt | code | open |
| L8 | Low | Supabase Auth dashboard hardening for anonymous sign-ins | Zach / coridian_ | open |

Pass list (checked, no finding) is at the end.

---

## 1. Supabase RLS and policies

Every table created by `docs/supabase_*.sql` has `enable row level security`. Tables with no policy at all are
deny-by-default for `anon`/`authenticated` and are written only by the service role, which is the intended shape.

Per-user rows with `auth.uid() = user_id` on every operation: `profiles`, `saved_leagues`, `user_settings`,
`push_tokens`, `gm_targets`, `trade_outcomes`, `decision_log`, `decision_memory_events`, `decision_memory_baselines`,
`team_stance`, `games_pickem_picks`, `guess_the_player_*_streaks`, `mobile_alert_reads`, `notification_read_state`,
`notification_events`, `prospect_watchlist`, `community_trade_reactions`, `espn_credentials`, `sim_worlds`,
`sim_snapshots`, `sim_results`, `sim_games`, `sim_events`, `sim_week_checkpoints`, `sim_free_season_claims`
(sim child tables also require the parent game to be the caller's).

Deny-by-default (RLS on, zero policies, service role only): `analytics_events`, `billing_webhook_events`,
`news_items`, `news_item_revisions`, `news_source_health`, `player_rating_snapshots`, `push_notification_log`,
`league_roster_snapshots` (also explicitly revoked from `anon`, `authenticated`).

Read-only shared data (select to `authenticated`, no write policy): `college_prospects`, `college_prospect_stats`,
`adp_snapshots`. Correct for public reference data. None is readable by `anon`.

Tables with no RLS statement: none found. (`supabase_premium_tiers_migration.sql` and
`supabase_trade_outcome_results.sql` only alter existing tables.)

Server-owned columns already guarded by trigger (`docs/supabase_server_owned_columns_guard.sql`,
`supabase_entitlement_security_hardening.sql`): `profiles.entitlement`, billing ids, `trial_ends_at`,
`user_settings.settings.referral_program`.

### M2 (Medium). `trade_outcomes` server-owned columns are client-writable

- Location: `docs/supabase_trade_outcomes.sql` (`trade_outcomes_update_own`), `docs/supabase_trade_outcome_results.sql`
  (adds `result_summary`, `result_computed_at`), reader `modules/community_trades.py` + `GET /v1/community/trades`.
- Issue: the update policy has no column restriction, so a client can set `result_summary`, `result_computed_at` and
  `followup_pushed_at` on its own rows. The community feed reads those rows with the service role and shows
  "interesting" results to every signed-in user, so a forged result is served to the community. `trade_summary` and
  `partner_team_name` are also free-form and displayed to others (React escapes them; moderation is the open gap).
- Exploit sketch: a signed-in user PATCHes their own `trade_outcomes` row through PostgREST with a fabricated
  `result_summary`; it appears in other users' community feed.
- Fix: trigger that resets those columns for non-privileged roles (same pattern as the existing guards). Section 2 of
  `docs/supabase_security_fixes_2026_11.sql`. Code follow-up: validate `trade_summary` shape/length at the API.
- Who: coridian_ SQL; code for the shape validation.

### M7 (Medium, design decision). `scouting_reports` / `community_shared_trades` expose other users' ids

- Location: `scouting_reports_select_all` (`using (true)`), `community_shared_trades_select_visible`.
- Issue: any signed-in client can read every row directly from PostgREST, including `user_id` and the 280-character
  `note` (scouting) or `display_name` (shared trades). The app UI only shows aggregates/anonymized items, but the raw
  rows are reachable with the public anon key plus any account (anonymous guest sign-in counts).
- Exploit sketch: create a guest account, query the table, harvest user UUIDs and free text.
- Fix: aggregate via a SECURITY DEFINER function and restrict the table to own rows (staged SQL in section 3 of the SQL
  file, to be run only after the API is switched). For shared trades, drop `user_id` from the readable surface via a view.
- Who: coridian_ decides (the crowdsourcing is deliberate per the SQL header), then SQL plus code.

### L1 (Low). Anonymous feedback insert is unbounded

- Location: `docs/supabase_feedback.sql`, `feedback_insert_guest` (`to anon with check (user_id is null)`).
- Issue: no column length constraint is visible in the migration; the anon key can bulk insert.
- Fix: length checks (SQL file section 4) and, if abuse appears, route guest feedback through the API.
- Who: coridian_ SQL.

### L6 (Low). `espn_credentials` ciphertext readable by the browser session

- Location: `docs/supabase_espn_credentials.sql` (`for all` owner policy), `modules/espn_credentials.py`.
- Issue: the table holds Fernet ciphertext under a server-only key, so this is defense in depth only: an XSS running
  as the user could read the ciphertext, which is useless without `ESPN_CREDENTIAL_KEY`.
- Fix: read through the service role in the API and drop the client select policy. Not urgent.
- Who: code then SQL.

---

## 2. Service-role key and secret exposure

Pass. Findings:

- `SUPABASE_SERVICE_ROLE_KEY` is read only in backend Python (`modules/referrals.py`, `modules/stripe_webhook.py`,
  `modules/revenuecat_webhook.py`, `modules/rookie_adp.py`, `modules/player_rating_history.py`, `modules/games.py`,
  `modules/news_ingest.py`, `modules/league_roster_snapshots.py`, `modules/notification_events.py`,
  `modules/community_trades.py`, `modules/college_prospect_ingest.py`) and in the Supabase edge functions
  (`supabase/functions/_shared/supabase_rest.ts`). `render.yaml` sets it only on the API and the two webhook services,
  not on `web-next`.
- No `service_role` / `SUPABASE_SERVICE` string anywhere under `web-next/` or `mobile/` source, config, or env files.
- Public client env names (all safe by design): `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
  `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_SENTRY_DSN`, `NEXT_PUBLIC_BILLING_BACKEND`, `EXPO_PUBLIC_*` (anon key, Sentry
  DSN, Google OAuth client ids, RevenueCat public SDK keys, AdMob unit ids).
- Repo secret scan (provider key prefixes, JWT shapes, private key headers): only documentation placeholders
  (`sk_test_REPLACE_ME`, `whsec_REPLACE_ME`). Tracked env files are `*.example` only; `.gitignore` covers `.env*` and
  `local_secrets/`.
- Server-only reads in `web-next` (`API_INTERNAL_URL`, share-card preview vars) are not `NEXT_PUBLIC_` and are
  server-component/route-handler only.

Residual risk (Zach): the checked-in `render.yaml` still lists the Render services; production runs self-hosted via
`docker-compose.yml` + Caddy. Confirm that the compose `web-next` service passes only the three `NEXT_PUBLIC_*` build
args (it does in the repo) and that the box env file for `mobile-api` is not shared with `web-next`.

---

## 3. `/v1` route audit

Method: AST scan of every `@app.get/post/patch/delete` in `services/mobile_api_service.py` (157 routes) plus the
mounted Sim router (`modules/sim/api.py`, `game_api.py`) and the two webhook services.

Auth results:

- 150+ routes depend on `require_user` (GoTrue `/auth/v1/user` check on every request, so revocation is honored).
- Intentionally unauthenticated: `/`, `/health`, `/ready`, `/v1/app-config`, `/v1/public/data-freshness`,
  `/v1/public/dynasty-values` (default settings only, never reads user/league/roster), `/v1/analytics/event`, `/v1/e`
  (optional user, allowlisted events, bot UA filter, its own rate bucket).
- `/v1/external/*` (11 routes): `require_external_api_key`, shared secret, `secrets.compare_digest`, uniform 401, 503
  if unconfigured. Reads only public player/news/trade-pool data. `/v1/content/feed`: `require_content_token`
  (SHA-256 of token compared with `hmac.compare_digest`, 32-character minimum).
- `/v1/founder/analytics`: 403 unless the server-issued `app_metadata.founder_ops` claim is true (not user-editable).
- Sim routes (`modules/sim`, mounted only when `SIM_ENABLED` is on): every route `Depends(require_user)`, store scoped by `user_id`, user JWT
  (RLS), filter values URL-quoted, 404 for another user's game id (no IDOR).
- Ownership: user-state routes (saved leagues, GM targets, trade outcomes, decisions, push tokens, community shared
  trades, scouting reports, watchlist, preferences, stances) read and write through the caller's own token, so RLS is
  the enforcement and the checked-in policies are correct. Cross-user reads that need the service role are narrow:
  pick'em leaderboard (`modules/games.py::fetch_league_picks`) first resolves the caller's own roster in that league
  (`_resolve_my_roster`) and returns graded totals only; community feed anonymizes and honors opt-outs.
- Pro gates: server-side for trade multi/ideas, Trade Hub, All Trades, Trade Finder, waivers, portfolio, GM plan,
  GM targets, college scouting writes, season sim, playoff odds, Draft Center, Sim (`_sim_is_pro`, fails to a
  retryable "plan_unverified" rather than a Free verdict). Free caps are enforced server-side too (weekly trade-eval
  limit, free league cap through `require_league_access`, ad-unlock pool in `modules/free_tier_ledger`). No Pro
  feature was found gated only in the client.
- Webhooks: Stripe signature verified (HMAC, constant-time, 5 minute tolerance, raw body) in both the Edge function and
  the Python service; RevenueCat uses a constant-time compare of the configured Authorization token. Both reject before
  doing work.

### H1 (High). Rate limiter bypass by rotating the Authorization header (FIXED, #2171)

- Location: `services/mobile_api_service.py`, `_client_rate_limit_key` / `_RateLimitMiddleware`.
- Issue: the bucket key was `ip:sha256(Authorization)`. A caller that sends a different bogus bearer token on every
  request gets a brand-new bucket each time, so the limiter never trips. Each bogus token also costs a GoTrue
  `/auth/v1/user` call in `require_user`, so it doubles as an amplifier against the Supabase auth quota (a Supabase
  throttle would then hit real users) and removes the brute-force protection in front of `/v1/external` and
  `/v1/content`.
- Exploit sketch: loop requests with `Authorization: Bearer <random>`; no 429 is ever returned.
- Fix (done): the middleware now also counts every request that carries an Authorization header against a per-IP
  bucket (multiplier `RATE_LIMIT_IP_CEILING_MULTIPLIER`, default 5x the per-identity limit, so many real users behind
  one NAT still fit). Tests added. The fail-open log line no longer prints the client IP.
- Who: code (done). Follow-up for Zach in M6.

### M3 (Medium). PostgREST filter strings built by interpolation (FIXED, #2173)

- Location: about 37 sites such as `services/mobile_api_service.py` (`league_id`, `outcome_id`, `prospect_id`, `emoji`
  interpolated unquoted into `...=eq.{value}` query strings), `modules/gm_targets.py`, `modules/decision_memory.py`,
  `modules/team_stance.py`, `modules/push_tokens.py`.
- Issue: an URL-encoded `&` or `,` in a path value (`%26or=...`) is decoded by FastAPI and appended to the PostgREST
  query as additional filters. Because these calls use the caller's JWT, RLS caps the damage to the caller's own rows
  and public tables, so this is defense in depth, but it also lets a caller bypass an intended row selection (for
  example delete several own rows with one call, or read another column set).
- Fix (done for the route-reachable sites): value is URL-quoted with `safe=""` through one helper. Tests added.
- Who: code (done).

### M4 (Medium, escalated). Referral Pro comp can be farmed with anonymous guest accounts

- Location: `services/mobile_api_service.py::_redeem_referral_code`, `modules/referrals.py` (3 referrals = 30 days of
  Pro via `user_settings.referral_program.comp_until`), `POST /v1/me/link-sleeper`.
- Issue: a referral is credited when the referred account links a Sleeper username. Anonymous Supabase sign-in is
  enabled (guest mode), so one person can mint many throwaway accounts, each redeeming the same code. The only brake is
  the per-IP rate limit. The comp window is an entitlement grant, which is why this was not changed here.
- Exploit sketch: script guest sign-ins, each calls link-sleeper with a referral code, referrer collects Pro.
- Fix options (needs a product/entitlement decision): require a non-anonymous (email or OAuth) referred account,
  require a distinct Sleeper username per referral and cap credits per referrer per month, and rate limit redemptions
  per IP. Server needs the `is_anonymous` claim from the verified JWT (not currently carried by `require_user`).
- Who: Zach/coridian_ decide; code follows. Not touched (entitlement area).

### M6 (Medium). `X-Forwarded-For` first hop is trusted

- Location: `_client_ip` (same function the limiter uses).
- Issue: the first `X-Forwarded-For` value is client-supplied unless the edge proxy overwrites it. With Caddy as the
  single edge (see `Caddyfile`) it normally does, but on any other topology (Render, a CDN in front of Caddy) a client
  can pick its own "IP" and get unlimited buckets.
- Fix: Zach confirms the production edge strips/overwrites inbound `X-Forwarded-For` (Caddy does by default unless
  `trusted_proxies` is set; a CDN in front must be added to that list). If a CDN is added, switch the code to take the
  right-most untrusted hop.
- Who: Zach (infra), then code if topology changes.

### L3 (Low). Free ad-unlock has no server-side ad verification

- Location: `_free_trade_idea_cap`, `modules/free_tier_ledger.py`.
- Issue: the client reports "I watched an ad" and the server grants one unlock per cooldown. A scripted client can
  claim unlocks without watching ads (a revenue, not a data, issue). Already hardened against the earlier
  trust-the-query-string bug.
- Fix: AdMob server-side verification (SSV) callback. Needs AdMob console config.
- Who: Zach (AdMob) then code.

### L5 (Low). `/health` discloses build SHA and deploy time

- Anonymous by design (ops uses it, and `feedback_live_means_deployed` relies on it). Low value to an attacker but
  confirms patch level. Fine to keep; noted for completeness.

---

## 4. Delete-account completeness (report only, nothing changed)

Flow reviewed: `supabase/functions/delete-account` + `_shared/account_deletion.ts` + `supabase_rest.ts`,
`docs/supabase_delete_account.sql`, `docs/account-deletion.md`.

What is covered: Stripe subscriptions cancelled first (abort on any Stripe error, so no deleted-but-billed user),
Sign in with Apple grant revoked when the client supplies a fresh code, `feedback_reports` and
`billing_webhook_events` rows deleted explicitly (they have no cascading FK), then `auth.users` deleted, which cascades
to: profiles, saved_leagues, user_settings, push_tokens, push_notification_log, gm_targets, trade_outcomes,
decision_log, decision_memory_*, team_stance, scouting_reports, prospect_watchlist, community_shared_trades (+reports),
community_trade_reactions, games_pickem_picks, guess_the_player_*, mobile_alert_reads, notification_*,
espn_credentials, and all sim tables. No Supabase Storage buckets are used anywhere in the repo, so there are no
storage objects to purge.

### H2 (High). `delete_user()` RPC is still client-callable

- Location: `docs/supabase_delete_account.sql` (`grant execute ... to authenticated`).
- Issue: the older SECURITY DEFINER function deletes the caller's `auth.users` row directly. Clients now use the edge
  function, but the RPC still exists and is granted, so a user (or a stale app build) can call it and skip Stripe
  cancellation, Apple revocation and the non-cascading cleanup. Result: a deleted account with a live paid Stripe
  subscription that keeps billing a card with no way to manage it, plus orphaned `feedback_reports` and
  `billing_webhook_events` rows.
- Exploit sketch: authenticated `supabase.rpc('delete_user')` from the browser console.
- Fix: revoke execute from `authenticated`/`anon`/`public` (SQL file section 1). Verified that neither web-next nor
  mobile calls the RPC any more.
- Who: coridian_ SQL. (Billing-adjacent, so not changed in code.)

### M5 (Medium, escalated). Gaps after deletion

1. RevenueCat: the subscriber record (App User ID = Supabase user id, plus any attributes) is not deleted or
   anonymized in RevenueCat; store subscriptions cannot be cancelled server-side (the client tells users to cancel in
   the store, documented). Fix: call RevenueCat "delete subscriber" in the edge function. Who: Zach (RC key and policy),
   then code.
2. Stripe: the subscription is cancelled but the Stripe Customer (email, name, payment methods) is kept. Fix:
   `DELETE /v1/customers/{id}` after cancel, or document retention for tax/dispute needs. Who: Zach.
3. `analytics_events.account_hash` (sha256 of user id with a static salt, see L7) is not deleted, so a deleted user's
   event history stays linkable by anyone who knows the id. Fix: delete by `account_hash` in the edge function using
   the same hash. Who: code (edge function change is in the deletion path, so escalated).
4. Other users' `user_settings.referral_program` rows still reference the deleted user's id as `referred_by` /
   referral entries (no FK). Low sensitivity (a UUID) but a dangling pointer.
5. Delete then re-signup resets the free allowances stored in cascading tables: `sim_free_season_claims` (one free sim
   season), `profiles.trial_ends_at`/trial eligibility (checkout already forfeits the trial when the email has a prior
   Stripe subscription, which limits but does not close this). Fix: keep a tombstone (hashed email or Apple/Google
   subject) outside the cascade. Who: coridian_ product + SQL.
6. Redis caches keyed by user id (profile, saved leagues, warm-up state, free-tier ledger) expire by TTL only; the
   free-tier ledger key can outlive the account. Low impact. Who: code.
7. Sentry (user id tag) and server logs keep the opaque id until their own retention expires. Who: Zach (retention).

---

## 5. PII in logs

Backend (`logger.*` / `print`): no email, token, Authorization header or ESPN cookie is logged. Findings:

- L2 (Low): `user_id` (opaque UUID) is logged in `Unhandled exception ... (user_id=...)`, `HTTP 5xx ... (user_id=...)`,
  the Stripe checkout failure line (billing code, not touched), and two keeper-penalty warnings. Pseudonymous and used
  for attribution; recommend keeping, and including the log retention window in the privacy policy. If a stricter
  stance is wanted, log a short hash instead.
- Fixed: the rate-limiter fail-open warning logged `ip:fingerprint`; it now logs the scope only (#2171).
- `modules/auth_supabase.py` `DYNASTYGM_AUTH` and `DYNASTYGM_STARTUP` stdout lines carry only operation names, status
  codes, hosts and booleans (no tokens).
- Rate-limit 429 lines log method, path and scope, not the client.

### M1 (Medium). Backend Sentry request bodies and credentials (FIXED, #2172)

- Location: `services/mobile_api_service.py` Sentry init; `POST /v1/espn/credentials`, `/v1/espn/leagues/preview`.
- Issue: the FastAPI/Starlette integrations attach request data to events. Sentry's default scrubber does not know
  `espn_s2` / `swid`, and JSON bodies are captured by default, so an unhandled error while saving ESPN cookies would send
  the cookies to Sentry. Exception messages and breadcrumbs could also carry bearer tokens or emails inside URLs.
- Fix (done): `modules/sentry_scrub.py` (`before_send` + `before_breadcrumb`) drops request bodies, cookies and query
  strings, redacts credential-shaped keys and JWT/bearer/email/URL-token values, keeps only the opaque user id, and
  init now sets `max_request_body_size="never"` and `send_default_pii=False`. Tests added.
- Who: code (done). Zach: confirm `SENTRY_DSN` project has "Prevent storing IP addresses" on and data scrubbing on.

Web and mobile: `sendDefaultPii: false` on both Sentry inits; web has two `console.error` calls that log the error
object only; mobile `console.warn` calls log push-token fetch/sync errors (no token values). No `console.log` of
sessions or tokens found. Pass.

### L7 (Low). Analytics account hash uses a static public salt

- Location: `modules/launch_analytics.py::hash_account_id` (`"dynastygm-analytics:" + user_id`).
- Issue: the salt is in the public repo, so the hash is a pseudonym, not anonymization: anyone holding a user id can
  recompute it. Fix: HMAC with a server-side secret, and record the change in the privacy policy. Who: code + Zach
  (new secret).

---

## 6. Other exposure

- CORS (backend): explicit allowlist (`WEB_APP_ORIGINS` + localhost:3000), `allow_credentials=False`, no wildcard,
  limited methods/headers. Pass. Edge functions: origin must equal `APP_BASE_URL` or `CORS_ALLOWED_ORIGINS`, no wildcard.
  Zach: make sure `WEB_APP_ORIGINS` / `APP_BASE_URL` are set in production so the web app is allowed and nothing else.
- Open redirects: checkout/portal return paths go through `_safe_return_path` (API) and `safeReturnPath` (edge: must start
  with a single `/`, no `//`, no backslash or CR/LF). Web post-sign-in return path is restored from localStorage via
  `safeReturnPath` with a TTL. OAuth `redirectTo` is `window.location.origin`. Pass.
- Security headers: web-next sets nosniff, X-Frame-Options DENY, HSTS, Referrer-Policy, Permissions-Policy.
- L4 (Low): no Content-Security-Policy (documented in `web-next/next.config.ts` as deferred until it can be tested in a
  real browser). Recommend a report-only CSP first. Who: code.
- L8 (Low, Zach / coridian_): in the Supabase Auth dashboard confirm anonymous sign-ins have CAPTCHA or a low per-IP
  rate limit, leaked-password protection is on, email confirmation is on, and "allowed redirect URLs" lists only the
  production origins. These are dashboard settings, not in the repo, and they bound M4 and the guest-account abuse.
- Supabase edge `verify_jwt`: true for checkout, portal, delete-account; false only for the two provider webhooks
  (signature/token authenticated) and `billing-plans` (public prices).
- Webhooks accept only POST with signature/token; error responses do not echo secrets.

---

## Fix tracking

| Item | PR | Notes |
|------|----|-------|
| H1 rate limiter IP ceiling, log redaction | #2171 | tests in `tests/test_mobile_api_rate_limit.py` |
| M1 Sentry scrubbing | #2172 | `modules/sentry_scrub.py`, `tests/test_sentry_scrub.py` |
| M3 PostgREST value quoting | #2173 | helper plus tests |
| H2, M2, L1 (and staged M7) | `docs/supabase_security_fixes_2026_11.sql` | coridian_ to review and run, NOT applied |

## Needs from Zach (secrets, billing, providers)

1. Decide M4 (referral comp abuse policy) and M5 items 1, 2, 5 (RevenueCat delete, Stripe customer delete, re-signup
   tombstone). Billing and entitlement code was deliberately not changed.
2. Confirm the production edge overwrites inbound `X-Forwarded-For` (M6).
3. Confirm `WEB_APP_ORIGINS`, `APP_BASE_URL`, `CORS_ALLOWED_ORIGINS` are set in production.
4. Sentry project: IP storage off, server-side scrubbing on; set retention to match the privacy policy.
5. Supabase Auth dashboard settings (L8).
6. If L7 is taken: provision a new `ANALYTICS_HASH_SECRET`. If L3 is taken: AdMob SSV key.

## Needs from coridian_ (SQL)

Run, after review, `docs/supabase_security_fixes_2026_11.sql` sections 1, 2 and 4 (section 3 only after the API
change). Then run its VERIFY queries and paste the output back so this audit can be marked confirmed against the live
database.

## Pass list

RLS enabled on every repo-defined table; service-role key absent from all client bundles; Stripe and RevenueCat webhook
authentication; external/content token comparisons; founder analytics authorization; Sim ownership; pick'em
membership check; free-tier ad-unlock server ledger; checkout/portal open-redirect guards; backend CORS; Sentry client
PII flags; no secrets committed.
