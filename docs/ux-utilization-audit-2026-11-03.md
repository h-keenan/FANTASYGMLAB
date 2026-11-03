# Feature utilization / information-architecture audit, 2026-11-03

Request (coridian_): "audit the full user experience. We have so many features and we need to make sure it's easy for the user to navigate and get full utilization."

This is not a readability audit (see `ui-first-time-audit-2026-11-02.md` and `ui-ease-of-use-audit-2026-11-01.md` for that). The question here is: **can a user find, reach, and be led to every feature at the moment it helps them?**

Screenshots: `docs/assets/ux-utilization-audit-2026-11-03/` (downscaled; full-size originals are on the audit machine under `/private/tmp/claude-501/ux/shots/`).

## 0. TL;DR

- The product has **~22 web destinations and ~36 app screens**. Primary nav is a flat list of 20 rows (7 league + 8 GM tools + 6 general, plus Premium/More on the app). There is no grouping by task, no "new" or "Pro" marker anywhere in the nav, and the orb is a bare logo.
- The biggest utilization leaks are **not** discoverability of the nav list. They are: (1) **dead-end screens** that tell you something and then stop (Alerts, Matchup, My Team, League Rankings, Recaps, Games, News, the trade verdict), (2) **paywalls that show one paragraph and no preview**, so paid value is invisible exactly when someone has reached for it, (3) **no return loop on web** (no push, no email, no "what changed since you were last here"; the app has the last one), and (4) **web/app drift** (Community, Playoff Odds, Trade History, College Scouting and Team Situation live in different places on each platform).
- A three-step "Start here" checklist exists (14-day window) but covers only three "look at" actions. Nothing teaches the features that change verdict quality (team situation/GM stance, GM Targets, Manager profiles, Lineup Planner, Playoff Odds what-if).
- Recommendation: ship Proposal A now (labels, lock markers, cross-links, signed-in landing), adopt Proposal B's six groups as the target model in two stages, and fold Proposal C's "what do you want to do" idea into the Dashboard rather than replacing nav. Details in section 5.
- Shipped from this audit (small, not merged): cross-link rows on Alerts and Matchup (web + app), a Sleeper link on Waivers (web + app), per-page browser tab titles (web). Section 6.

## 1. Method and honest limits

- Web: built `origin/main` (`next build`, `next start`) and ran the real FastAPI backend against real public Sleeper data (league "No quitters league", 12 teams, 2026 week 8, dynasty; Sleeper user `gstash1800`). Only Supabase was faked (a small local stand-in for sign-up and the saved-leagues table). Free-tier account, so paid screens show their paywall.
- Walked every league page, every general page, the orb sheet, the MENU dropdown, at 390px (2x) and 1280px, and scanned the DOM for outbound links per page (the 19 orb/nav links are present on every page and were subtracted to isolate in-content links).
- Code-derived: all link graphs, tap depths, gating, notification routing and parity claims were read from `web-next/src` and `mobile/src` (including `GmOrb.tsx`, `DesktopSidebar.tsx`, `navDestinations.ts`, `MoreScreen.tsx`, `RootNavigator.tsx`, `pushRouting.ts`, `dashboardLayout.ts`, `startHere.ts`, `sinceLastCheckIn.ts`).
- **The mobile app was not run** (no device/simulator in this session). All app findings are code-only; app before/after screenshots for the quick wins do not exist. Per the standing rule, app changes were verified with `tsc`, the app unit tests, and CI.
- Not verifiable here: real Pro/Premium states (`/premium` errors against the stand-in Supabase), push delivery, ESPN/Fleaflicker/MFL leagues, a real first-ever signup.
- One observed content inconsistency, flagged but not scoped here: Dashboard said "Check Matchup: Kendrick Bourne is out ... a healthy WR on your bench can step in" while Matchup's Suggested Moves said "Your Sleeper lineup already matches our suggested lineup" with Bourne shown OUT at FLEX (breaking-news timing is the likely cause; worth a check).

## 2. Feature inventory with entry points and tap depth

Depth key. **Phone web** = taps from Dashboard (orb counts 1, a row counts 1, so nav rows are 2). **Desktop web** = clicks from anywhere (the sidebar is always visible at md and up, so nav rows are 1). **App** = taps from Dashboard (orb 1 + row 1 = 2; More = orb, More, row = 3).
"Nav" = a row in the orb / sidebar. Gate: F free, Pro/Prem = paid (copy says "Pro" in the backend and "Premium" in web fallbacks), L = free with a visible limit.

