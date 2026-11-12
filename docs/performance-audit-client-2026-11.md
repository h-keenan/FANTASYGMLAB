# Client performance audit, 2026-11 (web-next + mobile)

Scope: the web app (`web-next/`) and the Expo app (`mobile/`). The backend speed pass is separate
(`docs/performance-audit-2026-11.md`) and was not touched. Goal: measure first, rank the real costs,
fix root causes that are safe, and keep behavior and visuals unchanged.

## Headline

All web numbers: production build (`next build` + `next start`, Turbopack), headless Chromium at phone
width (390x844, DPR 2, touch), **4x CPU throttle**, signed-in session, API + Supabase answered by a local
mock with 60 ms latency and *real* response bodies captured from the backend bench harness
(`scripts/bench_endpoints.py --bodies-dir`). Before = `origin/main`, after = this PR, same harness, same box,
medians of 3 cold-load runs (fresh browser context each). Total Blocking Time (TBT) is the sum of
long-task time over 50 ms; it is noisy on a shared laptop, so read it as direction, not exact ms.

| Web metric | Before | After | Change |
|---|---:|---:|---:|
| Shared first-load JS, every route (raw / gzip) | 874 KB / 257 KB | 753 KB / 223 KB | **-14% / -13%** |
| `/dashboard` first-load JS (raw) | 972 KB | 851 KB | -12% |
| `/trade-analyzer` first-load JS (raw) | 1,002 KB | 881 KB | -12% |
| Dashboard CLS (layout shift) | 0.110 | 0.000 | **fixed** |
| Players: bytes transferred on load | 2,563 KB | 994 KB | **-61%** |
| Waivers: bytes transferred on load | 1,602 KB | 906 KB | **-43%** |
| TBT, 4x CPU: dashboard / trade analyzer / players / waivers / GM plan | 208 / 251 / 279 / 367 / 172 ms | 138 / 229 / 210 / 291 / 117 ms | -34 / -9 / -25 / -21 / -32% |
| Duplicate `GET /v1/preferences` per page load | 2 | 1 | fixed |
| Trade Analyzer -> Players client transition: API calls | 5 | 2 | -60% |

| Mobile (static, no device) | Before | After |
|---|---:|---:|
| First-party modules evaluated before first frame | 404 (about 3.0 MB source) | 175 (about 1.0 MB source) |
| Screens evaluated at launch | 41 | 3 (Home, Login, Loading) + 5 top destinations warmed at idle |

The mobile numbers are module counts from the import graph (`scripts` were ad hoc, method below), not
measured Hermes startup time. No device or simulator build was made (see "Not measured").

## Method

- **Bundle per route**: `.next/diagnostics/route-bundle-stats.json` (Next 16 Turbopack has no per-route table in
  the build log), plus gzip of each chunk. `next experimental-analyze` was run too; its data file is binary, so
  chunk contents were attributed by string-matching package markers in the shared chunks.
- **Runtime**: Playwright-driven Chromium (CDP CPU throttle 4x), PerformanceObserver for FCP/LCP/CLS/longtask,
  `resource` timing for JS bytes, request log from the mock for waterfalls/duplicates, `next.router.push` for
  client route transitions.
- **Mobile**: `expo export --platform ios` (production Metro bundle) for bundle size/module count; a script over
  the TypeScript import graph (excluding type-only imports) to split what `App.tsx` pulls in eagerly from what
  only the navigator's screens pull in. Code reading for startup, contexts, lists, polling and image handling.

## What was already good (do not redo)

Earlier passes left the web in decent shape, and this audit confirmed it:
recharts is already behind `next/dynamic` (PlayerQuickView, radar/weekly charts) so it is not on the first-load
path; the dashboard loads progressively (`defer_trade_ideas`, then the season sim after first paint); the hero's
league reads are prefetched in parallel with the dashboard call; all data requests on a page start in parallel
(no serial waterfall found: on `/dashboard` every data call starts within about 1 ms of the others, after the
shared session lookup); context values are memoized. Mobile uses React Query with a persisted cache
(30 s stale, 24 h gc), `FlatList` with window/batch tuning on Players/Waivers/Trade Analyzer, `expo-image` with
`cachePolicy="disk"`, staged dashboard queries gated on `firstPaintDone`, and polling only on Live Draft and a
flag-gated Live Activity sync (nothing polls by default).

## Ranked findings

Impact is estimated for a typical phone session. "Fixed" items are in this PR.

