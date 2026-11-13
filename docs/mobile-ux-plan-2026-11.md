# Mobile UX audit and proposal, 2026-11

Status: proposal only. No product code changed. This PR adds this document and its mockups under
`docs/mobile-ux-plan-2026-11/`. Every nav or visual change below is an owner decision (see "Open decisions").

Owner brief (verbatim intent): mobile is 95%+ of users (native app and the web app on a phone). It has to be
easy to know where you are and how to get where you want, look good, read at a glance without fine detail, and
let people tap anything to expand. "We have so many features and I feel we might be shooting ourselves in the
foot with how we display features/information." Follow-up: the way we display this is pretty much how we
advertise, so this also proposes a visual language, an information-visualization catalog and a motion catalog.

## TLDR (top findings)

1. **There is no persistent navigation on phones.** The Expo app is a single native stack (no tab bar). The web app
   at phone width has the same thing: a floating "GM" orb at bottom center that opens a flat sheet of about 20
   rows. Every cross-section move costs 3 to 4 taps from the landing screen, and nothing on screen says which
   section you are in except an all-caps page title.
2. **The orb collides with content.** It floats over the last visible row on the Dashboard ("What do these mean?")
   and over the Upgrade button on GM Plan (real screenshots below). A nav control that covers primary actions is
   the opposite of seamless.
3. **The same concept has several names.** Three different "sim" things (Fantasy Sim, Season Outlook, Season Sim),
   Dashboard vs Today, Account vs More vs the ellipsis glyph, "Team Situation" still on screen after the page was
   retired, and `/premium` vs "Pro". Users cannot build a map when labels move.
4. **Screens say many things at once.** The Dashboard above the fold has 39 text elements, 5 large all-caps section
   headings, 6 equal-weight tiles and 3 different card styles; nothing is the hero. Account is 2.9 screens tall
   with 8 equally weighted cards. A free user's GM Plan opens on a 400px Pro explainer before any content.
5. **Detail-level text is too small and too dense for a glance.** Minimum font on every measured page is 10px; the
   header packs logo, page title, a truncated league/lens chip, search, bell and avatar into 390px; the
   web account menu items are about 40px tall; QB and RB position colors are not colorblind-safe unless paired
   with a letter (validator: deutan delta E 7.5, below the 8 target).

Recommendation in one line: a 5-tab bottom bar (**Today, Team, Trades, League, More**) with a global search
button replacing the orb as the navigation hub, one standard page header, a hero-number -> status chip -> one
line card pattern, and **Visual Direction B (dark glass, one neon accent, scoreboard numerals)**. Ship low-risk
fixes first, nav on web behind a flag second, the native app third.

---

## 1. Information architecture today (phone)

Sources: `web-next/src/lib/navCatalog.ts` (shared with `mobile/src/lib/navCatalog.ts`), `navDestinations.ts`,
`Header.tsx`, `GmOrb.tsx`, `AppContentShell.tsx`, `mobile/src/navigation/RootNavigator.tsx`, `HomeScreen.tsx`,
`MoreScreen.tsx`, `GmOrb.tsx`.

### 1.1 Structure

| Layer | Web at 390px | Expo app |
|---|---|---|
| Landing | `/` redirects: single or last league to its Dashboard; several leagues to `/portfolio` (a Pro page, so a free user with several leagues lands on a paywall card) | Home: league list, "Continue in <last league>" primary action, News globe and "..." glyphs in the header |
| Persistent nav | none. Header (logo, page title, league and lens chip, search, bell, avatar) plus floating GM orb | none. Native stack header only (back chevron, centered title) plus floating GM orb |
| Cross-section nav | GM orb sheet: search box, league section (7 rows), GM Tools (7), General (4), Pro, Account, Home. About 20 two-line rows, 57px each, so about 1,150px: the sheet scrolls | same sheet, same catalog |
| Account | avatar menu in header: How We Evaluate, Account settings, 5 legal links, Sign out. No Pro or billing entry in it | Home "..." glyph (accessibility label "Account") opens a screen whose route is `More` and whose title is "Account" |
| Page-level tabs | Waivers (3), League Rankings (2), Trade Hub (4), GM Plan (5), Draft Center (3), League Recaps (1), Games (2) | same, hosted in one screen per page (Trades screen hosts Hub, Finder, Analyzer) |

