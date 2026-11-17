# Performance audit (2026-11-16): general performance pass

Request: "need to improve general performance". Earlier passes already exist and were NOT redone:
`docs/performance-audit-2026-11.md` (backend: trade ideas, waivers, analyzer), `docs/performance-audit-client-2026-11.md`
(web+mobile: supabase bundle, request dedupe, headshots, lazy screens), `docs/audits/2026-11-performance-audit-2.md`
(sim reads, CI), `docs/perf-budget.md` (phone harness + budget check). This pass re-measured the current `origin/main`
and went after what is still left.

All numbers are local (shared Apple M1 that other sessions were also loading, so wall times are noisy and CPU ms /
profile function time are the numbers to trust), against the stub Sleeper/Supabase harness `scripts/bench_endpoints.py`
(copy of `data/`, throwaway redis, real `data/players.db` never opened for write).

## Measured: backend (`bench_endpoints.py --profile`, 16 endpoints, current main)

| Endpoint | Cold (first hit for a league) | Warm p50 CPU | Response |
|---|---:|---:|---:|
| dashboard (full, with trade ideas) | 4,250 ms | 31.8 ms | 5.6 KB |
| dashboard `defer_trade_ideas` (what web/app call first) | 1,753 ms | 31.4 ms | 5.3 KB |
| leagues-glance | 2,729 ms | 1.0 ms | 0.6 KB |
| trade hub | 1,620 ms | 4.1 ms | 1.0 KB |
| waivers | 1,110 ms | 87.0 ms | 115 KB |
| gm plan | 950 ms | 12.9 ms | 2.6 KB |
| team rankings | 558 ms | 19.5 ms | 23 KB |
| my team | 441 ms | 24.9 ms | 12 KB |
| matchup | 424 ms | 49.8 ms | 22 KB |
| **rankings (limit 100)** | 140 ms | **47.6 ms** | 97 KB |
| **player search** | 140 ms | **48.0 ms** | 21 KB |
| **player rank** | 116 ms | **25.4 ms** | 0.3 KB |
| player quick view | 48 ms | 33.1 ms | 3 KB |
| 8 simultaneous cold users, whole session | 75.6 s wall, 12.4 CPU s/user | | |

Upstream call counts per endpoint were already checked by the earlier backend pass (no N+1 found); not re-litigated here.

### Where cold time goes (cProfile, repo functions, cumulative)
- Full dashboard cold 6.6 s profiled: `trade_ideas._build_trade_ideas_impl` 4.75 s (overflow/drop engine `plan_trade_overflow`
  3.3 s, `evaluate_swap` 2.2 s), `dashboard_engine._compute_trade_independent` 1.2 s, `build_news_tiles` 0.84 s
  (`contextual_news_alert` x166, `news_signal.phrase_index_matches` 0.37 s self). Trade ideas are already deferred
  off the first paint on both clients, which is why `dashboard_deferred` is the number users feel.
- `copy.deepcopy`: 2.0 M calls cold (1.25 s self, 2.4 s cum over a whole session), almost all pandas `__finalize__`
  attrs copies and `evaluate_swap` context copies. Candidate for a follow-up (not a one-line fix).
- **Warm /rankings, /players/search, /players/{id}/rank each re-ran `attach_canonical_ranks` + full-pool OVR rating +
  stat-percentile annotation on every request** (`services/mobile_api_service.py` rankings ~5403-5424, search ~5574-5581,
  player rank ~5503). Profile of one warm /rankings: 118 ms in the handler, of which 37 ms `annotate_rankings_stat_pool`,
  34 ms `attach_canonical_ranks`, 8 ms `overall_ratings_for_pool`. Players search fires this per keystroke. The fixture pool
  is 1.7 K rows; production pools are larger, so this cost scales up.

## Measured: web (`next build`, 46 routes)

Shared first-load JS is 137 KB gz on every route (11 chunks); the biggest app routes: `/gm-game` 270 KB gz,
`/trade-hub` 196, `/sample-league` 195, `/dashboard` 192, `/trade-analyzer/[leagueId]` 191. Sentry (440 KB raw), satori
(393 KB raw) and recharts (276 KB raw) are all lazy chunks, not on any route's first-load list (verified against
`.next/diagnostics/route-bundle-stats.json`), so there is no heavy top-level library import left to split.
`node scripts/perf/check_perf_budget.mjs` on current main fails one route: `/league-recaps/[leagueId]` first-load 1005 KB
vs budget 979 KB.

