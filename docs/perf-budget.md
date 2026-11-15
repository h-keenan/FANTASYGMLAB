# Performance budget and measurement

Phone-first: about 95% of users are on iPhone Safari / the PWA. Everything here is measured on a phone-shaped
setup, not on a fast laptop.

## Harness (`scripts/perf/phone_perf.mjs`)

Chrome headless, 390x844 @ DPR 3, touch, iPhone UA, CDP CPU throttle (default 4x), CDP network profile (default
`4g`: 70 ms RTT, 9 Mbps; `NET=fast3g` for 150 ms / 1.6 Mbps), production build (`next build && next start -p 3190`,
`.env.local` with dummy Supabase and `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`). The backend is a Playwright
route mock (`scripts/sim_layout_playwright/simmock.mjs`, real response shapes) with a fixed `API_MS` latency (default
60), so before/after runs are comparable on one machine. Third-party hosts are aborted so runs are deterministic.

```
PW_CORE=<playwright-core>/index.mjs CHROME_PATH=".../Google Chrome" BASE=http://localhost:3190 \
  CPU=4 NET=4g API_MS=60 RUNS=3 OUT=perf.json node scripts/perf/phone_perf.mjs [sim|desk|sim-advance]
```

Per cold load: FCP, LCP, TBT, long tasks, CLS, JS/CSS KB, API call count and **request waterfall** (start offsets),
duplicate GETs, DOM nodes, `backdrop-filter` element count, heap. Per interaction step: INP-style event duration,
long-task total, LoAF blocking, CDP script/layout/style time and counts, DOM mutations (render-work proxy), API calls
and waterfall, and for scroll steps rAF frame deltas (p95, frames over 25 ms). Flows: Sim hub -> open game (Home),
footer menu sheet, tabs Team (28 rows) / Players (200) / Trades / League, player sheet, advance week; Desk sample league
(Today, Roster, Top moves, Trade). The Desk flows use `/sample-league` (shipped templates, no backend); real Desk
pages need captured API bodies (`scripts/bench_endpoints.py --bodies-dir`).

Server side: `python scripts/bench_sim_game.py --rtt-ms 35` (per-endpoint CPU p50/p95, store round trips, bytes).
Production latency cannot be measured from CI: every API response now carries `Server-Timing: app;dur=<ms>` (the sim
endpoints also `sim;dur=`), readable in DevTools or `PerformanceResourceTiming.serverTiming`; requests slower than
`SLOW_REQUEST_LOG_MS` (default 1500) are logged as `slow request METHOD path -> status in N ms`.

## Budget check (`scripts/perf/check_perf_budget.mjs`)

Run in `web-next/` after `next build`. Fails when a route's first-load JS exceeds `web-next/perf-budget.json`
(2026-11-14 build + 5%) or when CSS `@keyframes` animate a layout/paint property (`background-position`, box
model, `box-shadow`, `filter`, `backdrop-filter`): animate `transform`/`opacity` instead.

## Rules learned

- Never animate `background-position` (or anything but transform/opacity) on a fixed full-viewport layer. It repaints on
  the main thread every frame and forces every `backdrop-filter` glass card above it to re-blur. Measured: about 1.7 s
  of main-thread time per 5 idle seconds at 4x CPU, with 600 style recalcs and 600 paints. The same drift as a
  transform costs about 60 ms.
- Read views are pure functions of (snapshot, folded state, query): memoise against the shared state instance
  (`modules/sim/game_api.py::_memo_view`) instead of rebuilding per request.
- Independent reads start together; reads that need only an id start before the answer that carries the id.

## Known remaining hotspots (not fixed, with evidence)

- First API request starts about 1.2-1.7 s after navigation at 4x/4G: bundle download + evaluation + hydration. 1.48 MB raw
  JS loads on `/gm-game`, 35% of it executes at first paint (supabase auth-js 123 KB at 18%; the whole sim game screen
  loads with the hub). Splitting hub from game screen and trimming auth-js are the next levers.
- First layout of the Team lineup (28 rows) costs about 400-700 ms at 4x once per session (second visit 34 ms): cold glyph/
  font shaping in Chrome. Not confirmed on iOS, so not changed.
- `prestige-glow-pulse` / `premium-glow-pulse` animate `box-shadow`/`filter`; `onboarding-field-drift` is still used on the
  landing and onboarding shells.
- Every element with an inline `var(--color-surface-*)` gets `backdrop-filter: blur(10px)` (15 on Sim Home, 21 on Desk
  Today). Nested ones blur only their parent's flat colour; removing them needs a visual A/B on a real device.
- League rosters response is 153 KB (183 KB dynasty) uncompressed; gzip applies, field pruning has not been done.
- Sim notifications still wait for the game read (non-critical bell); Desk real endpoints were not benchmarked here.

## Round 2 findings (2026-11-14)

Measured and deliberately not changed:

- **Lazy sheets in the Sim hub** (player / team / pick / sim-to sheets as dynamic imports): `/gm-game` first-load JS
  1296 -> 1261 KB, but a controlled A/B (same box, built back to back, 5 runs x 2 alternations, 4x CPU, 4G) showed no
  gain in FCP, LCP or time of the first API request (888-1074 ms without, 1110-1291 ms with). Not shipped. Note that run-to-run
  noise on a shared laptop was larger than this effect (one earlier pair differed by 700 ms for no code reason): always A/B on one
  box, alternating, never compare against an old run.
- **Supabase auth-js (30 KB gz of the 250 KB gz shell every route pays)**: it is the session source of truth for the first request;
  deferring it means re-implementing token refresh. Not changed.
- **Nested `backdrop-filter`**: 4 of 13 blurred elements on Sim Home are nested in another blurred element. Removing all blur
  changed scroll-time compositor swap time by about 16% in desktop Chrome (noise level) and the main thread not at all, and an
  inner blur can be the thing that hides text scrolling under a sticky header inside a card. Needs a real-device GPU trace; not changed.
- **League rosters payload**: 154 KB raw but 13 KB gzipped on the wire; `top_assets` (25 KB raw) is the only duplicate. A shape
  change that web and the app both read for about 1 KB on the wire is not worth it.
- **Desk server endpoints** (`scripts/bench_endpoints.py`, stub Sleeper, warm p50 CPU, 200 OK): waivers 553 ms (114 KB, cold 1.3-4.3 s),
  trade_analyzer 331 ms, matchup 65, player_search 62, rankings 55, dashboard 33, dashboard_deferred 40, my_team 30, player_quick_view
  35, team_rankings 24, player_rank 22, gm_plan 15, trade_hub 6, leagues_glance 1.5. Waivers' per-roster work (roster value model,
  `trade_lineup_model.run_weeks`, deep copies) is recomputed every request; its league-wide pool is already Redis single-flighted.
  Caching it needs a key over (roster, rosters, valuation, strategy, stats freshness) to stay exact: next candidate, not done blind.
  Dashboard and Today already load progressively and in parallel (`dashboard/[leagueId]/page.tsx`).
- `Server-Timing: app;dur=` now covers all of these endpoints (see #1944), so production numbers will show per endpoint.
