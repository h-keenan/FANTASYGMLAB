# League import and sync: error-path audit (2026-11-19)

Scope: every failure mode between a provider call (Sleeper, ESPN, Fleaflicker, MFL) and what a user sees on web (`web-next/`) and the app (`mobile/`). Judged from code paths; no live provider calls. Providers found in code: Sleeper (username import, league id), ESPN (`modules/espn_leagues.py`, public or cookie login), Fleaflicker (`modules/fleaflicker_leagues.py`), MFL (`modules/mfl_leagues.py`). Yahoo and others are not supported.

## Top findings

1. **A Sleeper outage read as "you have no league".** `get_rosters` and `get_user_id` swallowed every failure into `[]` / `None`. `_resolve_my_roster` then returned `not_a_member_of_league` / `sleeper_user_not_found`, and the Dashboard told a user with a healthy league to "Connect a league".
2. **A failed username lookup was cached for the life of the process.** `get_user_id` was an `lru_cache`, so one Sleeper blip meant "user not found" until restart. Same for `get_league_drafts`, `get_draft`, `get_draft_picks` (empty list frozen).
3. **HTTP 429 from Sleeper on the username lookup read as "no account matched that username"** (only 5xx counted as a transport error). A non-object body there did too.
4. **One season failing hid behind the other**: `year_ok` masked a 5xx on the second season, so an empty first season plus a failed second said "no leagues found".
5. **Stale data was served with an age the clients never read.** The API adds `sleeper_data_as_of` when a 429 or timeout fell back to last-known data, but no web or app code consumed it, so stale data looked fresh.
6. **Imported-platform failed refresh = "league not found".** `SnapshotCache.get` and ESPN's snapshot getter returned `None` on any refresh error even with a good snapshot in memory. Fleaflicker and ESPN also folded 429 into "unavailable".
7. **Save during an outage said "league not found"** (`POST /v1/leagues/save`).

## Mode x layer table

Legend: current behaviour is before this change. Fix column names the change (flag in brackets).

| Mode | Backend (before) | Web (before) | App (before) | Fix |
|---|---|---|---|---|
| Sleeper down / 5xx / timeout, username lookup | `unavailable` status with message | Network error card with retry (`describeSleeperConnectError`) | Same | Already good; tests added |
| Sleeper 429, username lookup | Fell through to `user_not_found` | "We couldn't find a Sleeper user named ..." (wrong) | Same | New `rate_limited` status and message; clients show a rate-limit card with retry |
| Malformed JSON / wrong shape, username lookup | List body read as `user_not_found` | Wrong "not found" | Wrong | Treated as `unavailable` |
| Invalid username | `user_not_found` | Specific guidance + sample league | Same | Unchanged; tests |
| User with zero leagues | `no_leagues` | Specific guidance | Same | Unchanged; tests |
| One season fails, other answers | `ok` with partial list, or `no_leagues` if other empty | Complete-looking list, or "no leagues" | Same | `partial` flag and `partial_message`; empty+failed is `unavailable`. Clients show the partial note |
| League id unknown (`null` body / 404) | `get_league` returned `{}` -> 404 "League not found." | ErrorState | ErrorState | `LeagueNotFoundError`; same 404 body plus `reason` |
| Sleeper down, league open (rosters/league) | Empty -> "not a member" / "League not found" | "Connect a league" next action or 404 card | Same | `ProviderError` -> 503 / 429 / 502 with `reason`, `retryable`, `Retry-After` [`DYNASTYGM_PROVIDER_TYPED_ERRORS_V1`]; shared ErrorState with retry |
| Sleeper down, save league | `league_not_found` | "didn't load just now" | "isn't on Sleeper" | Reason `provider_unavailable` / `provider_rate_limited` with message; copy on both clients |
| Empty league (no rosters, pre-draft) | `[]`; Dashboard `empty_roster` next action | Draft center action | Same | Unchanged; distinguished from outage; tests |
| Partial rosters: null players, null/odd entries | Possible crash on non-dict entry | Possible blank | Same | `sanitize_rosters` [`DYNASTYGM_ROSTER_PAYLOAD_SANITIZE_V1`] |
| Orphan team (no `owner_id`) | Kept, matches nobody | Shown | Shown | Kept deliberately; pinned by test |
| Unknown / retired player ids | Pass through to value engines, which skip unknown ids | Row without value | Same | Unchanged; pinned by test (no drop) |
| Format change mid-season | League payload read live (30s bucket) | Reflects change | Same | Unchanged; pinned by test |
| Half-completed sync (some reads fail) | Failures cached (lru) for drafts / user id | Stuck empty | Stuck empty | Failures never cached [`DYNASTYGM_PROVIDER_TYPED_ERRORS_V1`] |
| Stale cache after failed refresh (Sleeper) | `sleeper_data_as_of` added, unused | Looked fresh | Looked fresh | Dashboard and My Team show an age label through shared `FreshnessLabel` |
| Stale cache after failed refresh (ESPN / Fleaflicker / MFL) | `None` -> "league not found" | 404 card | Same | Serve last snapshot with age note on transient failures only; never for private or missing [`DYNASTYGM_STALE_SNAPSHOT_ON_FAILED_REFRESH_V1`] |
| Imported platform rate limit | Fleaflicker, ESPN: "unavailable"; MFL had its own | Generic | Generic | `fleaflicker_rate_limited`, `espn_rate_limited` with messages |
| Imported platform private / not found / no teams / mapping too low | Typed `ExternalLeagueError` reasons | Specific messages | Same | Unchanged; tests |

## Flags (registered in `modules/experimental_graduation.py`)

| Flag | Default | Owner | Kill switch off means |
|---|---|---|---|
| `DYNASTYGM_PROVIDER_TYPED_ERRORS_V1` | on | coridian_ | Legacy swallow-to-empty and failures cached |
| `DYNASTYGM_ROSTER_PAYLOAD_SANITIZE_V1` | on | coridian_ | Roster payload passed through untouched |
| `DYNASTYGM_STALE_SNAPSHOT_ON_FAILED_REFRESH_V1` | on | Zach | Failed refresh returns `None` |

## Not fixed

- Retry policy (`SLEEPER_REQUEST_MAX_RETRIES`) is unchanged: two short retries on 429/5xx.
- Stale labels now also show on Waivers, Trade Hub, Matchup and Games (season sim and Pick'em), web and app. The standalone Playoff Odds panels (web `PlayoffOddsSection` on League Rankings, app `PlayoffOddsPanel`) are labeled the same way from `sleeper_data_as_of`, which `/playoff-odds` already returns via `_with_sleeper_as_of` (no backend change; the GM Plan page only embeds odds and is not a standalone panel). Still unlabeled: live-activity, and POST routes (what-if, pick, trade-odds-effect), which are not page loads. Live-activity has no in-app screen: `/live-activity` feeds only the iOS ActivityKit/WidgetKit surface (`liveActivity.ts`), which ships dark and would need a native Swift change to show a staleness line (the snapshot already carries `sleeper_data_as_of`, so a native label can read it). Not done here; there is no JS surface to label.
