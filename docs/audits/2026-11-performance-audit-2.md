# Performance audit 2 (2026-11): Fantasy Sim backend reads and CI

Scope reached in this pass: Sim game backend reads (measured) and CI test time (from a full durations run).
Web bundle/390px traces, mobile and live-scores budget were NOT measured here; see "Not covered".
No sim engine behavior was changed. The only code change is the bench script (scripts/bench_sim_game.py),
which now also covers league/rosters, player detail/history, team history and sim-to options.

## Method
`PYTHONPATH=. python scripts/bench_sim_game.py --fixture <pkl> -n 8 --only reads --json out.json`
(in-memory instrumented store, week-8 redraft game and a season-3 dynasty_v=3 game; CPU ms per request, response KB).

## Measured: GET read endpoints (CPU p50 ms / response KB)
| endpoint | redraft w8 | dynasty s3 w8 |
|---|---|---|
| home | 35.5 / 28.8 | 41.2 / 25.4 |
| team (other) | 23.7 / 16.7 | 24.6 / 18.7 |
| players (size 60) | 12.1 / 33.7 (p95 48) | 12.7 / 33.7 |
| league | 20.9 / 24.6 | 20.5 / 25.6 |
| league/rosters | 30.0 / 134 | 32.1 / 155 (p95 67) |
| inbox | 1.6 / 1.3 | 19.4 / 1.4 |
| picks | 1.0 / 0.1 | 22.2 / 61.4 |
| player history | 30.6 / 0.6 (2 store reads, 259 KB) | 132 / 0.9 (3 reads, 1.14 MB) |
| team history | 30.8 / 2.5 (2 reads) | 134 / 7.0 (3 reads, 1.14 MB) |
| player detail | 1.5 / 2.4 | 2.3 / 5.7 |
| sim-to options | 1.1 / 0.3 | 1.0 / 0.3 |

## Prioritized findings
1. History endpoints (player/team) in a dynasty game cost ~132 ms CPU and read 1.14 MB of store per request,
   4x the redraft cost. They replay the event log (no checkpoint reuse). Candidate: cache the folded history per
   (game, event count), or fold from the nearest checkpoint. Needs a digest-neutral change; not done here.
2. dynasty picks (22 ms, 61 KB) and inbox (19 ms) are 20x their redraft cost; both recompute pick values/offers per
   request. Candidate: memoize per event count.
3. league/rosters is 134-155 KB uncompressed (GZip middleware is on, so ~25 KB on the wire); acceptable, but the
   p95 spike (67 ms) suggests first-hit cost; paginate or lazy-load per team if the list grows with 20-season dynasties.
4. players size=60 p95 of 48 ms vs p50 12 ms in redraft: one cold-cache hit per game; benign.
5. Hot reads home/team/league (20-40 ms) already one store call each, matching docs/performance-sim-game-2026-11.md.

## CI duration
Full sequential run: 6042 passed in 1150 s (19 min). CI uses `pytest -n auto`, which is the right lever.
Slowest single tests are ~10-11 s each: tests/test_player_eligibility_memo_parity.py (8 parametrized cases, ~84 s total),
tests/test_trust_fixture_isolation.py, tests/test_sim_game_review.py route test. Candidate: share a module-scoped
warm fixture in the eligibility memo parity file (~1 min of CPU saved); use `--dist worksteal` to reduce tail skew.

## Fixes landed (each its own PR, with measurement)
| PR | change | before -> after |
|---|---|---|
| #1853 | memoize player/team history per save version (row_version) | dynasty history 132 ms CPU, 1.14 MB store read -> 0.6 ms warm (first miss ~70 ms). cProfile: ~97% of the old cost was event-row copying in the in-memory store; the fold itself is ~3 ms, so the real saving is skipping the ~7k-event Supabase page reads |
| #1854 (stacked on #1853) | same memo for GET picks and inbox | picks 22.2 -> 1.7 ms, inbox 19.4 -> 0.8 ms warm; first hit after a write unchanged (~12 ms) |
| #1856 | CI `--dist worksteal` | compare test-job wall time on that PR vs main (11-16 min, noisy) |
| #1857 | app background animation off under prefers-reduced-motion; TeamAvatar lazy/async | 390px, 4x CPU, idle 5 s: main-thread task 3.93-3.97 s with the animated background vs 3.33-3.47 s without (about 0.5-0.6 s, 13-16%) |
| #1858 | docs/supabase_rls_initplan.sql: bare auth.uid() RLS policies -> (select auth.uid()) | NOT applied or tested; 128 bare uses; apply on staging first |

All tests/test_sim_*.py pass (557) with the memo. Engine behavior unchanged (only read endpoints cached, keyed on the same version proof as the state cache).

## Web (web-next, next build, Turbopack route-bundle-stats)
- Shared first-load JS: 14 chunks, 819 KB raw / 244 KB gzip (audit 1: 753 / 223, about +9% since). Biggest chunks 229 KB and 154 KB
  (framework/runtime), 123 KB (supabase), ~58 KB (api client + sim strings). /fantasy-sim/[leagueId] 832 KB first load
  (~12 KB route-specific); heaviest: /gm-game 1209 KB, /trade-analyzer 960 KB, /design 959 KB, /trade-hub 957 KB.
- Recharts and the PQV modal are already behind next/dynamic. Follow-up candidate: split lib/api.ts per feature (~58 KB shared).
- Avatars: PlayerAvatar already lazy+async+fixed box; TeamAvatar fixed in #1857.
- Vitals at 390px, 4x CPU (prod build, headless, 3 runs): / LCP 176-212 ms, CLS 0; /features LCP 624-824 ms, CLS 0;
  /premium LCP 836-928 ms, CLS 0. Authenticated Home/Team/Players/PQV traces not captured (need the mock harness).

## Mobile (static review)
- Screens are lazy-required in RootNavigator; list screens use FlatList (initialNumToRender 16, windowSize 9).
- Sim player browser renders a page of rows plus "Show more" windows via .map inside the ScrollView (bounded, not virtualized).
  PlayerListRow is not React.memo and callers pass fresh tags/actions each render, so memo alone would not help; the real fix is
  memoizing SimDraftRow with props derived inside it. Not changed (no device measurement available).

## Supabase
- sim_games (user_id, created_at idx), sim_events PK (game_id, seq), sim_week_checkpoints PK (game_id, week): hot sim queries are indexed;
  notifications, decision memory, trade outcomes, alert reads and gm_targets also have matching indexes.
- Finding: bare auth.uid() in RLS policies (#1858).

## Data refresh / live scores
- players.db refresh (every 6 h): last 8 runs 0.5-0.7 min end to end; nothing to optimize.
- docs/live-scores.md budget (adaptive TTL; ~1000 calls/min Sleeper budget) already analyzed; no change proposed.

## CI
Tried a shared warm reference for test_player_eligibility_memo_parity. Dropped: it broke test_monkeypatched_rules_never_reuse_old_results
and gave no reliable gain on a loaded machine. Next candidate: shard the test job in two.

## Not covered
Authenticated-screen LCP/INP traces, per-route chunk composition (minified), mobile device startup profiling.
