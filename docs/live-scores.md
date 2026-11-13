# Live scores: freshness path and policy

Owner report (Thu night, NYG-WAS): Matchup ran about 7 minutes behind the Sleeper app.

## Where the lag came from (before)

Real points per starter are NOT computed by us: `_real_current_lineup` reads
`starters_points` / `points` straight from Sleeper's
`/league/{id}/matchups/{week}`. No stats endpoint or nflverse feed is involved in
the number itself, so there is no "slower second source" for points.

| Layer | Before | Worst-case age added |
|---|---|---|
| Sleeper's own scoring update | their pipeline | unknown, see below |
| `sleeper._get_matchups_cached` lru bucket (per process) | 30 s time bucket | 0-30 s |
| `sleeper_cache.shared_json` (Redis + local, single-flight) | 30 s TTL | 0-30 s (stacked on the lru: **up to 60 s**) |
| `sleeper_budget.should_defer` for free-tier users over 70% of the call budget | serves `last_known` with no age bound | **unbounded** (minutes) under load |
| `get_league` / `get_rosters` (settings.leg, roster ids) | 30 s lru + 30 s shared | not score-bearing |
| `_build_matchup` result | not cached (recomputed per request) | 0 |
| HTTP (Caddy `encode` only; API had no Cache-Control on /matchup; no service worker) | none | 0 |
| web-next client | **one-shot fetch, never refreshed** (reload only) | unbounded: the screen is as old as the last load |
| mobile client | RQ `staleTime` 30 s, refetch only on screen focus, persisted cache paints first, **no interval** | unbounded while sitting on the screen |
| mobile Live Activity poll | 60 s | 60 s + server |
| nflverse `games` (kickoff / `played`) | 6 h disk, 5 min in-process | affects only the LIVE badge / game fraction (wall-clock fallback covers it) |
| `sleeper.get_players` (injury status) | 5 min | affects the injury-exit rule only |

Server stack: 60 s steady-state, unbounded under budget deferral. Client: a screen
left open never refreshes. A watcher who last navigated a few minutes ago sees
everything older than their last navigation plus 60 s of server layers, which is
how 5 to 7 minutes shows up. Sleeper's own lag is not measurable from our side;
our layers are the part we control and were the dominant, avoidable term (we
cannot tell how much of the remaining few seconds-to-a-minute is Sleeper's
scoring pipeline, which updates its own app from the same source).

## Policy now (`modules/live_policy.py`)

- Live window = any regular-season kickoff of the current NFL week from 20 min
  before kickoff until `GAME_IN_PROGRESS_WINDOW` (4.5 h) after.
- Matchups TTL: adaptive (table below) for the live week during the window,
  `IDLE_TTL_SECONDS = 60` otherwise (and always for other weeks, so season scans
  stay cheap). One cache layer only (the per-process lru was removed): one
  upstream fetch per league per 20 s cluster-wide (Redis `SET NX` lock plus a
  per-process lock), regardless of users or workers.
- Live reads are exempt from free-tier budget deferral below 90% pressure; at or
  above it they defer to last-known data no older than 3 min (older: fetch
  anyway). Other Sleeper reads keep unbounded deferral.
- Derived values (win probability, projected finals, per-position edges) are pure
  arithmetic on the fetched points plus the already-cached valued frame and
  projections, recomputed each request. No stats fetch sits on the score path, so
  there is no global stats poll to add.
