# Local load test, 2026-10 (50 and 200 simulated users)

Everything ran locally. No production, no real users, no real Sleeper or
Supabase traffic.

## Method

- Harness: `scripts/load_test_local.py` (`--users N --workers 4 [--ramp S]`).
- FastAPI app (`services/mobile_api_service.py`) under `uvicorn --workers 4`
  on an 8-core / 8 GB Mac. The load driver, stub server and Redis ran on the
  same machine, so absolute numbers are pessimistic versus the production box.
- Data: a throwaway copy of `data/` (cwd of the app), so the real
  `data/players.db` was never touched.
- Sleeper AND Supabase are replaced by one local stub HTTP server (30 ms
  nominal upstream latency) that counts every Sleeper request. Each user gets
  their own synthetic 12-team league built from real player ids; 25% of users
  are Pro, 75% Free.
- Redis: a real throwaway `redis-server` shared by the 4 workers (the same
  topology as docker-compose, so single-flight caches behave as in prod).
- Per-user session: dashboard, my-team, trade-hub, matchup, waivers,
  playoff-odds, in that order, 0.2 s think time, 60 s client timeout.
- Runs: 50 users arriving at once; 200 users arriving at once; 200 users
  ramped over 120 s. All leagues are cold (worst case: a thundering herd of
  first opens).
- Runs 1 and 2 are the baseline (before the safety net). Run 3 includes the
  safety net from this PR (it never triggers on the stub unless the budget is
  crossed; see below).

## Results

Latency in ms. "n" is completed requests; timed-out requests are NOT in the
percentiles (survivor bias), so read the error column with them.

### 50 users, simultaneous, 4 workers (baseline): 0 errors, 91 s wall

| Endpoint | p50 | p95 | max |
|---|---|---|---|
| dashboard | 51,048 | 77,492 | 80,698 |
| my-team | 977 | 3,742 | 4,814 |
| trade-hub ideas | 13,133 | 25,257 | 41,159 |
| matchup | 614 | 3,634 | 4,759 |
| waivers | 1,507 | 6,457 | 7,098 |
| playoff-odds | 871 | 8,650 | 9,107 |

Sleeper calls: 2,121 total = **42.4 per user session**, about 1,400/min over
the 91 s run (over the 1000/min ceiling from a single burst of 50 users).
Breakdown per session: matchups 14.6, transactions 7.0, rosters 4.7, users
3.5, traded_picks 2.3, league 4.8, user lookups 5.3.

### 200 users, simultaneous (baseline): saturated

656 s wall. Completed (n) / timed out at 60-120 s: dashboard 9 / 191, trade-hub
5 / 195, matchup 26 / 174, waivers 84 / 116, my-team 84 / 116, playoff-odds
179 / 21. Of requests that did finish, p50 was 30-114 s. 13,301 Sleeper calls
(66.5 per session).

### 200 users, ramped over 120 s (with safety net): saturated

481 s wall. Completed vs timed out: dashboard 29 / 171, trade-hub 25 / 175,
matchup 25 / 175, waivers 25 / 175, my-team 65 / 135, playoff-odds 24 / 176.
Finished-request p50 / p95 (ms): dashboard 19,039 / 50,434; my-team 4,000 /
33,210; trade-hub 1,143 / 1,956; matchup 1,535 / 4,296; waivers 6,091 /
20,537; playoff-odds 1,357 / 45,792. 6,678 Sleeper calls (33.4 per session).

## Findings

1. **Capacity on this setup is roughly 50 concurrent cold users.** 50 users:
   no errors but 51 s dashboard p50. 200 users: the 4 workers are CPU
   saturated and most requests time out. Steady-state warm users are far
   cheaper; the risk is cold-cache bursts (a launch, a push notification, a
   deploy that empties Redis).
2. **Dashboard is the bottleneck** (51 s p50 at 50 cold users). It is the first
   screen and cold-computes the rankings frame, lineup and trade-idea inputs
   for the user's league. Trade-hub idea generation is second (13 s p50).
   Both are CPU work, so more workers/cores help directly and the GIL limits
   each worker to one such computation at a time.