| # | Finding | Evidence | Status |
|--:|---|---|---|
| 1 | **Shared layout chunk is 874 KB raw / 257 KB gz on every route**, including `/legal` and `/methodology`. About 248 KB of it was `@supabase/supabase-js`, which constructs and bundles Realtime (websocket), Storage and Functions clients that web-next never calls (it only uses `auth.*` and `.from()`). | Chunk attribution; esbuild comparison: `createClient` 222 KB / 58 KB gz vs auth-js + postgrest-js 121 KB / 30 KB gz | **Fixed** (-121 KB raw, -33 KB gz on all routes). Storage key is unchanged, so existing sessions keep working. |
| 2 | **Headshots: 350 px photos (20-40 KB each) in 24-34 px rows, all started at once.** Players loads 60 of them: 2.1 MB; Waivers 1.0 MB. The plain `<img>` had no `loading`/`decoding`. | `sleepercdn.com` responses on `/players` | **Fixed** (lazy + async decode; Players 2.56 -> 0.99 MB, Waivers 1.60 -> 0.91 MB). Follow-up: serve a ~72 px variant (Sleeper offers none; needs `next/image` optimizer or a cached resize route). |
| 3 | **Mobile launches by evaluating every screen.** `RootNavigator` statically imports ~40 screens and Metro's `inlineRequires` is off (Expo default), so the whole 2,381-module / 7.66 MB bundle's screen subtrees run before the first frame. 229 of 404 first-party modules (about 1.96 MB of 3.0 MB source) are reachable only through screens. | Import graph; `expo export` bundle 7.66 MB | **Fixed**: screens load on first render, top 5 warmed one per 150 ms turn after interactions. |
| 4 | **No GET dedupe or reuse on web.** Every page load sent `GET /v1/preferences` twice (two contexts read it); every route change re-fetched rankings/draft picks/rosters/IDP values (about 140 KB of rankings alone). Mobile gets this from React Query; web had no equivalent. | Mock request log | **Fixed**: in-flight dedupe for all signal-less GETs, plus a 10 s reuse window for four league reference reads only (`rankings`, `draft-picks`, `rosters`, `idp/values`), cleared by any write. Follow-up: SWR layer for the dashboard (a revisit re-sends 9 calls). |
| 5 | **Dashboard CLS 0.110.** The "Your team right now" skeleton was 188 px; the settled card is 324 px, so everything under it jumped 136 px. | `layout-shift` entries with sources | **Fixed** (skeleton reserves the settled height; CLS 0.000). |
| 6 | **Every page sends 2-3 separate `POST /v1/e` analytics calls** (page view plus per-feature events), each its own request with its own `getSession`. | Mock log | Follow-up: client-side batching needs the `/v1/e` contract to accept an array (backend). |
| 7 | **Always-mounted chrome ships in the shared chunk and hydrates on every page** (GmOrb, TradeOutcomePrompt, DesktopSidebar, PasswordRecoveryGate, PrivacyPill live in the root layout; about 170 KB of app code across the shared chunks). The framework itself (React DOM and the Next client runtime, the two largest remaining chunks at 235 KB and 159 KB raw) is the rest of the baseline. | Chunk sizes | Follow-up: `dynamic()` the signed-in-only chrome after auth resolves (needs a visual check on the orb, which the owner does not want redesigned). |
| 8 | **`globals.css` is 99 KB raw / 18 KB gz**, render-blocking. | Build output | Follow-up: split per-route CSS; low priority at 18 KB gz. |
| 9 | Mobile `AuthProvider` reads the stored auth scope, then `getSession()`, serially (one AsyncStorage read of latency). | Code | **Not changed**: the stored id must be in the ref before `onAuthStateChange` can fire, or the persisted query cache would be cleared at startup. Not worth the risk for one local read. |
| 10 | Mobile `inlineRequires: true` would defer third-party module evaluation too. | Expo default is `false` | Follow-up: needs a device build to validate side-effect ordering (reanimated, gesture-handler, notifications). Screen-level lazy loading (#3) was chosen because it is explicit, type-checked and has no ordering risk. |

## What changed

Web (`web-next/`)
- `src/lib/supabase.ts`: `AuthClient` + `PostgrestClient` composed directly (same wiring as `SupabaseClient`:
  anon key as `apikey`, user token as Bearer for table calls, same `sb-<ref>-auth-token` storage key). Adds
  `@supabase/auth-js` and `@supabase/postgrest-js` as direct dependencies at the versions already installed
  (2.117.3); `@supabase/supabase-js` stays for the `Session` type only.
- `src/lib/requestCache.ts` (+ tests): in-flight dedupe and the 10 s reference-read window; per-consumer clones
  so a page mutating its response cannot leak into another; failures never cached; a write (or a write that lands
  while a read is in flight) invalidates. `lib/api.ts` routes plain GETs through it; reads with a caller
  `AbortSignal` bypass it so one consumer cannot cancel another's request. `vitest.setup.ts` clears it between tests.
- `src/components/PlayerAvatar.tsx`: `loading="lazy" decoding="async"` (dimensions were already fixed).
- `src/components/TeamStatusHero.tsx`: skeleton reserves the settled hero height.

Mobile (`mobile/`)
- `src/lib/lazyModule.ts` (+ tests): memoized lazy loader and one-per-turn preload scheduler.
- `src/navigation/RootNavigator.tsx`: 38 screens become `lazyScreen(() => require(...))`; Home, Login and Loading
  stay eager. `Dashboard`, `Trades`, `Players`, `GmPlan`, `Waivers` are warmed after `InteractionManager` settles.
  ESPN gating, routes, params and options are untouched.

Parity notes: web already code-splits per route, so mobile's lazy screens are the equivalent of what Next does for
free. Request dedupe/reuse on web is the equivalent of mobile's existing React Query layer. The avatar change has no
mobile twin because `expo-image` already caches to disk and downsamples. Mobile still bundles Realtime via
`createClient`; in a 7.66 MB bundle that is not worth diverging the twin client for.

## Not measured (be honest)

- No Hermes/device startup time, no TTI on a real phone: the owner's rule is no autonomous TestFlight builds and
  no simulator build was made. The mobile gain is stated as modules/source deferred, not milliseconds.
- Web numbers are a laptop with a 60 ms mock; real LCP is dominated by API time (see the backend audit). CPU
  throttling at 4x approximates a mid-range phone, not a low-end Android.
- Mobile `eslint` could not run (the shared `node_modules` is stale for `eslint/config`); `tsc --noEmit` and the
  node test suite pass.

## Verification

- `web-next`: `tsc --noEmit`, `eslint` on changed files, full `vitest run` (228 files, 1,621 tests) pass.
- `mobile`: `tsc --noEmit`, `npm test` (611 tests, including the new lazy-loader tests) pass; `expo export
  --platform ios` bundles successfully (7.66 MB, same as before: this change moves evaluation, not bytes).
- `node scripts/check_lib_twins.mjs` passes.
