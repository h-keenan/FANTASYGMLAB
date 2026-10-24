# UI organizational audit (information architecture), 2026-10-23

Scope: `web-next/` and `mobile/`. This is IA, not pixel polish. Sources read:
`docs/ui-module-inventory.md`, `web-next/src/lib/navDestinations.ts`,
`DesktopSidebar`, `Header`, `GmOrb` (web and mobile), mobile
`RootNavigator.tsx` and `MoreScreen.tsx`, and every route in
`web-next/src/app` plus every screen in `mobile/src/screens`.

TLDR:
- Web and app are the same product with different nav trees. Names, grouping and
  even which pages exist differ (Teams, Playoff Odds and League Overview exist
  only on mobile; Community and Founder only on web).
- Five surfaces answer "what should I do now?" and overlap heavily.
- Mobile Home is a league list that leads to a second "home" (League Overview),
  which leads to a third (Dashboard). Web goes straight to Dashboard.

## 1. Sitemap, web vs app, with parity gaps

Web nav: left sidebar (desktop) or GM orb sheet (phone width), plus Header
(page title, search, alerts bell, league switcher, lens, Menu dropdown).
Mobile nav: native stack, no tab bar, floating GM orb sheet, header icons.

### League-scoped

| Feature | Web route (nav label) | Mobile screen (nav label) | Gap |
|---|---|---|---|
| League landing | `/dashboard` (Dashboard) is the landing | `LeagueDetail` (League Overview), then `Dashboard` | Mobile has an extra layer; web has none |
| Daily briefing | `/dashboard` (Dashboard) | `Dashboard` (orb said "Next Move", header said "Dashboard") | Name mismatch (fixed in this PR) |
| Alerts | `/alerts` (Alerts) plus header bell | `Alerts` | OK |
| My Team | `/my-team` | `MyTeam` | OK |
| Matchup | `/matchup` | `Matchup` | OK |
| Waivers | `/waivers` | `Waivers` | OK |
| Players / rankings | `/players` (+ `/players/[id]`) | `Players` (+ `PlayerDetail`) | OK; a mobile quick action calls it "Rankings" |
| Standings, power, playoff odds | `/league-rankings` (League Rankings) holds standings, playoff odds, franchise, draft capital, starter boards | `Teams` and `PlayoffOdds` as two orb entries | Same data: 1 page on web vs 2 entries on app; names differ |
| Team detail | sheet on League Rankings (ManagerProfileSheet) | `TeamRoster` | Different pattern |
| Trades | `/trade-hub`, `/trade-finder`, `/trade-analyzer` via `TradesTabBar` (one nav entry "Trade Hub") | `Trades` with tabs Trade Block / Search / Make a Trade (one entry "Trades") | Same idea, different names for entry and tabs |
| Trade history | `/trade-history` (General nav, plus link under tab bar) | `TradeHistory` (link in Trades header only, not in orb) | Web promotes it to nav; app buries it |
| GM Plan | `/gm-plan` (Team Situation and GM Targets folded in) | `GmPlan` plus separate orb entries `TeamStance` (Team Situation) and `GmTargets` | Web merged (Revision 20); app did not |
| Draft Center | `/draft-center` | `DraftCenter`, `PickDetail` | OK |
| Live Draft | `/live-draft` (GM Tools) | `LiveDraft`: was More only; orb entry added in this PR | Fixed |
| League recaps | `/league-recaps` (League Recaps) | `Recap` (was labeled "Recap") | Name mismatch (fixed in this PR) |
| Games (simulator, pick'em) | `/games` | `Games` | OK |
| Guess the Player leaderboard | `/guess-the-player-leaderboard`, link from Dashboard card | `GuessThePlayerLeaderboard`, More only | Web: no nav; app: More only |
| Player compare | `/player-compare` (no nav entry) | `PlayerCompare` (no nav entry) | Deep-link only on both |
| Pick detail | inline | `PickDetail` | Mobile-only drill-down |

### Account-scoped / general

| Feature | Web | Mobile | Gap |
|---|---|---|---|
| Home / league list | `/` is the logged-out landing; signed-in users auto-redirect to the league Dashboard (or `/portfolio` with several leagues) | `Home` league list is the signed-in root | Different first screen |
| Portfolio | `/portfolio` (General nav) | `Portfolio` (orb General) | OK |
| News | `/news` | `News` | OK |
| College scouting | `/college-scouting` (General nav) | `CollegeProspects` (More, "Scouting" section) | App buries it |
| Community trades | `/community` (General nav) | none | Web only |
| Premium | `/premium`, no nav entry (upsell cards, Account) | `Paywall` as orb "Premium" / "Manage subscription" | Web has no nav path to Premium |
| Account and settings | `/account` (Header Menu) | `More` (orb General, header icon) | Different names: Account vs More |
| How We Evaluate | `/methodology` (Header Menu) | `HowWeEvaluate` (More, About) | OK |
| Legal | `/legal/[key]` (Header Menu) | `LegalPage` (More) | OK |
| Connect league | `/connect-league` | inside `Home` | OK |
| Founder analytics | `/founder-analytics` (orb, founder only) | none | Intentional |
| Design reference | `/design` (not linked) | `Design` (More, developer) | Internal |

Largest structural parity gaps: (1) League Overview, Teams and Playoff Odds are
app-only while League Rankings is web-only. (2) Team Situation and GM Targets
merged into GM Plan on web, still standalone on app. (3) Community is web-only.
(4) Web has no Premium nav entry. (5) College Scouting and Trade History are
General nav on web, buried on app.

## 2. Duplicated or overlapping pages and features

1. **"What do I do now?" has five homes.** Web Dashboard has This week
   (up to 3 moves), Today (game plan card), Watchlist and Alerts, League
   Activity and Team Snapshot. GM Plan has a roadmap and trade opportunities.
   Alerts is a full page and a header bell. Matchup has Suggested Moves. Mobile
   adds League Overview with its own "Today's Game Plan" hero, Injury Concerns,
   Storylines and Waiver Suggestions. The same top recommendation can appear as
   a This week row, a Today card, a GM Plan area and the League Overview hero in
   one session. On web, "This week" and "Today" are two adjacent sections that
   say nearly the same thing at two levels of detail.
2. **Dashboard vs League Overview (mobile only).** Both are league landings.
   League Overview shows matchup, a hero "View Plan" button that opens
   Dashboard, a quick-actions grid (Matchup, Alerts, Waivers, Teams), my team
   strip, playoff odds strip and storylines. Dashboard has a different
   quick-actions grid (Trades, Rankings, Waivers, My Team or Draft Picks).
3. **Trade Hub vs Trade Finder vs Trade Analyzer vs Trade History.** Three
   routes behind one tab bar, and the first tab has the same name as the
   destination ("Trade Hub" tab inside "Trade Hub"). Trade History is a nav
   entry on web but a hidden header link on the app. Live Draft embeds a Trade
   Evaluator and Player Quick View has trade actions, so "analyze a trade" has
   four entry points. Web tabs say Hub / Finder / Analyzer; the app says Block /
   Search / Make a Trade for the same three things.
4. **My Team vs Portfolio vs Teams.** My Team is one roster. Portfolio is the
   same standing across all leagues. Teams (app) and League Rankings (web) are
   the league's other rosters. Dashboard's Team Snapshot (starter, bench,
   injuries) repeats My Team's snapshot.
5. **Waivers.** A full Waivers page, Waiver Suggestions on mobile League
   Overview, a WAIVER tag in Watchlist and Alerts, a waiver row in This week,
   and waiver items in GM Plan. One page, four teasers that are not labeled
   or linked consistently.
6. **Draft Center vs Live Draft.** Adjacent entries; one is picks, order and
   values, the other the real-time room. A new user cannot tell which to open.
   Both use the danger (red) glyph on web.
7. **Games, Playoff Odds, League Rankings.** Playoff odds live in League
   Rankings (web board), Games ("Playoff odds" section on both platforms), the
   app's Playoff Odds screen and a strip on League Overview. The Season
   Simulator "what if" is a fourth variant of the same simulation.
8. **League Activity / Recaps / News / Alerts.** The League Activity card on
   Dashboard (LeaguePulseCard), the League Recaps page and mobile Storylines are
   the same recap content at three sizes. News (NFL-wide) and Alerts (your
   roster) both carry player news.
9. **Team Situation / GM Targets / GM Plan.** Merged on web. On the app: three
   orb entries, plus a header icon to GM Targets and a More row for Team
   Situation, while GM Plan also contains a Team Situation section.
10. **Settings in several places.** Evaluation lens in the header, Experience
    and Density in More, Team Situation stance as a GM Plan section and a header
    stance button, league type control at the bottom of Dashboard.

## 3. Nav depth and discoverability

- **First thing a new user sees.** Web: landing, sign in, onboarding, then the
  league Dashboard (stat strip, This week, Today): one dominant action. App:
  onboarding, Home (league list with entitlement and News cards), tap a league,
  League Overview (matchup, hero, quick actions, strips), and the Dashboard
  briefing is a third tap.
- **More is a junk drawer.** Preferences, Team Situation, Trade History, Live
  Draft, Guess the Player leaderboard, College Prospects, notifications, About,
  Developer, Legal, Account. Real features hide among settings.
- **Reachable only by deep link or secondary path:** Player Compare (both),
  Trade Finder and Trade Analyzer (tab only, by design), GM Targets and Team
  Situation on web (redirects), Guess the Player leaderboard (card link on web,
  More on app), Trade History on app (Trades header icon), Premium on web
  (upsell cards only), Pick Detail (inside Draft Center), Live Draft on app
  (before this PR).
- **Naming inconsistencies for one thing:** Dashboard / Next Move / Game Plan /
  Today / Today's Game Plan; Trade Hub / Trades / Trade Block; Recap / League
  Recaps; League Rankings / Teams; Players / Rankings; Account / More;
  Alerts / Watchlist and Alerts; Home (league list on app) vs Home (landing on
  web). Landing copy already says "Game Plan, not the retired Next Move", yet the
  app orb said Next Move.
- **Order.** Web League group: Dashboard, Alerts, My Team, Matchup, Waivers,
  Players, League Rankings (7). App: League Overview, Dashboard, Alerts, My Team,
  Matchup, Waivers, Teams, Playoff Odds, Players (9). GM Tools: web 6 entries,
  app 7 (Trades, GM Targets, Team Situation, GM Plan, Draft Center, Recap,
  Games). Alerts sits above My Team because it is time sensitive, but Dashboard
  and Alerts are adjacent entries with overlapping intent.
- **Depth.** The orb is flat (good). Real depth costs: Trade History (2 taps),
  Scouting (More, 2 taps), Live Draft (More, 2 taps before this PR), Settings.
  The app orb is about 21 rows before General.
- **Web Header Menu** holds How We Evaluate, Account and legal; the same items
  live in More on the app. Fine, but Account is not in the sidebar.

## 4. Page-level hierarchy problems

Directive: one dominant module per page (UI_HIERARCHY_DIRECTIVE).

| Page | Problem | Dominant module should be |
|---|---|---|
| Web Dashboard | About 8 equally weighted blocks: stat strip, This week, Today, Watchlist, League Activity, two Guess the Player cards, Team Snapshot, league type control. Mini-games sit above Team Snapshot. | This week and Today merged into one hero |
| Mobile Dashboard | Today, More next moves, Quick Actions grid, League Activity, Team Snapshot, Watchlist and Alerts, plus a destination button per item | Today |
| Mobile League Overview | Matchup, Today's Game Plan hero, context row, quick actions, my team strip, playoff odds strip, injuries, storylines, waiver suggestions | Matchup or hero, not both |
| GM Plan (about 790 lines web, 840 app) | Team Situation, focus areas, Trade Opportunities (appears twice in app source), Protected Core, Watching; several "View all" links | Roadmap / top focus area |
| Trade Hub | Filters, hold card, idea list, tab bar and history link stacked above content | Top trade idea |
| Trade Analyzer (934 lines) | Exchange builder, verdict, ring, lean bar and reasoning in one scroll | Verdict callout; builder collapses once built |
| Matchup (777 lines) | Insights, lineup comparison, suggested moves, planner at equal weight | Score plus suggested moves |
| League Recaps (1037 lines) | Lead story plus many equal story cards | Lead recap |
| Waivers | 4-5 headed sections | Top add for your roster |
| Live Draft | Rankings, recommendations, teams, board and trade evaluator all at once | Current recommendation |
| Games | Four sections (simulator, league odds, what-if, pick'em) on one page | Pick'em (weekly); other sections as tabs |
| More (app) | 10+ sections, 770 lines, no dominant item | Account and Premium status |

Card-in-card nesting: `AccentCard` inside a section panel on This week (row
list inside accent card inside section); the Watchlist card (grouped rows each
with ToneBadge and nested player chips); GM Plan focus-area cards that contain
rows that contain cards; trade idea cards (card, exchange side, asset row,
badge: three nested surfaces); mobile More option groups inside
`ModalFormCard`/`AnimatedCard`.

Long scroll: Dashboard, GM Plan, League Recaps, Trade Analyzer, Player profile.
Most have no in-page anchor or tab navigation.

## 5. Proposed information architecture

### Top-level groups (same labels on web and app)

1. **Today**: Dashboard (absorbs This week and Today as one hero), Alerts as a
   section plus bell.
2. **My Team**: My Team, Matchup, Waivers, GM Plan (with Team Situation and
   Targets). Portfolio stays in General (cross-league).
3. **Trades**: one entry "Trades" with tabs Ideas / Analyzer / History (Finder
   folded into Ideas; History a real tab, not a floating link).
4. **League**: Standings (League Rankings with Playoff Odds as a tab), Players,
   Recaps, Games.
5. **Draft**: Draft Center with Live Draft as its primary action; College
   Scouting as a tab (prospects feed the draft).
6. **More / Account**: Account, Premium, Settings, News, Community, About, Legal.

### Before / after

| # | Before | After | Effort | Impact |
|---|---|---|---|---|
| 1 | Mobile League Overview, then Dashboard (two landings) | One landing: Dashboard. Standings and league context move to Standings | M | High |
| 2 | Web: This week and Today adjacent; mobile: Today and More next moves | One "Today" hero with the top move, rest as a list | M | High |
| 3 | Team Situation, GM Targets, GM Plan (3 app entries, header icon, More row) | One GM Plan entry (match web); stance and targets as sections | M | High |
| 4 | Teams and Playoff Odds (app), League Rankings (web) | "Standings" with tabs Standings / Power / Playoff Odds on both | M | High |
| 5 | Trade Hub / Finder / Analyzer / History; web tab named Trade Hub inside Trade Hub | "Trades" with tabs Ideas / Analyzer / History, same names on app and web | M | High |
| 6 | Draft Center and Live Draft as siblings; Scouting under More | "Draft" group: Draft Center, Live Draft, Scouting | S | Medium |
| 7 | More holds features plus settings | More holds only settings, legal, about; features move into nav | S | Medium |
| 8 | Dashboard has two mini-game cards and League Activity above Snapshot | Mini-games move to Games; League Activity becomes the last teaser | S | Medium |
| 9 | Premium not in web nav | Add Premium / Manage plan to web General | S | Medium |
| 11 | Web GM Plan, Trade Analyzer, Recaps long scrolls | Collapse secondary sections; one dominant module each | M each | Medium |
| 10 | Community web only | Add to app General, or record as an intentional exception | S-M | Low |
| 12 | Account (web) vs More (app) | One name ("Account") on both, with Settings inside | S | Low |

Ranked by impact: 1-5 High, then 6, 7, 8, 9, 11, then 10, 12. Effort: S under
1 day, M 1-3 days including web and app parity.

Parity exceptions worth keeping: Founder Analytics (web, founder only), Design
reference, Pick Detail drill-down (app).

## 6. Small safe fixes (done in this PR)

Label and order changes only, on the mobile orb (the web destination list in
`navDestinations.ts` is the reference, and already shared by sidebar and orb):

1. Mobile orb "Next Move" renamed **Dashboard** (matches web nav, the screen's
   own header and landing copy).
2. Mobile orb and screen header "Recap" renamed **League Recaps** (matches web).
3. **Live Draft** added to the mobile orb GM Tools, right after Draft Center
   (web order). The More row stays as a secondary path.

Not done (needs a design or owner decision): Trades vs Trade Hub rename, Teams
vs League Rankings, merging Team Situation and GM Targets on app, moving
Scouting or Trade History, a Premium entry on web.
