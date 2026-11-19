# Design: cookie-based web auth session for server-side first paint

Status: proposal (design only, no code). Date: 2026-11-18. Scope: `web-next/` only.
The native app (`mobile/`) is unchanged. Next stays pinned at 16.4.1.

## TL;DR

- Today the token lives in `localStorage`, so a server component cannot see it. The HTML renders skeletons
  (FCP ~650 ms) and the first API call starts ~2.5 s in on fast3g (it needs the JS download, hydration and a token read).
- Proposal: keep the Supabase session in a **server-readable cookie**, refresh it in Next middleware, and let
  server components call FastAPI with `Authorization: Bearer <access_token>` exactly as the browser does now.
  **The backend needs no change**: it never sees the cookie.
- Estimated gain: first data 2.5 s -> ~1.1-1.9 s, useful content 3.9 s -> ~2.2-3.0 s (fast3g). Wide uncertainty; see section 5.
- Cost: roughly 10-14 engineering days plus a security review and a staged rollout. Real risks are refresh-token
  races (forced global sign-outs) and the httpOnly-vs-client-needs-a-token tension (section 2.5).
- Recommendation: **conditional go**, after a 2-day flag-gated spike on one route to validate the gain. A cheaper
  alternative (section 8, early-fetch script) captures part of the win with no auth change and should be done first.

## 1. Current state

### 1.1 Client
- `web-next/src/lib/supabaseAuth.ts`: `new AuthClient({ storageKey: "sb-<ref>-auth-token", persistSession: true,
  autoRefreshToken: true, detectSessionInUrl: true, flowType: "implicit" })`. Built from `@supabase/auth-js`
  directly (no `createClient`, no `@supabase/ssr`). Storage is default `localStorage`.