## Ranked findings

| # | Finding | Evidence | Status |
|--:|---|---|---|
| 1 | Rankings / search / player-rank recompute the ranked + rated + annotated pool per request | profile above | Fixed (see "After") |
| 2 | Dashboard cold: trade-idea search 4.75 s, news tiles 0.84 s, trade-independent 1.2 s | profile above | Follow-up (already deferred off first paint) |
| 3 | `deepcopy` of pandas attrs / swap contexts, 2.0 M calls cold | profile above | Follow-up |
| 4 | `/league-recaps/[leagueId]` over its first-load JS budget by 26 KB (CI budget step red on main) | `check_perf_budget.mjs` | Fixed (see "After") |
| 5 | Mobile: no `React.memo` anywhere; FlatList `renderItem` closures are inline (Players, Waivers, Trade Finder, Teams) so rows re-render on any parent state change | `mobile/src/screens/PlayersScreen.tsx:431` etc. | Follow-up (needs row prop stabilization, device check) |
| 6 | Web always-mounted chrome (TradeOutcomePrompt, PasswordRecoveryGate) is small (shared helpers); lazy-loading them would save little and delay the recovery gate, so not done | code | Not worth it |

## After

Method: same harness, `--only conc --endpoints rankings,player_search,player_rank,my_team,matchup --reps 8`, run with
`DERIVED_CACHE=0` (the kill switch, which computes exactly the old way) vs default; response hashes identical on all five
endpoints (rankings, search, player rank, my team, matchup).

| Endpoint (warm CPU p50) | Before | After | Change |
|---|---:|---:|---:|
| `/rankings?limit=100` | 48.9 ms | 18.3 ms | -63% |
| `/players/search` (every keystroke) | 49.4 ms | 18.9 ms | -62% |
| `/players/{id}/rank` | 20.7 ms | 7.2 ms | -65% |

Fix: `_ranked_pool()` in `services/mobile_api_service.py` memoizes the attach-ranks / full-pool OVR rating / stat-percentile
annotation per valued-pool content key (the existing `derived_cache.Memo`, 120 s TTL, single flight, private copy per
caller, untagged frames compute directly). Guard: `tests/test_ranked_pool_memo.py` asserts a second call does zero
rank/rate/annotate work, callers get private copies, and a different scoring context / pool / rating mode never shares.
Test isolation: `derived_cache.clear_all_memos()` plus an autouse conftest fixture, because valued-frame tags name a cache
entry, not content, and tests reuse league ids with different stubbed data (this also closes a latent leak for the other memos).

Web, first-load JS from `next build` (`.next/diagnostics/route-bundle-stats.json`, gzip from `scripts/web_bundle_report.mjs`):

| Route | Before | After |
|---|---:|---:|
| `/league-recaps/[leagueId]` | 1005 KB raw / 171 KB gz (over the 979 KB budget) | 957 KB raw / 160 KB gz |
| `/league-rankings/[leagueId]` | 1001 KB raw / 157 KB gz (at the budget) | 917 KB raw / 149 KB gz |

Fix: History, Storylines and Roundup (Recaps' non-default tabs, extracted to `LeagueHistoryTab.tsx` /
`LeagueStorylinesTab.tsx`, existing `LeagueRoundupTab.tsx`) and `ManagerProfileSheet` (mounts only after a tap, in Recaps
and League Rankings) are now `next/dynamic` chunks with a skeleton/no-op fallback. Same data, same UI. The budget file
ratchets `/league-rankings` to 963 KB so the win cannot silently regress; `check_perf_budget.mjs` now passes on all 46 routes.
Mobile twin: not applicable, mobile screens are already lazily evaluated (previous client audit) and RN has no first-load JS budget.

Not done this pass (ranked above as follow-ups): dashboard cold trade-idea search, deepcopy overhead, mobile row memoization.

## Round 2 (2026-11-16, same harness, current `origin/main` after the Today rebuild and PQV/team-sheet work)

