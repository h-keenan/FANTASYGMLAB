# Backend performance audit, 2026-11

Scope: `services/mobile_api_service.py` and `modules/` (not `modules/sim`). Goal from the
owner: "we still need overall speed improvements". This is a *measured* pass: build a
repeatable benchmark, rank the real costs, fix root causes, prove outputs are unchanged.

## Headline

All numbers are local, on a shared Apple M1 (8 cores, 8 GB) that other sessions were also using
(load average 7 to 9), against a stub Sleeper/Supabase with 30 ms nominal latency. Before = `origin/main`
at the PR's base commit, run with the **same harness file**, interleaved with the "after" runs.

| What | Before | After | Change |
|---|---:|---:|---:|
| GM Plan, first request for a league (cold; runs the full trade-idea search) | 18.5 s | 4.7 s | **-74%** (3.9x) |
| Trade Analyzer, warm request | 675 ms | 309 ms | **-54%** (2.2x) |
| Waivers, warm request (115 KB response) | 1,334 ms | 652 ms | **-51%** (2.0x) |
| Dashboard, first request for a league (cold, includes trade ideas) | 4.7 s | 3.0 s | -36% |
| Leagues glance, cold | 2.3 s | 1.5 s | -33% |
| Rankings / Player search, warm | 80 ms / 80 ms | 61 ms / 62 ms | -24% / -23% |
| One new user's whole session (single user, all 16 endpoints on one league) | 9.3 s wall, 8.4 s CPU | 6.7 s wall, 6.2 s CPU | -28% / -26% |
| 8 simultaneous cold users, whole session each (median of 3 paired runs) | 97.5 s wall, 17.8 CPU s/user | 64.8 s wall, 11.4 CPU s/user | -34% / -36% |
| Dashboard under 8 simultaneous cold users, p50 / p95 | 57.2 s / 94.2 s | 18.0 s / 24.2 s | -69% / -74% |

Responses are byte-for-byte identical (canonical JSON hash) on all 16 benchmarked endpoints in all
3 paired runs (see "Equivalence"). Sleeper and Supabase call counts per endpoint are unchanged
(no N+1 was found, see below).

## Method

`scripts/bench_endpoints.py` (new, repeatable) drives the FastAPI app **in process** over
`httpx.ASGITransport`, so the sync handlers run in the real anyio threadpool, with:

- a stub HTTP server for Sleeper + Supabase (reused from `scripts/load_test_local.py`; it counts every
  upstream request by kind),
- a throwaway `redis-server` on a free port (never shared between runs),
- a **copy** of `data/` in a temp dir as the working directory. The harness hashes the real
  `data/players.db` and `data/sleeper_players.json` before and after and warns if either changed;
  `rankings.load_players` / `build_players_table` are never called on the real db,
- Pro stub users (so free-tier gates and weekly limits do not short-circuit the work).

Endpoints (16): dashboard (full and `defer_trade_ideas`), league rankings, team rankings, trade
analyzer (POST), trade hub, trade finder, my-roster, my-team ("today"/team view), player rank,
player quick-view (roster/player detail), player search, GM plan, matchup, waivers, leagues-glance.

Per endpoint it records: cold request on a never-seen league, warm p50/p95 wall and CPU
(`process_time`, a steadier metric than wall on a noisy box), concurrent p50/p95/CPU with N users
each on their own league, response size, upstream call counts, a canonical response hash
(volatile keys and relative-age strings stripped), and with `--profile` cProfile top-20 self time and
repo-function cumulative time for a cold and a warm request (`--prof-dir` keeps raw `.prof` files,
`--bodies-dir` keeps canonical bodies for diffing).

```
python scripts/bench_endpoints.py --reps 8 --conc 8 --profile --out bench.json
python scripts/bench_compare.py --before base_1.json base_2.json --after after_1.json after_2.json
```

Harness traps found while building it (all handled in the script, worth knowing):

- `require_user` calls `_maybe_schedule_players_refresh`, which, when the copied dump looks older
  than 5 minutes, spawns `scripts/refresh_players_db_subprocess.py` with `cwd=<repo root>` and the
  live Sleeper network. Without `DYNASTYGM_TEST_MODE=1` a benchmark run **rewrites the checkout's
  real `data/players.db` and `data/sleeper_players.json`**. The harness sets the flag and keeps the
  dump "fresh".
