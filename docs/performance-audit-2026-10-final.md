# Final performance audit, 2026-10-23

Scope: everything shipped this week (progressive Dashboard #1436, Portfolio
#1475, This week strip, privacy layer #1466, Sleeper budget #1429, Free-tier
league gate #1479, imported-league pages, share-card prefetch #1476, landing
carousel). All measurements are local: no production, no real users, a
throwaway copy of `data/`, stub Sleeper + Supabase (30 ms), throwaway Redis.

## 1. Backend (local load harness)

Harness: `scripts/load_test_local.py --users N --workers 4 --progressive`
(all leagues cold, 25% Pro). "Baseline" is commit `5eaa2bdf` (before this week)
run with the SAME harness file. Machine was a shared 8-core Mac with other
sessions running, so single-run noise is roughly +-25%; CPU seconds per user is
the steadier metric. 0 errors and 100% dashboard completion in every run.

| Run | wall | CPU s/user | Sleeper calls/session | dashboard p50 / p95 (ms) | my-team p50/p95 | trade-hub p50/p95 | matchup p50/p95 | waivers p50/p95 | playoff p50/p95 |
|---|---|---|---|---|---|---|---|---|---|
| 25 users, baseline | 33 s | 5.5 | 57.6 | 9,144 / 14,330 | 301 / 2,270 | 598 / 7,588 | 424 / 2,410 | 1,095 / 3,731 | 695 / 2,132 |
| 25 users, main | 29 s | 4.8 | 60.9 | 11,911 / 14,746 | 316 / 1,456 | 1,925 / 6,457 | 879 / 2,350 | 1,892 / 3,518 | 709 / 944 |
| 25 users, main + this PR | 38 s | 6.0 | 60.8 | 10,536 / 19,257 | 761 / 1,106 | 522 / 9,474 | 463 / 3,261 | 2,112 / 15,673 | 681 / 1,052 |
| 50 users, baseline | 118 s | 11.8 | 63.0 | 39,689 / 61,883 | 1,674 / 4,286 | 28,163 / 39,599 | 1,329 / 7,303 | 7,650 / 17,412 | 877 / 1,600 |
| 50 users, main | 68 s | 6.2 | 56.0 | 28,198 / 40,008 | 1,152 / 3,932 | 4,258 / 6,228 | 1,692 / 7,595 | 7,268 / 12,513 | 1,141 / 1,636 |
| 50 users, main + this PR | 69 s | 7.1 | 53.4 | 32,018 / 43,248 | 646 / 2,849 | 2,114 / 9,502 | 1,130 / 4,126 | 4,942 / 12,404 | 853 / 1,565 |

Progressive Dashboard (`--progressive`): first paint (deferred call) p50 / p95
at 50 users is 15.5 s / 18.3 s on main (18.7 / 28.2 s baseline); full
dashboard 28 s / 40 s (39.7 / 61.9 s baseline). At 25 users first paint is ~8 to
12 s.

Reading the table honestly:

- Main versus the pre-week baseline at 50 cold users is a real improvement:
  wall 118 s to 68 s, CPU per user 11.8 to 6.2 s (-47%), trade-hub p50
  28 s to 4.3 s, dashboard p95 62 s to 40 s. At 25 users the two are within noise.
- Main versus main + this PR is NOT distinguishable at harness level (the
  one backend change below is a ~3% share of dashboard CPU and the machine was
  noisy). The change is justified by the microbenchmark, not by these rows.
- Capacity statement is unchanged from `docs/load-test-2026-10.md`: ~50
  simultaneous cold users is the limit of 4 workers on this class of box
  (dashboard full response ~30 to 40 s), but nothing errors at 50 any more.
  Sleeper calls per cold session are 53 to 61 (budget is 1000/min, so a 50-user
  burst is still ~2,700 calls over ~70 s, right at the soft limit).

### Profiles (cProfile per request, 8 users, 2 workers)

Top three by CPU, all cold-cache:

1. `GET /dashboard`: ~85% is trade-idea generation
   (`trade_hub_engine.generate_trade_idea_records` -> `trade_ideas.build_trade_ideas`),
   dominated by pandas row/column access on pyarrow-backed string columns
   (`Series.__getitem__` ~250k calls, `pyarrow.compute.take`, `deepcopy` ~330k
   calls), plus 13 to 18 serial Sleeper `get_matchups` calls per request.
   `team_eval._score_starter_weighted_roster` (called 174 times) was the single
   cheapest hot spot: it compared `df["position"] == pos` and indexed `df.loc[i, "position"]`
   per row. FIXED (below).