Catalog (the one shared list): core (league pages) = Dashboard, Alerts, My Team, Matchup, Waivers, League
Rankings, Players. GM Tools = Trade Hub, GM Plan, Draft Center (Pro), Live Draft (Pro), League Recaps, Games,
Commissioner (Pro). General = Portfolio (Pro), Fantasy Sim, News, Community. Chrome = Home, Pro, Account,
Founder Analytics. Not in the menu but real routes: Trade History, College Scouting, Playoff Odds, Trade
Finder, Trade Analyzer, Trade Offer, Player Compare, Player detail, Season Outlook (`/fantasy-sim`),
Team Situation and GM Targets (redirects to GM Plan).

### 1.2 Taps to top tasks

Counted from cold app open, returning user, last league remembered (Home shows "Continue in ..." on the app; web
redirects to the league). The orb counts as one tap and opens the sheet. "Proposed" assumes the bottom bar in section 3.

| Task | Today (taps) | Path today | Proposed |
|---|---:|---|---:|
| See what matters this week (dashboard) | 1 | Continue | 0 (Today is the landing) |
| Check or set lineup | 3 | Continue, orb, My Team | 1 (Team tab, Lineup is default) |
| Analyze a trade | 4 | Continue, orb, Trade Hub, Analyzer tab | 1 to 2 (Today quick action "Grade trade", or Trades > Analyze) |
| Find a trade partner | 4 | Continue, orb, Trade Hub, Finder tab (Pro) | 2 (Trades > Finder) |
| Look up a player | 3 (+ typing) | Continue, orb, Players, or orb search | 1 (search button on every screen) |
| Waivers | 3 | Continue, orb, Waivers | 1 to 2 (Today quick action, or Team > Waivers) |
| League standings | 3 | Continue, orb, League Rankings | 1 (League tab) |
| Set Team Situation | 3 | Continue, orb, GM Plan (stance picker is the Overview tab) | 1 to 2 (Today "Plan" card, or Team > Plan) |
| GM Plan | 3 | Continue, orb, GM Plan | 2 (Team > Plan) |
| Fantasy Sim | 2 | orb, Fantasy Sim (not league scoped) | 2 (More > Fantasy Sim) |
| Account or billing | 2 | "..." then Account (app), avatar then Account settings (web); Pro via orb General | 2 (More > Pro or Account) |

The Dashboard is cheap (1 tap) and everything else is 3 to 4. The proposal moves the median task from 3 taps
to 1 to 2 and, more importantly, makes each one repeatable by muscle memory: the same bar, same place.

### 1.3 Dead ends, duplicates, naming, "where am I"

Dead ends and weak wayfinding
- **Orb overlap** (see 2.2): the nav control hides content, and tapping through it is not possible.
- **Locked pages are full cards, not chips.** Free users hit a 400px Pro explainer (Portfolio, GM Plan) with no
  preview of the value and no way to see the rest of the page. The orb shows a gold Pro marker, so the lock is
  known before the tap, which is good; the landing experience is not.
- **Free multi-league users land on a Pro page** (`/` to `/portfolio`).
- **Back and context are inconsistent.** Web league pages have no back affordance (the page title and a chip
  only); app screens use the native back chevron with `headerBackButtonDisplayMode: minimal`, so the previous
  screen name is not shown. A deep page such as a player does not say "Players" anywhere.
- **Tabs inside pages have different looks and behaviors** (underline tabs on GM Plan, pill segments elsewhere,
  `#hash` tabs on League Rankings, route tabs on Trade Hub).
- Web header shows the section as an all-caps 14px label ("DASHBOARD") that truncates next to the league chip
  ("Dynasty Overl... . Dynasty").

Duplicate entries
- Alerts: bell in header, orb row, a "Watchlist & Alerts" Dashboard section.
- News: orb General row, app Home globe glyph, player News tab.
- Trade History: Trade Hub tab and the app Account screen "Your Team" section.
- Players: orb Players, orb search results, Waivers Explore, Draft Center Scouting, Player Compare.
- Trade ideas: Dashboard strip, Trade Hub Hub tab, GM Plan "Trade ideas" section, GM Plan Trades tab.
- Season forecast: GM Plan "Season Outlook" card, Games "Season Sim", Fantasy Sim, plus Portfolio odds.

Inconsistent names (all verified in code or screenshots)
- Three sims: **Fantasy Sim** (`/gm-game`, draft a team and play a season), **Season Outlook** (`/fantasy-sim`, a GM
  Plan tab, playoff odds and projected finish), **Season Sim** (Games tab). Route names and labels cross each other.