Harness additions: `bench_endpoints.py` now also covers `team_sheet`, `depth_chart` and `injury_history` (the endpoints added with
the team sheet / PQV work). Numbers are local, noisy (shared M1); the profiled cumulative time and call counts are the ones to trust.
Response hashes: the volatile-stripped bodies from before and after are byte-identical for dashboard (full and deferred),
team sheet, my team and matchup (the only diff on an unstripped run is a "synced just now" / "N ago" age string, which the harness
strips). Same-league comparisons only (the harness numbers leagues by run order).

### Findings and results

| # | Finding | Before | After | Status |
|--:|---|---:|---:|---|
| 1 | `evaluate_swap` built the kept-rows frame slice (`before[~isin(...)]`, an astype over the whole roster frame plus attrs copies) on every uncached call even when the precomputed `after_profiles` made the frame unused | dashboard cold, profiled, 6.04 s; `passes` 3.54 s | 5.03 s; `passes` 2.69 s (-17% / -24%) | Fixed (lazy slice) |
| 2 | `run_weeks` rebuilt the free-agent pool's points once per availability scenario (per week x scenario x side), though they do not depend on who is present | `run_weeks` 1.03 s cum (1504 calls) | 0.93 s | Fixed (hoisted once per week; same floats) |
| 3 | `deepcopy`: 11.6 K pandas `__finalize__` attr copies per cold dashboard. Cause: the loader's provenance attrs (`public_player_*` cache status/timings, `structured_*` refresh fingerprints, 12-14 keys) ride on every derived frame and pandas deep-copies them each time a column is boxed or a frame sliced. Nothing downstream reads them (only the `load_players` caller and tests do) | 441 K deepcopy calls, 0.49 s cum | 162 K calls, 0.20 s cum (-63% / -59%) | Fixed (dropped when the valued frame is built; loader frame untouched) |
| 4 | Team sheet warm: `roster_value_model.league_needs` re-ran each request (its own cache is keyed by the frame *object* id, and the valued frame is a fresh copy per request); `/teams/{id}/profile` and `/my-team` had the same miss | team sheet warm p50 137 ms (0.17 s of it `league_needs`) | 62 ms (-54%) | Fixed (the content-keyed `_league_needs_memoized` the Analyzer already used) |
| 5 | Dashboard news tiles "0.84 s" (round 1) | 0.037 s on this fixture | | Not reproducible: it scales with the news feed size, not a code cost. No separate cache entry added |
| 6 | Trade-idea search itself (`plan_trade_overflow` -> `evaluate_swap`, 54 ideas x ~11 swaps) | 2.69 s of the 5.0 s full cold | | Follow-up. Remaining cost is real model work (4 `run_weeks` per swap); a further win needs a smarter candidate bound or sharing contexts across ideas, not a cache. Already deferred off first paint (`dashboard?defer_trade_ideas` cold 1.07 s) |
| 7 | Leagues-glance cold 2.8 s, trade hub cold ~4 s (first cold hit of a league, includes shared frame builds); warm 1.7 ms / 6 ms | | | Warm is fine; cold is dominated by the same shared valued-frame / needs builds, no new hotspot found |
| 8 | New endpoints: depth chart 7 ms warm, injury history 1.2 ms warm, team sheet see #4 | | | OK |

Warm / cold, same run (CPU ms p50, ms): dashboard cold 4,156 -> 3,560; dashboard_deferred cold 1,067 -> 1,027; team_sheet warm 137 -> 62;
matchup warm 50 -> 50 (unchanged; its cost is the projection pass).