2. `GET /waivers`: `waivers_logic._build_waiver_free_agent_pool_cached` ->
   `player_eligibility` (7,538 calls) and `get_season_player_stats`; 81 KB
   response body, 7 s p50 at 50 users. Not cheap to change (output-sensitive).
3. `GET /trade-hub`: `team_trade_history.league_trade_tendencies_cached`
   (`DataFrame.to_dict` of the league trade history, 0.29 s cumulative per miss).
   my-team and matchup are ~0.2 to 0.3 s CPU each; negligible.

### Fix shipped (output identical)

`modules/team_eval.py::_score_starter_weighted_roster`: read the position column
once into a Python list / numpy object array instead of `df["position"] == pos`
and per-row `df.loc` lookups. Same selection order and scores. Verified against
the original implementation on 1,295 randomised frames (object and pyarrow
string dtypes, 5 lineup settings; all equal) and by the new
`tests/test_team_eval_starter_scoring_perf_identical.py`. Microbench on a
40-player roster: 4.33 ms to 1.10 ms per call (3.9x). It is called ~170 times per
cold dashboard, so about 0.55 s of CPU saved per cold dashboard.

### Free-tier gate (#1479): no extra Supabase round trip in the hot path

`require_league_access` reads the profile via `_fetch_profile_fields` and (Free
only) saved leagues via `_fetch_saved_leagues_cached`. Both are per-user Redis
single-flight caches (15 s TTL) that the route body (`_resolve_my_roster`) uses
too, so after the first request in a window the gate costs 1 Redis GET (Pro) or
2 (Free) and zero Supabase calls. `require_user` is a FastAPI dependency and is
memoised per request, so the gate does not call GoTrue a second time. Result is
memoised on `request.state` per league. No code change needed.

The largest remaining Supabase hot-path cost is not the gate: `require_user`
calls GoTrue `/auth/v1/user` once per request, uncached.

### Not changed (risky or not identical)

- Caching the GoTrue user lookup for ~10 s per token hash would save one
  Supabase round trip per request but changes revocation latency. Product call.
- `redis_cache._release_lock` uses WATCH/GET/MULTI/DEL/EXEC (about 3 round trips)
  per cache miss; `sleeper_budget.record_call` does INCR+EXPIRE every call
  (could EXPIRE only when INCR returns 1). Both are sub-millisecond on a local
  Redis; not worth touching blind.

## 2. Web (webpack production build, Chromium at 390px)

### Bundle (gzip, JS loaded by the page HTML)

| Page | Before | After | Change |
|---|---|---|---|
| `/` (landing) | 429 KB | 295 KB | -134 KB (-31%) |
| `/portfolio` | ~445 KB | 310 KB | -135 KB |

Cause: `PlayerQuickViewProvider` sits in the root layout and statically imported
`PlayerQuickView`, which pulls in `recharts` (~114 KB gz chunk) on every route,
including the signed-out landing page. `LandingAuthIsland` -> `OnboardingPaywall`
also statically pulled `@stripe/stripe-js` + `@stripe/react-stripe-js` for a
checkout that only opens on a tap. Both are now `next/dynamic` (`ssr: false`),
loaded on first open. Behaviour is identical apart from a one-time chunk fetch
the first time a player card or checkout opens.

Chunk inventory on the landing page after the change: Next client runtime
65 KB, React DOM 63 KB, supabase-js 49 KB (needed for the returning-user
redirect), polyfills 38 KB (Next default), layout 12 KB, page 7 KB; CSS 15 KB
gz total. Satori and `yoga.wasm` are only reachable through
`await import("@/lib/shareCard/clientRender")` in `TradeAnalyzerContent` (own
lazy chunks, never in a page's HTML); the privacy layer (`lib/privacy.ts` 10 KB
source) and analytics (10 KB source) are small and shared. No unused npm
dependencies found (recharts, satori, stripe x2, supabase all imported).
Landing images: next/image with `sizes`, only the first two carousel slides are
`priority`; brand PNGs are 2048 px sources but served through the optimizer at 32/64 px;
fonts are the system stack (no webfont, nothing to swap).