- The stub serves no player dump, so a stale dump made every `sleeper.get_players()` take the
  blocking-refresh path (88 ms per call in `my_team`); also fixed in the harness.
- A fixed Redis port let two overlapping runs share a cache; the port is now random per run.
- `playoff_probability` (Monte Carlo, unseeded) differs run to run on *unchanged* code (checked:
  base vs base), so it is excluded from the output hash.

## Where the time goes (baseline, ranked)

Per user-visible cost, baseline:

1. **Trade-idea generation** (GM Plan 18.5 s cold, Dashboard 4.7 s, Trade Hub, Leagues glance 2.3 s).
   Under load this is what makes 8 cold users take 97 s. 85% of it is the drop/overflow engine
   (`drop_candidates` / `roster_value_model.evaluate_swap`) called ~1,000 times per search.
2. **Waivers** (1.33 s on *every* request, not cached because it is per-roster): the same
   `evaluate_swap` machinery, 131 swaps per request.
3. **Trade Analyzer** (0.68 s per request): `league_needs`, `build_context`, `profile_roster`.
4. **Dashboard news tiles** (about 1.9 s of a 5.7 s cold dashboard): article-to-player matching.
5. Rankings / player search / quick view / matchup / my-team (28 to 80 ms warm): percentile
   passes and frame conversions.

The cProfile top-20 (before and after) is at the bottom. Before, the dominant self-time items are not
domain logic at all: `frame_records` (cum 21 s over 7,879 calls), `_fast_dtype` / `dtype.__str__`
(1.0 M calls, 3.9 s cum), `to_numpy`, `take`, `deepcopy`.

## Root causes and fixes

Every fix keeps the previous implementation as an in-test oracle
(`tests/test_performance_equivalence.py`, 33 tests).

1. **`RosterValueContext.row(player_id)` rescanned the whole team frame per call**
   (`frame["player_id"].astype(str) == id`, then a full `frame_records` conversion). The drop engine
   calls it from `_facts` ~4,900 times per trade-idea search: 25 s of 36 s profiled in a cold GM
   Plan. Now one lazily-built id index per context (first row wins, missing ids skipped, a private
   copy returned each call). Effect: the single biggest cold-path win.
2. **`frame_records` classified every column's dtype with `str(dtype)` on every call** (about 4 us
   each, 140 columns, 1 M calls). Dtypes are hashable and few: classified once and cached.
   12-row, 140-column frame: 1.24 ms to 0.58 ms. Benefits all 13 call sites.
3. **`evaluate_swap` / `evaluate_trade` re-profiled the whole roster for every swap.**
   `profile_roster` is a pure per-row function, so a swap's "after" roster reuses the memoized
   "before" profiles for kept rows and profiles only the added rows
   (`trade_lineup_model.profile_swap_after`). It declines (falls back to the old path) when an added
   row brings a field the profile reads that the roster frame lacks, or a non-widening dtype change.
   Plus: only the two columns the value map needs are converted, `PlayerPoints` aging is memoized per
   profile (`_aged`), and identical swaps within one context are memoized
   (`RosterValueContext.swap_cache`, keyed on the drops and the added rows' scalar contents, a deep
   copy returned each time; 40% of waiver swaps were repeats).
4. **`profile_roster`, `_active_rows`, `build_context` converted all ~140 columns** of 8,000-row league
   frames to Python dicts to read about 17. They now convert only the columns they read
   (`_PROFILE_ROW_COLUMNS`; a test records the reads and fails if the function ever reads another
   column).
5. **`healthy_equivalent_roster`** built a pandas Series per injured row (`iterrows` + `to_dict`);
   now one bulk conversion.
6. **News identity scan** (`resolve_article_player_identity[ies]`) called `contains_phrase` for every
   (article, player-name) pair: 674,000 calls per cold dashboard. Names are normalized once per
   distinct index (content-keyed memo, so a mutated mapping can never be stale) and the necessary
   substring condition is tested inline first; hits still go through `contains_phrase`.
7. **`player_quick_view._percentile_from_values`** used a Python lambda per group plus a per-row list
   comprehension, called 19 times per rankings / search / quick-view request. Vectorized
   (`np.rint` rounds half to even exactly like `round()`).

## Results

### Single user (median of 3 paired runs, 6 warm reps each)

