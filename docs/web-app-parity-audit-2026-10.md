# Web vs app parity audit (2026-10-24)

Trigger: coridian_, after the liquid-glass pass (#1499): the app's Portfolio
"does not look like the website; it's missing player profile pictures and
stuff like that." Ask: audit website vs app module by module and make the app
look like the website.

Standing rules applied: one shared module with variants (no per-page
duplicates), web/app parity, no fabricated data, keep module organization.

## Method and confidence

For each main screen I compared the web component (`web-next/src/components/*Content.tsx`,
plus the shared modules it imports) against the mobile screen
(`mobile/src/screens/*Screen.tsx`) by shared-module imports, the data fields
each one reads, and spot reads of the render code. This is a structural audit,
not a pixel audit: **nothing was compared visually side by side**, and I did
not run either app. Rows marked "verify" need a screenshot pass or a check
that the API already returns the field. Mobile renders are native, so exact
spacing/glass depth cannot be derived from code alone.

Cross-cutting finding (the root cause of "does not look like the website"):
the app already has the shared atoms (`PlayerAvatar`, `TeamAvatar`,
`PositionBadge`, `CompactPlayerModule`, `PlayerIdentityRow`, `ToneBadge`,
`SectionHeading`), but several screens render **text-only rows or plain
`InsightRow`s** where the web renders those atoms. Portfolio was the clearest
case: web `BriefingItemPlayers` chips (headshot + position + tier ring) per
signal, `TeamAvatar` on each league card, and a per-card "Open Dashboard"
link, none of which the app had. The same "briefing item rendered as text
only" pattern exists anywhere a `DashboardItem`/`BriefingItem` is shown.

Size: S = under half a day, M = about a day, L = multi-day or needs API work.

## Per-screen table

### Portfolio (fixed in this PR)

| Web module | App status | Gap | Shared fix | Size |
|---|---|---|---|---|
| `TeamAvatar` on each league card | missing | no team logo | mobile `TeamAvatar` (`team_avatar_url` added to the type) | S, done |
| `BriefingItemPlayers` per signal (headshot, position badge, tier ring, injury, trade package) | missing (`InsightRow` text) | no player identities | new mobile `BriefingItemPlayers` (on `CompactPlayerModule` + `TradeAssetRow`) | M, done |
| Signal row: category `ToneBadge` + headline + reason with dedupe | different (icon + label) | no reason dedupe | `lib/portfolioSignals.ts` mirrors web rules | S, done |
| Header "Your leagues" + subtitle + "+ Add a league" | different (info note) | missing title/link | `SectionHeading` + link to Home | S, done |
| Card title "Team — League", metadata "5-2 · Roster Power #7", gold top-3 rank pill | different (separate lines, boxed pill) | layout/wording | same | S, done |
| "Open {league} Dashboard" link, "Open this league to see your Next Move" fallback | missing | no explicit CTA | same | S, done |
| Drafting note with "Watch live draft" link | partly (text only) | no link | link to `LiveDraft` | S, done |
| ESPN note with "Open My Team" link | partly (text only) | no link | not done, see ranked list | S |
| Exposure tab | present | verify parity (web `PortfolioExposureView` vs app `PortfolioExposurePanel`) | none known | S verify |

### Dashboard / landing

| Web module | App status | Gap | Shared fix | Size |
|---|---|---|---|---|
| `TodayModule` / `GamePlanCard` (top priority with trade give/get, player chips) | `TodayHero` + `DashboardInsightRow` | mentioned_players beyond the route player not shown (web shows all) | route Dashboard rows through the new `BriefingItemPlayers` | M |
| `WatchListCard` | `WatchlistAlertsSection` | present, tags match | none | - |
| `LeaguePulseCard` | local `LeaguePulseSection` (lighter adaptation, inside DashboardScreen) | per-screen duplicate, fewer tiles | promote to a shared component with web's tile set | M |
| `StatStrip` (Record/Power/Franchise/Avg Age, Starter/Bench/Injuries) | `DashboardStatRow` | present | none | - |
| `StartHereCard`, `GuillotineCard`, Guess cards | present | none | none | - |
| Landing page (`LandingShowcase`) | n/a (app has Home/leagues) | web-only marketing, justified | none | - |

### GM Plan

| Web module | App status | Gap | Shared fix | Size |
|---|---|---|---|---|
| `PlayerRow` + `OvrGauge` + `ValueStat` | `PlayerIdentityRow` + `OverallRatingBadge` | present; gauge style differs (`ValueRing` on web, `CircularProgressRing` on app) | one ring spec shared across `OvrGauge`/`CircularProgressRing` | M |
| `GmPlanSections`, `PillRow` tabs | `SegmentedTabBar` | present | none | - |
| Trade exchange (`TradeAssetExchange`) | `TradeAssetRow` (now a shared component, was exported from DashboardScreen) | OK | none | - |

### Trades (Hub / Finder / Analyzer / History)

| Web module | App status | Gap | Shared fix | Size |
|---|---|---|---|---|
| `TradeIdeaCardView` (+ `ShareTradeButton`, lean bar) | `TradeIdeaCard` | present; verify lean bar and rings | none known | S verify |
| `TradeAssetExchange` in Hub/Finder | local `ExchangeAssetList` in `TradeFinderScreen`/`TradeHubScreen` | known per-screen duplicates (listed in `ui-module-inventory.md`) | migrate to `TradeAssetRow` | M |
| `TradesTabBar` | `TradesScreen` (145 lines, `SegmentedTabBar`) | present | none | - |

### Matchup

| Web module | App status | Gap | Shared fix | Size |
|---|---|---|---|---|
| `MatchupContent` rows (avatar, position, injury) + `MatchupPlanner` | `MatchupScreen` + `MatchupPlanner` | present; web rows themselves are not yet on `PlayerRow` | web side is the follow-up | M |
| `StatStrip` | `DashboardStatRow` | present | none | - |

### Waivers

| Web module | App status | Gap | Shared fix | Size |
|---|---|---|---|---|
| `PlayerIdentity` rows with tier avatar, `ConfidenceMeter` | `PlayerIdentityRow`, `WaiverRecommendationCard` | present | none | - |
| `HighlightTarget` deep-link scroll | not checked | verify `?playerId=` deep link on app | - | S verify |

### Players / Player profile

| Web module | App status | Gap | Shared fix | Size |
|---|---|---|---|---|
| `PlayersContent` list with `PlayerRow` | `PlayersScreen` with `PlayerIdentityRow` | present | none | - |
| `PlayerHeroHeader` (112px avatar) | `PlayerHero` | present | none | - |
| `PlayerQuickView` (tap any identity) | no equivalent; taps navigate to `PlayerDetail` | web opens a quick sheet, app a full screen | decision needed, not a bug | L |
| Career / Schedule / Trends tabs | inside the 2411-line `PlayerDetailScreen` | verify tab parity | - | S verify |

### Teams / Team roster

| Web module | App status | Gap | Shared fix | Size |
|---|---|---|---|---|
| `LeagueRankingsContent` rows with `TeamAvatar`, archetype `ToneBadge` | `TeamsScreen` with `TeamAvatar` | present; verify badges | - | S verify |
| `ManagerProfileSheet` | `ManagerProfileModal` | present | none | - |
| Roster rows (`MyTeamSections`: `PlayerRow`, `OvrGauge`) | `TeamRosterScreen` with `PlayerIdentityRow` | present | none | - |

### News

| Web module | App status | Gap | Shared fix | Size |
|---|---|---|---|---|
| Matched-player identity on each story (`PlayerAvatar` 28px + `PositionBadge`, tap opens quick view) | **missing**: `NewsScreen` imports no avatar/badge component, and the app's `NewsItem` type has no `matched_player_*` fields | stories are text only | add the fields to the type (verify `/v1/news` already returns them; web reads them), render `CompactPlayerModule` | M |

### More / Account

| Web module | App status | Gap | Shared fix | Size |
|---|---|---|---|---|
| Account sections as glass cards (Identity, Billing, Preferences, Actions, Danger) | `MoreScreen` (772 lines) grouped by `SectionHeading` | structure differs (web cards vs app grouped list); app also carries settings web puts elsewhere | verify visually; likely fine | S verify |
| `ReferralCard`, `Toggle`, `Button` | present | none | none | - |

### Games

| Web module | App status | Gap | Shared fix | Size |
|---|---|---|---|---|
| `GamesContent` (`PillRow`, `PlayerRow`, `TeamAvatar`, `RankingRow`, `ToneBadge`) | `GamesScreen` (`SegmentedTabBar`, `PlayerIdentityRow`, `TeamAvatar`, `ToneBadge`) | present | none | - |
| Season simulator title odds | shipped both (#1501) | none | none | - |

## Ranked fix order (impact on "looks like the website", then size)

1. News: matched-player avatar + position badge on every story (M; confirm API field first).
2. Dashboard Top Priority / Watch rows: show every mentioned player via `BriefingItemPlayers`, not just the route player (M).
3. Portfolio ESPN note "Open My Team" link and ESPN leagues rows (S; left out of this PR, text note only).
4. Alerts screen: same `DashboardItem`/`NewsItem` identity treatment as News (`AlertsScreen` uses `PlayerIdentityRow` for matched players already; verify) (S verify).
5. League Pulse: promote the local `LeaguePulseSection` to a shared component with the web tile set (M).
6. Trade Hub/Finder: migrate local `ExchangeAssetList`/`CategoryBadge`/`ImpactBadge` to `TradeAssetRow` / `ToneBadge` (M).
7. OVR ring: one spec across web `OvrGauge`/`ValueRing` and app `CircularProgressRing`/`OverallRatingBadge` (M).
8. Player tap behavior: DONE 2026-10-24 (coridian_ decision). The app now opens a shared PlayerQuickViewSheet; its Full profile action opens PlayerDetail.
9. Visual pass of More vs Account card structure and Exposure tab (S each).
10. Waivers deep-link highlight and Player tabs parity check (S verify).

## What this PR changed

- Mobile Portfolio now follows the web layout and content (see the Portfolio table).
- New shared pieces: `components/BriefingItemPlayers.tsx` (reusable for rank 2), `lib/portfolioSignals.ts` (+ test),
  and `components/TradeAssetRow.tsx` (extracted from `DashboardScreen`; `GmPlanScreen` now imports it from there).
- API types: `PortfolioLeague.team_avatar_url`, `DashboardItem.mentioned_players`, `route_player_injury_status`.
- Headshots use the existing `PlayerAvatar` (sleepercdn.com), team logos the existing `TeamAvatar`. No new hosts.

## Follow-up 2026-10-24 (gaps 7, 9, 10)

- 7 DONE: new shared `OvrGauge` (mobile) mirrors web `OvrGauge`/`ValueRing` sizes and tint
  (`overallRatingColor` = web `overallRatingTint`, theme danger/premium/success, dark and light).
  `OverallRatingBadge` (label "OVR") now renders it; PlayerHero and Compare use it; share cards and
  Player Detail use the same tint. MKT/DUR sub-rating pills stay pills (tint now matches).
- 9 DONE: More gains the web Identity card (email, Sleeper username, plan from `/v1/me`). Exposure
  panel already matched web structure; added the expand chevron on the count pill. Left: web wraps
  Preferences in a card (app uses option cards), and the app has no valuation-lens param for Exposure.
- 10: Player Detail tab set matches web (Stats/Trends/Schedule/Career/Model, Awards+Bio below).
  Waivers `?playerId=` highlight is NOT implemented on the app: Waivers has no `playerId` route
  param and no in-app screen produces the link (Dashboard rows open the player sheet). Left.