- `web-next/src/lib/supabase.ts`: a lazy facade (perf round 5, PR #2162). `auth.getSession()` answers from
  `peekStoredSession()` (parses `localStorage[storageKey]`, trusted only if the access token has >= 120 s left and
  the URL is not an auth callback). Otherwise it `import()`s the ~100 KB auth chunk. `onAuthStateChange` loads the
  real client on idle (<= 4 s) so refresh and other-tab sign-out are still observed.
- `web-next/src/context/AuthContext.tsx`: `getSession()` on mount, then `onAuthStateChange`; exposes
  `signIn` (password), `signInWithOAuth` (`redirectTo = window.location.origin`, or `linkIdentity` for guests),
  `signInAnonymously`, `signOut`, `deleteAccount`, `resetPassword`. Sign-out also clears cached Portfolio snapshots.
- `web-next/src/lib/api.ts` `authorizedRequest`: `await supabase.auth.getSession()`, throws 401 "Not signed in" if
  absent, then `fetch(env.apiBaseUrl + path, { headers: { Authorization: "Bearer <token>" } })`. The token is also
  part of the read-coalescing cache key. About 70 call sites use non-GET methods. Billing and
  `delete-account` use the same token against Supabase edge functions.
- No `middleware.ts` / `proxy.ts` exists today. There are no auth cookies.

### 1.2 Flows
| Flow | Today |
| --- | --- |
| Password sign-in | `signInWithPassword` -> token pair written to localStorage -> `SIGNED_IN` event |
| OAuth (Google/Apple) | **Implicit flow**: redirect to provider via Supabase, return to `origin` with `#access_token=...&refresh_token=...`; `detectSessionInUrl` parses the fragment and stores it. No PKCE, no server callback route. |
| Email confirm / recovery | Same fragment parsing; `PASSWORD_RECOVERY` event drives `PasswordRecoveryGate` |
| Refresh | auth-js timer in the page refreshes ~10 s before expiry and writes the new pair to localStorage |
| Sign-out | `auth.signOut()` (supabase default scope is global: revokes refresh tokens server-side), removes the key |
| Multi-tab | auth-js uses the `storage` event + a navigator lock; a refresh in one tab is picked up by others |

### 1.3 Backend authentication
`services/mobile_api_service.py::require_user` takes the `Authorization` header and calls GoTrue `/auth/v1/user`
via `auth_supabase.fetch_auth_user_cached` (cached) on each request. It deliberately does **not** verify JWT
signatures locally and holds no JWT secret; GoTrue is the source of truth for expiry and revocation. A second path
(`_bind_espn_login`) parses the same bearer header. CORS (`CORSMiddleware`): origins from `WEB_APP_ORIGINS` +
`http://localhost:3000`, `allow_credentials=False`, headers `Authorization, Content-Type`, methods
GET/POST/PATCH/DELETE. The API reads no cookies today.

## 2. Proposed design

### 2.1 Library choice
`@supabase/ssr` (cookie storage for `createServerClient` / `createBrowserClient`) is the intended fit. It builds on
`@supabase/supabase-js` (already a dependency, ^2.117.3) and works with Next 16 App Router `cookies()`. Nothing in Next 16.4.1
blocks it, but it is not installed, and adding it needs a bundle-size check because the app deliberately avoids
`createClient()` (Realtime/Storage not bundled). Fallback ("custom equivalent"): a ~150-line module that (a) reads/writes
the session in chunked cookies named `sb-<ref>-auth-token(.N)` and (b) calls GoTrue `/auth/v1/token?grant_type=refresh_token`
with `fetch` on the server. Recommend the custom module for the server side (zero client bundle) and `@supabase/ssr` only if
its chunk format is wanted for interoperability. Decide in the spike (verify the version constraints against the lockfile then).

### 2.2 Cookie layout
- Name: `sb-<ref>-auth-token` (+ `.0`, `.1` chunks of ~3.1 KB). A Supabase JWT + user JSON is commonly 2-4 KB (more with large
  `user_metadata`); browsers cap ~4 KB per cookie. Store only `{access_token, refresh_token, expires_at}`, not the user object.
- Flags: `Secure`, `SameSite=Lax`, `Path=/`, host-only (no `Domain`; web and API are different sites anyway),
  `Max-Age` = refresh-token lifetime. `HttpOnly`: see 2.5.

### 2.3 Middleware refresh
Add `web-next/src/proxy.ts` (Next 16 name for middleware; confirm against the pinned version in the spike).
Matcher: signed-in page routes only; exclude `_next/static`, images, `/api/lp`, `/public-trade-values`, robots, and all public
marketing/SEO routes (they stay static/cacheable and never touch cookies). On a matched request:
1. No cookie -> pass through (unauthenticated render, same as today's signed-out path).
2. If `expires_at - now < 60 s`, refresh with GoTrue using the refresh token, single-flight per request, set the new cookie on the
   response and forward it on the request headers so the server component in the same request sees the new token.
3. On refresh failure (revoked/reused), clear the cookie and continue unauthenticated.
Server components never refresh (cookies are read-only there). Prefetch/RSC requests must not each trigger a refresh race:
only refresh inside the margin and rely on 3.4.

### 2.4 Which routes server-fetch first-paint data
Start with the highest-traffic signed-in surfaces, one at a time, behind the flag: `/dashboard`, `/leagues` (league list),
`/portfolio`, then `/my-team` and `/matchup` (league-scoped). For each, fetch only the 1-2 endpoints that gate first useful content
(see `docs/league-switch-first-useful-performance.md`). Everything below the fold, modals, tools and rarely-used pages stay
client-fetched. Public routes (rankings, trade value chart, sample league) stay static. A signed-out visitor sees today's output.

### 2.5 httpOnly versus what the browser needs
Tension: the browser still calls `api.fantasygmlab.com` directly with a bearer token (~70 mutating call sites, share-card blobs,
billing). An httpOnly cookie is unreadable by JS. Options:

- **A. Non-httpOnly cookie (the `@supabase/ssr` default).** Simplest; client keeps reading the session. XSS exposure equals
  localStorage today (no regression, no gain). Cookie is sent on every same-origin request (3-4 KB header bloat on assets
  unless path-scoped or assets are served cookieless).
- **B. httpOnly cookie + same-origin token endpoint.** `GET /auth/session` (route handler, `Cache-Control: no-store`, requires
  `Sec-Fetch-Site: same-origin` and a custom header) returns only the short-lived access token (<= 1 h); the client keeps it in
  memory and calls FastAPI as today. The refresh token is never script-readable, so XSS can no longer exfiltrate a long-lived
  credential (it can still use the session while the page is open). Replaces the `peekStoredSession` fast path for the first client call.
- **C. Full BFF proxy** (`/api/proxy/*` forwards with the cookie). Strongest isolation but adds a hop to every API call, moves CSRF
  to a much larger surface and loads the Next server. Not recommended.

Recommendation: A as the phase-1 stepping stone, B as the target. The rest of the doc holds for both.

### 2.6 Server components calling FastAPI
A server-only helper `serverApi.ts` (`import "server-only"`):
- reads the (refreshed) cookie via `cookies()`; no session -> returns `null` and the page renders its signed-out/skeleton state;
- `fetch(env.apiBaseUrl + path, { headers: { Authorization: "Bearer ..." }, cache: "no-store" })` with a tight timeout (~1.5 s);
  on timeout/error the page falls back to client fetch, never blocks;
- never pass the token to client components; pass only data;
- ship raw data and keep privacy-mode masking (`maskIfPrivate`) client-side to avoid hydration mismatch;
- seed the existing client request cache (`requestCache.ts`) with the server data so hydration does not refetch. Today the cache key
  embeds the access token (`${accessToken}|...`), so it must move to a user-id key (a refresh would otherwise invalidate the seed);
- backend GoTrue verification is cached, so a server fetch costs the same as a browser fetch;
- confirm Next-server and API regions; the gain shrinks if they are far apart.

### 2.7 Streaming and Suspense
Layout/chrome flush immediately (this is today's ~650 ms FCP). The data module is a server component inside
`<Suspense fallback={<ExistingSkeleton/>}>`; Next streams the resolved HTML into the same response. Never `await` the API in the layout
or page body (that would add the API time to TTFB and FCP). Reuse existing skeleton components so the visual contract and the
skeleton guard tests are unchanged. On failure render the skeleton and let the client fetch retry.

### 2.8 What stays client-side
All interactivity and mutations (trade analysis, lineup actions, imports, billing, delete-account), data after first paint
(league switching, tabs, search), live/draft polling, share-card generation, privacy-mode masking, the lazy auth client for the sign-in
forms, and public pages. `AuthContext` keeps its API and initializes from a server-rendered session-presence hint (never the token),
which also removes the signed-in chrome flash.

## 3. Threat model

### 3.1 CSRF
Cookies are sent automatically, so:
- **FastAPI is not exposed**: different site, browser calls carry no credentials, CORS `allow_credentials=False`, auth only via the
  `Authorization` header. A cross-site form/fetch cannot attach a bearer token. No CSRF risk on the ~70 mutating endpoints, and it
  must stay that way: **do not add cookie auth to FastAPI.**
- **New surface is Next-origin routes** that accept the cookie: middleware refresh (idempotent), `/auth/session` (option B),
  sign-in/out/callback handlers. Existing same-origin routes (`/api/lp`, share-card routes) must be audited for cookie reliance
  (today they take a bearer header).
- Mitigations: `SameSite=Lax` (blocks cross-site POST), `Origin` / `Sec-Fetch-Site` check on every state-changing Next handler
  (reject unless same-origin), custom-header requirement on fetch-only handlers, no state change on GET (sign-out is POST; Lax still
  sends cookies on top-level GET navigations). A double-submit token is unnecessary if the Origin check is enforced and all
  business mutations stay on FastAPI.

### 3.2 Cookie flags and size
See 2.2. Chunk writes must be atomic: write all chunks and delete stale higher-index chunks in the same response; a partial/corrupt
read is treated as signed out, never thrown. Keep total cookie bytes below ~8 KB. A `__Host-` prefix (Secure, Path=/, no Domain) is a
good fit but renames the cookie, which conflicts with dual-read; adopt in phase 2. Relax `Secure` on localhost only.

### 3.3 XSS exposure versus localStorage
- localStorage today: any XSS reads access + refresh token and can take them off-device; the refresh token outlives the tab.
- Option A: identical exposure (no regression).
- Option B: refresh token unreachable; XSS only acts while the victim's page is open, or calls `/auth/session` for a <= 1 h token.
  A real improvement, not immunity. Tightening CSP with nonces is orthogonal and a separate item.

### 3.4 Refresh-token rotation and reuse detection
Supabase rotates refresh tokens and detects reuse (reuse outside the configured interval, default 10 s, revokes the session family).
The risk is self-inflicted: concurrent middleware refreshes (parallel RSC requests/prefetches) plus the browser's own auth-js refresh
could present the same refresh token twice, and a reuse outside the interval **signs the user out everywhere** (including the app).
Mitigations: during phase 1 the browser stays the primary refresher and middleware refreshes only when the token is already expired or
< 60 s left; confirm the reuse interval is >= 10 s (Needs Zach); single-flight per request; in option B disable browser `autoRefreshToken`
so exactly one refresher exists. Instrument `refresh_token_already_used` (section 6).

### 3.5 Session fixation, logout everywhere, log leakage
- Fixation: the session is issued by GoTrue and written fresh on sign-in; never accept a token from a query parameter into the cookie
  except via the validated callback. Rewrite the cookie on sign-in and on guest upgrade (`linkIdentity`).
- Logout: a POST handler clears all chunk cookies and calls GoTrue `signOut` with the token (`global` for sign out everywhere, `local` for
  this device; keep today's default). A cookie whose refresh fails is treated as signed out. Cross-tab: `BroadcastChannel` ping so other
  tabs drop state (replaces the `storage` event auth-js relied on).
- Logs: Authorization and Cookie must never be logged. Audit Next access logs, any reverse proxy, Sentry (strip `cookie`, `authorization`,
  request bodies), and the backend slow-request log (method/path/status only; confirm no headers). Server fetch URLs carry no token.
  Note the current implicit-flow fragment is itself a leakage vector (tokens in URL/history until stripped); PKCE removes it.

### 3.6 OAuth callback (Google, Apple) and PKCE
Switch the web flow from implicit to **PKCE**. Add `GET /auth/callback` (route handler): receives `?code=`, exchanges it with GoTrue using
the code verifier, writes the session cookie, redirects to the intended path (validated against a same-origin allowlist to avoid open
redirect). The verifier lives in a short-lived httpOnly Lax cookie (~10 min) set when the flow starts, so initiation must use the
cookie-aware client. `redirectTo` changes from `window.location.origin` to `<origin>/auth/callback`. Google and Apple return to Supabase
first, so provider consoles are unchanged, but **Supabase Redirect URLs must allow the new path**. Email confirmation and recovery links
move to the token-hash `/auth/confirm` pattern; the fragment path keeps working during dual-read. Test guest `linkIdentity`
(manual-linking is already enabled in the dashboard). Mobile OAuth is separate and unaffected.

### 3.7 CORS between web origin and `api.fantasygmlab.com`
Browser calls are unchanged (`Authorization` header, no cross-origin cookies), so CORS stays `allow_credentials=False`:
**do not enable credentials.** Server-to-server fetches are not subject to CORS. `WEB_APP_ORIGINS` must keep listing the web origin(s)
(including preview/staging).

## 4. Native app implications
`mobile/src/lib/supabase.ts` uses its own client with AsyncStorage and bearer tokens; it shares no code path with `web-next/src/lib/supabase*.ts`.
Nothing changes there. The backend only ever needs the **bearer** form, because the Next server extracts the token from the cookie and forwards it
as a bearer header, so **the backend must not need to accept cookies** and should not (keeps the CSRF story trivial and leaves `require_user` and
`_bind_espn_login` untouched). For the web/app parity rule this is an explicit exception: infrastructure change, no UI delta. One cross-platform
effect: a global sign-out or a reuse-detection revocation triggered by the web also ends the app's session (same Supabase session family).

## 5. Expected gain (ms)

Inputs (fast3g, 4x CPU, from the task brief): FCP ~650 ms (skeleton HTML), first API call starts ~2.5 s, useful content ~3.9 s. The perf4/perf5
scratchpads exist but I did not re-run traces for this doc; the figures below are derived from those inputs and the known critical path, not new measurements.

Today's path to first data: HTML (~650 ms) -> shared JS download (~1.0-1.3 s at 1.6 Mbps) -> parse/execute/hydrate under 4x CPU (~0.5-0.8 s) ->
AuthContext mount, `getSession` from localStorage -> request starts (~2.5 s) -> API TTFB + RTT + payload (~0.9-1.4 s) = useful content ~3.9 s.

With streamed server fetching: the shell still flushes at ~650 ms (middleware adds ~5-30 ms when the token is fresh and no network call is needed). The
server starts the API call as soon as it renders the route: server-to-API RTT ~10-60 ms plus API processing (~200-700 ms for the targeted endpoints, GoTrue
verify cached), then the chunk streams down the open connection. Transfer on 1.6 Mbps: ~30-60 KB gzip = 150-300 ms (RSC+HTML is larger than JSON; up to ~400 ms).
First data on screen (needs no JS): ~650 + 300-800 + 150-400 = **~1.1-1.9 s**, about **0.6-1.4 s earlier** than today's 2.5 s start plus response. Useful content:
the streamed module is real HTML so it paints before hydration, while interactivity and other client-fetched modules still wait for JS, so overall useful content lands
**~2.2-3.0 s (gain ~0.9-1.7 s)** if the gated module is the only blocker, less if others remain client-fetched.

Uncertainty, honestly:
- Per-endpoint server latency varies several-fold; a slow endpoint (multi-league portfolio) may land after 2.5 s, giving zero or negative gain unless the timeout fallback kicks in.
- Hosting topology (Next server far from API) can add 100-300 ms.
- A proxy/CDN that buffers responses defeats streaming entirely; must be verified on the real host.
- Cookie header (3-4 KB) on requests costs ~20 ms each upstream on 3g; matters for assets unless path-scoped.
- If client-cache seeding fails the user downloads the data twice.
- Hydration cost under 4x CPU is unchanged; this does nothing for TBT/INP.
- Warm repeat visits already benefit from the lazy fast path, so the gain there is smaller (maybe 0.3-0.8 s).
The spike must measure with the repo's existing fast3g harness before any rollout.

## 6. Rollout plan

1. **Flag** `WEB_COOKIE_SESSION` = `off | dual | on` (server env, plus a per-user percent bucket). Kill switch: set `off`; `off` must be byte-identical to today.
2. **Phase 0 (spike, dark)**: middleware + `serverApi` on one route for allowlisted internal users; measure.
3. **Phase 1 (dual-read, mirror)**: auth-js on localStorage stays the source of truth; on `SIGNED_IN` / `TOKEN_REFRESHED` the client POSTs the session to a same-origin
   `/auth/session` (Origin-checked) which sets the cookie. Server components use the cookie when present, else render skeletons. **Existing users migrate without logout**:
   their localStorage session (already readable via `peekStoredSession`) is mirrored to a cookie on the next page load; no re-login. Two-refresher risk handled per 3.4.
4. **Phase 2 (cookie is truth)**: browser moves to cookie-backed storage (A) or in-memory token (B), PKCE callback ships, browser autoRefresh off in B. Keep reading legacy
   localStorage for 30 days: if found with no cookie, migrate once and delete the key; then drop the fallback.
5. **Rollback**: flag `off`. In phase 1 localStorage is authoritative, so users are unaffected. In phase 2, dual-write localStorage for the first N days so `off` still finds a valid
   session; after the window, rollback means re-login for users with a stale localStorage copy (accepted and documented).
6. **Observability** (never log tokens): middleware refresh attempts/success/failure, `refresh_token_already_used`, cookie parse/chunk-mismatch failures, server-fetch latency histogram and
   timeout-fallback rate per route, signed-out-rate delta (the key regression signal), FastAPI 401 rate on server calls, and RUM first-data/useful-content split by flag bucket
   (existing Server-Timing + RUM). Rollback triggers: sign-out rate up > 0.5 pp, server-fetch 401 > 1%, or p75 first-data regression on any route.

## 7. Needs Zach

1. Supabase Dashboard > Authentication > URL Configuration: add `https://<web origin>/auth/callback` and `/auth/confirm` (plus preview/staging origins) to Redirect URLs.
2. Auth settings: confirm refresh-token rotation is on and the **reuse interval** (>= 10 s); confirm JWT expiry (1 h assumed) and session timebox/inactivity (drives cookie `Max-Age`).
3. Email templates: switch confirmation/recovery links to the token-hash form (phase 2).
4. Google/Apple consoles: expected no change (callback is Supabase's); verify only.
5. Web-host env vars: `WEB_COOKIE_SESSION`; server-side Supabase URL + anon key (already public; no service-role key needed or wanted); an internal `API_BASE_URL` for server fetches if different from the public one.
6. Domain/cookie: confirm the production web hostname (host-only cookie assumed, no shared parent domain), HTTPS everywhere, and that the host/proxy streams responses unbuffered.
7. API `WEB_APP_ORIGINS` must still list the web origin(s); no CORS credential change.
8. Security review sign-off on sections 3.1-3.6 before phase 2 (phase 0/1 can run on staging without it).
9. Hosting regions of web server vs API for the spike.

## 8. Effort, risks, recommendation

Effort (one engineer): spike 2 d; middleware + cookie module + `serverApi` + cache seeding 3 d; PKCE/callback + templates + guest-link tests 2 d; first three routes
(Suspense, skeleton parity, tests) 2-3 d; flag/dual-read/migration + observability 1-2 d; security review and fixes 1-2 d. Total ~10-14 d plus ~2 weeks elapsed soak.

Risks: forced global sign-outs from refresh reuse (highest); hydration mismatch or double fetch; streaming buffered by the host (invalidates the gain); header bloat; test churn
(many tests mock `supabase.auth`); SSR now depends on the API (load and failure modes move into the Next server); signed-in routes become dynamic (public routes unaffected);
Apple/Google edge cases; an ongoing obligation to keep both storage paths correct until localStorage is retired.

Recommendation: **conditional GO, spike first.** If the spike shows first-data below ~1.9 s on fast3g for `/dashboard` with streaming intact on the real host, proceed through
phase 1 (low risk: localStorage stays authoritative, so no logout risk) and decide on phase 2 later. Phase 2 is where the security benefit (option B) and most risk live, and the
performance gain does not need it. If the spike misses, NO-GO.

Alternatives (do first or instead):
- **Update 2026-11-19: the early-fetch step shipped for Today (`/dashboard/<league>`)**, see `web-next/src/lib/earlyFetch.ts`. Measured cold, fast3g, 4x CPU, 5 runs:
  first API request ~3.6 s -> ~0.6 s, useful content 3.85 s -> 2.73 s (median). Cookie SSR must beat that new baseline.
- **Early-fetch inline script**: a tiny script in `<head>` reads the same localStorage token and starts the first API call (kept on `window`) before the framework JS loads, plus
  `<link rel="preconnect" href="https://api.fantasygmlab.com">`. Estimated to move first-API start from ~2.5 s to ~0.7-0.9 s (it needs only the HTML); first render then still waits for hydration,
  so ~1.5-2.2 s. No cookies, no backend change, keeps the #2162 lazy auth work, 1-2 days, trivially reversible. Costs: a CSP nonce, same XSS exposure as today, and a refresh path for nearly
  expired tokens. **Suggested first step**: it captures much of the gain and shows how much cookie SSR adds on top.
- **Edge-cached public first paint**: ISR/`s-maxage` HTML with real content for signed-out-safe parts (rankings, values, tool shells). No auth change, near-zero risk, helps SEO and
  logged-out visitors, but does not remove the signed-in wait for personal data.