| endpoint | cold ms before | cold ms after | warm p50 ms before | warm p50 ms after | warm CPU ms before | warm CPU ms after | warm speedup | output |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| dashboard | 4,744 | 3,038 | 19.9 | 19.5 | 18.7 | 18.2 | 1.0x | identical |
| dashboard_deferred | 2,077 | 2,002 | 19.6 | 18.9 | 18.5 | 17.6 | 1.1x | identical |
| rankings | 173 | 154 | 79.9 | 60.8 | 79.2 | 59.8 | 1.3x | identical |
| team_rankings | 674 | 660 | 24.8 | 24.6 | 23.8 | 23.5 | 1.0x | identical |
| trade_analyzer | 1,175 | 809 | 675.3 | 309.1 | 671.5 | 306.8 | 2.2x | identical |
| trade_hub | 1,135 | 1,073 | 5.6 | 6.0 | 4.6 | 4.9 | 0.9x | identical |
| trade_finder | 48 | 48 | 1.5 | 1.4 | 1.1 | 1.0 | 1.1x | identical |
| my_roster | 247 | 241 | 1.4 | 1.4 | 0.9 | 0.9 | 1.0x | identical |
| my_team | 464 | 446 | 27.8 | 28.1 | 26.2 | 26.3 | 1.0x | identical |
| player_rank | 123 | 112 | 23.6 | 23.7 | 22.8 | 23.3 | 1.0x | identical |
| player_quick_view | 56 | 54 | 43.1 | 44.7 | 42.7 | 43.8 | 1.0x | identical |
| player_search | 171 | 156 | 80.5 | 61.9 | 79.7 | 61.0 | 1.3x | identical |
| gm_plan | 18,473 | 4,728 | 17.4 | 16.5 | 16.2 | 15.5 | 1.0x | identical |
| matchup | 432 | 428 | 61.3 | 68.0 | 59.4 | 65.5 | 0.9x | identical |
| waivers | 2,058 | 1,313 | 1,334.1 | 652.1 | 1,330.8 | 650.0 | 2.0x | identical |
| leagues_glance | 2,266 | 1,529 | 1.9 | 1.9 | 1.4 | 1.4 | 1.0x | identical |

"Cold" is the first request for a league never seen by this process; the order is the table order, so
later endpoints benefit from process-level caches the earlier ones warmed (the players frame, stats).
`trade_hub` and `dashboard` return a "building" response first when trade ideas are not ready, which is
why their cold and warm look cheap: the ideas cost shows up in `gm_plan` (synchronous) and the
dashboard's full call. Differences of 0.9 to 1.1x are noise (matchup, trade_hub, my_team were not touched).

One new user, all 16 endpoints in order on one league: 9.3 s wall / 8.4 CPU s before,
6.7 s / 6.2 CPU s after.

### 8 simultaneous cold users (each on their own league; median of 3 paired runs)

| | before | after |
|---|---:|---:|
| wall, all 8 users finish | 97.5 s (96.8, 97.5, 172.4) | 64.8 s (60.2, 64.8, 68.3) |
| CPU per user | 17.8 s (17.8, 17.6, 28.5) | 11.4 s (10.5, 11.4, 12.1) |

(The 172 s / 28.5 s "before" run overlapped another session's load: noise is large, which is why
CPU seconds and paired medians are reported.) Per endpoint, medians of 3 paired runs:

| endpoint | p50 before | p50 after | p95 before | p95 after | CPU ms before | CPU ms after |
|---|---:|---:|---:|---:|---:|---:|
| dashboard | 57,163 | 17,989 | 94,170 | 24,214 | 64,304 | 24,182 |
| trade_analyzer | 17,467 | 8,001 | 24,772 | 9,794 | 22,291 | 11,435 |
| waivers | 12,506 | 6,174 | 16,686 | 8,324 | 16,133 | 7,614 |
| team_rankings | 7,541 | 9,538 | 17,805 | 11,646 | 7,779 | 8,699 |
| leagues_glance | 2,410 | 2,286 | 3,655 | 3,301 | 2,584 | 2,405 |
| gm_plan | 471 | 563 | 629 | 720 | 751 | 790 |
| other 8 endpoints | within noise | | | | | |

Honest reading: the trade-idea search is single-flighted per league, so when it finishes sooner the
*other* endpoints that were waiting on it (`trade_hub`, `dashboard_deferred`) now wait on a different
moment in the flow; per-endpoint p50s therefore redistribute and the session totals (wall, CPU per
user) are the meaningful numbers. `team_rankings` under load is equal within noise.

### Upstream calls (no N+1 found)

