# Feature map (2026-11-03)

Why: coridian_ worry, "so many features, but it's not organized correctly, and so many things may be hidden to users." This is the one list of every user-facing feature, its home, its other doors, and whether it is Pro.

Method: code-read only (nav lists `web-next/src/lib/navDestinations.ts`, `mobile/src/components/GmOrb.tsx`, `mobile/src/screens/MoreScreen.tsx`, `RootNavigator.tsx`, route folders under `web-next/src/app`, Pro gates in `services/mobile_api_service.py`). Nothing was click-tested. W = web, A = iOS/Android app.

Pro column: **Pro** = the server returns `premium_required` / withholds the data for Free. **Part** = free page, some content Pro. Free caps (dashboard items, trade ideas, GM targets, leagues) are server constants; no numbers are repeated here.

The user-facing version of this list is the in-app page "What FantasyDesk can do" (W `/features`, A `Features` screen; source `lib/featureCatalog.ts` on each side).

## 1. League features (open for the current league)

| Feature | Home W | Home A | Other doors | Pro | W vs A / notes |
|---|---|---|---|---|---|
| Dashboard | `/dashboard/[id]` | `Dashboard` | Nav, orb, Home league card | Part (free sees a capped list of action items) | A has a playoff-odds strip; W does not |
| Alerts | `/alerts/[id]` | `Alerts` | Nav, orb, header alerts dropdown (W) | Free | |
| My Team | `/my-team/[id]` | `MyTeam` | Nav, orb, Dashboard "Open My Team" | Free | Age tile opens `Teams` age list on A |
| Matchup | `/matchup/[id]` | `Matchup` | Nav, orb, Start here card, Dashboard card | Free | Planner on both |
| Waivers | `/waivers/[id]` | `Waivers` | Nav, orb, Start here, Dashboard now strip | Part (FAAB shortlist, usage stats are Pro) | Another change is editing this screen; not touched here |
| Players (search, rankings) | `/players/[id]` | `Players` | Nav, orb search box | Free | |
| Player profile / quick view | `/players/[id]/[playerId]`, quick-view sheet | `PlayerDetail`, quick-view sheet | Tapping any player anywhere, orb search | Free (advanced usage stats Pro) | A has Percentile sheet; W has Percentile explorer |
| Player Compare | `/player-compare/[id]` | `PlayerCompare` | **Only** from a player's page or quick view (and GM Plan / Live Draft links on W) | Free | **One hidden way in** on both |
| League Rankings (power) | `/league-rankings/[id]` | `Teams` | Nav, orb, Dashboard rank strip | Free | |
| Playoff Odds | `/league-rankings/[id]#playoff-odds` | `PlayoffOdds` | Nav, orb, Games | **Pro** | W is a section of League Rankings; A is its own screen |
| Trade ideas ("Trade Hub", A "Trade Block") | `/trade-hub/[id]` | `Trades` tab `block` | Nav, orb, Dashboard trades block, Start here | Part (free sees a few ideas) | |
| Trade Analyzer | `/trade-analyzer/[id]` | `Trades` tab `make` | **Tab inside Trade Hub**, "Add to Trade" in quick view, shared deep links. No nav row on purpose | Free | Deep tab, not in nav |
| Trade Finder | `/trade-finder/[id]` | `Trades` tab `search` | **Tab inside Trade Hub**, "Find trades" in quick view | **Pro** | Deep tab, not in nav |
| GM Plan (includes Team Situation, GM Targets) | `/gm-plan/[id]` | `GmPlan` | Nav, orb, More > Your Team > Team Situation (A), header stance button (A) | Part (focus areas Pro; GM Targets capped for Free) | `/team-situation`, `/gm-targets` and A `TeamStance`, `GmTargets` are redirects into GM Plan |
| Draft Center | `/draft-center/[id]` | `DraftCenter`, `PickDetail` | Nav, orb | **Pro** | |
| Live Draft | `/live-draft/[id]` | `LiveDraft` | Nav, orb, More > Your Team (A) | **Pro** (board and picks; discovery is visible) | |
| League Recaps | `/league-recaps/[id]` | `Recap` | Nav, orb, recap-ready card, push | Free | |
| Games (season sim, pick'em) | `/games/[id]` | `Games` | Nav, orb | Part (what-if sim is Pro) | |
| Guess the Player leaderboard | `/guess-the-player-leaderboard/[id]` | `GuessThePlayerLeaderboard` | **W: only from the Guess the Player cards. A: only More > Your Team** | Free | **One way in on each platform** |
| Commissioner | `/commissioner/[id]` | `Commissioner` | Nav, orb | **Pro** (open to any league member with Pro, as shipped) | Includes the Trade veto calculator (section on the same screen) |
| Manager tendencies / manager profile | Sheet from team names in Rankings, Trade Hub | Modal from team names | Only via tapping a manager | Pro (tendencies gate) | Sheet, no page; one way in per surface |
| Evaluation lens (Dynasty / Rebuild / Redraft) | Header chip | Header button | Header only | Free | One door, always visible |

## 2. Account-wide features (not tied to one league)

| Feature | Home W | Home A | Other doors | Pro | Notes |
|---|---|---|---|---|---|
| Home / switch league / add league | `/` | `Home` | Header league switcher, nav | Free (league count capped for Free) | |
| Portfolio | `/portfolio` | `Portfolio` | Nav, orb | **Pro** | |
| News | `/news` | `News` | Nav, orb, header globe (A), player "See all news" | Free | |
| Trade History | `/trade-history` | `TradeHistory` | Nav, orb, More > Your Team (A), trade follow-up prompt | Free | |
| Community trades | `/community` | `Community` | Nav, orb, bottom of Trade History (A) | Free | |
| College Scouting | `/college-scouting` | `CollegeProspects` | W: nav. A: not in the orb; More > Scouting **only if you opted in** on the Dashboard prompt | **Pro** | **A: one way in, and hidden until opt-in** |
| Pro plans / trial | `/premium` | `Paywall` | Nav "Pro", upsell cards, Account billing | n/a | Guests are asked to create an account first, never sold to |
| Account (identity, billing, prefs, push categories, invite link, export, delete, replay tour) | `/account` | `More` ("Account") | Header MENU (W), header "..." (A), nav, orb | Free | |
| Notification settings | Account | More > Notifications | Only there | Free | One door each |
| How We Evaluate | `/methodology` | `HowWeEvaluate` | W: footer/header links; A: More > About only | Free | **A: one way in** |
| Legal pages | `/legal/[key]` | `LegalPage` | Footer / More > Legal | Free | |
| Sample league (no account) | `/sample-league` | `SampleLeague` | Landing button, import form / Home with no league | Free | |
| What FantasyDesk can do | `/features` | `Features` | **New:** Account link (W+A), Start here card link (W+A) | Free | Added in this change |

## 3. Public pages (no sign-in, for search and sharing)

`/dynasty-rankings/[position]`, `/dynasty-players/[slug]`, `/dynasty-trade-value-chart`, `/dynasty-tools`, `/methodology`, share-card images (`/share-card/*`). Web only; they are marketing/SEO surfaces and link into the app. No app twin on purpose.

## 4. Features with only one way in (hidden risk)

1. **Player Compare** (W+A): only from a player's page.
2. **Trade Analyzer and Trade Finder** (W+A): only as tabs inside Trade Hub (plus quick-view shortcuts). Nav rows were removed on purpose (coridian_ 2026-10-17). The new Features page now gives each its own door, deep-linking to the tab on A.
3. **Guess the Player leaderboard** (W: only from the Guess cards; A: only More > Your Team). Not on the new page (a daily game, not a core tool).
4. **College Scouting** (A): only More > Scouting and only after opting in; the new Features page is a second door (shown to everyone, with the Pro tag).
5. **How We Evaluate** (A): More > About only.
6. **Notification settings, Referral/invite link, Replay tour**: Account / More only (normal for settings).
7. **Manager tendencies**: only by tapping a manager name.
8. **Evaluation lens**: header chip only (always visible, so low risk).

## 5. Web vs app differences worth knowing

- Trades: W has `/trade-hub`, `/trade-analyzer`, `/trade-finder` as separate pages with tabs; A has one `Trades` screen with three tabs.
- Playoff Odds: W is a section of League Rankings; A is its own screen.
- Dashboard playoff-odds strip: A only.
- Team Situation / GM Targets: both are sections of GM Plan; A also has a header stance button and a More row.
- Live Draft: A has an extra row in More. Guess leaderboard: A only in More, W only from the Guess cards.
- ESPN leagues feed only some screens on both platforms (`EspnUnavailableScreen`); the Features page links open the normal screens and those show the "not available for ESPN yet" state.
- Public SEO pages: W only.

## 6. Keeping this honest

`featureCatalog.test.ts` (W) checks every Features item opens a real route and matches the sidebar glyph, color and Pro flag; the app test checks every item is a registered screen and matches the GM orb icon/color/Pro flag; the W test also pins the two catalogs to each other. This document is not tested; update it when a feature is added or moved.