- **Dashboard** (nav, page title) vs **Today** (glossary: the briefing). The sample league has both a "Dashboard"
  and a "Today" tab.
- **Account / More**: app route `More`, screen title "Account", glyph is an ellipsis; web header avatar says
  "Account" and its page title "Account"; its menu item says "Account settings".
- **Team Situation**: retired as a page, still a section title in GM Plan, a push category and Pro copy ("Free
  keeps your Team Situation").
- **Pro** vs `/premium` and internal "premium"; **GM Plan** (page) vs "GM" orb vs "GM Tools" (group label) vs
  "My Team" (page) vs "MY TEAM" (Dashboard section that is really team tiles).
- "Teams" (app route) is the League Rankings screen; "TeamRoster" is another manager's roster.
- Rankings: "League Rankings", "Power Rank", "Franchise Rank", "Starter Strength" all appear as equal tiles.

---

## 2. Measurements (Playwright, 390x844, DPR 2, dark theme)

Method. Real `web-next` dev server (`npm ci`, dummy `NEXT_PUBLIC_SUPABASE_URL/ANON_KEY` in a gitignored
`.env.local`), Playwright, signed-in session injected, API and Supabase answered by a mock
(`mock-src/audit-playwright.mjs`; the Dashboard and `/v1/me` use realistic fixtures from
`DashboardContent.test.tsx`, other endpoints answer `{ok:true}`). Limitation, stated plainly: **only Dashboard, GM
Plan, Account, Connect League, Premium, Portfolio and /sample-league render real content with this mock.** The
other pages (Trade Hub, Players, Waivers, League Rankings, My Team, Matchup, Games, Alerts, Draft Center,
Commissioner, Recaps) hit their error state, so their rows below measure chrome only and should be re-measured
against real data. The screenshots in `before-real/` still show the real header, orb and menus. The "N" badge
bottom-left is the Next.js dev indicator, not product UI.

Metrics: scroll height in viewport heights (vh); distinct font sizes (rounded to 0.5px); text elements and
interactive elements with any pixels above the fold; interactive targets under 44x44 above the fold; text
failing WCAG AA on its nearest opaque background (approximate: translucent glass and gradients are not
resolved, so 0 here means "no flagged text", not "passes").

| Screen (real data?) | Scroll (vh) | Distinct sizes | Text els above fold | Taps above fold | Taps under 44px | Min font |
|---|---:|---:|---:|---:|---:|---:|
| Dashboard (fixture) | 1.39 | 7 | 39 | 13 | 0 | 10px |
| GM Plan, free state (fixture) | 1.41 | 5 | 32 | 16 | 0 | 10px |
| Account (fixture) | 2.92 | 3 | 25 | 10 | 3 | 10px |
| Sample league (fixtures) | 2.36 | 8 | 26 | 13 | 0 | 10px |
| Connect league | 1.00 | 4 | 21 | 12 | 3 | 10px |
| Portfolio (Pro gate card) | 1.00 | 5 | 12 | 5 | 0 | 10px |
| Trade Hub / Analyzer / Finder / Players / Waivers / Rankings / My Team / Alerts (error state, chrome only) | 1.00 | 4 to 5 | 8 to 12 | 7 to 8 | 0 | 10px |
| Header avatar menu open over Dashboard | n/a | n/a | n/a | 22 | 8 (menu rows are about 40px tall) | n/a |
| GM orb sheet (not measured by script) | n/a | n/a | n/a | about 20 rows at 57px = about 1,150px of list | n/a | n/a |

Reading the numbers
- A glanceable phone screen is roughly 1 to 1.5 vh, 5 to 6 type sizes, one hero. The Dashboard is in range on
  height but has **39 text elements above the fold** and five equal-weight section headings, so scanning cost is high.
- Account is **2.9 vh of eight equal cards**. The Pro, billing, invite and deletion cards carry the same visual weight.
- The shipped chrome (header, orb, menu) is the same on every page, so its costs multiply: header 6 items in 390px,
  orb sheet about 20 two-line rows, menu rows about 40px.
- Colorblind check (dataviz validator, dark surface): QB `#fb7185` vs RB `#4ade80` deutan delta E 7.5 (WARN, floor
  is 8 target). Position colors are therefore fine **only with the letter label always present**, which the
  mocks enforce.

### 2.1 Five-second test, per screen

| Screen | What it says in 5 seconds today | What it should say |
|---|---|---|
| Dashboard | "Your team right now: a lineup warning and a record" then four more headings. No single call to action. | "Week 11: favored by 3.5. One priority: get an RB. Deadline in 5 days." |
| GM Plan (free) | "This is a Pro feature" (a 400px card) after a Team Situation picker | "Here is your plan headline; unlock the rest." Show the headline blurred or as a chip, not a wall of copy |
| Account | "A long settings list" | "You are on Pro, trial ends in 6 days; everything else lives behind rows" |
| Sample league | "Four tabs, a lot of player rows" | "This is what you get: verdict, lineup, plan" |
| Orb sheet | "A long list of pages, all alike" | "The five places I go most, then search" |
| Header | "FD logo, a label, a truncated chip, three icons" | "You are in Today, in this league; search is one tap" |

### 2.2 Real before screenshots (in `before-real/`)

- `dashboard_fold.png`: five all-caps section headings, glow effects on two cards, six equal tiles; the orb sits on
  "What do these mean?".
- `orb_open.png`: the nav sheet; "GM TOOLS" is clipped by the dev badge and the list continues off-screen.
- `account_menu.png`: the avatar menu is legal links; billing and Pro are not here.
- `gm-plan_full.png`: "TRADE IDEAS / View all" appears **above** the "GM PLAN / Your season-arc roadmap" heading;
  the orb covers the Upgrade button.
- `league_menu.png`, `connect_fold.png`.

---

## 3. Proposed mobile-first information architecture

### 3.1 Bottom navigation (web phone + app, same labels and glyphs)

Five tabs, always visible on league screens, 84px tall including safe area, glyph + label (never glyph only),
active = accent color, 3px top indicator with glow, badge counts for things to do.

| Tab | Glyph | Contains (segments inside the tab) | Badge |
|---|---|---|---|
| **Today** | house | the briefing: matchup hero, top priority, quick actions, glance tiles, next-up (lineup lock, waivers run, deadline) | none (it is the inbox) |
| **Team** | jersey | Lineup (default), Roster, Waivers, Plan (GM Plan, Pro, includes Team Situation stance and Season Outlook) | injured or empty starters |
| **Trades** | swap arrows | Ideas, Analyze, Finder (Pro), History | new trade ideas |
| **League** | bars | Standings (League Rankings), Players, Recaps, Games (Season Sim, Pick'em) | none |
| **More** | three dots | Pro and billing card at top; Play: Fantasy Sim, Portfolio, Draft Center, Live Draft, Commissioner; Follow: News, Community, College Scouting (opt-in); You: Account and leagues, Settings and alerts, How we evaluate, Legal | trial or billing issue |

Global, on every screen (header, not tab): **search** (players and pages; replaces the orb sheet's search and
becomes the one way to look up a player), **bell** (Alerts, with count), **league chip** (switch league and lens).

What happens to the GM orb: it stops being the navigation hub. Recommended: retire the floating button and
fold its search into the header; keep the "GM" identity as the name of the assistant surfaces (priority card,
plan). Open decision D2 below (some users may know the orb; a one-release overlap is possible).

Why these five: they match the five jobs a manager does weekly (what now, my roster, deals, the league, the rest)
and cover the ten top tasks in 1 to 2 taps. Players is not a tab because lookup is search-first and browsing is
rare; it sits as the second League segment. Matchup is the Today hero (tap opens it) so it does not need a tab.
Alerts is the bell. Draft and Commissioner are seasonal or role-specific and appear on Today as cards when they matter.

### 3.2 Standard page header

```
[<]  Title (26/800)                 [search] [bell(2)]
     [League name . Wk 11  v]                          <- context chip, tap = switch league / lens
     [ Lineup | Roster | Waivers | Plan ]               <- segment pills (page tabs), sticky
```
- Top-level tab pages: large title, no back. Deep pages (player, verdict): back button plus the **parent name as
  the title** ("Players"), so "where am I" is always answered by the back label.
- Context chip on every league screen. It shows League and Week (and lens when non-default), truncates in the middle
  not the end, and is the single switcher on web and app.
- Replaces the all-caps 14px page label, the three-control cluster and the per-page `PageTitle` that is
  visually hidden. One component, used by every screen, sits in `shared` so web and app cannot drift.

### 3.3 "You are here" pattern (four cues, always)
1. Bottom bar active tab (color, indicator, bold label).
2. Page title (or parent name on deep pages).
3. Segment pill highlighted within the tab.
4. League chip (which league, which week).

### 3.4 Quick actions
A row of four equal tiles under the hero on Today (glyph + two-word label + optional count badge). They are
contextual by phase: in-season "Set lineup, Grade trade, Waivers, Player"; deadline week swaps Waivers for "Find
partner"; draft season swaps in "Draft Center"; playoffs "Set lineup, Matchup". Long-press is never required.

### 3.5 Card hierarchy: hero number -> status chip -> one-line why -> tap for detail
Every card answers in this order: one big tabular number or word (26 to 44px), one status chip with icon and
label (never color alone), one sentence of why (13 to 15px, secondary), then a chevron or action. Anything
longer is a sheet or a page behind the tap. Section headings drop from 24px all-caps to 11px small caps labels
inside the card.

### 3.6 Glance-first components and color semantics
Stat tile (label 11 caps, value 26/800, delta chip), trend chip (arrow, delta, window: "+4 / 30d"), status chip,
sparkline, ring, gauge, health strip, form strip, pressure meter (catalog in section 5).
Semantics are fixed and global:

| Color | Means | Never used for |
|---|---|---|
| Green `--color-success` | good, win, healthy, rising | decoration |
| Amber `--color-warning` | watch, questionable, getting close | Pro |
| Red `--color-danger` | act now, out, falling, deadline close | brand |
| Cyan `--color-accent` | interactive, active nav, info | status |
| Gold `--color-premium` | Pro only | anything else (the matchup and priority cards drop gold glows) |
| Position colors | position identity, always with the letter | status or rank |

### 3.7 Progressive disclosure and density rules
- Three levels: **L0 glance** (hero, chip, one line), **L1 tap-to-expand sheet** (the why, the numbers, the
  alternatives), **L2 full page** (tables, history, tools). Nothing on L0 requires reading more than one sentence.
- Max **one hero per screen**, max **7 blocks** per screen above the first scroll, **6 type sizes** system-wide
  (11, 13, 15, 18, 26, 44), min 11px, min 44px tap targets, 16px gutters, 12px card gaps.
- Max **two accent colors** per card; one neon per screen.
- Locked (Pro) content is a **chip on the real content** ("Pro"), with a one-line value preview, never a
  full-page card above the content. The sheet that opens on tap carries the explanation and Upgrade.
- Explanatory copy lives behind one "?" (the existing `PageTitle info` pattern) or in L1, not in cards.

### 3.8 Feature prioritization

| Tier | Features | Placement |
|---|---|---|
| Primary (weekly) | Today briefing, lineup, waivers, trade analyze and finder, standings, player lookup, alerts | bottom bar, search, bell |
| Secondary (situational) | GM Plan and Season Outlook, Matchup detail, Draft Center and Live Draft in season of use, Recaps, Games, Portfolio | segments or More, surfaced on Today as a card when relevant |
| Tertiary (rare) | Fantasy Sim, Community, News, College Scouting, Commissioner, Account, legal | More |

Merge and rename (using `lib/terms.ts`: Today, GM Plan, Pro):
- **Dashboard -> Today** everywhere (nav label, header title, sample-league tab; the sample league's second "Today" tab becomes "Plan").
- **One sim family**: keep **Fantasy Sim** for the draft-a-team game. Rename the GM Plan tab **Season Outlook** -> "Outlook" (it is a forecast), Games tab **Season Sim** -> "What-if" or fold into Outlook. Decision D4.
- **Account / More**: one route name `More`, one title "More", the Account row inside it says "Account and leagues".
- **Team Situation** becomes "Stance" inside GM Plan (the word users see in the stance picker) and the push category follows.
- **Premium** stays out of UI; route `/premium` can stay but redirect `/pro`.
- Merge duplicates: Trade History only under Trades; News only under More plus the player News tab; Alerts only via the bell.

---

## 4. Mockups (390px, rendered from HTML/CSS with the app tokens)

All images are in `docs/mobile-ux-plan-2026-11/` (2x PNG, 780x1688). Sources are in `mock-src/` (open any `.html`
at 390px). "Before" is a real screenshot from section 2; "after" is a mock.

| What | Before | After |
|---|---|---|
| Bottom nav + Today | `pair-today.png` (left) | `B-today.png` (right) |
| League dashboard glance card (ring, rank, standings) | `pair-league.png` (left, current dashboard) | `B-league.png` |
| More / menu | `pair-more.png` (left, orb sheet) | `B-more.png` |
| Player page header | (not captured: needs real player data; current header is a text list of name, position, team, age) | `B-player.png` |
| Trade verdict | (not captured, same reason) | `B-verdict.png` |

Before/after observations from `pair-today.png`: five large all-caps headings become one 26px title; the matchup
becomes the single hero with a win-probability bar; the priority gets one button; 6 equal tiles become 3 tiles
plus 4 quick actions; the orb (which covered content) is gone, replaced by the bar. Type sizes in the Today mock:
6 (11, 13, 15, 18, 26, 44) against 7 today. Honest note: raw text-element count is similar (40 vs 39); the gain
is hierarchy and navigation, not less content, and the build should still cut copy (see density rules).

---

## 5. Visual language proposal (the "how we advertise" part)

### 5.1 (A) Three visual directions, same three screens

All three are built on the shipped tokens (`--color-*`, tabular numerals) and show Today, a trade verdict and a
player page header at 390px so they can be compared directly. Contact sheets: `direction-A.png`,
`direction-B.png`, `direction-C.png`; individual frames `A-*.png`, `B-*.png`, `C-*.png`.

| | A. Broadcast scoreboard | B. Dark glass, one neon (recommended) | C. Clean data card |
|---|---|---|---|
| Feel | sports-TV: angled slabs, lower-thirds, italic scoreboard digits, yellow rail | the shipped brand, refined: translucent surfaces, cyan accent, big tabular numbers, soft glow only on the hero | white cards, hairlines, one dark button, color only for status |
| Strength | most distinctive and most shareable; numbers feel like a game | matches the app today; lowest migration cost; best for night and game day; premium feel | highest legibility and density; closest to a finance app |
| Risk | strongest identity change; condensed uppercase is slower to read in bulk; yellow collides with Pro gold; large rewrite | can look generic if every card glows (so: one glow per screen) | loses brand personality; light-first is off the dark-OLED default; weakest as an ad |
| Cost | high (new type, shapes, nav) | low to medium (tokens exist; mostly layout and hierarchy) | medium (needs a full light theme pass; a Day theme already exists) |
| Best use | **share cards and store screenshots** (accent only) | **the app and web UI** | reference for the Day theme and tables |

**Recommendation: B for the product, borrowing A's scoreboard numerals for the matchup and verdict heroes and its
look for share cards; C stays the reference for the Day theme and data-heavy tables.** Reasons: (1) it is already
what users see, so it needs no relearning and no store re-submission of a new identity; (2) the owner's issue is
hierarchy and navigation, which B fixes with layout, not paint; (3) dark glass with one neon reads as premium
in screenshots; (4) A on every screen would slow reading and make Pro gold ambiguous.

### 5.2 (B) Information-visualization catalog (`viz.png`)

Each pattern is a shape that replaces a paragraph or table. Status colors always ship with an icon or label.
Rules from the dataviz guidance applied: one axis, no dual axis, sequential = one hue, status colors reserved,
text in text tokens, direct labels, thin marks, 2px gaps between adjacent fills, tooltips or tap detail on every mark.

| # | Pattern | Replaces | Where |
|---|---|---|---|
| 1 | Verdict gauge (arc plus word plus 3 chips) | Trade Analyzer paragraph verdict | Trade Analyzer, Trade Hub ideas, share card |
| 2 | Value-balance bars (give vs get) | two columns of totals and "you win by X" | Trade verdict, Offer builder |
| 3 | Trend sparkline plus delta chip | Trends tab table, "value up" prose | Player header, My Team rows |
| 4 | Health strip (one tile per starter: check, ?, x) | Alerts list, "injured starters: 2" tile | Today, Team > Lineup |
| 5 | Position heat tiles (rank tinted, STRONG/WEAK label) | My Team analysis tables, needs paragraph | Team, GM Plan |
| 6 | Playoff-odds ring | Playoff Odds table, outlook headline | League dashboard card, Today tile |
| 7 | Week-by-week form strip (bar = margin) | recap lists, game log | Matchup, Recaps, player |
| 8 | Rank-change arrows | tiny delta columns in rankings | League > Standings |
| 9 | Pressure meter (segments go amber then red) | "Deadline: Nov 19", bye copy | Today, Team |

### 5.3 (C) Motion catalog (clips in `clips/`, GIF, 390x420, 14fps)

Purposeful, short, and one per moment. Tokens: durations `--dur-fast 150ms`, `--dur-base 240ms`, `--dur-slow
480ms`, `--dur-hero 900ms`; easings `--ease-out cubic-bezier(.16,1,.3,1)` (entrances, count-ups),
`--ease-std cubic-bezier(.2,0,0,1)` (slides, sweeps), `--ease-spring cubic-bezier(.34,1.56,.64,1)` (pops, lands).
Source: `mock-src/motion.html` (open `?d=<name>`).

| Clip | File | Spec | Used for |
|---|---|---|---|
| Number count-up | `clips/countup.gif` | 900ms ease-out; chip pops at 700ms | matchup, value, odds heroes |
| Verdict reveal | `clips/verdict.gif` | arc 480ms, word spring, chips +80ms stagger | Trade Analyzer result |
| Card stagger | `clips/stagger.gif` | 240ms rise 24px, 60ms step, max 5 cards | any list on first load |
| Pick lands | `clips/pick.gif` | rise 400ms, 6% squash, slot flashes green | draft pick, add player to lineup |
| Advance-week sweep | `clips/sweep.gif` | light bar 480ms then scores tick 700ms | Fantasy Sim week result |
| Trade accepted | `clips/accept.gif` | ring spring 480ms, ripple 900ms, 14 confetti (decor) | trade confirmed |
| Injury pulse | `clips/injury.gif` | 1.6s soft ring, Out only, stops after 3 loops | health strip |
| Bye / deadline countdown | `clips/bye.gif` | segments fill 60ms step; amber at 5d, red at 2d | pressure meter |
| Tab switch slide | `clips/tabs.gif` | 240ms ease-out, indicator and content move together | page segments |
| Pull to refresh | `clips/pull.gif` | rubber-band 56px, spinner scales in, release 480ms | Today, Waivers |
| Skeleton shimmer | `clips/skeleton.gif` | 1.4s linear, shapes match final layout | every loading state |
| Title confetti | `clips/title.gif` | trophy spring, 40 pieces, 1.6s, once per season | league champion, Fantasy Sim title |

Motion rules: motion confirms a state change or draws the eye to the one thing that matters; nothing loops
forever except skeletons and the Out pulse (and that stops); never animate while a user types or scrolls;
60fps transform and opacity only; max 600ms for any UI response except hero moments (900ms).
**prefers-reduced-motion** (web) and `AccessibilityInfo.isReduceMotionEnabled` (app): count-ups snap to the final
value, reveals are an opacity fade of 150ms, confetti and pulses are off, shimmer becomes a flat tint. The
prototype honors it (`clips/reduced-motion-verdict.png` shows the final state with zero movement).
Native note: use Reanimated worklets for the count-up and sweeps; the project already has a documented orb
history where Reanimated and inset tweaks were dead ends (memory: GM orb bug history), so prototype one motion on
a device before committing the set.

### 5.4 (D) The advertising angle

The three screens that sell the product on a store page or a share link, in order:
1. **Trade verdict** (`store-screenshot-verdict.png`, `share-card-verdict.png`). One giant WIN, three chips, a value
   balance. It is the product's promise in one frame and a native share card.
2. **Today** (`B-today.png`). Hero matchup plus one priority, quick actions and the bar show a calm, actionable
   weekly brief.
3. **League dashboard glance** (`B-league.png`). The ring and rank say "you will see where you stand in a second".
   (Player header is a close fourth, good for a "know any player" screenshot.)

Composition: 1290x2796 store frame, headline in the top 25% (big, one accent word, <= 6 words: "Know if a trade wins, in
one glance."), one subline, then the phone with real UI bleeding off the bottom with a soft cyan glow; no
device chrome beyond a bezel. Share card 1080x1350: the verdict word, two chips, the two bars and the player names,
brand and a short URL at the bottom; no screenshots of tables. Use fixture data (never real users' names) and
Direction A's slab styling for share cards only if D1 approves it.

---

## 6. Phased implementation plan

Effort: S = about 1 to 2 days, M = about a week, L = 2+ weeks, for one engineer on web plus app. Risk: L/M/H.

| Phase | Ships | Why first | Risk | Effort |
|---|---|---|---|---|
| 0. Quick wins, no new nav | Orb clearance (bottom padding so it never covers the last row or primary buttons); min font 11px and 44px menu rows; GM Plan heading order and free-state card shrink to a chip plus one line; header page label to title case and middle-truncated chip; Account page grouped (Billing and Pro first, preferences collapsed); `terms.ts` additions (Dashboard to Today, Team Situation to Stance, one sim family) with the existing test enforcing it | Biggest visible polish per hour; no product decision; ships in one PR per platform | L | S to M |
| 1. Shared page header + "you are here" | One header component (title or parent name, back, league chip, search, bell, segment pills) in `web-next/src/components` and `mobile/src/components`, adopted screen by screen | Needed by nav; fixes inconsistency; flaggable | M | M |
| 2. Today rebuild (web, then app) | Hero matchup, top priority, quick actions, glance tiles, next-up. Reuses existing `DashboardContent` data, no API change | Biggest glance win; independent of nav; measurable | M | M |
| 3. Bottom nav on web phone (flagged) | 5-tab bar below `md`, search replaces orb, orb hidden under the flag, founder first then percentage | Biggest navigation win; reversible; 95% of users are on phones so web carries most of them | M to H (touches every page's bottom padding, analytics screen names, deep links) | M to L |
| 4. Bottom nav in the Expo app | `@react-navigation/bottom-tabs` (JS only, no new native module expected) wrapping the existing stack; same labels and glyphs | Parity rule (web and app ship together); needs a store build | H (iOS review in flight; no autonomous build push; native QA needed) | L |
| 5. Glance components and motion | Viz catalog as shared components (ring, gauge, strips), motion tokens, reduced-motion path | Compounding polish; each is independent | L to M | M, incremental |
| 6. Marketing assets | Store screenshots and share cards from fixtures | Cheap after Phase 2 | L | S |

What ships first for the biggest win: **Phase 0 (this week), then Phase 2 and Phase 1 in parallel, then Phase 3.**
Phase 3 is the largest single win but the only one with real regression risk, so it follows measurement and a flag.

Verification plan: Playwright at 390x844 on real data (not the mock used here), measure the same table
(vh, sizes, taps under 44, text elements, min font), tap-count script for the 11 tasks, plus a short usability
check with 5 users (find waivers, analyze a trade, look up a player). Success: median task <= 2 taps, min font
>= 11px, 0 targets under 44px, one hero per screen.

---

## 7. Open decisions for the owner

1. **D1 Visual direction.** Approve B (recommended) with A reserved for share cards, or pick A or C.
2. **D2 The orb.** Retire it (recommended) when the bottom bar ships, keep it as search-only, or keep as is and add the bar anyway?
3. **D3 Tab set.** Today / Team / Trades / League / More OK? Alternative: replace League with Players if lookup matters more than standings; or make Waivers its own tab.
4. **D4 Naming.** Dashboard to Today; Team Situation to Stance; the three sims (Fantasy Sim, Outlook, What-if). Needs coridian_'s call because `terms.ts` is the glossary of record.
5. **D5 Pro lock presentation.** Chip on real content with a preview (recommended) vs today's full explainer card; also what a free multi-league user sees at `/` instead of Portfolio.
6. **D6 Landing.** Today is the landing for returning users (recommended); the league list moves into the league chip. Confirm.
7. **D7 Rollout.** Web behind a flag first (founder, then percent), app after; and whether Phase 4 waits for the in-flight iOS review.
8. **D8 Motion scope.** Approve the 12-clip set or a subset (recommend: count-up, verdict reveal, stagger, skeleton, tab slide first).
9. **D9 Density default.** Keep "Guided" explanations default or make Compact the default now that hierarchy carries the message?
10. **D10 Player header and verdict before-images.** Re-measure on real data before Phase 2/3 sign-off (this audit could not render them).

## Appendix: files

- Mockups: `docs/mobile-ux-plan-2026-11/B-today.png`, `B-league.png`, `B-more.png`, `B-verdict.png`, `B-player.png`,
  `A-*.png`, `C-*.png`, `direction-A|B|C.png`, `pair-today.png`, `pair-league.png`, `pair-more.png`, `viz.png`,
  `store-screenshot-verdict.png`, `share-card-verdict.png`.
- Clips: `docs/mobile-ux-plan-2026-11/clips/*.gif` and `reduced-motion-verdict.png`.
- Real before screenshots: `docs/mobile-ux-plan-2026-11/before-real/`.
- Sources: `docs/mobile-ux-plan-2026-11/mock-src/` (HTML, generators, motion prototype, audit script).