Counted at the stub, first request for a fresh league in a warm process (identical before and after):

| endpoint | Sleeper | Supabase auth | Supabase rest | response bytes |
|---|---:|---:|---:|---:|
| dashboard | 26 | 1 | 4 | 5,245 |
| dashboard_deferred | 8 | 1 | 3 | 5,123 |
| rankings | 1 | 1 | 1 | 96,459 |
| team_rankings | 18 | 1 | 1 | 23,208 |
| trade_analyzer | 8 | 1 | 4 | 7,535 |
| trade_hub | 15 | 1 | 4 | 1,026 |
| trade_finder | 1 | 1 | 1 | 85 |
| my_roster | 6 | 1 | 2 | 419 |
| my_team | 6 | 1 | 2 | 12,180 |
| player_rank | 1 | 1 | 1 | 320 |
| player_quick_view | 0 | 1 | 1 | 2,995 |
| player_search | 1 | 1 | 1 | 19,806 |
| gm_plan | 22 | 1 | 4 | 2,578 |
| matchup | 8 | 1 | 2 | 18,727 |
| waivers | 9 | 1 | 4 | 114,489 |
| leagues_glance | 8 | 1 | 4 | 620 |

The multi-week matchup fan-out is already concurrent (`get_matchups_for_weeks`), Sleeper reads go
through the shared cache and budget, and every request is one auth + 1 to 4 profile/stance reads.
The CPU, not the upstream calls, is the cost.

## Equivalence

- `tests/test_performance_equivalence.py` (33 tests): each optimization against its inline
  pre-change implementation. `row()` for every id, unknown ids, duplicates, missing ids and private
  copies; `evaluate_swap` against the full-frame version over 40+ swaps (injured drops/adds, duplicate
  adds, extra/unread columns, read columns the roster lacks, Series rows, scalar-only and non-scalar
  rows); `profile_swap_after` against `profile_roster` of the concatenated frame; the whole drop engine
  end to end; `_aged`; vectorized percentiles against the lambda version over random pools with NaNs,
  ties, small groups, missing positions and shuffled indexes; the phrase scan against the
  `contains_phrase` loop over 300 random articles; `healthy_equivalent_roster` against the
  `iterrows` version across score columns and lens variants; the narrowed column reads.
- End to end: canonical response bodies for all 16 endpoints, 3 paired runs, identical before vs after
  (`--bodies-dir`, then `cmp`). Excluded: unseeded Monte Carlo `playoff_probability`, timestamps, and
  relative-age strings ("synced 12m ago").
- Existing suites touching these modules (drop candidates, trade lineup, trade analyzer, waivers,
  news, quick view, dashboard, league rankings, mobile API service, about 150 test files) pass locally.

## Not changed, and why

- **Trade-idea generation still dominates cold load** (roughly half of profiled cold time after the fixes). The
  remaining cost is spread over `build_context` per candidate package, `run_weeks`, and
  `waiver_actionable_player_pool` (about 120 ms per call in the Trade Analyzer profile; row-wise Python by design).
  A cross-request memo of `league_needs` / the waiver pool needs a content-addressed fingerprint of
  the valued frame (it is a fresh copy per request, so the existing `id()`-keyed memos rarely hit).
  That is the best next step, but it touches cache-invalidation semantics and is a bigger design
  change than this pass.
- **Player annotation / trust validation** (`trust_engine._stable_payload`, ~0.5 s of cold CPU) is
  already memoized across processes in `player_eligibility`; the cost shown is the genuinely cold build.
- **Payload trimming.** `rankings?limit=100` is 96 KB, `waivers` 114 KB. Trimming changes responses,
  which this pass promised not to do; flagged for a product decision (fields below the fold, or
  `fields=` projection).
- `DataFrame.attrs` deep copies (`__finalize__`, ~2% of cold) and Redis `pickle.loads` of cached
  frames on every hit were measured and are small; not worth the risk.
- The single-flight lock timeout (15 s) makes late waiters recompute the same result under heavy
  load. Faster compute makes that rarer; raising or adaptively scaling it is a separate decision.

## Cold and warm cProfile detail

Top 20 by self time and repo functions by cumulative time, one request per endpoint, aggregated over
all 16. cProfile inflates call-heavy functions (use the relative order, not the milliseconds).

**Before, cold requests, top 20 by self time**

