# Client data races audit, 2026-11

Follow-up to `2026-11-auth-offline-error-paths.md`, which sampled "stale response overwrites newer state". This audit covers web (`web-next/src`) and app (`mobile/src`) end to end.

## Shared layer

There is no single fetch hook. Web pages use `useEffect` + `api` (`lib/api.ts`, with `lib/requestCache.ts` coalescing GETs keyed by user + path; the path carries the league). The app mixes React Query (keys from `lib/queryKeys.ts`, all rooted at user + league) with `useEffect`/`useFocusEffect` loads. Every request already carries league in its key, so wrong-league data comes from response application, not from cache keys.

Fix: `lib/latestRequest.ts` and `lib/useLatestGate.ts` (byte-identical twins).

- `createLatestGate()`: `begin()` returns an `isCurrent()` ticket and retires older ones; `cancel()` retires all. Requests are not aborted (shared in-flight reads in `requestCache` stay valid); only stale results are ignored.
- `createSingleFlight()`: pending guard for mutation taps.
- Kill switch: `RACE_GUARDS_ENABLED` in `latestRequest.ts`. `false` restores previous behaviour exactly (every ticket current, no tap dropped).
- Purchase, billing portal and delete-account calls are untouched. They only ever get a UI disable guard; they are never aborted, retried or wrapped.

League switch note: web remounts a page when the `[leagueId]` segment changes, and the app's `switchLeagueKeepingScreen` uses `StackActions.replace` (new instance) except when it pops to an existing Dashboard (React Query keyed). So in-place league change reaching a `useState` screen is rare; the primary exposures are lens/stance/player/selection changes inside one league, and shared hooks.

## Findings

Class: A stale response, B data kept after key change, C cache key, D double submit, E optimistic without rollback.

| Class | Screen | Platform | Current behaviour | Fix |
|---|---|---|---|---|
| A | Trade Offer (`TradeOfferContent`, `TradeOfferScreen`) | web, app | `load` on playerId/lens change applies whichever answer lands last | gate ticket; test resolves newer first |
| A | Live matchup hook (`useLiveMatchup`) | web | lens change: old request still in flight, `load` early-returns, old-lens payload applied, no refetch | per-request ticket, `inFlight` reset on effect restart |
| A | Trade Analyzer | web, app | in-flight answer lands after assets/partner (app also stance/lens) edited | gate cancelled on selection change |
| A | Multi-team Analyzer | web, app | late answer restores verdict for an edited trade | gate cancelled in `invalidate()` |
| A | Trade Hub ideas + All Trades (paging) | app | lens/stance/ad-unlock reload or paging append races | two gates; "load more" blocked while first page loads |
| A | Trade Finder search | app | answer for old package lands after toggle | gate cancelled on toggle, scope, league |
| A | GM Plan load | app | slow earlier load overwrites plan, roster, targets | gate on load |
| A | News (player filter) | app | older player's items overwrite newer | gate on load |
| B | News roster digest | web | previous league's alerts stay up | cleared in effect cleanup |
| E | Team stance (GM Plan / stance context) | web, app | optimistic stance never reverted on failed save | revert unless user picked newer |
| E | Commissioner draft-order rule | web, app | failed save left wrong rule shown (5 min cached on app) | revert on failure |
| D/E | Sim auto-manage toggle | web | overlapping taps, rollbacks restore different "previous" | single-flight |
| D | Home connect selected leagues | app | `addBusy` clears mid-loop; second tap re-saves | single-flight around whole flow |
| D | ESPN league import save | app | relies on rendered disable only | single-flight |
| D | Share trade to community | app | no re-entry guard | single-flight |
| D/E | College prospect watchlist | app | repeated tap sends same write twice, rollback wrong | per-prospect busy set |

Checked and fine: web `useSavedLeagues`, `useDefaultLeague`, `useTeamStatusData`, `leaguePlayerSearch` (key has league, lens, term), `requestCache` (user + path keyed, generation cleared on writes), `ValuationLensContext` (per league), `PlayerNewsTab`, `MatchupPlanner`, `PlayerCompareContent`, `PlayerLeagueActions`, `AlertsDropdown` (keyed by league). App: all `useQuery` screens (keys include league, week, rule), `PlayersScreen`, `PlayerCompareScreen`, `PlayerDetailScreen`, `TradeOddsEffect`.

## Not fixed (documented)

- B on app stack screens (`WaiversScreen`, `DraftCenterScreen`, `PlayoffOddsPanel`, `TeamRosterScreen`, `TradeFinderScreen` roster, `TradeAnalyzerScreen` selections): no reset on in-place league change. Not reachable today because league switch uses `replace`; revisit if any switch path becomes `setParams`.
- `DashboardAlerts` (web) `load()` unguarded; page remounts per league, so impact is nil.
- `ShareToCommunityToggle` (app): switching off while a share is in flight can leave the trade public; fixed in the account-isolation follow-up: `lib/shareToggleFlow.ts` (web and app twin) serializes share and off, so an off during an in-flight share waits for the id and then removes the trade. Kill switch `SHARE_OFF_WINS_ENABLED`.
- C (low): `fd:trade-outcome-prompt-dismissed` (web sessionStorage), `fgl:dashboard-seen-recs:<league>` and `fgl:trade-hub-seen:<league>` (app AsyncStorage) are not user-keyed; a second account on the same device inherits seen/dismissed state. No data exposure.
- Checkout, billing portal, delete-account: not changed. Any guard there is a UI disable only.
