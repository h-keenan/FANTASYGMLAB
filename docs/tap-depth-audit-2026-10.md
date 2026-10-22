# Tap-depth audit — 2026-10

Status: **findings and proposals only, awaiting product-owner approval.** Nothing
here has been built. Every proposal below reuses an existing surface (a deep link,
a contextual action on an existing row/sheet, the GM orb, or a reorder). Proposals
that would add a nav item are called out explicitly and are not recommended.

Source of truth: the code on `origin/main` at `0195e076`. Main files read:
`web-next/src/lib/navDestinations.ts`, `components/{Header,DesktopSidebar,GmOrb,
LandingAuthIsland,DashboardContent,PlayerQuickView,PlayerProfileContent,
PlayersContent,TradesTabBar,TradeAnalyzerContent,TradeFinderContent,TradeIdeaCard,
PortfolioContent,AccountContent}.tsx`, `lib/gamePlanPresentation.ts`;
`mobile/src/navigation/RootNavigator.tsx`, `components/{GmOrb,BrandHeaderBar,
LeagueSwitcherHeaderButton,LeaguesGlanceSection,QuickActionsGrid}.tsx`,
`screens/{Home,Dashboard,More,PlayerDetail,Players,Trades,TradeHub,TradeAnalyzer,
TradeFinder,MyTeam,Portfolio,LeagueDetail}Screen.tsx`.

## 1. Counting rules

- **Start point:** a signed-in user with one saved league. On both web and mobile
  that user is auto-redirected to the league **Dashboard** (web
  `LandingAuthIsland`; mobile `HomeScreen` auto-nav, with Home left underneath on
  the stack). Users with **two or more** saved leagues land on **Portfolio**
  instead on both platforms; every league-scoped job costs them +1 tap (pick a
  league card) on their first job of a session.
- **One tap** = one press that changes what's on screen (open the menu/orb/sheet,
  pick a row, switch a tab, press a button). Typing a search term is noted as
  `+type` rather than counted. Scrolling isn't counted, but long scrolls are noted.
- Three columns throughout: **Web desktop** (≥`md`, persistent `DesktopSidebar`),
  **Web phone** (below `md`: the sidebar is hidden and the floating `GmOrb` sheet
  is the nav), and **Mobile app** (Expo).
- **No usage data exists in the repo.** Web fires `page_view` on every route plus
  a few `*_opened` events (`trade_hub_opened`, `waivers_opened`,
  `my_team_opened`, `trade_analyzer_opened`, `pqv_opened`, `gm_orb_opened`, …),
  but the counts live in the analytics DB, not in code. The mobile app sends **no
  client analytics events at all**. So job frequency below is an informed
  weighting (High = weekly in season, Medium = a few times a month, Low =
  occasional), not measured.

## 2. Navigation map

### 2.1 Web entry surfaces

| Surface | Where | What it reaches |
|---|---|---|
| Header brand mark | every page | `/`, which **redirects a signed-in user straight back** to Dashboard (1 league) or Portfolio (2+) |
| Header league switcher | league-scoped pages only | every saved league, **keeping the current page** (`swapLeagueIdInPath`), plus "Add a league" → `/connect-league` |
| Header lens button | league-scoped pages only | Dynasty / other valuation lenses (in place) |
| Header page title | every page | label only, not a control |
| Header "menu" | every page | Methodology, Account, 5 legal pages, Sign out |
| Desktop sidebar | desktop only, signed in | League group (Dashboard, Alerts, My Team, Matchup, Waivers, Players, League Rankings), GM Tools (Trade Hub, GM Plan, Draft Center, Live Draft, League Recaps), General (Home, Portfolio, News, Trade History, College Scouting, Community) |
| GM orb sheet | phone width only, not on `/` | same three groups as the sidebar, plus Founder Analytics for founders. No search, no unread badges, no quick actions |
| `TradesTabBar` | Trade Hub / Finder / Analyzer | the 3 trade tabs + "Trade History →" |
| Player Quick View (PQV) | any player name/avatar (`PlayerIdentityTrigger`) on Dashboard, Alerts, My Team, Matchup, Waivers, Players, GM Plan, League Recaps, Trade Finder, Player Compare, News, Live Draft | "Open Full Profile", "Compare this player". **Nothing else** |
| Player Profile page | PQV → Open Full Profile | Stats / Trends / Schedule / Career / Model tabs, "Compare" |
| Players list rows | `/players` | "Compare", **"Add to Trade"** (→ Trade Analyzer `?playerId=`, pre-filled) |
| Dashboard Game Plan / Watch List tiles | Dashboard | CTA deep-links to Waivers / Trade Hub / My Team **with `?playerId=` highlight** |
| Dashboard premium link | Dashboard (free users) | `/premium` |
| Account page | menu → Account | Identity, Billing ("Manage Billing" → Stripe portal; free users get a Premium link), Preferences (experience level etc.), Account actions, Delete account |
| Portfolio league cards | `/portfolio` | that league's Dashboard, its Live Draft |