3. **Sleeper fan-out is per-session heavy**: 33-66 calls per session cold. A
   single 50-user burst already exceeds ~1000 calls/min. Matchups are the
   biggest line (one call per week for playoff odds/dashboard), then
   transactions and rosters. The 30 s time-bucketed `lru_cache` getters in
   `modules/sleeper.py` are **per process**, so 4 workers fetch the same
   league up to 4 times; they are also not shared via Redis.
4. A failed Sleeper call used to be cached as an empty list/dict for the whole
   30 s bucket, so one 429 produced an empty roster for 30 s.
5. Harness note: the stub returns 404 for the 16 MB `/players/nfl` dump, so
   the players refresh retried (24-31 attempts); production gets the on-disk
   dump. Not counted in the per-session numbers above beyond that total.

## Sleeper audit (gaps in shared caching)

- `modules/sleeper.py::_request_json` is the choke point for league, rosters,
  users, matchups, transactions, traded picks, trending, stats and user
  lookup. Caches: 30 s bucketed `lru_cache` (per process), 10 min trending,
  disk caches for the players dump and season stats.
- Not shared across workers: users/rosters/league/matchups/transactions/
  traded_picks. Candidate follow-up: put them behind
  `redis_cache.redis_single_flight_cache` like the rankings frames.
- `modules/sleeper_leagues.py` calls `requests.get` directly for user id and
  user leagues lookups (not cached across workers, no retry). Now counted
  against the budget; caching them in Redis is a follow-up.
- `services/fantasy_content.py` only references a Sleeper URL string.

## Safety net added in this PR

`modules/sleeper_budget.py`, wired into `modules/sleeper.py` and the mobile API.

- **Budget counter**: every outbound Sleeper request (each retry attempt, the
  players dump, the two `sleeper_leagues` lookups) increments a per-minute
  counter in Redis (shared by all workers) with a process-local sliding window
  as the fail-open fallback. Defaults: 1000/min budget (`SLEEPER_CALLS_PER_MINUTE`),
  soft threshold 70% (`SLEEPER_BUDGET_SOFT_FRACTION`). The out-of-process
  players.db rebuild subprocess is not counted.
- **Priority**: over the soft threshold, league warm-ups are not started, the
  background players refresh (both the dump download and the players.db
  rebuild trigger) pauses, and free-tier requests are served last-known
  Sleeper data instead of refreshing. Paid-tier (Pro / Front Office) requests,
  and requests whose profile read failed, always proceed. If nothing is
  cached a free-tier request still fetches live (no fabricated data);
  background work with nothing cached just skips. Entitlement rules are
  unchanged: the tier is only read from the existing profile lookup.
- **429 / timeout / 5xx**: after retries are exhausted `_request_json` returns
  the last successful payload for that URL (bounded to 1,024 entries,
  per process) instead of an empty result, and records its fetch time.
  Plain 4xx (e.g. 404) never falls back. With no last-known payload the
  behavior is unchanged (None / empty).
- **As-of**: dashboard, my-team, trade-hub, matchup, waivers and playoff-odds
  responses gain `sleeper_data_as_of` (ISO timestamp of the oldest last-known
  payload used) only when last-known data was served. None of those responses
  had an existing timestamp field. No UI change in this PR: web-next and
  mobile ignore the key, so parity is unchanged; surfacing it as a small
  "as of" note on both platforms is a follow-up if wanted. Results cached in
  Redis single-flight caches do not carry the key on later cache hits.
- Tests: `tests/test_sleeper_budget.py` (17 focused tests); `tests/conftest.py`
  resets the budget module per test.

## Suggested next steps

- Share the 30 s league getters across workers through Redis single-flight.
- Fetch matchups once per league and week range, not per caller.
- Pre-warm and rate-limit cold dashboard builds (queue instead of fan-out).
- Re-run at 50 users on production-like hardware to confirm the 4-worker
  capacity estimate before a launch.
