# Silent failures audit (2026-11-19)

Scope: places where a failure renders as a blank module, an empty list that reads as "nothing here", or no log at all. Starts from section 6 of `2026-11-band-aid-audit.md`. Method: an AST scan of `services/` and `modules/` for broad `except` handlers whose body has no log/raise (724 found), a grep of web-next and mobile for swallowed promise rejections (64 web, 101 mobile, excluding tests), and a read of the user-facing ones.

## What already exists (reused, not duplicated)

- Web: `ErrorState` (`web-next/src/components/ErrorState.tsx`: full, `bare`, `compact`, `onRetry`) and `EmptyState`; `SlowLoadNote` already gives every page skeleton a slow-load message and a retry (so "spinner with no timeout" is covered at page level). `errorStateGuard.test.ts` bans hand-rolled `<p role="alert">Could not load` blocks.
- App: `ErrorState` (title, message, `onRetry`, `compact`), `EmptyState`, `SlowLoadNote`. No new components were needed on either platform; the findings are call sites that did not use them.

## Ranked findings (user impact)

| # | Where | What the user sees | Status |
|---|---|---|---|
| 1 | `modules/sleeper.py` `_request_json` plus the cached league getters (`_get_users_cached`, `_get_rosters_cached`, `_get_league_cached`, `get_league_drafts`, `get_draft`, `get_matchups`) | The module had no logger at all. A Sleeper timeout, 5xx, 404 or non-JSON body became `[]`/`{}` and was cached for the 30s bucket, so a league looks empty (no rosters, no matchup) with nothing in the logs | Fixed: throttled warning with label, coarse reason, league id (no URL, no payload) |
| 2 | `GET /v1/players/{id}/weekly-stats` (`services/mobile_api_service.py`) | An empty season aggregate (load failure) returned `weeks: []`, rendered as "no games" | Fixed: body carries `stats_available`, a warning is logged; existing contract kept |
| 3 | `SimRealHistory` (web + app) | "Could not load past seasons" was a bare line with no retry; the game-log request failing was swallowed to `[]` and read as "No NFL seasons on file" | Fixed: shared ErrorState with Try again; failed game log shows a compact error |
| 4 | `PortfolioFreeStanding` (web + app) | Dashboard fetch failure: component returned `null`, the Free standing card silently vanished | Fixed: compact ErrorState with Try again |
| 5 | `SimGameTrades.tsx:312, 322` and mobile twin | Failed roster load leaves the trade builder empty with no message (from the band-aid audit) | Open |
| 6 | `SavedLeaguesSection.tsx:31` | Supabase read failure hides the whole saved-leagues section; the user cannot tell "none" from "failed" | Open |
| 7 | `ManagerProfileSheet.tsx:163`, `ManagerTendenciesCard.tsx:35`, `PlayerValueHistory.tsx:34`, `ValueSignalsCard.tsx:34`, `GuillotineCard.tsx:62` | Secondary card returns `null` on failure; by design for optional enrichment, but there is no signal to the team | Open (log via error reporter) |
| 8 | `ShareToCommunityToggle.tsx:82`, `TradeHistory` delete/report (web `.catch(() => {})`, app twins) | Failed delete or report looks like success | Open |
| 9 | `services/mobile_api_service.py` (102 silent broad excepts), `modules/rankings.py` (44), `modules/push_triggers.py` (41), `modules/trade_ideas.py` (22), `modules/prepared_player_frame.py` (14) | Mostly best-effort telemetry and cache reads; the risky ones are where the fallback is an empty payload the client renders as real data. Auth and billing files are listed only: `modules/auth_supabase.py` (18), `session_integrity.py` (11), `free_tier_ledger.py` (9) | Open; trade engine and valuation files are out of scope here |
| 10 | Pref stores (`DisplayPreferencesContext`, theme/density/onboarding contexts) | Storage failures swallowed | Fine: preferences degrade to defaults |

## Recommended follow-ups

1. Add the `bestEffort(label, fn)` helper from the band-aid audit so every swallowed secondary read reports a coarse label to the error reporter (items 5-8).
2. Make the remaining Sleeper empty-on-failure getters (`modules/sleeper.py` other than those fixed) return an explicit unavailable marker the endpoint can pass to the client, and stop caching it.
3. Extend `errorStateGuard.test.ts` to flag `return null` directly after a `failed` state.

## Tests added

- `tests/test_silent_failures_logging.py`: failures are logged with context and without the URL/secret, throttled, and the weekly-stats body says `stats_available: false`.
- `web-next/src/components/SilentFailures.test.tsx`: error + retry, failed game log is not "no games", genuine empty still says so, Portfolio retry.
- `mobile/src/lib/silentFailures.test.ts`: source-level guard (the app has no RN render harness).