### 2.2 Web destinations — minimum taps from Dashboard

| Destination | Desktop | Phone | Path |
|---|---|---|---|
| Dashboard | 0 | 0 | landing |
| Alerts / My Team / Matchup / Waivers / Players / League Rankings | 1 | 2 | sidebar row · orb → row |
| Trade Hub / GM Plan / Draft Center / Live Draft / League Recaps | 1 | 2 | sidebar · orb |
| Trade Finder / Trade Analyzer | 2 | 3 | Trade Hub → tab |
| Trade History | 1 | 2 | General group (also `TradesTabBar` link) |
| Portfolio / News / College Scouting / Community | 1 | 2 | General group |
| GM Targets / Team Situation | 1 | 2 | merged into GM Plan (old routes redirect) |
| PQV for a known player | 2 +type | 3 +type | Players → search → row |
| Player Profile (+ its 5 tabs) | 3 (+1 per tab) | 4 | … → PQV → Open Full Profile |
| Player Compare | 2 | 3 | Players row "Compare" (second player picked on page) |
| Account / Methodology / Legal | 2 | 2 | menu → item |
| Premium | 1 (free users, Dashboard link) / 3 | 1 / 3 | Dashboard link · menu → Account → Premium link |
| Connect league | 2 | 2 | league switcher → Add a league |
| Guess-the-Player leaderboard | 1 | 1 | Dashboard card link |
| Founder Analytics (founders) | **no link** | 2 | orb → Founder; the desktop sidebar has no Founder section |

### 2.3 Mobile entry surfaces

| Surface | Where | What it reaches |
|---|---|---|
| GM orb sheet | every screen except onboarding; draggable | **Destination search** ("Search where to go"), League group (League Overview, Next Move = Dashboard, Alerts *with unread badge*, My Team, Matchup, Waivers, Teams, Playoff Odds, Players), GM Tools (Trades *with "new" dot*, GM Targets, Team Situation, GM Plan, Draft Center, Recap *with ready dot*), **inline Switch League radio list**, General (Home, Portfolio, News, Premium, More) |
| Header buttons | most league screens | League switcher (→ **LeagueDetail** of the new league, not the current screen), Evaluation lens, GM stance |
| `BrandHeaderBar` | Players, My Team, Matchup, Alerts, Trades, Draft Center, LeagueDetail, Playoff Odds, Team Situation | ★ → GM Targets, … → More |
| Dashboard | landing | Quick Actions grid (Trades, Rankings → Players, Waivers, Draft Picks), Matchup card, Recap card, tile CTAs ("Review in Trade Hub", "Open Waivers" — **no player id passed**), tap a tile's player → PlayerDetail |
| Home | orb → Home | Your leagues list, **Add league**, leagues-at-a-glance modules (→ Trades with a specific tab, Waivers, Alerts), News |
| More | orb → More or … | Density, Experience level, Theme, Team Situation, Trade History, College Prospects (*only if the user said yes to college football*), notifications, How We Evaluate, replay intro, legal, Manage Subscription (*near the bottom*), Export data, Delete account |
| Trades | orb → Trades | Trade Block / Search (Finder) / Make a Trade (Analyzer) tabs; `initialTab` param supported; clock icon → Trade History |
| PlayerDetail | any player row | Share, ☆ Add to GM Targets, Compare; Stats / Trends / Schedule / Career / Model tabs. **No trade action** |
| Modals | — | Paywall, Trial Lapsed, share previews (trade, player, compare, portfolio, recap) |

