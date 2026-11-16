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
