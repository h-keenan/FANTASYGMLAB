# Performance notes, 2026-10-31

Local only: throwaway data copy, stub Sleeper/Supabase, throwaway Redis. Nothing was run against production.
Follows `docs/performance-audit-2026-10-final.md` (its "remaining bottlenecks" list drove the picks).

## Measurement tooling

- `scripts/load_test_local.py`: `LT_PROFILER=pyinstrument` now profiles only the handler thread. The old cProfile
  hook is interpreter-global on Python 3.12+ (sys.monitoring), mixes in every other thread and errors under
  concurrent requests (500s at 8 users), so its numbers were unusable. `LT_KEEP_LOG=<path>` keeps the api log.
- `scripts/web_bundle_report.mjs`: per-route client JS (gzip) from a finished `next build` (Turbopack).

## Backend

Harness result: 12 cold users, 2 workers, same machine, three runs each way: wall 33 to 48 s vs 38 s baseline,
CPU/user 5.1 to 7.1 s vs 5.6 to 9.6 s. Run-to-run noise (+-30%) is larger than any change below, so the harness
cannot resolve them; the numbers below are deterministic microbenchmarks with output-equality checks.

| Change | Before | After | Output check |
|---|---|---|---|
| `get_season_player_stats` cold build: 18 weekly Sleeper calls were serial on the request that missed the cache; now a 6-thread pool, week order and failure skipping preserved, caller's Sleeper-budget context carried (`sleeper._fetch_weekly_stat_payloads`) | 2.83 s at 150 ms per call | 0.46 s | `tests/test_sleeper_weekly_stats_parallel_fetch.py` (order, failures, non-dict payloads, context) |
| `playoff_simulator` and guillotine history: up to ~17 serial `get_matchups` calls, now `sleeper.get_matchups_for_weeks` (same per-week cache) | 14 x 50 ms = 0.7 s | about 0.1 s | test above; playoff/guillotine suites pass |
| `filter_waiver_actionable_players` (dashboard x2, trade hub, waivers): `DataFrame.apply(axis=1)` built a Series per row; now `frame_records` dicts | 52.8 ms per 1.8k rows | 34.4 ms | decisions and filtered frame identical (`DataFrame.equals`, index, dtypes) on the players table |
| `waivers_logic` stale free agent flag, same pattern | 55.6 ms | 31.7 ms | bool vector identical |
| `trade_lineup_model` `profile_roster` / `_active_rows`: `DataFrame.to_dict("records")` -> `frame_records` (already parity-tested helper) | 2.86 ms per 30-row roster | 0.96 ms | `repr` of all 1.8k records identical |

Dashboard cold, single user, pyinstrument: 4.1 s, of which 3.3 s (80%) is trade idea generation
(`_UserSideAnalyzerGate.passes` -> `evaluate_trade_analyzer_fit`, 15 graded trades at ~0.13 s). Warm waivers 0.57 s,
warm my-team/matchup 0.2 to 0.5 s.

Not shipped (measured, but blocked):
- `trust_engine._stable_payload` exact-type fast path: 170 ms -> 42 ms per 1.8k player records (identical output, est.
  0.5 s per cold players build on the full pool). Reverted because `tests/test_executive_surface_parity.py` and
  `tests/test_trade_hub_first_useful_result.py` forbid touching `modules/trust_engine.py` in a PR. Patch is a 6-line
  addition at the top of `_stable_payload`; needs an explicit exception from the owner.
- Trade idea generation itself (80% of cold dashboard): needs a dedicated pass (cache `weekly_lineup_impact` /
  `profile_roster` per roster, not per candidate trade).
- GoTrue per-request lookup cache: product call (revocation latency).
- `nfl_schedule._load_games_uncached` does a blocking `requests.get` on the request path when the 6 h disk cache is
  stale (0.4 s measured here, file absent in the sandbox). Candidate for stale-while-revalidate.
- Compression is already on (`GZipMiddleware`, 1 KB minimum); waivers body 81 KB.

## Web (`next build`, gzip JS per route, `scripts/web_bundle_report.mjs`)

| Route | Before | After |
|---|---|---|
| `/players/[leagueId]/[playerId]` | 242 KB | 128 KB |
| `/player-compare/[leagueId]` | 222 KB | 116 KB |
| `/design` (internal) | 252 KB | 139 KB |
| all other routes | unchanged | unchanged |
| all chunks reachable | 576 KB | 472 KB |

Cause: `recharts` (~110 KB gz) was statically imported via `WeeklyPointsChart` (compare, player trends) and
`ModelRadarChart` (via `PlayerQuickView`, which the profile page imports statically). Both are now `next/dynamic`
(`ssr: false`) with a placeholder of the chart's exact footprint (`CHART_HEIGHT`, moved to
`weeklyPointsChartHeight.ts` so skeletons do not import the chart), and the chart chunk is preloaded on mount in
parallel with the page's data fetch. tsc clean, vitest 159 files / 1118 tests pass, eslint clean on touched files.

Reviewed, no change needed: players list is already capped (`PREVIEW_ROWS`), 8 plain `<img>` are avatars and
share-card/store-badge artwork that must render unmodified, no web font, no react-query in the app.

## Mobile (static review, no build)

Every list is a `FlatList` with `initialNumToRender`/`windowSize` tuned (PlayersScreen 16/9), `expo-image` is in
use. Nothing changed: no measurable win without a device run.

## Remaining, ranked

1. Cold trade idea generation (80% of cold dashboard CPU).
2. `trust_engine._stable_payload` fast path (needs the guard test exception).
3. Stale-while-revalidate for the NFL games CSV and per-request GoTrue lookup.
4. Re-run `scripts/load_test_local.py --users 50 --workers 4` on a quiet box to get capacity numbers.