### 2.4 Mobile destinations — minimum taps from Dashboard

| Destination | Taps | Path |
|---|---|---|
| Next Move (Dashboard) | 0 | landing |
| Matchup / Recap | 1 | Dashboard card |
| Trades (Trade Block) / Players / Waivers / Draft Center | 1 | Dashboard Quick Actions |
| Trade Finder (Search) / Trade Analyzer (Make a Trade) | 2 | Quick Action Trades → tab |
| Alerts / My Team / Teams / Playoff Odds / League Overview / GM Targets / Team Situation / GM Plan / Portfolio / News / Home / More / Premium | 2 | orb → row |
| My Team Bench / Analysis tabs | 3 | orb → My Team → tab |
| PlayerDetail for a known player | 2 +type | Quick Action Rankings → search → row (3 from screens without the grid) |
| PlayerDetail tabs | +1 each | |
| Player Compare | 3 +type | … → PlayerDetail → Compare (only entry point) |
| Trade History | 3 | Trades → clock icon, or orb → More → row |
| College Prospects | 3, **or unreachable** | orb → More → row, shown only when college-football interest = yes |
| Settings (any) | 2 (+scroll) | orb → More; 1 from screens with `BrandHeaderBar` |
| Add league sheet | 3 | orb → Home → Add league |

Web-only destinations with no mobile equivalent: Community, Live Draft, Guess-the-Player
leaderboard. Mobile-only: League Overview, Teams, Playoff Odds (web folds standings and
playoff odds into League Rankings), Trade Hub "For You / All Trades" toggle.

## 3. Common jobs — tap counts today

Counted from Dashboard. "Steps" lists the cheapest path; D / P / M = web desktop / web
phone / mobile app.

| # | Job | Freq | D | P | M | Cheapest steps |
|---|---|---|---|---|---|---|
| 1 | Check lineup / start-sit | High | 1 | 2 | 2 (Matchup: 1) | D: sidebar My Team (or Matchup). P: orb → My Team. M: orb → My Team; or the Dashboard Matchup card |
| 2 | Evaluate a trade with a specific player (one of theirs for one of mine, to a verdict) | High | 5 +type | 6 +type | 7 +type | D: Players → type → Add to Trade (pre-fills the receive side, owner team selected) → tap "You send" → tap my player → Analyze. P: same +orb. M: orb → Trades → Make a Trade → tap my player → Receive side → type, tap target → Analyze |
| 2b | Same job, **starting from a player row** (Waivers, Alerts, My Team, Dashboard tile…) | High | 5 +type | 6 +type | 7 +type | The row opens PQV / PlayerDetail, which has no trade action, so you back out and start job 2 from scratch and re-type the name |
| 3 | Find trade partners for one of my players | Medium | 4 | 5 | 5 | D: Trade Hub → Trade Finder tab → tick player → Find. M: orb → Trades → Search → tick → Find Trades. Web Finder is Premium-gated |
| 4 | Check waivers / FAAB decision | High | 1 | 2 | 1 | D: sidebar Waivers; FAAB Shortlist and FAAB ranges are sections on the page (scroll). M: Quick Action Waivers. A Dashboard waiver tile's CTA highlights the named player on web; mobile drops the player id |
| 5 | Look up any player | High | 2 +type | 3 +type | 2–3 +type | D: Players → type → row (PQV). M: Quick Action Rankings → type → row (3 via orb from any other screen) |
| 6 | Switch league (and keep doing what I was doing) | Medium | 2 | 2 | 4 | Web: switcher → league (stays on the same page). M: switcher → league lands on **League Overview**, then orb → original screen |
| 7 | Read alerts | High | 1 | 2 | 2 | sidebar / orb → Alerts. Unread badge on mobile only |
| 8 | See Portfolio | Medium | 1 | 2 | 2 | General group / orb. 0 for multi-league users (it's their landing) |
| 9 | Add a league (to the form) | Low | 2 | 2 | 3 | Web: switcher → Add a league. **From Portfolio (the multi-league landing) web has no switcher: open a league → switcher → Add = 3.** M: orb → Home → Add league |
| 10 | Change settings / experience level | Low | 3 | 3 | 3 (2 from `BrandHeaderBar` screens) | Web: menu → Account → option. M: orb → More → option (scroll) |
| 11 | Manage the subscription | Low | 3 | 3 | 3 | Web: menu → Account → Manage Billing → Stripe. M: orb → More → long scroll → Manage Subscription → store. Orb "Premium" → Paywall is shown to every user, subscribed or not |
| 12 | Share a trade | Medium | 2 (idea) / **✗ (analyzer)** | 3 / **✗** | 4 (idea) / +2 after a verdict | Web: Trade Hub → Share on the card (native share). There's no share on a web Trade Analyzer verdict. M: orb/Quick Action → Trades → share icon → "Share image" in the preview |

### Worst five today (by max taps)

1. **Evaluate a trade with a specific player**: 5 / 6 / 7. It's worst from a player row, because no player surface on either platform links into the analyzer except the web Players list.
2. **Find trade partners for a player**: 4 / 5 / 5.
3. **Share a trade**: 2 / 3 / 4 for ideas. **Impossible** for a web Analyzer verdict.
4. **Switch league and continue**: 2 / 2 / **4**. Mobile throws you to League Overview.
5. Tied at 3 taps on every platform: **experience level**, **manage subscription**, and **add a league from Portfolio**. **Look up a player** is 3 on web phone and on mobile away from Dashboard.

## 4. Problems found

### Over 3 taps
- Evaluate-a-trade (all platforms), find-partners (all), share-a-trade (mobile),
  switch-and-continue (mobile). The Player Profile page on web phone (4) only matters
  if Profile tabs are a primary job, which they aren't.

### Dead ends (no route onward to the obvious related action)
- **Web PQV** offers only Open Full Profile and Compare. There's no "Add to Trade",
  "Find trades", "Add to GM Targets" or share, even though the Analyzer already
  accepts `?playerId=` and the Players list already builds that exact link
  (`gamePlanTileHref("trade-analyzer", …)`).
- **Web Player Profile**: Compare only. Same gaps.
- **Mobile PlayerDetail**: Share, Watch and Compare, but no trade action. The Trades
  screen already takes `initialTab`, but neither tab takes a player.
- **Web Trade Analyzer verdict** can't be shared (mobile can; `ShareTradeButton`
  already exists on web trade-idea cards).
