# Information architecture and hierarchy plan (2026-11)

Status: research and plan. **No product code changed.** This PR adds this document and `2026-11-ia-mockups.html`
(390px phone frames, before and after; open it in a browser).

Trigger (coridian_, phone user; mobile is about 95% of users): "overwhelmed by how much information there is and how
poorly organized it is." His example is the Fantasy Sim draft room: a huge on-the-clock card, four stacked tab/filter/sort
rows, PROJ/OVR/ADP chips on the right of each player row, and no at-a-glance "who has been drafted". He wants compact
summaries you tap to expand (site-wide, standing rule), one tab row per page, tabs at the top to tell pages in a category
apart, and a real game plan rather than piecemeal fixes.

Read for this: `CLAUDE.md`, `docs/ui-patterns.md`, `docs/mobile-ux-plan-2026-11.md`, `docs/audits/2026-11-navigation-audit.md`,
`docs/fantasy-sim-mobile-layout.md`, and (from open PR #1871, branch `footer-glass-tabs`) `docs/audits/2026-11-menu-consolidation.md`,
`lib/navCatalog.ts`, `lib/navDestinations.ts`, `lib/pageFamilies.ts`. Facts below are read from code on `origin/main` (and #1871 for the
families). Sizes marked "measured" come from earlier Playwright audits in those docs; sizes marked "est." are my estimates from the
component structure and must be re-measured in Phase 0.

## TLDR

- The problem is not one screen; it is that **every page grew its own stack of cards, tab rows and chips**. Pattern pieces to fix it
  already exist (`Collapsible`, `Sheet`, `FilterSheet`, `StructuredRow`, `PillRow`, `PlayerListRow`, page families in #1871). What is
  missing is **one enforced anatomy** and a lint/test that holds pages to it.
- #1871 (families as tabs) fixes "where is that page" but **adds a second tab row** on pages that already had one (Waivers, Players,
  Draft Center, Recaps). Rule 1 below resolves that: the family strip is the page's only tab row.
- Target: 5 footer tabs, each a family with 2 to 5 top tabs; 12 More-sheet rows disappear (the More sheet drops from about 20 rows to 8).
- Phase 1 (1 week, low risk) fixes the draft room and ships the shared `CompactModule` and row anatomy. Phases 2 to 4 migrate pages one family at
  a time. Everything ships web and app together.
- 8 product decisions are listed in section 6; the top three are the **Fantasy Sim vs Season Outlook rename**, **Draft as a League tab**, and
  **whether Home and Portfolio merge**.

---

## 1. Inventory

### 1.1 How to read it

Columns: **Route** (web) and **App screen**; **Family/tab** today (per #1871); **Modules** in render order; **Size** (phone screens of scroll,
"m" measured, "e" estimated); **Same info elsewhere**; **Tap**: whether the module opens something (Y, partial, N).
"Ctl rows" = tab rows + filter/sort rows stacked above the content on a phone (the number the owner is reacting to).

### 1.2 League-scoped pages (web `/x/[leagueId]`)

| Route / App screen | Family now | Modules (in order) | Size | Same info elsewhere | Tap | Ctl rows |
|---|---|---|---|---|---|---|
| `/dashboard` Dashboard | Today | StartHereCard, SinceLastVisit strip, TeamStatusHero (record, odds, status), DirectionCheckin, NeedsAttention, TodayModule (next moves), FirstValueOffer, TradesBlock (ideas + deadline), My Team 6-tile strip, Guillotine card, Watchlist and alerts, "More" fold (League pulse, 2 mini-games, league type) | 1.4 m (39 text els above fold) | Needs-attention, Today module, Trades block, Watchlist all say "do this next"; My Team tiles repeat My Team + League Rankings; Alerts also in bell | Y (insight links) | 0 |
| `/alerts` Alerts | Today (More row) | Unread filter, event rows (player, type pill) | 1+ e | Dashboard Watchlist; bell dropdown; News | Y | 1 |
| `/my-team` MyTeam | Team: Roster | Title + help, Team snapshot (ring + 6 tiles), Team analysis list + Roster notes + "Act on a need", Roster (tabs Starters/Bench/IR/Taxi/IDP), Composition bar, Keeper candidates | 2.3 e | Snapshot repeats Dashboard My Team strip; analysis repeats TeamStatusHero chips | Y (tiles to boards) | 2 (family strip + roster tabs) |
| `/matchup` Matchup | Team: Matchup | Scoreboard, Lineup comparison (ComparisonHeader + SlotList), Position edges, Matchup insights, Suggested moves, Live feed, planner/swap sheet | 3+ e | Dashboard hero ("favored by"); Waivers suggested adds | partial | 2 (strip + view pills) |
| `/waivers` Waivers | Team: Waivers | Waiver summary, tab row (Recommended/Explore/Watchlist), Priority Adds, FAAB shortlist, Top stash, Bench depth, Droppable players, rec-filter pills, FilterSheet | 3+ e | Players (Explore = all free agents); Dashboard "today's moves" claims | Y | 4 (strip, tabs, rec filter, filter) |
| `/players` Players | Team: Players | Search, position pills, Filters button (+ chips), Sort select, list (PlayerListRow with stats at right), Compare / Add-to-Trade actions | 2.5 e | Waivers Explore; Draft Center Scouting; orb search | Y | 4 (strip, position, filters, sort) |
| `/players/[leagueId]/[playerId]` PlayerDetail | n/a | Header, tiles (Value, OVR, Usage) each TapForWhy, tabs (Overview, Model, News ...) | 2 e | PQV sheet shows same tiles | Y | 1 |
| `/player-compare` PlayerCompare | Team (orb) | Two pickers, side-by-side stats | 1.5 e | PQV | partial | 0 |
| `/gm-plan` GmPlan | tools (More) | Tabs Overview / Trades / Core / Watching / Season Outlook; Plan snapshot grid, Team situation card, Trade ideas, Watching, Protected core, Season outlook | 1.4 m (free state) | Trade ideas = Trade Hub; Season outlook = Games > Season Outlook = League Rankings > Playoff Odds; GM targets/Team situation (redirects) | Y | 2 |
| `/fantasy-sim/[leagueId]` FantasySim ("Season Outlook") | GM Plan tab | Playoff odds, projected finish, what-if controls | 2 e | Dashboard hero odds; Games > Season Outlook; League Rankings > Playoff Odds | partial | 1 |
| `/draft-center` DraftCenter | Team (via More) | Tabs Overview / Picks / Scouting; Draft Capital, Future Capital, Strategy posture tiles, League Draft Decision Signals (StructuredRows), Partner Discovery, pick rows, scouting list | 2.5 e | Trade Hub (pick trades); Players | Y | 3 |
| `/live-draft` LiveDraft | Team (via More) | Draft status, position filter, recommendations + score breakdown, pick plates, trade evaluator | 3 e | Draft Center | partial | 2 |
| `/trade-hub` TradeHub | Trades: Hub | Filters, Deadline card, Hold card, idea cards (full body each), Multi-team ideas, Value signals | 3+ e | Dashboard Trades block; GM Plan Trades + Trade ideas | Y | 2 |
| `/trade-finder` TradeFinder | Trades: Finder | Shop selector (2 selects + pills), asset rows, results as idea cards | 2.5 e | Hub ideas | Y | 3 |
| `/trade-analyzer` TradeAnalyzer | Trades: Analyzer | Mode toggle (2-team/multi), team select, You send / You receive (TradePickerSheet), verdict, odds effect, lineup warnings, next move, share toggle | 3 e | Hub idea "Analyze" | Y | 2 |
| `/trade-offer` TradeOffer | flow | Build an offer | 1.5 e | Analyzer | Y | 0 |
| `/trade-history` TradeHistory | Trades: History | Your shared and confirmed trades | 1.5 e | Community; Account (app) | Y | 2 |
| `/league-rankings` Teams | League: Rankings | Your standing tiles, Power, Franchise, Starter, Bench, Roster age boards (one section each), Playoff odds (Pro), manager sheet | 4 e | Dashboard My Team tiles; Games > Season Outlook; GM Plan Season outlook | Y | 1 |
| `/league-recaps` Recap | League: Recaps | Archive week pills, recap story, history (season pills + filter pills), League memory view pills, Roundup tab | 3+ e | News; Alerts | partial | 4 (the worst case) |
| `/games` Games | League: Games | Tabs Season Outlook / Pick'em; what-if sim (Pro), league sim table, Pick'em matchups | 2.5 e | GM Plan Season Outlook | Y | 2 |
| `/commissioner` Commissioner | More (Pro) | Calendar, lineup efficiency, flagged teams, "worth a look", veto calculator | 3 e | League Recaps | partial | 2 |
| `/college-scouting` | Draft Center tab | Prospect list, my report | 2 e | Draft Center Scouting | Y | 2 |
| `/guess-the-player-leaderboard` | none | Leaderboard | 1 e | Dashboard mini-game | N | 0 |
| `/team-situation`, `/gm-targets` | redirects to GM Plan | none | n/a | n/a | n/a | n/a |

### 1.3 Account-wide and outside-league pages

| Route / App screen | Footer (outside league) | Modules | Size | Same info elsewhere | Tap |
|---|---|---|---|---|---|
| `/` Home | Home | League list, "continue", connect/onboarding | 1 m | Portfolio | Y |
| `/portfolio` Portfolio (Pro) | Portfolio | Saved leagues with standing/odds, exposure, remove league | 1+ m (paywall card for free) | Home; Dashboard hero | Y |
| `/gm-game` GmGame ("Fantasy Sim") | Fantasy Sim | Hub (saved games), setup, then the game (section 1.4) | see 1.4 | none | Y |
| `/news` News | News | News feed (player rows, event pills) | 2 e | Alerts; PQV News tab | Y |
| `/community` Community | More | Craziest trades this week, shared trades feed | 2 e | Trade History | Y |
| `/account` More/Account | More | 8 equal cards (Pro, billing, invite, prefs, college, sign-out, delete) | 2.9 m | `/premium` | Y |
| `/premium` Paywall | More | Plans | 1.5 e | Account | Y |
| `/connect-league`, `/sample-league` | n/a | Connect form; sample dashboard | 1 / 2.4 m | Dashboard | Y |
| `/features`, `/methodology`, `/legal/*`, `/design`, `/founder-analytics` | links only | static / internal | n/a | n/a | n/a |
| SEO surface: `/dynasty-players/[slug]`, `/dynasty-rankings/[position]`, `/dynasty-tools`, `/dynasty-trade-value-chart`, `/trade-analyzer` (no league), `/trade-analyzer/bridge` | not in app nav | Public pages | n/a | n/a | out of scope here (note: the public chart uses "Trade value", which is correct for the real product; only the Sim bans it) |

### 1.4 Fantasy Sim game (`/gm-game`, app `GmGame`): the same problem, inside one page

Phone shell: header + game orb (Home, Team, Players, Trades, League, More). Source: `SimGame*.tsx`.

| Screen | Modules | Size | Ctl rows | Notes |
|---|---|---|---|---|
| Hub / Setup | saved games, new game | 1 e | 0 | |
| **Draft room** (`SimGameDraft`) | On-the-clock card (header, progress bar, ETA block, recent picks ticker (hidden under md), best-available strip, needs pills, suggestion + Draft button, Auto-pick button); tab row Players / Board / Queue / Roster / Picks; search; position pills (ALL QB RB WR TE FLEX K); Sort pills (ADP / Proj / **Trade value**); rows with PROJ, OVR, ADP chips at the right edge and Queue + Draft buttons | 2.7 m (card about 400px e) | **4** | Board (rounds x teams grid) and Picks are tabs; the Players list is the default. Value labeled "Trade value" in the sort and in the on-the-clock hint ("Value 91") |
| Home | matchup card, checklist, reserves strip, inbox, waiver card, bye card, injuries, collapsed League section (standings, hot/cold, moves) | 2.5 m | 0 (already collapsible) | closest to the target |
| Team | lineup, bench, IR, taxi rows (SimRosterLine: PROJ, OVR labeled stats) | 2.25 m | 1 | |
| Players | search, position pills, 2 selects, All players / Waivers toggle, queued claims | 2.8 m | 3 | |
| Trades | Inbox / Make an offer / My block pills, offer cards, build screen | 1.6 m | 1 | uses "Trade value" |
| League | Standings / Scores / Feed / Teams / Players pills | 1.4 m | 1 | |
| Offseason, Recap (story), Final grade | StoryCarousel, Season in Review (4 tabs) | 2.2 m | 1 | |
| More sheet | Rules, Reset week, Delete game | n/a | n/a | |

### 1.5 Global chrome

| Surface | Contents | Duplicates |
|---|---|---|
| Footer (in league, #1871 glass) | Today, Team, Trades, League, More | |
| Footer (outside) | Home, Portfolio, Fantasy Sim, News, More | |
| More sheet (~20 rows; `navCatalog.ts`) | League: Today, Alerts, My Team, Matchup, Waivers, League Rankings, Players. GM tools: Trade Hub, GM Plan, Draft Center, Live Draft, League Recaps, Games, Commissioner. General: Home, Portfolio, Fantasy Sim, News, Community. Account: Pro, Account | 14 of the 20 rows are also footer tabs or family tabs |
| Header | back, title, league chip, search, bell | Alerts row |
| Orb search | "Page > Tab" rows from `navDestinations.ts` | |

### 1.6 What the inventory says

1. **Control-row stacking is the owner's pain, and it is page-specific**: Recaps 4, Waivers 4, Players 4, Draft room 4, Draft Center 3, Players (sim) 3.
2. **The same decision is told 3 to 4 times**: "what should I do" (Dashboard x4, GM Plan, Hub, Waivers), "season outlook" (3 pages, 3 names), "my team stats" (Dashboard, My Team, League Rankings).
3. **Stats are right-aligned chips on rows** (PlayerListRow), which squeezes the name column on a phone.
4. **Many modules are always open and not tappable as a summary**. Where compaction exists (sim Home `Collapsible`, Dashboard "More") it is local to that page.
5. #1871's families fix discoverability but multiply tab rows.

---

## 2. Information hierarchy rules (enforceable)

Each rule has a check. Phase 0 turns the checks into a unit test + a Playwright scan that fails CI (the existing `sim_layout_playwright` scripts are the model).

**R1. One tab row per page.** The only tab row is the family strip (top, glass, `PageTabBar`). A page's internal views are not tabs: they are
(a) sections (collapsible), (b) a value in the control row (R2), or (c) a sheet. *Check:* at most one `role="tablist"` / `PillRow` used as tabs per route; the strip has 2 to 5 tabs.
Pages with no family (Today/Alerts is a family of 2) never show a strip of 1.

**R2. One control row.** Search, position, sort and filters share a single 44px row: `[search icon] [primary pills, scroll] [Sort button]`, with everything
else behind a **Filters** button (existing `FilterSheet`, count badge). Never a second row of pills, never a visible `<select>` row.
*Check:* at most one element with `data-ctl-row` per page, height 44px.

**R3. Every hero or summary module has a compact form.** Compact = 1 or 2 lines (title line + one status line), 56px min, a chevron, tappable whole-row.
Tap expands in place (up to a screen of body) or opens a `Sheet` (R5). Default state: only the top 1 to 3 modules are expanded and only when they ask
for an action. Open state is remembered per id (already in `Collapsible`). *Check:* a page may not render a card taller than 120px in its default state unless it is the hero or contains a primary action.

**R4. One shared module and one shared row.**
- `CompactModule` (promote `Collapsible`/`SimFold` to `components/ui/CompactModule.tsx` + mobile twin; lib twin for the open-state key and the density tiers): props `id, title, summary (1 line), badge, accent, defaultOpen, mode: "inline" | "sheet", children, sheetTitle`.
- `DataRow` anatomy (extend `PlayerListRow`/`StructuredRow`, do not create a third): `[lead: pos badge or avatar] [name (1 line, truncate)] [primary right element] [chevron]` with a **chip line under the name**: meta text (team, age) then at most 3 labeled chips. The right edge holds one thing only: the action (Draft, Add, Queue) or one number (rank, score). *Check:* no `PlayerListStat` renders in the right cluster on screens narrower than 480px.
- No page may define its own card chrome: `AccentCard`/glass only through these two.

**R5. Sheets vs pages vs inline.**
| Content | Where |
|---|---|
| A decision or an action the user takes now | page (list row) |
| Detail of one row (why a trade, a player's full card, a manager) | `Sheet` (one at a time, existing overlay stack) |
| The full version of a summary (full draft board, all 6 tiles, all alerts) | sheet or inline expand, never a new page unless it is a destination |
| Filters beyond the primary pills; sort beyond 3 options | `FilterSheet` |
| Explanations of a number | `TapForWhy` sheet, never visible paragraphs |
| A different job (Analyzer vs Ideas) | a different tab (R1) |

**R6. Density tiers.**
| Tier | Height | Use | Example |
|---|---|---|---|
| T0 glance | 44 to 56px, 1 line | status, counts, "Do now 3" | on-the-clock bar |
| T1 row | 56 to 72px, name + chip line | list rows | player row, trade idea row |
| T2 card | up to 120px | the hero, a primary action | Today hero |
| T3 expanded | up to ~1 screen, inline | module body | team tiles |
| T4 sheet | up to 90% screen | detail | PQV, full board |
Default page budget: first screen shows the hero + 3 to 5 T0/T1 items; total default scroll at most 2 screens (measured with the Playwright scan).

**R7. Stat chips go under the name, in a fixed order**: position-specific meta first (team, age, bye/injury), then at most 3 of PROJ, OVR, ADP (draft) or Rank, Record (league) or Win/Confidence (trades). One tone per chip (existing `ToneBadge` tokens). Number-bearing chips are `TapForWhy`.

**R8. Naming (one word, one thing).**
- **Fantasy Sim** = the sandbox draft-and-play game (`/gm-game`). Keep (store/marketing name).
- **Season Forecast** = the real league's rest-of-season simulation (today "Season Outlook", `/fantasy-sim/[id]`, also "Season Sim" in Games, also "Playoff Odds" in League Rankings). One page, one name; the others become sections of it or links to it. Route `/fantasy-sim/[id]` stays and gets a `/season-forecast` alias later (no link breaks).
- **Today** (not "Dashboard") everywhere; **Plan** for GM Plan in tab labels (page title "GM Plan"); **Ideas** for Trade Hub's tab (page title stays "Trades").
- **Fantasy Sim never says "Value" or "Trade value"** (draft, rows, sorts, hints, chips). Allowed labels: PROJ, OVR, ADP, Rank, Edge. The backend sort key `value` and the field `value` are unchanged; only the label changes (sort "OVR" maps to the existing ordering; see Phase 1 note on what that sorts by). The sim's trade screens need a number to compare offers: use "Sim rating" or the existing balance bar with no label (decision D4).
- The real product keeps "Trade Value" (it is correct there, and a separate concept).

**R9. Tappable, always.** Every stat about the user's league has an insight destination (`lib/insightLinks.ts`, already enforced). Compact modules inherit this: the collapsed line is the link or the expander, never dead text.

**R10. Fantasy Sim isolation.** Sim layout/label rules never import into or change real-league logic. Shared components change (R4) but sim-specific copy and data stay in `lib/sim*`. Nothing here calls `rankings.load_players` or touches `data/players.db`.

---

## 3. Target information architecture

### 3.1 In a league (footer: Today, Team, Trades, League, More)

```
Today                         strip: Today | Alerts (count badge)
  Today                       hero line, Do now (merged), My team, Watchlist, League pulse, Play
  Alerts                      unread/read list (one filter in the control row)

Team                          strip: Roster | Matchup | Players | Waivers | Plan
  Roster                      summary line (expands to 6 tiles); sections Starters / Bench / IR+Taxi / Mix+keepers
  Matchup                     scoreboard hero line; sections Lineup, Edges, Suggested moves (live feed inline)
  Players                     control row (search, position, sort, Filters); list; Compare lives in the row action
  Waivers                     control row (View: Recommended / Explore / Watchlist as the one selector); list
  Plan                        (GM Plan) stance line; sections Targets, Core, Trade moves (link to Trades); no inner tabs

Trades                        strip: Ideas | Analyzer | Finder | History
  Ideas (Hub)                 window line, control row (Filters, Sort), idea rows -> sheet; Multi-team, Market movers modules
  Analyzer                    2-team / multi-team as a toggle inside the page (existing); verdict in sheet
  Finder (Pro)                shop one player or pick; results as idea rows
  History                     my trades; shared trades as a section

League                        strip: Standings | Recaps | Draft | Pick'em
  Standings                   your standing line; control row metric chips (Power, Franchise, Starters, Bench, Age, Odds); one list
  Recaps                      week pills move into a single "Week" button (sheet); Roundup and Memory become sections
  Draft                       (Draft Center Overview+Picks), Live Draft entry as a banner when a draft is live, Scouting as a section/sheet
  Pick'em                     weekly picks; "Season Forecast" is a section on Standings (odds metric) and a link from Today hero

More (8 rows)                 Home (leagues), Portfolio, Fantasy Sim, News, Community, Commissioner (Pro, commissioners only), Pro, Account
```
Notes: Forecast (Season Outlook + Games "Season Sim" + Playoff Odds) merges into **Standings > Odds** (metric chip) plus a "Season Forecast" detail
sheet/page reached from the Today hero and the Plan page. Commissioner stays a More row because it is rare; it could become a League tab for commissioners (D6).

### 3.2 Outside a league (footer: Home, Portfolio, Fantasy Sim, News, More)

```
Home        league list (+ "continue")            D3: Home and Portfolio could be one "Leagues" tab (Leagues | Portfolio strip)
Portfolio   standings across leagues (Pro)
Fantasy Sim hub; in a game the game's own shell (below)
News        strip: News | Trades feed (Community)   (Community leaves More)
More        Pro, Account, Methodology, Legal, Help
```

### 3.3 Fantasy Sim game (own shell; orb stays)

Orb pages: **Home, Team, Players, Trades, League, More** (unchanged names). Changes:
- **Draft room**: one page with the compact bar, picks strip, mini board, one strip (Players | Queue | Roster), one control row (see mockup 1). Board and Picks tabs are removed.
- **Team**: Lineup/Bench/IR/Taxi become collapsible sections (the `Collapsible` pattern already exists); no tab row.
- **Players**: the All players | Waivers toggle becomes the single selector in the control row; position pills + Sort button; the two selects move into Filters.
- **League**: keep the 5-view strip (it is the one row) but make it Standings | Scores | Feed | Teams (Players moves into Teams as a section).
- Trades: strip Inbox | Offer | Block is already one row; keep.

### 3.4 Mapping from the current routes (URLs do not change in Phase 1 to 3)

| Current | Target (category > page > tab) | More row removed |
|---|---|---|
| `/dashboard` | Today > Today | Today |
| `/alerts` | Today > Alerts | Alerts |
| `/my-team` | Team > Roster | My Team |
| `/matchup` | Team > Matchup | Matchup |
| `/players`, `/player-compare` | Team > Players (Compare = row action) | Players |
| `/waivers` | Team > Waivers | Waivers |
| `/gm-plan` (+ GM targets) | Team > Plan | GM Plan |
| `/draft-center`, `/college-scouting` | League > Draft (Scouting = section) | Draft Center |
| `/live-draft` | League > Draft (banner when live; own route stays) | Live Draft |
| `/trade-hub` | Trades > Ideas | Trade Hub |
| `/trade-analyzer`, `/trade-offer` | Trades > Analyzer | |
| `/trade-finder` | Trades > Finder | |
| `/trade-history` | Trades > History | |
| `/league-rankings` (+ Playoff Odds) | League > Standings (odds = metric chip) | League Rankings |
| `/fantasy-sim/[id]` + Games "Season Outlook" | Season Forecast (section of Standings, link from Today/Plan) | |
| `/league-recaps` | League > Recaps | League Recaps |
| `/games` (Pick'em) | League > Pick'em | Games |
| `/commissioner` | More (or League tab for commissioners, D6) | |
| `/community` | News > Trades feed | Community |
| `/news` | News > News | |
| `/portfolio`, `/` | Home / Portfolio (D3) | |

Rows removed from the More sheet: **Today, Alerts, My Team, Matchup, Waivers, League Rankings, Players, Trade Hub, GM Plan, Draft Center, Live Draft, League Recaps, Games, Community** (14), leaving Home, Portfolio, Fantasy Sim, News, Commissioner, Pro, Account (+ a Help row). Orb/sidebar search keeps finding every page as "Page > Tab" (`navDestinations.ts` tabs stay), so nothing becomes unfindable.

Implementation note: families are data in `lib/pageFamilies.ts` (#1871). The 5-tab Team family and the extra Today family are data edits plus
`shellActiveTab` mapping updates (draft-center/live-draft move from Team to League there; `pageFamilies.test.ts` pins this).

---

## 4. Mockups

`docs/audits/2026-11-ia-mockups.html`: self-contained, 390px frames, tokens copied from `globals.css`. Before and after for **Draft room, Team, Trades,
League, Today**. Not drawn (same anatomy): Plan, Players/Waivers, Matchup, Analyzer/Finder, sim Home/Team/League. Notes under each frame list what
changed and which rule it follows. The before frames are rebuilt from current components (labels/order real, heights approximate; no live screenshots were taken).

Draft room summary (the owner's example), against his list:
- Huge on-the-clock card -> 56px bar: "You're on the clock · 1.04 / Suggested: X / [Draft] / chevron". Chevron expands needs, progress, ETA, Auto-pick in place.
- No at-a-glance drafted -> **recent-picks strip + mini draft board always visible** (rounds x teams, position-tinted cells, your column outlined, current pick pulsing; the existing `simDraftBoardGrid` data and `SimDraftGrid`, drawn at 17px cells; tap opens the full grid in a sheet).
- Four rows -> one strip (Players | Queue | Roster) + one control row.
- Chips on the right -> chips under the name; right edge is Queue + Draft.
- No "Value"/"Trade value": sort is ADP / PROJ / OVR; the hint line drops "Value 91" (shows "fills a need" or the ADP).

---

## 5. Phased build plan

Sizes: S under 1 day, M 1 to 3 days, L 3 to 7 days for one engineer. Parity: each phase ships web and app in the same brief (ocyws's rule); app screens use `SegmentedTabBar`, `Collapsible`, `FilterSheet`, `Sheet`, `PlayerListRow` twins that already exist.

**Phase 0: guardrails and measurement (M).** Re-measure every page (scroll height, ctl rows, tallest default card) with the existing Playwright harness and commit the table; add the rule checks (R1, R2, R3, R7) as a script that reports, then fails CI once Phase 4 lands (ratchet: per-page allowed counts that only go down). Risk: the dev server mock only renders 6 pages with real content (known from the mobile UX audit); extend the mock. Parity: script is web-only; app check is a unit test on screen structure.

**Phase 1: shared pieces + draft room (L).** (a) `CompactModule` (rename/promote `Collapsible`; keep `Collapsible` as an alias so nothing breaks) and a `DataRow` chip-line variant of `PlayerListRow` (prop `statsPlacement="below"`; default stays "right" until each page migrates). (b) Draft room: compact bar, recent-picks strip, mini board, drop Board/Picks tabs, one control row, chips under name, remove "Value/Trade value" copy (sort label + hint). (c) Same on the app (`GmGameScreen` draft). Files: `SimGameDraft.tsx`, `SimDraftHero.tsx` (split into bar + expanded body), `SimDraftGrid.tsx` (mini variant), `SimDraftBoard.tsx` (controls), `simDraft.ts`, `simListStats`. Risks: the "OVR" sort needs a backend sort key; today `sort=value` orders by the sim's 0-100 trade value, which is a different number from OVR. **Do not relabel without checking**: either add `sort=overall` server-side (sim-only API, `docs/fantasy-sim-api.md`) or label by what it does ("Best value" is banned too, so "Rank"). I could not confirm this from the client code; it is the first thing to verify. Draft pick latency must not regress (the pick flow, optimistic row and queue persistence are untouched). Tests: `SimPhoneLayout.test.tsx`, `SimGameContent.test.tsx`, Playwright draft scripts.

**Phase 2: Team + Trades families (L).** One tab row per page in the Team and Trades families: Waivers (merge tab row + rec filter into one View selector + Filters), Players (position pills + sort in one row; Filters sheet), My Team (snapshot compact; roster groups as sections), Trade Hub (idea rows -> sheet, window one line), GM Plan (remove inner tabs -> sections; Season Outlook tab -> link to Forecast). Add Plan to the Team strip. Risk: `?tab=` deep links from orb search, emails and pushes: keep every old `?tab=` working by mapping it to the section (open + scroll). Parity: app `MyTeamScreen`, `WaiversScreen`, `PlayersScreen`, `TradeHubScreen`, `GmPlanScreen`.

**Phase 3: Today + League families (L).** Dashboard: the hero line, one "Do now" list merging NeedsAttention + TodayModule + TradesBlock + Watchlist (the server already ranks `attention` and `next_moves`; this needs a dedupe by decision key, see `docs/audits/executive-decision-ordering-audit.md`), compact modules for My team / Watchlist / League pulse / Play. Alerts as the second Today tab. League: Standings with a metric chip row (one board at a time; Roster Age and Playoff Odds are metrics), Recaps (week button -> sheet, drop three pill rows), Draft tab (Draft Center + Live Draft banner), Pick'em. Risk: Dashboard is the most-visited page and carries analytics (`fgl-dashboard-complete`, insight links); keep ids and events. Forecast consolidation touches three pages (decide D1 first).

**Phase 4: Sim game pages + More sheet trim + naming (M).** Sim Team/Players/League per 3.3; More sheet drops 14 rows (data edit in `navCatalog.ts`, which also feeds the app orb); rename Season Outlook to Season Forecast (labels only; routes unchanged, alias later). Risk: removing More rows hides pages for users who learned them; mitigate with the strip, orb search, and a one-time "Pages moved" coach mark (D8).

**Phase 5: enforcement and polish (S/M).** Flip the rule checks to failing; delete dead per-page card chrome; update `docs/ui-patterns.md` (CompactModule, DataRow) and `docs/player-card.md`; visual regression screenshots (this audit has none for the real pages; TestFlight rebuilds are limited, so rely on Playwright web at 390px and static checks for the app).

Order rationale: Phase 1 answers the owner's concrete example and proves the shared pieces; Phases 2 to 3 are the real fix (family by family, each shippable alone); Phase 4 removes the old entries only after the new homes exist.

### Risks (cross-cutting)

- **Prod ships on merge** (CLAUDE.md): each phase should be a stack of small PRs behind the existing shell flag (`NEXT_PUBLIC_BOTTOM_NAV`, founder-only by default) so coridian_ can review on his phone before everyone sees it.
- **The `test` CI job has a known golden-value drift**; verify failures against a clean clone of the merged commit before blaming a phase.
- **Twin drift**: every new lib file goes through `scripts/check_lib_twins.mjs`.
- **No band-aids** (standing rule): Phase 1's draft fix is built on the shared `CompactModule`/`DataRow`, not a draft-only patch.
- **Fantasy Sim isolation (R10)**: verify with the existing sim/real separation tests; no real-league code paths change.
- **Agent budget** (Zach): 2 to 3 sonnet agents at a time, one per family.

---

## 6. Decisions needed (product questions)

1. **D1 Season naming/merge.** OK to rename "Season Outlook" to **Season Forecast**, and fold Games > Season Outlook and League Rankings > Playoff Odds into it (as the "Odds" metric on Standings + one detail page)? Keep "Fantasy Sim" for the game?
2. **D2 Draft under League?** Draft Center and Live Draft as a **League > Draft** tab (my proposal) vs under Team (where the shell puts them today) vs Trades (pick trades).
3. **D3 Home + Portfolio.** Merge into one "Leagues" tab (Portfolio is Pro; free multi-league users currently land on a paywall card), or keep both?
4. **D4 Sim trade number.** The sim's trade screens need some comparable number. Allowed: "Sim rating", an unlabeled balance bar, or keep "Trade value" there but not in the draft/lists? (You asked for none "anywhere in the Fantasy Sim".)
5. **D5 Team strip size.** Five tabs (Roster, Matchup, Players, Waivers, Plan) fit at 390px but are tight; OK, or move Players to the Trades strip or into search?
6. **D6 Commissioner.** More row (rare, Pro) or a League tab shown only to commissioners?
7. **D7 Today "Do now" cap.** Show 3 with "See all", always merged across sources (my default), or let users choose sources?
8. **D8 Removing 14 More rows.** Remove immediately (my default; strips + search cover them) or keep them for one release behind a "Pages moved" coach mark?

Also worth confirming: is the web app on a phone (coridian_'s screenshots) the primary review surface for these mockups, so web ships first and the app follows in the same week? (Memory: "Owner uses web on phone".)

---

## 7. What this audit did not do

- No live screenshots; "before" frames are reconstructed from code. Sizes marked "e" are estimates.
- Did not read every card component line by line (about 376 components); module lists come from each page's imports and headings.
- Did not verify the backend sort keys for the draft board (see Phase 1 risk).
- No product code was changed; no `data/players.db`, `rankings.load_players` or Sleeper calls were touched.
