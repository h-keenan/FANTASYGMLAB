# Portfolio load-time audit, 2026-11

Owner report: "Portfolio still takes arguably too long to load." Earlier passes:
`docs/performance-audit-2026-11.md` (backend) and `docs/performance-audit-client-2026-11.md` (client).
Portfolio = web `/portfolio` (`web-next/src/app/portfolio/page.tsx`), mobile `PortfolioScreen`,
backend `GET /v1/portfolio/leagues` (index) + `GET /v1/portfolio/leagues/{id}` (one row) +
legacy `GET /v1/portfolio` (all rows in one response, still used by shipped app builds).

## Headline

Measured with `scripts/bench_endpoints.py --portfolio 1,5,12` (new): stub Sleeper 30-60 ms, stub Supabase 30 ms,
one in-process API (one GIL), client driven like the real ones (index, then rows 3 at a time).
Shared Apple M1 with other sessions running (load 4-13), so read wall times as direction; CPU is the steadier
number. Medians of 5 runs per side, before = `origin/main` at the PR base, same harness file, interleaved.

**Cold visit** (first ever / long absence; user never seen by the process):

| Leagues | Metric | Before | After |
|---|---|---:|---:|
| 1  | first card (identity visible) | 3.1 s | 2.2 s |
| 5  | first card | 3.7 s | **1.2 s** (-69%) |
| 5  | all headlines (record, ranks, archetype, top asset, health) | 8.7 s | **2.4 s** (-72%) |
| 12 | first card | 3.6 s | **1.4 s** (-60%) |
| 12 | all headlines | 37.1 s | **5.6 s** (-85%) |
| 1 / 5 / 12 | all cards complete incl. signals | 3.1 / 8.8 / 37.1 s | 4.4 / 12.7 / 41.2 s (+20% CPU, see "Cost") |

**Revisit after the 2-minute cache layers expired (the common case: coming back a few minutes later)**:

| Leagues | Before (all cards) | After (all cards) | After (first card) |
|---|---:|---:|---:|
| 1  | 1.4-1.8 s | 55-61 ms | 6-16 ms |
| 5  | 8.5-13.3 s | 66-73 ms | 10-13 ms |
| 12 | 38-43 s | 102-113 ms | 20-24 ms |

Revisit within the fresh window (warm): 1 league unchanged (55 ms), 5 leagues 165 -> 66 ms, 12 leagues 438 -> 189 ms.

**Failed rows at 12 leagues** (per-league 25 s deadline; one process): before, cold runs had timed-out rows in
2 of 5 runs and the after-expiry revisit had them in both runs (hash `6f12...` = rows with `timed_out`);
the legacy `GET /v1/portfolio` timed out (25 s) at 12 leagues in every run on both sides (in production with 4 workers it
spreads out; the single-process bench cannot show that). After: cold runs failed in 2 of 5 (same load-induced
deadline, it is a CPU-bound single process), revisits 0 of 2. The root cause for the cold case is CPU per league (below).

On a device the client additionally paints from its own cache before any request:
web (new) from localStorage, mobile from the persisted React Query cache (already existed, now also correct
for the headline-first flow).

## Where the time went (measured)

- Per league cold row: about 2.5 s CPU. cProfile of one cold row: trade-idea search 60% (drop/overflow engine,
  `evaluate_swap`), then rankings frame / `league_needs` / posture / valued frame. Everything under a row lives in
  120 s time buckets (`VALUED_PLAYERS_FRAME_TTL_SECONDS`, `LEAGUE_RANKINGS_FRAME_TTL_SECONDS`,
  `TRADE_HUB_IDEAS_TTL_SECONDS`), so any visit more than 2 minutes after the last one recomputed every league from
  scratch: cost scales linearly with league count (1 / 5 / 12 leagues: 2.6 / 9.2 / 41.7 s CPU).
- Request waterfall was already parallel (index, then 3 rows at a time); Sleeper calls 8 / 36 / 85 and Supabase
  REST 4 / 12 / 28 for 1 / 5 / 12 leagues: about 2.3 REST calls per league (stance + GM targets, each Redis-cached 15 s).
  No serial awaits or duplicated rankings builds across leagues were found: valuations are per league (different
  rosters/settings) so there is no cross-league frame to share without changing results.
- Payload: about 3.9 KB per league row; not a cost.
- Web had no stale-while-revalidate and rendered every league eagerly.