### 2.1 Pages (league-scoped)

| Feature | Web entry points | App entry points | Depth (phone web / desktop / app) | Gate |
|---|---|---|---|---|
| Dashboard | Nav, logo, league switcher, Home | Home league row, nav | 1 / 1 / 1 | F |
| Alerts | Nav, header bell (dropdown, then page), Dashboard watchlist "View all alerts", Now-strip chip | Nav, Dashboard card | 1 (bell) / 1 / 1 | F |
| My Team | Nav, Dashboard "Open My Team" | Nav, Dashboard, Teams | 2 / 1 / 2 | F |
| Matchup | Nav, Dashboard Now chip, Start-here card, Today rows | Nav, Dashboard weekly card, lock-reminder push | 1-2 / 1 / 1-2 | F (planner uses what-if limits) |
| Waivers | Nav, Dashboard Now chip, Start-here, Today rows, GM Targets link | Nav, Dashboard strip, waiver-reminder push | 1-2 / 1 / 1-2 | L (full board Pro) |
| Players (search, rankings, filters) | Nav, header search, orb search, PQV "Open Full Profile" | Nav, orb search | 2 / 1 / 2 | F |
| Player profile (full page) | Players row, PQV "Open Full Profile" | Player Detail (tabs: Stats, Trends, Schedule, Career, Model) | 3 / 2 / 2-3 | F |
| Player Quick View (modal/sheet) | Any player identity (13 surfaces) | Any player identity | 1 from any list | F |
| Player Compare | PQV "Compare this player", Players row, profile, GM Plan, Live Draft. **No nav row** | PQV/Player Detail | 3 / 3 / 3 | F |
| League Rankings (standings, playoff-odds button, power, values, picks, starters, bench) | Nav | Nav ("League Rankings" row opens `Teams`) | 2 / 1 / 2 | F (odds Prem) |
| Manager profile sheet (tendencies, trades, opponent card) | **Only** from a team row in League Rankings | **Only** from a team row in Teams | 3 / 2 / 3 | F |
| Playoff Odds | Button inside League Rankings; Games "Your odds"; Dashboard odds strip | **Own nav row** | 3 / 2 / 2 | Prem (what-if) |
| Trade Hub (ideas) | Nav, Dashboard Trades block, Start-here, Today, deadline card | Nav (route `Trades`), Dashboard, deadline push | 2 / 1 / 2 | L (2 of N ideas free) |
| Trade Finder | Trade Hub tab, Players/PQV "Find trades" | Trade Hub tab, PQV | 3 / 2 / 3 | Prem |
| Trade Analyzer | Trade Hub tab, Dashboard "Analyze a trade", PQV "Add to Trade", Players "Add to trade", public bridge from share cards | Trade Hub tab, PQV | 1 / 2 / 3 | L (daily cap, LimitWall) |
| Trade verdict (counter, alternates, share, report, community toggle) | Inside Analyzer | Inside Analyzer | n/a | F/L |
| Trade History / outcomes | Sidebar General, Trade Hub tab bar link | **More only** (and Trades screen link, push) | 2 / 1 / 3 | F |
| GM Plan (roadmap, team situation, GM targets, watching) | Nav, Today rows, PostureChip, Trade Hub link | Nav, More ("Team Situation"), header star = GM Targets | 2 / 1 / 2 | Prem |
| Draft Center | Nav | Nav | 2 / 1 / 2 | Pro (wall) |
| Pick Detail | **None** | Draft Center / Analyzer picks | n/a | |
| Live Draft | Nav | Nav **and** More | 2 / 1 / 2-3 | Prem (wall) |
| League Recaps (recaps, history, storylines) | Nav, League Pulse card | Nav, Dashboard recap-ready card, Alerts recap card | 2 / 1 / 2 | F |
| Games (season sim + pick'em, what-if) | Nav, Dashboard odds strip | Nav | 2 / 1 / 2 | Prem (what-if) |
| Commissioner (integrity) | Nav (shown to everyone) | Nav (commissioners only) | 2 / 1 / 2 | Pro (wall) |
| Guess the Player (cards + leaderboard) | Dashboard "More" cards, leaderboard link | Dashboard card, **More** leaderboard row | 2-3 / 2-3 / 2-3 | F |
| League type / Guillotine | Dashboard "More" | Dashboard | 2 / 2 / 2 | F |
| Sample league | Landing, connect page, header links | Home, onboarding | n/a | F (guests) |

### 2.2 Pages (account / cross-league)

| Feature | Web | App | Depth (phone web / desktop / app) | Gate |
|---|---|---|---|---|
| Home / league list / switch league | Nav "Home", header switcher | Home screen, header switcher | 2 / 1 / 1 | F |
| Portfolio (all leagues) | Nav | Nav | 2 / 1 / 2 | Prem (wall for 1 league) |
| News | Nav, header (inside bell dropdown), PQV news | Nav, Home header globe, PQV | 2 / 1 / 2 | F |
| College Scouting | Sidebar General | **More, only after opting in via a one-time Dashboard prompt** | 2 / 1 / 3 | Pro (wall) |
| Community (shared trades feed) | Sidebar General (own page) | **Only inside Trade History** (feed at the bottom) | 2 / 1 / 4 | F |
| Account (identity, billing, preferences, push toggles, referral, delete) | MENU, then Account | More | 2 / 2 / 3 | F |
| Premium / pricing / billing | Account Billing, any upsell card. **No nav/MENU row** | Orb "Premium" row (or Manage subscription) | 3 / 3 / 2 | |
| How We Evaluate / methodology | MENU | More | 2 / 2 / 3 | F |
| Legal pages | MENU, landing footer | More | 2 / 2 / 3 | F |
| Founder Analytics | Nav (founder only) | Nav (founder only) | n/a | internal |
| Design system page | `/design` | long-press on More title | hidden | internal |

### 2.3 Cards, modules, sheets, flows

| Item | Where it shows | Leads to | Notes |
|---|---|---|---|
| Start Here (3 steps) | Dashboard, first 14 days, until dismissed/done | Matchup, Trade Hub, Waivers | same list web and app (tested for parity) |
| Now strip (Lineup / Alerts / Waivers / Deadline chips) | Dashboard | Matchup, Alerts, Waivers, Trade Hub | |
| Trades block (top idea + Analyze a trade + More ideas) | Dashboard | Trade Hub, Analyzer | |
| Today / Game Plan (free: 4 moves) | Dashboard | Per-row destination via `destinationCtaLabel` | upsell inline |
| My Team snapshot / Watchlist and alerts | Dashboard | My Team, Alerts | |
| "More" collapsed (League Pulse, Guess the Player x2, League type) | Dashboard | Recaps, leaderboard | label says "League activity, games, settings" |
| Deadline card | Dashboard, Trade Hub | Trade Hub | |
| Playoff-odds strip | Dashboard (app and web) | Games / Playoff Odds | |
| Lineup Planner (Edit lineup, swap sheet, Open in Sleeper) | Matchup, only after tapping Edit lineup | what-if endpoint | one entry point |
| Suggested Moves | Matchup | none onward | **dead end** (fixed in part, section 6) |
| Percentile explorer sheet | PQV stat rows | in-sheet | one entry point |
| Player value history, trends, career, schedule, model radar | PQV / profile / Player Detail tabs | in-place | web PQV is condensed; full profile is the destination |
| Manager Tendencies chips/card | Trade ideas, Analyzer partner row | none onward to manager profile | **no link to full manager profile** |
| League switcher, lens menu, GM stance button (app), posture chip | Header | Home / lens / GM Plan | posture chip links to Team Situation (redirect) without league name |
| Share flows | Web: Analyzer verdict (PNG/text + record), Trade idea, player hero. App: trade, idea, player, **compare, portfolio, recap** | Public share-card pages | recap/portfolio/compare share are app-only |
| Share to Community toggle | Analyzer | Community feed | |
| Referral card | Account (web) / More (app) | invite | only entry point |
| Trade outcome prompt ("did it happen?") | Global in layout (web) / root navigator (app) | Trade History | also a push category |
| Guess the Player prompts | Dashboard | leaderboard | |
| Push permission prompt, College interest prompt | App Dashboard | OS permission / More > Scouting | one-time |
| Guest create-account modal, age gate, password recovery, ESPN import, embedded checkout | modal flows | | guests cannot buy: upgrade CTA routes through account creation |
| Replay intro tutorial | App More | onboarding | no web equivalent |

### 2.4 Notifications

| Channel | What | Where it lands | Web | App |
|---|---|---|---|---|
| Push (9 user-toggleable categories: top priority, watch, recap, injury, team situation, trade follow-up, lineup lock, trade deadline, waiver reminder; capped 4/week; injury/lineup lock/deadline reserved) | proactive | `pushRouting.ts`: lineup_lock to Matchup, waiver_reminder to Waivers, trade_deadline to Trade Hub, trade_followup to Trade History, any push with a player to Player Detail, else Dashboard | **No web push** | yes |
| In-app bell dropdown + Alerts page | roster news, read state synced across devices | external article link and player chip only | yes | yes (Alerts screen) |
| Dashboard Now strip / watchlist | summary counts | Alerts, Matchup, Waivers | yes | yes |
| Account push toggles | preferences | | **shown on web but nothing on web delivers push** | yes |
| Email | none found | | none | none |

## 3. Discoverability matrix

Legend: **1** = exactly one entry point; **B** = buried (3+ taps or only via More / a tab inside another page); **O** = reachable only through the orb/sidebar list (no contextual link); **-** = no contextual link from the screens where the need arises.

| Feature | Entry points | Flags | Why it matters |
|---|---|---|---|
| Manager profile (tendencies, recent trades, opponent card) | League Rankings / Teams team row only | **1, B** | The moment of need is a trade pitch: Trade Hub idea cards and the Analyzer partner row show tendency chips but link nowhere. |
| Lineup Planner (swap sheet, what-if win odds) | "Edit lineup" on Matchup | **1** | The product's best "do something" tool sits behind a secondary button. |
| Playoff Odds | App nav; web button inside League Rankings + Games + Dashboard strip | web **B** | Web has no nav row; App has one. |
| Player Compare | PQV/Players/profile only | **O (no nav)**, B | Fine as contextual, but there is no "compare" on Trade Analyzer verdict or Waivers. |
| Trade Finder | Trade Hub tab; PQV "Find trades" | **B** (intentional, 2026-10-17) | Pro feature; the tab label is the only hint and the Analyzer verdict never suggests it. |
| Trade History | Sidebar (web), **More** (app), tab link | app **B** | It is where outcomes (the accountability loop) live; push tap lands there. |
| Community | Web sidebar; app only inside Trade History | app **1, B** (4 taps) | Parity gap. |
| College Scouting | Web sidebar; app More after opt-in | app **B**, hidden until opt-in | |
| Guess the Player leaderboard | Card link; app More | **B** | |
| GM Targets (watch list) | PQV "Add to GM Targets", Waivers watchlist tab, GM Plan tab, app header star | web: nav has no row | Retired nav row (merged into GM Plan 2026-10-18); users who knew it have no pointer. |
| Pick Detail | App only | app **1** | Web has no equivalent. |
| Premium / billing | App orb; web via Account then Billing or upsell cards | web **B** | Carried from the 11-01 audit (F5). |
| Referral | Account / More | **1, B** | Growth loop hidden at depth 3. |
| Account, push settings (app) | MENU / More | **B** | Push is the app's retention channel; the toggle is at depth 3 and the permission prompt is one-time. |
| Valuation lens (Dynasty/Redraft) | Header chip | visible, but unexplained | |
| Orb search | Header search icon, orb | visible | A strong tool that is not mentioned in onboarding. |

### 3.1 Missing contextual links (the user needs X, the screen does not offer it)

| From | Needs | Today | Status |
|---|---|---|---|
| Trade verdict | Better options: Trade Finder; partner's manager profile; roster impact (My Team) | Share, counter, alternates, report. The Trade Hub tab bar is on the page but carries no assets. | open (decision D4) |
| Waivers add | Suggested drop; place the claim | "Place claims in Sleeper" text only; no drop suggestion (data gap, see gap analysis) | Sleeper link **shipped**; drop = decision D6 |
| Player quick view | Trade, compare, targets, profile | **Already present**: Add to Trade, Find trades, Add to GM Targets, Open Full Profile, Compare. (Verified; no gap.) Missing: "waiver add" when the player is a free agent, and "manager who owns him". | open (D5) |
| Matchup | Waivers/trade/roster for a weak spot; the swap sheet | Swap sheet is behind Edit lineup; nothing onward | onward links **shipped** |
| Alerts | The action page; the player's page | External article and player chip only | next-steps row **shipped**; per-alert action = D3 (needs a field from the API) |
| News | Affected player, roster, waivers | PQV on player names; article link | open (D3) |
| My Team | Trade/waiver for a position of need (Team Analysis has strength/need rows) | Zero outbound links in the DOM scan | open (Q3, no data gap: needs are computed) |
| League Rankings | Trade with this team; compare | Team row opens manager sheet | open |
| League Recaps, Games | Anything | none | open |
| Paywalled screens | What I would get; sample; what free includes | One paragraph + Upgrade | D1 |
| Dashboard Today "Free: up to 4 next moves" | which moves are hidden | text only | |

### 3.2 Dead ends and back-navigation

- **Dead ends (no onward link, DOM-verified on web):** My Team, League Rankings, League Recaps, Games (outside Upgrade), News (outside article), Trade History empty state ("No trade history yet. Confirm a trade to see it here." with no link to Analyzer), Community empty states, every paywall card (only Upgrade), Alerts "All quiet" (fixed), Player Compare with no player ("Browse players" is the only way out).
- **Back navigation (web):** no in-page back control on any page. On a phone browser the OS/browser back works; an installed PWA or in-app webview has no back. Player profile, Player Compare and Analyzer have no "Back to Players / Back to Trade Hub". The MENU is not nav (legal + account). The app has native back.
- **Wrong-context landing:** `PostureChip` links to `/team-situation/{id}` without `?name=`, which redirects to GM Plan and shows the raw league id until the header resolves the name (also true for stale bookmarks).
- **Tabs that look like pages:** Trade Hub / Finder / Analyzer are three routes behind one tab bar; Trade History is a link above the tabs, not a tab (three different labels: nav "Trade History", H1 "Did it work out?", subtitle "Trades you've shared and confirmed").

## 4. Utilization-driving gaps (day 1, day 2, week 1, returning)

### 4.1 What a new user sees as their next best action

| When | Web | App | Gap |
|---|---|---|---|
| Day 1, signed up, no league | Landing page still shows the marketing hero; the connect form is ~3 screens down (carried F2) | Onboarding (3 steps: value, connect, level) goes straight to connect | Web hands a brand-new user the *least* prominent path to the one thing they must do |
| Day 1, league connected | Dashboard: **Start Here** (3 looks), Now strip, top trade idea, Today (free: 4 moves) | same, plus push prompt and college-football prompt | Good. Checklist is "look at" only. |
| After 3 looks | Checklist disappears | same | Nothing replaces it. No "next: set Team Situation", "Add 3 GM Targets", "Turn on push", "Try Playoff Odds", "Connect your other leagues", "Invite a friend". |
| Day 2 | Same Dashboard. No change feed. | "Since your last check-in: N new items" on Dashboard | **Web has no "what changed"**; app does. |
| Week 1 | Nothing | Pushes (cap 4/week) incl. one-time Team Situation nudge, lineup lock, waiver reminder | **Web-only users receive nothing** outside the tab (no web push, no email). Account page still lists push toggles. |
| Returning, 14+ days | Start Here gone | same | There is no "what's new" or feature spotlight anywhere (grepped web and app). Features shipped since onboarding (Lineup Planner, Manager Tendencies, GM Targets, Playoff Odds what-if) are never introduced to existing users. |
| Empty states | Teach well in places ("All quiet", "No trade history yet") | EmptyState component | Most empty states say what is missing but give no action; they teach "no", not "do this". |

The signup carousel advertises 8 features (Game Plan, Trade Hub, Matchup, Lineup Planner, Player Quick View, Playoff Odds, Manager Tendencies, Waivers). After signup, four of those (Lineup Planner, Player Quick View, Playoff Odds, Manager Tendencies) have no introduction and no stable entry point; users have to stumble on them.

### 4.2 Premium value at the moment it matters

What works: Trade Hub shows "Free: showing 2 of 8 trade ideas, Upgrade"; Today shows "Free: up to 4 next moves, Upgrade"; Waivers says what Premium adds in one line.
What does not (screenshot 04): Draft Center, Live Draft, Commissioner, College Scouting, Portfolio and Games what-if each show **one paragraph and a single Upgrade button**, with no mock, no example number, no "what free includes", and no marker in the nav that the page is gated. A user pays attention to the paywall only after tapping through.

Constraints respected in the proposals: guests may not buy (CTA for a guest must be "Create account", already the `guestUpgrade` flow), analytics stays off, legal items are held.

Inconsistency: backend wall copy says "Pro feature" (Draft Center, College Scouting, Exposure, Playoff Odds, Commissioner) while several web fallbacks and Live Draft/GM Plan/Portfolio/Trade Finder say "Premium feature", the route is `/premium`, the app row says "Premium", and billing plans are "Pro". The 2026-11-02 audit (P10) already asked for one word.

## 5. Naming and IA consistency (web vs app, nav vs title vs content)

| Topic | Observation | Suggested fix |
|---|---|---|
| Trade Hub / Trades / Finder / Analyzer | Nav "Trade Hub"; app route `Trades`; three sub-pages with three titles; Trade History a fourth link; Analyzer page H1 is the league name with "Trade Analyzer" as a tiny kicker | Keep "Trade Hub" as the one word; tabs: Ideas, Finder, Analyzer, History |
| More vs Account | App "More" = Account + preferences + Trade History + Live Draft + College + Team Situation + Guess leaderboard + push + legal. Web "MENU" = legal + Account + sign out. Web sidebar General holds Trade History/College/Community | One definition: "Account" (identity, billing, settings, legal); move feature rows out of More |
| Players vs Rankings | Nav "Players" (subtitle "Search, rankings, and player insights") and nav "League Rankings" (power rankings); the Rankings page opens with Standings | Rename the page "League" or reorder so the title matches the first section |
| Games | Contains season simulator, playoff odds what-if and pick'em; users looking for "Playoff Odds" will not open "Games" on web; app has a separate Playoff Odds row | One name ("Playoff Odds") for the sim; "Games" for pick'em/guess only |
| Home | Subtitle "Switch leagues and manage account" but there is also Account | "My Leagues" |
| GM Plan | Absorbed Team Situation and GM Targets; app still has More > Team Situation; PostureChip still links to the old route | Link the posture chip straight to the GM Plan tab |
| Alerts | Header bell and nav say Alerts; Dashboard chip says "3 to watch"; page can say "All quiet" (carried F11) | one vocabulary: "alerts" |
| Pro vs Premium | See 4.2 | pick one |
| Page title vs H1 | H1 is the league name on Alerts, My Team, Players, Rankings, Trade Hub/Finder/Analyzer, GM Plan, Recaps; the page name on Matchup, Waivers, Games, News | Page name as H1, league as kicker (carried P7) |
| Browser tab title | Every in-app page was just "FantasyDesk" | **Fixed in PR** (web) |
| Orb | aria-label "Open GM menu"; sheet title "Where to go"; sidebar has no label; visually a logo | name it (decision D2) |
| Platform parity | Community, Trade History, College Scouting, Playoff Odds, Team Situation, Pick Detail, Premium row, recap/portfolio/compare share, push, "since last check-in", replay tutorial all differ | table in section 2; each is a decision, not a quick win |

## 6. Three IA proposals

Current primary nav for reference (phone orb sheet / desktop sidebar):

```
LEAGUE     Dashboard | Alerts | My Team | Matchup | Waivers | Players | League Rankings   (+ Playoff Odds on app)
GM TOOLS   Trade Hub | GM Plan | Draft Center | Live Draft | League Recaps | Games | Commissioner
GENERAL    Home | Portfolio | News | Trade History | College Scouting | Community  (app: Premium | More)
Header     search | bell | MENU(legal/account)        Phone: orb (bottom centre, logo only)
```

### Proposal A: minimal, label and link fixes (no restructure)

```
Orb / sidebar (same 3 groups, same order)
  LEAGUE     Dashboard | Alerts | My Team | Matchup | Waivers | Players | League Rankings | Playoff Odds (web+app)
  GM TOOLS   Trade Hub | GM Plan | Draft Center [Pro] | Live Draft [Pro] | League Recaps | Games | Commissioner [Pro]
  GENERAL    My Leagues | Portfolio [Pro] | News | Trade History | College Scouting [Pro] | Community
  ACCOUNT    Premium | Account (replaces "More"/"MENU")
Header: search | bell | Account      Orb gets a text label "Menu" on first visits
Every dead-end screen gets a "what to do next" row (shipped for Alerts, Matchup)
```
- Changes: Pro lock markers in nav; Premium + Account rows on web; Community and Trade History/College rows in the app orb; page-name H1; signed-in landing leads with "Connect your league"; per-page tab titles; one Pro/Premium word; web "since last visit" strip on Dashboard.
- Pros: days of work, no URL or muscle-memory change, fixes most of U1/U2/U5/U6. Cons: the list stays flat at ~22 rows; does not fix the day-2 loop on its own. Effort: S-M (1-2 weeks incl. app). Risks: low; nav-label changes touch tests and screenshots; lock markers need the entitlement in the orb on both platforms.
- Fixes: dead ends (3.1/3.2), parity rows (5), naming (5), paywall visibility in nav (4.2), tab titles.

### Proposal B: six destinations (Dashboard, My Team, Trade Hub, League, Draft Center, Research), orb everywhere

```
Phone: bottom bar of 5 + orb     Desktop: sidebar of 6 groups, each with sub-tabs
  Dashboard     Today, Alerts, Start here / What changed, Portfolio (multi-league), Playoff odds strip
  My Team       Roster | Lineup (Matchup + planner) | Waivers | GM Plan | GM Targets
  Trade Hub     Ideas | Finder | Analyzer | History | Community
  League        Standings + Playoff Odds | Power rankings | Managers | Recaps | Games | Commissioner
  Draft Center  Picks | Live Draft | College Scouting | Rookies
  Research      Players | Compare | News | Methodology
Orb: floating on every page and every width ("Ask / go anywhere": search, jump list, current-page actions)
Header: league switcher | bell | Account (identity, billing, push, legal)
```
- Pros: ~20 destinations become 6 mental buckets that match what people do; every tool lives next to its siblings (Matchup beside Waivers, Manager profiles beside Rankings, Compare beside Players); moves feature rows out of More; the tab bars already exist (Trade Hub, Games, Recaps) so the pattern is known. Cons: biggest change; URLs move (301s and deep links, push payloads, share-card QR bridges); each parent needs a good landing view; five tabs plus orb is tight at 390px.
- Effort: L (4-6 weeks, web + app, with redirects and analytics-safe route changes). Risks: breaking bookmarks and push deep links, retraining current users, doing web and app out of step; the prior decision to hide Finder/Analyzer from nav shows the owner prefers fewer rows (this continues that direction).
- Fixes: all of A's structural findings plus U4 (the grouping itself teaches features) and the 20-row list.

### Proposal C: task-based "what do you want to do" hub

```
Primary nav = Home + 5 verbs (each opens a card hub, then the existing page)
  Win this week      lineup, matchup, waivers, alerts
  Make a trade       ideas, analyzer, finder, history
  Plan the future    GM plan, draft center, picks, scouting, live draft
  Scout the league   rankings, playoff odds, recaps, managers, commissioner
  Look someone up    player search, compare, news
Orb = same verbs + search
```
- Pros: best match for first-time users and for "I have a problem" intent; each verb page can show the live state ("Lineup: check", "2 waiver adds", "1 trade idea") so it doubles as a utilization surface. Cons: adds a layer (two taps to anything), power users lose direct rows, verb names need research (what is "Plan the future" to a redraft player?), and every verb page is new design work. Effort: L-XL. Risks: slows expert users and adds a screen that duplicates the Dashboard.
- Fixes: day-1/day-2 guidance and the "so many features" feeling, but fewer of the dead-end and parity problems.

### Recommendation

1. **Do A now** (it is mostly small, and the largest lift for utilization is dead ends, lock markers and the return loop, none of which need new IA).
2. **Adopt B's six groups as the target**, delivered in two stages that do not break URLs: first as the section headers in the orb/sidebar (labels only: Dashboard, My Team, Trade Hub, League, Draft Center, Research), then as real parent pages with tabs after a click test. The GM orb becomes available at every width.
3. **Use C inside the Dashboard**, not as a nav: turn Start Here into a progressive checklist by task ("Win this week", "Make a trade", "Plan the future") with live state, and add the "what changed" strip on web.
Reason: B matches how the owner already pruned nav (Finder/Analyzer into tabs, GM Targets/Team Situation into GM Plan), A avoids a big-bang rewrite, and C's value is guidance, which belongs on the Dashboard.

## 7. Quick wins vs decisions

### 7.1 Shipped as small PRs (not merged; web + app parity)

| PR | Change | Platform | Verified |
|---|---|---|---|
| #1630 NextSteps (Alerts + Matchup) | A shared "What to do next" / "Fix a weak spot" link row (waivers, trade ideas, lineup, roster) at the bottom of Alerts (including "All quiet") and Matchup | web + app | web: unit tests, 390px screenshots; app: tsc, CI only (not run on a device) |
| #1631 Waivers: Sleeper link | "Open your league in Sleeper" next to "Place claims in Sleeper; we don't submit them"; omitted for ESPN/Fleaflicker/MFL | web + app | web: unit tests, screenshot; app: tsc, CI |
| #1632 Page titles (web) | Tab/history/bookmark title becomes "Waivers · FantasyDesk" etc. via a tiny server layout per segment, using the same labels as the nav | web only (the app has no tab titles) | unit tests, headless check of the rendered `<title>` |

Before/after screenshots: `docs/assets/ux-utilization-audit-2026-11-03/08-before-after-alerts-waivers-390.jpg`, `09-before-after-bottoms-alerts-matchup-390.jpg`.

### 7.2 More quick wins not yet shipped (safe, still small)

- Q1 Trade Analyzer verdict: a "See other packages in Trade Finder" link carrying the same assets (the TradeBridge already carries `?a=&b=`). Needs product to confirm Finder is Pro-only wording.
- Q2 My Team: a "Fill this need: Waivers / Trade ideas" link on each need row in Team Analysis (needs data already computed).
- Q3 Empty-state actions: Trade History ("Analyze a trade"), Community ("Share a trade from the Analyzer"), Player Compare ("Browse players" exists).
- Q4 `PostureChip` link: pass `?name=` / link to GM Plan directly.
- Q5 Web: remove or relabel the Account push toggles ("Push is delivered by the mobile app") until web push exists.
- Q6 Dashboard "More" summary text: say what is inside ("League Pulse, Guess the Player").
- Q7 Header orb: add a visible "Menu" text label (needs design sign-off, so also a decision).

### 7.3 Decisions needed from coridian_

| # | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | Paywall pages: show a blurred/sample preview and "what free includes" | none / static example / real data blurred | real data blurred or a static example; no analytics added; guests see "Create account" |
| D2 | Name and show the orb/nav entry | add "Menu" label, rename header MENU to "Account", move legal into Account | do all three (carried P2) |
| D3 | Alerts/News to action: add an `action` field per item (e.g. injury on a starter -> Matchup, free agent -> Waivers) | API change vs client heuristics | API field, so web and app stay identical |
| D4 | Trade verdict onward links: Finder, partner manager profile | add both | yes |
| D5 | Player quick view: show "Add via Waivers" for free agents and "owned by X" with link | | yes |
| D6 | Waiver "suggested drop" | build candidate model vs not | needs a real model; do not ship a rule-of-thumb |
| D7 | Web return loop: web push, email digest, or "what changed since last visit" strip | pick at least the strip | strip first (reuse mobile `sinceLastCheckIn`), push later |
| D8 | Nav lock markers (Pro/Premium) and the one paid word | Pro vs Premium | pick one and apply to backend copy too |
| D9 | App parity: Community row, Trade History row, Playoff Odds on web | add / leave | add, consistent with B |
| D10 | Which IA proposal | A, then B in stages (recommended), C | see section 6 |
| D11 | Start Here v2 (task-based progressive checklist) and an optional "What's new" card for existing users | | yes, inside the Dashboard |
| D12 | Signed-in landing (carried P1) | | do it |

## 8. Findings summary (ranked)

| ID | Sev | Finding | Fix |
|---|---|---|---|
| U1 | H | Paid pages: one paragraph and no preview; nothing in nav marks them | D1, D8, A |
| U2 | H | Dead-end screens (Alerts, Matchup, My Team, Rankings, Recaps, Games, News, verdict, empty states) | shipped for Alerts/Matchup; Q1-Q3, D3-D5 |
| U3 | H | No return loop on web: no push, no email, no "what changed"; push toggles shown on web | D7, Q5 |
| U4 | M | Onboarding sells 8 features; 4 have no introduction or stable entry (Planner, Quick View, Playoff Odds, Manager Tendencies); checklist is 3 "look at" steps and then gone | D11 |
| U5 | M | Web/app drift (Community, Trade History, College, Playoff Odds, Team Situation, Pick Detail, Premium, shares, since-last-check-in) | D9 |
| U6 | M | Naming (Trade Hub/Trades, More/Account/MENU, Games vs Playoff Odds, Players vs Rankings, Pro vs Premium, H1) | section 5 |
| U7 | M | Orb is a bare logo, half-height sheet hides GM Tools/General, MENU is not navigation | D2 |
| U8 | M | No in-page back on web; Compare/Profile/Analyzer lack a return link | decision with B |
| U9 | L | Single-entry features: Manager profile, Lineup Planner, Referral, Account push | A / B |
| U10 | L | Every in-app tab titled "FantasyDesk" | **shipped** |
