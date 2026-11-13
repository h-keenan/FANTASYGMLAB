# Live plays and updates: what we can legitimately use

Goal (owner): live plays and live updates on the Matchup page while it is open.
This doc records what data exists, what shipped now, and a recommendation for
real play-by-play. Prices below are rough and unverified: get quotes before
deciding.

## Shipped now (no new third-party dependency)

1. **Scoring feed from polled snapshots** (`lib/liveFeed.ts`, web + app twins).
   Each poll (30-60 s while live, see `docs/live-scores.md`) the client diffs
   every starter's points and stat line against the previous poll and emits one
   event per changed player: "Skattebo +6.0 (rushing TD, 4 yds)". Derived
   from stat deltas: passing/rushing/receiving TD with yards, field goal, extra
   point, interception thrown, fumble lost, 2-pt, catches with yards, rushes
   with yards, defensive TD/INT/fumble recovery/sack/safety. Stamped with the poll
   time, marked "approx." when several things merged into one poll or when only
   points (no stat line) changed. Kept in memory (max 50, per league+week), shown
   in a collapsible Live feed grouped by NFL game, "NEW" on unseen items, plus a
   pulse on cards whose points just changed.
2. **Stat lines**: `modules/live_stat_lines.py` reads Sleeper's league-wide week
   stats (`/stats/nfl/regular/{season}/{week}`, the same endpoint
   `modules/sleeper.py` already uses for season stats) through the shared cache
   at the live TTL (20-90 s adaptive). One fetch per (season, week) cluster-wide,
   shared by every league and user; per request it is a dict lookup per starter.
   Load stays flat. If that payload is missing or stale the feed degrades to
   points-only events ("yardage / other scoring", approx.).
   Caveat to verify in production: it is an undocumented Sleeper endpoint and we
   have not measured how quickly it updates mid-game relative to
   `/league/{id}/matchups`. Matchups points are the source of truth; stats only
   explain them.
3. **Game-level context** from data we already cache (`modules/nfl_schedule.py`,
   nflverse `games.csv`): opponent, home/away, kickoff, status
   (scheduled / in_progress / final), final score once nflverse publishes it, and
   an estimated quarter (`~Q3`) from wall-clock progress. There is **no** live
   scoreboard source in the repo: no live team score, quarter or clock, which is
   why the quarter is an estimate and marked `~`.

Not built: a server-side "events since cursor". The client diffs its own polls,
which costs nothing server-side; the limit is that a page opened mid-game has no
history before it opened, and two open tabs/devices each build their own feed.
If we later want shared history, derive events once per league per refresh from
the cached previous snapshot in Redis (key: league/week/starter) and add
`?since=<cursor>`; this is cheap (one diff per league per 20-30 s) but it needs the
cursor contract and retention rules first. Notification-center hook: left as a
follow-up.

## Options for real play-by-play

| Source | What it gives | Latency | Cost | Risk |
|---|---|---|---|---|
| Sleeper | Points and weekly stat lines; **no play-by-play** | stats update during games (to be measured) | free | undocumented stats endpoint, rate limits (already budgeted) |
| nflverse PBP (nflfastR/nflreadr releases) | Full play data with EPA, drives | **post-game**: files are rebuilt after games (hours, sometimes the next day) | free (open data) | not live; fine for recaps and "what happened" after the game, not for a live feed |
| ESPN public JSON (`site.api.espn.com/.../football/nfl/scoreboard`, `summary?event=`) | live score, quarter, clock, drives and plays | seconds to ~1 min | free, no key | **unofficial**: no SLA or documentation, can change or block without notice; terms restrict commercial use of ESPN data; do not build a product dependency on it |
| NFL.com feeds | same class | | | unofficial and restricted, same concerns |
| Paid providers: Sportradar, SportsDataIO, Stats Perform, Genius Sports, MySportsFeeds | licensed live play-by-play, scores, clock, injuries; push or fast polling | 1-15 s | from roughly low hundreds of dollars per month (SportsDataIO / MySportsFeeds tiers) to five figures per year (Sportradar and enterprise feeds), with redistribution terms that differ by plan | contract, per-seat or per-call limits, attribution requirements |

## Recommendation

1. Keep (a)+(b) as the product for now: they are legitimate, free, and answer
   "what just happened to my players" with honest labels.
2. For a true live scoreboard (team score, quarter, clock) and play text, use a
   **licensed provider** and start with the cheapest tier that permits
   redistribution in an app (get quotes from SportsDataIO and MySportsFeeds
   first; Sportradar if we need push/SLA). Fetch it server-side once per game per
   few seconds, cache cluster-wide like Sleeper matchups, and never call it per
   user. Budget: provider fee plus one worker; no per-user cost.
3. Do not ship ESPN's unofficial endpoints as a dependency of a paid product. If
   used at all, treat them as a best-effort enhancement behind a feature flag
   with a hard fallback to the current feed, after a legal read of the terms.
4. Use nflverse PBP after the game for recap text ("Skattebo 4-yd TD run, Q2") and
   to backfill the feed history for the finished game.

## Verification still needed

- Measure Sleeper weekly-stats freshness during a live Sunday window against the
  matchups points (log stat-line age vs points age).
- Confirm stat key names for IDP/DEF/K in live payloads (the derivation uses
  Sleeper's `fgm`, `xpm`, `pass_int`, `fum_lost`, `def_td`, `int`, `sack`, ...).