Tests: `tests/test_perf_round2.py` (needs memo reuses work for the same content, accepts no status, a different frame does not share;
valued frame drops only load-provenance attrs and leaves the loader's own frame alone); the lazy slice and the pool hoist are guarded by
the existing `tests/test_performance_equivalence.py` (swap identical to the full-frame implementation) and `tests/test_trade_lineup_model.py`
(exact scenario enumeration).

### Mobile: FlatList row re-renders

Players, Waivers (explore list), Trade Finder (roster list) and Teams passed an inline `renderItem` that created fresh closures per row, so
every parent state change (search text, accordion, selection, sort) re-rendered every mounted row. Now each list has a stable
`renderItem` (`useCallback`) that hands the row only primitives plus stable callbacks; the row (`PlayerListItem`, `FreeAgentListItem`,
`RosterRow`, `TeamRowCard`) is `React.memo` and binds its own handlers. Only a row whose own props changed (e.g. the one accordion row that
opened) re-renders. Verified statically (tsc clean, 979 lib tests pass); no device profile (see the TestFlight-limit note: no rebuild).

### Web: first-load JS after today's UI work

`next build` + `scripts/web_bundle_report.mjs` (gz): /gm-game 270 -> 279, /dashboard 192 -> 202, /trade-hub 196 -> 202, /sample-league 195 -> 206,
/trade-analyzer 191 -> 197. `check_perf_budget.mjs` passes on all routes (no regression over budget). Dashboard growth is the Today
rebuild's page code (about 62 KB gz of route-only chunks, no heavy shared dependency). Trial: lazy-loading the two mini-game cards in
"More" saved only 1 KB gz, so it was not kept. No budget change.

## Round 3 (2026-11-17, after the UI batches #2031-#2045)

Method: same `scripts/bench_endpoints.py` harness, same machine and load; "base" is a clean `git archive` of the Round 2 commit
(8f1cf007) run on the same box, so regressions from the UI batches are real, not noise. Volatile-stripped response bodies for all 19 endpoints are
byte-identical before/after every backend change (`diff -rq`). Web numbers come from a production `next build` at 390px; the Today harness is new
(`scripts/perf/desk_cold.mjs`: 4x CPU, 4G or fast3g profile, API mocked from the bench bodies and delayed by each endpoint's measured cold/warm server time).

### Regressions found and fixed (PR #2046, merged 7b76d6b9)

| Endpoint | Round 2 base | main before | After | Cause |
|---|---:|---:|---:|---|
| my-team warm p50 | 22.6 ms | 49.6 ms | 25.4 ms | handcuff role (`_role_adjustment`) scanned the whole player pool per projected player; now a (team, position) index built once per lookup dict |
| matchup warm p50 | 50.4 ms | 78.5 ms | 38.1 ms | same |
| team sheet warm p50 | 60.0 ms | 72.1 ms | 60.7 ms | same |
| waivers warm p50 | 98.2 ms | 128.6 ms | 101.8 ms | shared waiver source built a `positive.loc[idx]` Series up to 3x per candidate; one `to_dict("records")` pass |
| dashboard cold (first league) | 3.65 s | 6.5 s | 4.2 s | waiver-alternative guardrail built the need model for all 12 rosters (480 uncached swaps) to read one; `league_needs(only_roster_ids=...)` |
| dashboard `defer_trade_ideas` cold | 1.0 s | 2.4 s | 1.2 s | same (the Today tile's waiver pick) |
| trade hub cold | 1.4 s | 2.6 s | 1.3 s | same |
| leagues-glance cold | 2.2 s | 4.4 s | 1.9 s | same |

Trade-idea search (the 2.5 s cold in `build_trade_ideas`): profile shows 2.0 s of it was `_waiver_alternative_for_need -> select_top_waiver_opportunity ->
shared_waiver_adds -> league_needs` (12 rosters x ~40 `evaluate_swap`), not the swap/overflow engine. League-wide calibration is unchanged; only the assessed
roster set shrinks, so the entry is identical (`tests/test_perf_round3.py`: subset equals the full table's entry, a cached full table serves a subset, and
`select_top_waiver_opportunity` returns identical rows). `build_trade_ideas` 2.5 s -> about 0.7 s. The `ranked.sort()` TypeError in
`_iter_blockbuster_send_packages` was already fixed on main (8386dc77, total-order key, `test_elite_acquisition_blockbuster.py`).

### Cold Today at 390px (PR #2050)

Cold waterfall (4G, 4x CPU): HTML + 22 scripts (335 KB gz) -> hydrate -> first API request at 0.87 s -> `GET /v1/leagues/{id}` (lens detection) -> only then the
four above-the-fold requests (team-rankings, matchup, needs, dashboard), +0.14 s later on the fixture and about +0.8 s with a realistic cold Sleeper league fetch.
Fix: those requests no longer wait for lens detection (Dynasty, the common case, keeps the lens; a redraft league remounts on the right lens on its first visit only, and the skeleton
holds until detection settles).

| Today, useful content, fast3g, median of 3 | main | #2050 |
|---|---:|---:|
| cold, league fetch 800 ms | 4685 ms | 3998 ms |
| cold, league fetch 150 ms | 4024 ms | 3972 ms |
| 4G, league fetch 150 ms | 2.28 s | 2.23 s |

Breakdown of the remaining fast3g cold (about 4.0 s): 2.6 s before the first API request (script download of 335 KB gz at 1.6 Mbps plus parse and hydrate), 1.2 s server time
of the deferred dashboard, the rest render. The 2.5 s target holds on 4G; on fast3g the JS download is the floor.

### Server verdict: latency/waterfall, not capacity

Local container (bench harness, stub Sleeper/Supabase at 30 ms nominal, 1 process, 431 MB max RSS for the whole run):

| Endpoint | cold ms (cpu ms) | warm p50 / p95 ms | cold upstream calls (Sleeper / Supabase REST) |
|---|---:|---:|---:|
| dashboard `defer_trade_ideas` | 1230 (982) | 31.4 / 69.1 | 8 / 3 |
| team rankings | 555 (428) | 21.0 / 24.4 | 18 / 1 |
| matchup | 417 (142) | 38.1 / 38.8 | 8 / 2 |
| my team | 438 (250) | 25.4 / 29.9 | 6 / 2 |
| trade hub | 1294 (1026) | 5.3 / 6.5 | 15 / 4 |
| waivers | 1081 (793) | 101.8 / 103.7 | 9 / 4 |
| leagues-glance | 1854 (1583) | 1.7 / 2.3 | 8 / 4 |

Warm is 20-100 ms and cold is 75-85% CPU (the Python is computing, not waiting on Sleeper or Supabase: even 8 serial 30 ms upstream calls are at most 240 ms of a 1.2 s cold).
With 4 workers and a quiet box (the owner's under 10% RAM / low CPU) there is spare capacity; what a user feels is that every visit is cold: the valued-frame and derived
caches expire after 120 s (`VALUED_PLAYERS_FRAME_TTL_SECONDS`, `derived_cache` TTL), so low traffic means nearly every visit recomputes (1.2 s deferred dashboard, 3.4 s for a worker's very
first request), then waits behind JS download and the fetch chain. Lead for a next pass: stale-while-revalidate plus a background precompute on league open, keyed on the players fingerprint instead of a 120 s bucket.

### Web bundles (`next build`, first-load JS raw KB; budget from `perf-budget.json`)

UI batches added about 10 KB raw (3 KB gz) to the shared chunks of every route (e.g. `/_not-found` 889 -> 900, `/dashboard` 1089 -> 1092); `/news` grew 982 -> 998 and was
over its 989 budget (CI red). PR #2047: the News League tab (pulls in all of Recaps) is a `next/dynamic` chunk: `/news` 998 -> 957, budget ratcheted 989 -> 985.
Checked statically (no regression found): `PageStatusLine` (65 lines, no state), `CompactModule` (two window listeners per module via `useSyncExternalStore`, cheap),
`PlayerAvatar` fallback (`pickAvatarSource`, per-id failure state), `verdictTone` (pure table lookups).

### App (static; no device build per the TestFlight limit) (PR #2051)

Eager import closure of `index.ts`: 263 project files, 1.6 MB source. `api.ts` pulled the 155 KB `simGame.ts` (221 runtime exports) onto the launch path through one helper
(`simDynastyPaths`); it moved to `simPaths.ts`. `App.tsx` imported the Inter barrel so Metro bundled all 18 weights (exported assets 10 MB -> 6.1 MB with the five used).
Already good: screens are lazy `require()`s, ads is a no-op shim. Remaining startup candidates (not changed, need a device to verify): `PlayerQuickViewSheet` (32 KB),
`PercentileExplorerSheet` (29 KB) and `PortfolioStanding` (31 KB) are eager though only mounted on tap; `configureRevenueCat()` runs in the first effect before fonts finish.
Mobile list re-render counts were not re-measured (no device); the Round 2 memoization is unchanged.

### Still slow

- Cold per-league CPU: `plan_trade_overflow` (about 31 `evaluate_swap` per idea, 24 ideas in leagues-glance cold = 3 s profiled) needs a candidate bound, not a cache.
- 120 s cache TTLs make every low-traffic visit cold (above).
- First-load JS 335 KB gz on Today; on fast3g the download alone is about 2 s.
- Web per-page cold/warm for Matchup, Team, League, Players, Waivers, Trades, Sim Home were not browser-measured (only Today has a harness); their API and bundle numbers are above.