### Landing at 390x844 DPR 2, CPU 4x, 5 runs, median (local server)

| Metric | Before | After |
|---|---|---|
| FCP | 632 ms | 620 ms |
| LCP | 932 ms | 688 ms |
| CLS | 0.112 | 0.000 |
| TBT | 364 ms | 103 ms |
| Transfer | 854 KB | 450 KB |
| Requests (JS) | 36 (23) | 31 (18) |

Network throttling had little visible effect on localhost, so absolute FCP/LCP
are optimistic; the TBT, bytes and CLS deltas are the reliable signal. The CLS
source was `LandingAuthSlotPlaceholder` reserving 15rem (240 px) while the real
signed-out sign-in card is 131 px at phone width (152 px desktop); when the
auth island resolved the whole content below jumped ~109 px. The placeholder is
now 8.25rem.

## 3. Mobile (static review only, nothing changed)

- Assets: 708 KB total, largest 87 KB (`splash-icon.png`), 8 onboarding webp
  (35 to 55 KB each). Fine.
- Dependencies: every one is referenced (`react-native-url-polyfill` via
  `supabase.ts`, `react-native-worklets` via the babel plugin). Candidates to
  confirm are single-use: `expo-blur`, `expo-device`, `expo-file-system`,
  `expo-web-browser`, `expo-auth-session` (1 import each).
- `RootNavigator.tsx` statically imports all ~35 screens; `PlayerDetailScreen`
  (101 KB), `DashboardScreen` (57 KB), `GmOrb` (51 KB), `api.ts` (110 KB) are the
  big modules. Expo's Metro inlines requires by default and Hermes loads
  bytecode lazily, so impact is modest; converting rarely used screens to lazy
  `getComponent` is possible but risky without a device run.
- `mobile` `npm test` could not run in this worktree (no `node_modules`
  installed); no mobile files were touched.

## 4. Validation

- Web: `tsc --noEmit` clean, `eslint` clean on touched files, full vitest
  113 files / 817 passed / 1 skipped, webpack `next build` OK (dummy
  `NEXT_PUBLIC_*`).
- Python: full pytest 3,886 passed, 22 failed, 17 errors. The same 22 + 17
  fail identically with the original `team_eval.py` swapped back in (the
  worktree's tracked `data/` holds stubs, so the data-fixture tests cannot
  pass; includes the known pre-existing failures). New test passes.

## Remaining bottlenecks (ranked)

1. Cold Dashboard CPU (~30 to 40 s p50 at 50 simultaneous cold users): trade
   idea generation in pandas. Next steps: per-team precomputed dict frames
   instead of per-row `Series[...]`, drop the 330k `deepcopy`s, and run idea
   generation after first paint only (the progressive Dashboard already defers
   it for the client; the server still computes it on the full call).
2. Sleeper fan-out: 53 to 61 calls per cold session; matchups 13 to 18 serial
   calls per dashboard. Fetch weeks concurrently or once per league/week-range
   and share the 30 s getters across workers via Redis single-flight.
3. Waivers (7 s p50 at 50, 81 KB body): eligibility over ~7.5k players per
   cold build; memoise per players-db fingerprint (the shared Redis tier exists
   for the frame, not the eligibility result).
4. Per-request GoTrue lookup in `require_user` (one Supabase round trip on
   every authenticated request).
5. Web: `Next client runtime + React DOM + supabase-js` (~177 KB gz) floor on
   every page; landing CLS now 0, TBT ~100 ms.

## Recommendations

- Capacity: 4 workers on one 8-core box tops out near 50 simultaneous cold
  users. For a launch or push-notification spike, run a second worker box
  behind Caddy (Redis is already shared) or raise to 8 workers if the box has
  the cores; both are config, not code.
- Share the remaining per-process caches (30 s Sleeper getters, eligibility
  memo) through the existing Redis single-flight layer so extra workers or boxes
  do not multiply Sleeper calls.
- Pre-warm: trigger the league warm-up right after `save_league` (exists) and
  after a deploy for recently active leagues, so a Redis flush is not a
  thundering herd.
- Decide whether a ~10 s cached GoTrue lookup is acceptable for revocation
  semantics.
- Re-run `scripts/load_test_local.py` at 50 users on production-like hardware
  before the next big marketing push; local numbers are pessimistic (driver,
  stub, Redis and workers share cores).