- **Web Trade Finder** ignores `?playerId=` (Trade Hub, Waivers, My Team and Analyzer
  all read it).
- **Web "Home" nav row** (sidebar + orb, "Switch leagues and manage account")
  redirects a signed-in user with a saved league straight back to Dashboard or
  Portfolio. It's a loop, and its subtitle promises something web Home doesn't do.
- **Web Portfolio** has no "Add a league" entry, and it's the one league-less page
  multi-league users land on.

### Reachable only through one obscure path
- Mobile **College Prospects**: only More → Scouting, and only rendered when the
  user answered yes to college football. Otherwise it's unreachable (web has a
  sidebar entry).
- Mobile **Player Compare**: only PlayerDetail → Compare. Web has five entry points.
- Mobile **Manage Subscription**: the bottom of a long More screen.
- Web **Founder Analytics** on desktop: no link at all (the orb has it, but the orb is
  hidden on desktop).
- Web **Trade Analyzer / Finder** have no nav row of their own (deliberate, per
  coridian_ 2026-10-17). Their only routes are the Trade Hub tabs and the Players
  "Add to Trade".

### Web ↔ mobile inconsistencies
- League switch: web keeps the current page, mobile goes to League Overview.
- Dashboard tile CTAs: web passes `?playerId=` and highlights the player, mobile
  navigates without it.
- Players rows: web has Compare + Add to Trade, mobile rows only open PlayerDetail.
- GM Targets watch toggle: on mobile PlayerDetail, but not on web PQV/Profile (web adds
  targets only from GM Plan).
- Orb: mobile has destination search, unread/new badges and inline league switching.
  The web orb has none.
- Dashboard shortcuts: the mobile Dashboard has a Quick Actions grid. On web phone
  everything is orb → row (the Explore grid was removed on purpose).