| self ms | cum ms | calls | function |
|---:|---:|---:|---|
| 3,371 | 3,112 | 138 | `<built-in method time.sleep> (~:0)` |
| 2,557 | 3,734 | 20,439,993 | `<built-in method builtins.isinstance> (~:0)` |
| 2,414 | 2,554 | 245,041 | `take (compute.py:467)` |
| 1,744 | 20,981 | 7,879 | `frame_records (frame_records.py:28)` |
| 1,494 | 2,867 | 1,761,546 | `deepcopy (copy.py:119)` |
| 1,493 | 5,849 | 1,599,426 | `__str__ (_dtype.py:32)` |
| 1,491 | 4,281 | 1,615,464 | `_name_get (_dtype.py:342)` |
| 1,388 | 3,046 | 250,595 | `to_numpy (array.py:1700)` |
| 1,309 | 1,309 | 9,003,918 | `<method 'get' of 'dict' objects> (~:0)` |
| 1,172 | 1,179 | 1,782,875 | `__iter__ (array.py:818)` |
| 1,034 | 2,744 | 688,190 | `pandas_dtype (common.py:1821)` |
| 1,029 | 1,223 | 9,168,528 | `<built-in method builtins.issubclass> (~:0)` |
| 1,012 | 2,290 | 1,570,218 | `issubdtype (numerictypes.py:418)` |
| 1,005 | 2,147 | 351,952 | `__init__ (string_arrow.py:134)` |
| 844 | 4,342 | 4,268 | `run_weeks (trade_lineup_model.py:604)` |
| 801 | 5,815 | 245,031 | `take (array.py:1568)` |
| 791 | 1,984 | 264,183 | `_take_nd_ndarray (take.py:118)` |
| 766 | 3,893 | 1,024,060 | `_fast_dtype (frame_records.py:24)` |
| 763 | 931 | 2,048,771 | `maybe_box_native (cast.py:186)` |
| 749 | 9,640 | 7,346 | `_interleave (managers.py:1898)` |

**Before, warm requests, top 20 by self time**

| self ms | cum ms | calls | function |
|---:|---:|---:|---|
| 211 | 273 | 1,820,887 | `<built-in method builtins.isinstance> (~:0)` |
| 187 | 1,724 | 625 | `frame_records (frame_records.py:28)` |
| 176 | 181 | 20,508 | `take (compute.py:467)` |
| 147 | 280 | 196,761 | `deepcopy (copy.py:119)` |
| 126 | 126 | 955,795 | `<method 'get' of 'dict' objects> (~:0)` |
| 122 | 350 | 137,575 | `_name_get (_dtype.py:342)` |
| 121 | 256 | 23,182 | `to_numpy (array.py:1700)` |
| 120 | 469 | 134,056 | `__str__ (_dtype.py:32)` |
| 100 | 215 | 38,991 | `__init__ (string_arrow.py:134)` |
| 85 | 228 | 58,308 | `pandas_dtype (common.py:1821)` |
| 82 | 188 | 135,459 | `issubdtype (numerictypes.py:418)` |
| 75 | 77 | 752,404 | `<built-in method builtins.issubclass> (~:0)` |
| 72 | 356 | 396 | `run_weeks (trade_lineup_model.py:604)` |
| 71 | 98 | 407,975 | `<built-in method builtins.len> (~:0)` |
| 70 | 87 | 210,882 | `maybe_box_native (cast.py:186)` |
| 69 | 70 | 112,808 | `__iter__ (array.py:818)` |
| 63 | 434 | 20,508 | `take (array.py:1568)` |
| 62 | 313 | 85,987 | `_fast_dtype (frame_records.py:24)` |
| 62 | 92 | 104,300 | `__eq__ (string_.py:235)` |
| 60 | 654 | 22,455 | `astype (string_arrow.py:325)` |

**After, cold requests, top 20 by self time**

