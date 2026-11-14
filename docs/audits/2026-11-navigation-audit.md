# Navigation and tappable-insight audit (2026-11)

Trigger (coridian_): "navigation is terrible; there are still info modules, like the one saying
you're the second youngest roster, that are completely untappable."
Scope: web (`web-next/`) and the app (`mobile/`), kept in parity. PR #1869 (More -> Fantasy Sim did
nothing: a pop-up close walked history back over the link navigation) is separate and not repeated here.

## 1. The principle and the mechanism

Every fact the app states about the user's league, team or players must open the page or sheet that
explains or acts on it. The rule is enforced by one central map, not per card:

- `lib/insightLinks.ts` (byte-identical twin, web + app): `InsightKey` -> `{ page, metric?, section?, label }`.
  Adding a stat means adding a key here first, so "where does it go" is always decided.
- Web adapter `lib/insightHref.ts` (key -> URL with league query and `#anchor`); app adapter
  `lib/insightNav.ts` (key -> screen + params, `openInsight(navigate, key, ...)`).
- Web shared component `components/ui/InsightLink.tsx`: a real `<a>` (so link semantics, middle-click, focus ring),
  glass look untouched, corner chevron, pressed state, accessible name "Avg Age, 26.1, League avg 25.2, open the
  Roster Age rankings". `StatStrip` takes `league` and an `insight` per item, so any strip becomes tappable by data.
- App: `DashboardStatRow` / `MetricCard` already had `onPress` + the chevron; they now receive it from `openInsight`.
- Destination anchors: League Rankings gained a **Roster Age** board (youngest = #1, matching the app's Teams `age`
  metric) and stable anchors `#your-standing`, `#board-<metric>`, `#playoff-odds`.

## 2. Findings: untappable facts (all fixed unless noted)

| Where (web / app) | Fact | Was | Now |
|---|---|---|---|
| Dashboard "My Team" strip (web, `DashboardContent`) / `DashboardTeamStats` (app) | Power, Franchise, Starter, Bench rank, **Avg Age** ("League avg 26.1"), Injured starters | plain tiles (app: only Power/Franchise tappable) | each opens its rank board / Alerts |
| My Team "Team Snapshot" (web `MyTeamContent`) / `TeamSnapshot` (app `MyTeamScreen`) | Record, Power, Franchise, Starter, Bench, Avg Age | plain tiles | each opens the matching board / standing |
| Dashboard sample strip (app `DashboardStatStrip`) | Record, Avg Age | not tappable | tappable |
| `TeamStatusHero` position chips (web + app) | "RB: Needs help" etc. | plain chips (only the "Improve RB first" line linked) | each chip opens Team Analysis on My Team |
| `LeaguePulseCard` (web) | Hot/Cold streak, most active manager | only a 16px "›" was a link | whole card is the link (app card already was) |
| Draft Center posture tiles (web + app) | Draft Capital rank, Future Capital rank, Strategy | plain tiles | open Draft Capital board / GM Plan |
| League Rankings | no age board existed, so "Avg Age" had no destination on web | n/a | added Roster Age board |

Not changed, with reason (see section 5): Guillotine survival strip, Matchup value/margin strip, Waivers header
stats, Trade Hub "hold" card, Portfolio exposure strip.

## 3. Entry-point map

Web phone shell (`lib/shellNav.ts`, `AppShellBar`; on for founder by default, `NEXT_PUBLIC_BOTTOM_NAV`):

- In a league: tabs Today / Team / Trades / League / More. Segment -> lit tab: dashboard, alerts -> Today;
  my-team, matchup, players, waivers, gm-plan, fantasy-sim, draft-center, live-draft, player-compare,
  college-scouting -> Team; trade-hub/finder/analyzer/offer/history -> Trades; league-rankings, league-recaps,
  games, commissioner -> League; anything else lights More.
- More sheet (every nav page, grouped League / GM tools / General / Account, from `navCatalog.ts`):
  Today, Alerts, My Team, Matchup, Waivers, League Rankings, Players | Trade Hub, GM Plan, Draft Center, Live Draft,
  League Recaps, Games, Commissioner | Home, Portfolio, **Fantasy Sim (`/gm-game`)**, News, Community | Pro, Account.
