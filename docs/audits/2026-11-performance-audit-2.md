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

## Not covered (follow-ups)
Web next build route sizes and 390px / 4x CPU CLS/LCP/INP traces, animated-background cost, mobile list
virtualization/startup, Supabase index review, live-scores budget, players.db rebuild time.