| self ms | cum ms | calls | function |
|---:|---:|---:|---|
| 3,347 | 3,128 | 138 | `<built-in method time.sleep> (~:0)` |
| 1,596 | 2,634 | 12,668,172 | `<built-in method builtins.isinstance> (~:0)` |
| 1,041 | 1,986 | 1,331,653 | `deepcopy (copy.py:119)` |
| 921 | 921 | 6,897,991 | `<method 'get' of 'dict' objects> (~:0)` |
| 729 | 807 | 69,141 | `take (compute.py:467)` |
| 595 | 3,106 | 2,932 | `run_weeks (trade_lineup_model.py:621)` |
| 523 | 1,790 | 494,092 | `_stable_payload (trust_engine.py:248)` |
| 514 | 517 | 762,505 | `__iter__ (array.py:818)` |
| 443 | 769 | 89,028 | `<built-in method builtins.sorted> (~:0)` |
| 436 | 946 | 158,722 | `__init__ (string_arrow.py:134)` |
| 427 | 427 | 3,764,583 | `<method 'append' of 'list' objects> (~:0)` |
| 373 | 373 | 3,906 | `raw_decode (decoder.py:351)` |
| 340 | 411 | 969,344 | `maybe_box_native (cast.py:186)` |
| 321 | 1,860 | 60,574 | `_deepcopy_dict (copy.py:218)` |
| 314 | 1,754 | 1,739 | `frame_records (frame_records.py:55)` |
| 299 | 564 | 196,580 | `_candidates (trade_lineup_model.py:609)` |
| 284 | 2,114 | 89,380 | `__finalize__ (generic.py:6119)` |
| 279 | 364 | 351,018 | `take (trade_lineup_model.py:576)` |
| 278 | 379 | 1,530,033 | `<built-in method builtins.len> (~:0)` |
| 256 | 372 | 75,460 | `points_for (trade_lineup_model.py:687)` |

**After, warm requests, top 20 by self time**

| self ms | cum ms | calls | function |
|---:|---:|---:|---|
| 144 | 196 | 1,163,662 | `<built-in method builtins.isinstance> (~:0)` |
| 130 | 248 | 171,662 | `deepcopy (copy.py:119)` |
| 111 | 111 | 800,510 | `<method 'get' of 'dict' objects> (~:0)` |
| 91 | 93 | 8,699 | `take (compute.py:467)` |
| 69 | 149 | 25,601 | `__init__ (string_arrow.py:134)` |
| 52 | 158 | 12,126 | `sanitize_array (construction.py:531)` |
| 47 | 232 | 260 | `run_weeks (trade_lineup_model.py:621)` |
| 44 | 61 | 236,621 | `<built-in method builtins.len> (~:0)` |
| 40 | 232 | 7,380 | `_deepcopy_dict (copy.py:218)` |
| 40 | 75 | 5,775 | `to_numpy (array.py:1700)` |
| 37 | 37 | 333,254 | `<method 'append' of 'list' objects> (~:0)` |
| 36 | 133 | 11,907 | `__getitem__ (array.py:721)` |
| 36 | 230 | 234 | `frame_records (frame_records.py:55)` |
| 35 | 281 | 10,641 | `__finalize__ (generic.py:6119)` |
| 30 | 82 | 23,228 | `pandas_dtype (common.py:1821)` |
| 30 | 30 | 43,531 | `__iter__ (array.py:818)` |
| 30 | 213 | 8,699 | `take (array.py:1568)` |
| 28 | 43 | 39,206 | `__eq__ (string_.py:235)` |
| 28 | 269 | 98 | `profile_roster (trade_lineup_model.py:474)` |
| 28 | 59 | 5,212 | `<built-in method builtins.sorted> (~:0)` |

**Before, cold: repo functions by cumulative time**

| cum ms | calls | function |
|---:|---:|---|
| 50,259 | 4 | `generate_trade_idea_records_cached (modules/trade_hub_engine.py:832)` |
| 50,254 | 4 | `<lambda> (modules/trade_hub_engine.py:881)` |
| 50,253 | 4 | `_generate_trade_idea_records_cached (modules/trade_hub_engine.py:744)` |
| 50,237 | 4 | `generate_trade_idea_records (modules/trade_hub_engine.py:501)` |
| 50,069 | 4 | `build_trade_ideas (modules/trade_ideas.py:4343)` |
| 50,059 | 4 | `_build_trade_ideas_impl (modules/trade_ideas.py:4631)` |
| 46,424 | 138 | `redis_single_flight_cache (modules/redis_cache.py:179)` |
| 39,534 | 7 | `wrapper (services/mobile_api_service.py:739)` |
| 38,580 | 124 | `passes (modules/trade_ideas.py:4544)` |
| 38,214 | 62 | `_overflow_plan (modules/trade_ideas.py:4525)` |
| 38,010 | 62 | `plan_trade_overflow (modules/drop_candidates.py:524)` |
| 35,846 | 62 | `drops_for_overflow (modules/drop_candidates.py:444)` |
| 24,751 | 5,033 | `_facts (modules/drop_candidates.py:154)` |
| 24,521 | 5,033 | `row (modules/roster_value_model.py:310)` |