## What changed

Backend
- `modules/portfolio_cache.py` (new): finished-row cache. Fresh 120 s; stale up to 30 min is served at once and
  refreshed in the background (one refresher per row cluster-wide, Redis lock); older or absent is computed in
  the request, single-flight across workers. Key = user, league, lens + fingerprint of every per-user input
  (entitlement, the row's Sleeper username, team stance, GM targets/untouchables), so changing any of them is a
  miss with no invalidation hooks. Only successful rows are cached; fail-open to computing if Redis is down.
  Values are the final `jsonable_encoder` row, so a cached row serializes exactly like a fresh one.
- `GET /v1/portfolio/leagues/{id}` and legacy `GET /v1/portfolio` both go through it.
- `GET /v1/portfolio/leagues/{id}?signals=defer`: headline-first. On a row-cache miss, answers with every field
  except `top_item`/`top_items` and `signals_pending: true`, skipping trade ideas, posture and briefing
  (`build_league_summary(defer_signals=True)`). Cached rows are always returned complete (no extra field).
  Absent parameter = byte-identical behavior to before.

Clients (web + mobile, shared loader in both `portfolioLoader.ts` between SHARED markers, twin check passes)
- Two-phase per league: all headlines are queued before any league's signals; cards show a signals skeleton.
- Windowing: first 6 leagues load immediately; the rest are released as the list scrolls near them
  (web: sentinel at the window edge, 600 px lookahead; mobile: `onEndReached`); Share on mobile releases all first.
- Stale-while-revalidate: web stores the last complete Portfolio per user/lens in localStorage (cleared on
  sign-out), paints it instantly, revalidates rows older than 30 s with one full request each, never blanks stale
  data on a failed refresh. Mobile does the same on top of its persisted query cache.

## Cost (honest)

Headline-first splits one request into two for leagues without a cached row, so a cold complete visit costs
about 20% more CPU (cold all-cards 3.1 -> 4.4 s at 1 league; 8.8 -> 12.7 s at 5; 37 -> 41 s at 12): the shared layers
are cached so most of the second request is the trade-idea search, but the first request also pays the rankings
work and the second repeats lineup/injury work. It buys much earlier content and, with windowing, a user who does
not scroll never pays for the below-the-fold leagues. It does not make a truly cold 12-league first visit finish
sooner; that needs cheaper trade-idea generation (follow-ups).

## Equivalence

- Final composed rows (canonical JSON hash, volatile keys stripped) are identical before/after for 1 and 5 leagues
  in all runs, and for 12 leagues whenever no row timed out (`d247e39a12ac50ec` on both sides). Legacy
  `GET /v1/portfolio` body hashes match too (1 and 5 leagues).
- `tests/test_portfolio_performance.py` (new): cached row == legacy row; cache hit/miss on every input; failed rows not
  cached; numpy values round-trip; stale served then refreshed once; too-old rebuilt; Redis down computes; single-flight;
  headline fields == full-row fields, `signals_pending` flow; engine-level test that `defer_signals` skips
  trade ideas/posture/briefing and changes nothing else.
- Client: loader (window, ordering, warm/skip, abort, retry), snapshot, progress composition, content skeleton/sentinel
  and a page-level test (headline then signals; instant paint from storage; fresh rows untouched; failed refresh keeps
  stale data) on web; the same loader tests on mobile (`node --test`).
- No valuation or ranking code changed.

## Not measured

- Client render time / time-to-first-content in a real browser or device: not measured (no Playwright pass, no
  device build). Server-side time to first card and to all headlines are in the tables; the client paints from cache
  in the same frame on a revisit.
- Production multi-worker behavior (bench is one process, so it overstates GIL contention).

## Follow-ups

- Duplicated work inside one cold row: `filter_waiver_actionable_players` runs 3x (about 400 ms of profiled time),
  `league_needs` 2x (about 400 ms). Safe to memoize per (frame, league) but touches shared engines used by Trade Hub /
  Waivers, so it needs its own equivalence tests; not done here.
- Cheaper trade-idea generation (60% of a cold row), or computing trade ideas lazily only when a league card is
  opened / scrolled into view.
- Batch the per-league stance and GM-target Supabase reads into one query per user (about 2 REST calls per league).
- Proactive warming: refresh a user's Portfolio rows when they sign in or open Home so even the first visit is warm.
