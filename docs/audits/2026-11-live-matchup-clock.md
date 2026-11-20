# Live matchup clock and play feed audit, 2026-11-19

Reports (coridian_): the Matchup panel does not update projections while a player's game is live, and the live play section does not seem to work.

## Findings

- Live points were fresh (Sleeper matchups cached 20-90s adaptive, clients poll 30s).
- `remaining` in the projected-final / win-probability blend came from a flat 190-minute wall clock since kickoff, and "final" from nflverse `played` (hours of lag, bounded by a 4.5h window). Halftime, delays and overtime were wrong.
- The live play feed upstream was healthy (Sleeper `/stats/nfl/regular/{season}/{week}` returned live stat lines), but the feed only emitted TD / 20+ yd / turnover deltas between two polls, started empty on a cold start, returned nothing when Redis failed, and was gated on a schedule file that may be missing.

## Change

- `modules/live_scoreboard.py`: real quarter, clock, score, down and distance, and final status from ESPN's public scoreboard JSON (`site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard`). Server side only, one shared fetch (single-flight cache), 20s TTL while live and 10 min when idle, generic User-Agent with no personal data, fail-open to the wall-clock estimate.
- `game_remaining` (regulation minutes left / 60; halftime 0.5; overtime a small positive share) feeds `game_fraction_remaining`, so projected finals, team totals and win probability use the real clock. Scoreboard "post" gives final immediately.
- New per-starter fields: `game_clock_label` ("Q2 5:54", "Half", "OT 9:12", "Final"), `game_remaining`, `game_situation` ("2nd & 7 at HOU 25"); live scores replace the nflverse-final-only scores.
- Feed: events carry the clock label; a cold start (or Redis down) shows honest "N TD so far" lines read from the current stat line, labelled `so_far`; nothing is invented. A scoreboard game in progress also enables the feed when the schedule file is missing.
- Kill switch: `DYNASTYGM_LIVE_REAL_CLOCK` (owner Zach), `0` restores the old behaviour.

## Risk

The ESPN endpoint is unofficial: no published terms, SLA or key, and it can change shape or be restricted without notice. Same risk class as `modules/public_roster_percentages.py`. Mitigations: server-side only, heavy caching (a handful of requests per minute cluster-wide regardless of users), no credentials or user data sent, strict parsing that skips a malformed event, and fail-open to the previous wall-clock behaviour. If ESPN blocks us nothing breaks; the display falls back to the estimate.

## Verified

Unit and golden tests (`tests/test_live_scoreboard.py`) with fixture payloads: clock points, halftime, overtime, final, bye, exited/injured, real vs wall-clock, feed. The public endpoints were read-only fetched on 2026-11-19 (HOU-IND Q2 6:32 live) to confirm payload shape.