**After, cold: repo functions by cumulative time**

| cum ms | calls | function |
|---:|---:|---|
| 31,167 | 143 | `redis_single_flight_cache (modules/redis_cache.py:179)` |
| 20,202 | 7 | `wrapper (services/mobile_api_service.py:739)` |
| 15,353 | 4 | `generate_trade_idea_records_cached (modules/trade_hub_engine.py:832)` |
| 15,348 | 4 | `<lambda> (modules/trade_hub_engine.py:881)` |
| 15,347 | 4 | `_generate_trade_idea_records_cached (modules/trade_hub_engine.py:744)` |
| 15,330 | 4 | `generate_trade_idea_records (modules/trade_hub_engine.py:501)` |
| 15,152 | 4 | `build_trade_ideas (modules/trade_ideas.py:4343)` |
| 15,146 | 4 | `_build_trade_ideas_impl (modules/trade_ideas.py:4631)` |
| 12,358 | 2 | `get_league_dashboard (services/mobile_api_service.py:11793)` |
| 10,777 | 124 | `passes (modules/trade_ideas.py:4544)` |
| 10,476 | 62 | `_overflow_plan (modules/trade_ideas.py:4525)` |
| 10,264 | 62 | `plan_trade_overflow (modules/drop_candidates.py:524)` |
| 9,440 | 1,058 | `evaluate_swap (modules/roster_value_model.py:455)` |
| 9,075 | 724 | `_evaluate_swap_uncached (modules/roster_value_model.py:485)` |

**Before, warm: repo functions by cumulative time**

| cum ms | calls | function |
|---:|---:|---|
| 3,206 | 6 | `wrapper (services/mobile_api_service.py:739)` |
| 2,891 | 1 | `get_league_waivers (services/mobile_api_service.py:16265)` |
| 2,082 | 1 | `post_trade_analyzer (services/mobile_api_service.py:6019)` |
| 1,875 | 1 | `_compute_trade_analyzer (services/mobile_api_service.py:6106)` |
| 1,724 | 625 | `frame_records (modules/frame_records.py:28)` |
| 1,659 | 96 | `evaluate_swap (modules/roster_value_model.py:407)` |
| 1,553 | 1 | `build_drop_board (modules/drop_candidates.py:498)` |
| 1,458 | 333 | `_facts (modules/drop_candidates.py:154)` |
| 1,445 | 333 | `row (modules/roster_value_model.py:310)` |
| 1,421 | 6 | `suggest_drop_for_add (modules/drop_candidates.py:353)` |
| 1,345 | 17 | `candidate_pool (modules/drop_candidates.py:216)` |
| 1,193 | 3 | `plan (services/mobile_api_service.py:5987)` |
| 1,185 | 3 | `plan_trade_overflow (modules/drop_candidates.py:524)` |
| 1,034 | 3 | `drops_for_overflow (modules/drop_candidates.py:444)` |

**After, warm: repo functions by cumulative time**

| cum ms | calls | function |
|---:|---:|---|
| 1,675 | 6 | `wrapper (services/mobile_api_service.py:739)` |
| 1,362 | 1 | `get_league_waivers (services/mobile_api_service.py:16265)` |
| 1,250 | 1 | `post_trade_analyzer (services/mobile_api_service.py:6019)` |
| 1,065 | 1 | `_compute_trade_analyzer (services/mobile_api_service.py:6106)` |
| 808 | 96 | `evaluate_swap (modules/roster_value_model.py:455)` |
| 767 | 62 | `_evaluate_swap_uncached (modules/roster_value_model.py:485)` |
| 428 | 13 | `assess_needs (modules/roster_value_model.py:745)` |
| 420 | 52 | `wire_options (modules/roster_value_model.py:590)` |
| 410 | 1 | `build_counter_offer_packages (modules/trade_offer_analyzer.py:423)` |
| 409 | 2 | `_record (modules/trade_offer_analyzer.py:486)` |
| 409 | 2 | `_regrade_counter_package (services/mobile_api_service.py:6431)` |
| 406 | 3 | `evaluate_trade_analyzer_fit (modules/trade_analyzer_fit.py:495)` |
| 370 | 1 | `build_drop_board (modules/drop_candidates.py:498)` |
| 368 | 6 | `suggest_drop_for_add (modules/drop_candidates.py:353)` |