- IA naming: Dashboard ↔ "Next Move", League Recaps ↔ "Recap", League Rankings ↔
  Teams + Playoff Odds. GM Targets / Team Situation are separate orb rows on mobile
  but merged into GM Plan on web.
- Trade Hub "For You / All Trades" toggle exists on mobile only.
- My Team is one page on web, but Overview / Bench / Analysis tabs on mobile (Bench
  costs +1).

### Same destination, very different depth
- Trade History: 1 on web desktop vs 3 on mobile.
- Player Compare: 2 on web vs 3 +type on mobile.
- College Prospects: 1 on web vs 3-or-unreachable on mobile.
- Trade Analyzer with a pre-filled player: 2 from the web Players list vs not possible
  on mobile.

## 5. Proposals (ranked)

**Score** = (taps saved on the typical path, summed over the platforms it changes) ×
frequency weight (High 3, Medium 2, Low 1). A dead end that becomes reachable counts as
1 tap saved per platform. Ties are broken by judgment.

| Rank | Proposal | Surface reused | Taps saved (D/P/M) | Score | Needs mobile build | New nav item? |
|---|---|---|---|---|---|---|
| 1 | **"Add to Trade" on PQV, Player Profile and mobile PlayerDetail, and as a mobile Players row action**, deep-linking to the Analyzer pre-filled. After a quick-add, the Analyzer **flips the active side to the empty side**, so the next tap picks the counter-asset. Web reuses `gamePlanTileHref("trade-analyzer", …)`; mobile passes `Trades { initialTab: 'make', playerId }` and `TradeAnalyzerScreen` seeds from it, mirroring web's `quickAddPlayerId` logic | PQV actions row, PlayerDetail action row, Players row | Job 2b: 1/2/3 (5→4, 6→4, 7→4), no re-typing. Job 2 from Dashboard: 1/1/2 | 24 | Yes (mobile half). The web half, including the side flip on the existing Players "Add to Trade", ships without a build | No |
| 2 | **"Find trades" on PQV / Profile / PlayerDetail for players on my roster**, pre-selected in Trade Finder with the search auto-run. Web: Trade Finder reads `?playerId=` like its sibling tabs. Mobile: `Trades { initialTab: 'search', playerId }`. Free users get the existing upsell | Same action rows | From a My Team row: 2/3/3 (4→2, 5→2, 5→2) | 16 | Yes (mobile half) | No |
| 3 | **Orb destination search also matches player names** and opens PlayerDetail / PQV. Mobile already has the field. Web phone would get the same field in its existing orb sheet (flagged: a new control inside the sheet, not a nav row) | GM orb sheet | Job 5: 0/1/1 from any screen (3→2) | 6 | Yes | No (adds a search field to the web orb) |
| 4 | **Web Portfolio: an "Add a league" link in the Portfolio header** (same `/connect-league` the switcher uses), and a mobile league-switcher sheet "Add a league" row (web's switcher already has one) | Portfolio header, switcher sheet | Job 9: 2/2/1 (Portfolio 3→1; mobile 3→2) | 5 | Yes (mobile half) | No |
| 5 | **Mobile league switcher keeps the current screen** (swap the `leagueId`/`leagueName` params, as web's `swapLeagueIdInPath` does). Fall back to League Overview only on screens without league params. Applies to both the header switcher and the orb's inline list | Existing switchers | Job 6: 0/0/2 (4→2) | 4 | Yes | No |
| 6 | **Share button on the web Trade Analyzer verdict**, reusing `ShareTradeButton` (mobile already has this) | Analyzer result card | Job 12 (verdict): dead end → 1 tap on D and P | 4 | No | No |
| 7 | **"Add to GM Targets" (watch) on web PQV / Profile**, matching mobile PlayerDetail's ☆ toggle and calling the endpoint GM Plan already uses | PQV actions row | Watching a player from any row: 1/1/0, no typing | 4 | No | No |
| 8 | **Season-aware mobile Dashboard Quick Actions**: in season, the 4th slot becomes My Team instead of Draft Picks (Draft Picks keeps its orb row and My Team's own draft link). Offseason stays as today | Existing 4-slot grid (a reorder, no new slot) | Job 1: 0/0/1 (2→1) | 3 | Yes | No |
| 9 | **Mobile Dashboard tile CTAs pass the player id** and Waivers / Trades highlight it, as web already does | Tile CTA buttons | Job 4 from a tile: ~1 (scroll-and-find) | 3 | Yes | No |
| 10 | **Context-aware orb "Premium" row on mobile**: for subscribed users it reads "Manage subscription" and opens the same store URL More uses. Also move More's Manage Subscription up beside the account rows | Orb row, More (reorder) | Job 11: 0/0/1 (3→2) | 1 | Yes | No |
| 11 | **Always show mobile More → College Prospects** (the college-football prompt keeps personalizing content, but stops hiding the row) | More row | Unreachable → 3 | 1 | Yes | No |
| 12 | **Remove the web "Home" row** from the sidebar and orb. It only redirects back, and the brand mark already links to `/` | — | 0 taps; removes a dead row (less clutter) | — | No | Removes one |

Not recommended, because each needs a new nav item:
- A Premium / Manage Billing item in the web header menu (would save 1 tap on job 11,
  a Low-frequency job).
- A College Prospects or Community row in the mobile orb. #11 covers the College
  Prospects reachability gap without one.
- A Founder Analytics section in the desktop sidebar. It's founder-only, so not
  user-facing clutter, but it is a new section. Typing the URL works today.

## 6. Jobs after the proposals

| # | Job | Before D / P / M | After D / P / M | Driven by |
|---|---|---|---|---|
| 1 | Lineup / start-sit | 1 / 2 / 2 | 1 / 2 / **1** | #8 |
| 2 | Evaluate a trade (from Dashboard) | 5 / 6 / 7 (+type) | **4 / 5 / 5** (+type) | #1 |
| 2b | Evaluate a trade (from a player row) | 5 / 6 / 7 (+type) | **4 / 4 / 4** (no typing) | #1 |
| 3 | Find trade partners (from a My Team row) | 4 / 5 / 5 | **2 / 2 / 2** | #2 |
| 4 | Waivers / FAAB | 1 / 2 / 1 | 1 / 2 / 1 (mobile tile CTA lands on the player) | #9 |
| 5 | Look up any player (from any screen) | 2 / 3 / 3 (+type) | 2 / **2 / 2** (+type) | #3 |
| 6 | Switch league and continue | 2 / 2 / 4 | 2 / 2 / **2** | #5 |
| 7 | Read alerts | 1 / 2 / 2 | 1 / 2 / 2 | — |
| 8 | Portfolio | 1 / 2 / 2 | 1 / 2 / 2 | — |
| 9 | Add a league (from Portfolio) | 3 / 3 / 3 | **1 / 1** / 3 (2 from any league screen) | #4 |
| 10 | Experience level | 3 / 3 / 3 | 3 / 3 / 3 | — (Low frequency; no change proposed) |
| 11 | Manage subscription | 3 / 3 / 3 | 3 / 3 / **2** | #10 |
| 12 | Share a trade idea / verdict | 2 / 3 / 4 · ✗ / ✗ / +2 | 2 / 3 / 4 · **+1 / +1** / +2 | #6 |

No job stays above 3 taps from its typical starting point except evaluate-a-trade (4).
Its floor is "pick their player, pick mine, press Analyze", which is about as low as it
can go without auto-analysis.

## 7. What the code can't tell us

- **Real usage.** No event counts are in the repo, and the mobile app sends no client
  analytics, so the frequency weights are judgment. Before choosing between #3, #5 and
  #8, check Founder Analytics' `page_view` paths and `pqv_opened` / `gm_orb_opened` /
  `trade_analyzer_opened` for web.
- **The share of users with more than one league.** That decides how much the
  Portfolio-landing +1 and #5 matter.
- **Desktop vs phone split on web.** The orb vs sidebar costs differ by a tap on every
  destination.
- What the mobile Paywall shows an already-subscribed user who opens it from the orb.
  The code only shows a post-purchase success state.
- Whether Trade Finder on mobile is meant to stay ungated (a web comment says it should
  match web's Premium gate). That decides whether #2's mobile link shows results or an
  upsell.
- Visual position and scroll depth (e.g. how far down More's Manage Subscription
  really sits on a given device). Counts here are structural, not measured on device.