- Payload fields: `as_of` (when Sleeper's data was really fetched),
  `as_of_age_seconds`, `live`, `poll_after_seconds` (30 while live, null
  otherwise). Headers: `Cache-Control: private, no-store`, `Age`, `Server-Timing`.
- Clients (`web-next/src/lib/liveScores.ts` and the byte-identical
  `mobile/src/lib/liveScores.ts`): poll every 30-60 s only while `live`, screen
  visible/focused, app foregrounded and online; exponential backoff on errors
  (cap 5 min, honors Retry-After from `busyRetry`); catch-up refresh on becoming
  visible; "Updated 12s ago" plus Refresh button (web) and pull-to-refresh
  (mobile); last good data stays on screen when a refresh fails. The Live
  Activity poll is 30 s.

Worst-case lag while live: 20 s (shared cache) + 30 s (poll, up to 33 s with
jitter) + RTT = ~50-55 s of our own, down from 60 s to unbounded. Idle: 60 s
cache, no polling. Load stays flat: per league one Sleeper call / 20 s
(`scripts/bench_sleeper_cache.py`: 130 legacy calls vs 10 shared for the same
burst; `tests/test_live_scores_freshness.py` asserts 1 upstream call for 40
concurrent readers).

## Live projected final

Per starter whose game is in progress (`projected_final`, shown as "Proj final
18.4" next to live points on web and mobile):

    projected_final = actual + remaining * projection_mean + pace_adjustment
    pace_gap        = actual - (1 - remaining) * projection_mean
    pace_adjustment = w * pace_gap * remaining,  w = 0.25 * min(1, elapsed / 0.5)

`remaining` is `game_fraction_remaining` (wall clock since kickoff over
`GAME_WALL_CLOCK`). The pace blend never exceeds 25% of the gap, ramps in with
game progress so an early touchdown barely moves it, and vanishes at the end of
the game. Injury exit: a started, non-final game with an out/IR/inactive/PUP/
suspended `injury_status` (or an explicit `exited_game`) has remaining
projection 0 (final = points so far) and no remaining variance. That status
rides on the 5-minute players cache, so an exit shows up with that lag; it is the
one input not refreshed on the 20 s path. `modules/matchup_win_probability.py`
uses the same figure for each starter's mean, so the win chance and the per
starter number can never disagree.

## Adaptive TTL and the budget ceiling

At a fixed 20 s TTL each live league costs 3 Sleeper calls/min, so the ~1000/min
budget saturates at ~333 concurrently watched leagues. The live TTL therefore
scales with pressure (`sleeper_budget.calls_in_last_minute() / BUDGET_PER_MINUTE`,
cluster-wide via Redis):

| Pressure | Live TTL | Calls/min per league | Leagues that fit in 1000/min |
|---|---|---|---|
| < 40% | 20 s | 3.0 | ~330 |
| 40-60% | 30 s | 2.0 | ~500 |
| 60-80% | 45 s | 1.33 | ~750 |
| 80-90% | 75 s | 0.8 | ~1250 |
| >= 90% (severe) | 90 s, plus age-bounded (3 min) deferral for free tier | 0.67 | ~1500 |

- Hysteresis: a tier is entered at its threshold and left only 5 points below it.
- Each league's TTL has a deterministic +-15% jitter so leagues loaded together
  do not expire together.
- Only watched leagues get a live TTL: a league needs a request within the last
  120 s, otherwise it gets the 60 s idle TTL. Nothing is ever refreshed in the
  background; a fetch happens only because a request found the cache expired.
- `poll_after_seconds` = max(30, current TTL), so clients never poll faster than
  the server refreshes (client poll clamp is 30-120 s); `as_of` is the real fetch
  time, so the "Updated Ns ago" label stays honest at any tier.
- Beyond ~1500 simultaneously watched leagues the ceiling is real: TTL tops out at
  90 s and the severe-pressure deferral keeps other reads alive, but calls would
  exceed budget. That needs a second egress IP or a Sleeper allowance, not more
  caching.

Simulation (`tests/test_live_scores_adaptive.py`, 1000 live leagues x 4 users,
5 minutes, 150 calls/min of unrelated Sleeper traffic): upstream calls per minute
942 (cold start, users arriving), then 745, 620, 660, 743, each within budget with
the baseline after the first minute; worst staleness 101 s (the 90 s tier with
jitter), i.e. under heavy load the live screen degrades gracefully to about 100 s
of server age plus the poll, instead of blowing the budget.