- Outside a league: Home / Portfolio / Fantasy Sim / News / More.
- Desktop: `DesktopSidebar` and the GM orb (phone, shell off) render the same destinations; the orb search also
  finds "Page > Tab" rows (Trade Hub > History, Draft Center > Scouting, League Rankings > Playoff Odds,
  GM Plan > Season Outlook).
- Header: standard `ShellHeader` back (named parent), title, league chip, search, alerts bell.
- In-page links: `NextSteps`, `TradesTabBar`, `ViewAllLink`, TeamStatusHero rows, and now insight links.

App: stack navigator (`RootNavigator`); GM orb + `MoreScreen`; native header back on every screen; `orbTabs.ts`
maps the same catalog to routes.

Fantasy Sim, two different things that share a word:

- **Fantasy Sim game** `/gm-game` (app `GmGame`): sandbox draft-and-play game, not league-scoped. Entry: More >
  Fantasy Sim, bottom tab outside a league, `FantasySimContent`'s "Play the sim game" button.
- **Season Outlook** `/fantasy-sim/[leagueId]` (app `FantasySim`): the real league's rest-of-season simulation.
  Entry: GM Plan > Season Outlook (tab and card), Games > Season Outlook, orb search. Back target is GM Plan.
  It is deliberately not a menu row (pinned by `navDestinations.test.ts`).

## 4. Dead ends found and fixed

1. **Fantasy Sim hub/setup/error had no way out on a phone (web).** `pathOwnsPhoneChrome("/gm-game")` hides the
   global header, GM orb and shell bar for the whole path, but only the in-game screen draws its own header and orb.
   The hub ("Your games"), New game setup and error screens therefore had no navigation at all (affects every phone
   user, shell flag or not). Fix: `SimExitBar` (phone-only Back + Home) on every non-game view.
2. **Trade History dropped the league (web).** It is a non-league route, so the bar swapped to the outside-league
   tabs, the lit tab fell to More and Back said "Home" instead of Trade Hub. Fix: `TradesTabBar` and the orb tab
   link pass `?league=&name=`; `shellLeagueContext` reads it for the bar and header; `trade-history` gets parent
   `trade-hub`. Opened without a league (direct link) it behaves as before.
3. **Roster Age had no destination on web** (no board). Added.
4. Stats that were tappable only on one platform (app: Starter, Bench, Age, Record, Injuries on Dashboard/My Team;
   web: all of them) are now tappable on both, from the same map.

## 5. Left (not done in this PR)

- Guillotine survival strip (web `GuillotineCard`): items are index-mapped glyphs, so a per-item insight key would be
  wrong; needs its own keys once the card's metrics are named. Key `survival` is reserved in the map.
- Matchup "Your value / Proj margin" strip, Waivers header stats, Portfolio exposure strip, Trade Hub "hold" card
  (hold reasons are explanations already, destination to be decided by product).
- League Rankings "Your standing" mini-tiles (same-page anchors to boards) and the app's `TeamSnapshotRow` (sample
  dashboard only) still plain.
- Account-wide pages opened from a league (News, Community, Portfolio, Trade History without `?league=`) still switch
  the bar to the outside-league tabs; Back says Home. Intentional for now ("General"), but a league-aware Back is the
  general fix if product wants it.
- `Link onClick={onClose}` in the More sheet is the pattern behind #1869; any other pop-up whose rows are links should
  rely on the overlay-history fix, not on their own close handler.
- Naming: "Fantasy Sim" (game) vs "Season Outlook" (league simulation, route `/fantasy-sim`) is easy to confuse.
- Visual check of the new chevrons on a phone was not done (no screenshots); verification is unit tests plus tsc.

## 6. Tests

Web: `lib/insightLinks.test.ts` (every key resolves to a real league page and board; anchors; aria text),
`components/ui/InsightLink.test.tsx` (link, chevron, StatStrip with/without league), `shellNav.test.ts`
(league context, trade-history parent), plus assertions in `LeagueRankingsContent`, `MyTeamContent`,
`DraftCenterContent`, `LeaguePulseCard`, `TeamStatusHero`, `SimGameContent` tests. App: `src/lib/insightNav.test.ts`.
`node scripts/check_lib_twins.mjs` passes with `insightLinks.ts` registered as IDENTICAL.
