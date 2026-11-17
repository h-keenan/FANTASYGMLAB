# Header deep audit and rewrite proposal (2026-11-14)

coridian_: "we need an overall header deep audit and potential rewrite, I don't like how it looks in most of the concept pages." Inputs from his earlier picks: league switcher as a bottom sheet with league cards, a Desk header on one row with a crest chip, and no duplicated "Today". Builds on `docs/audits/2026-11-header-audit.md` (switcher findings, #1957). Mockups: `docs/audits/ui-pass-7/header-<page>.html` (V1/V2/V3 at 390px for Today, Team, Players, Trades hub, League, News, Sim home, Sim team, a detail page and a sheet; the switcher open inside each; V2 in light for Today/Team/League). Nothing here is implemented.

## 1. What the header is today, per page family

Web phone has two header systems: the **phone shell** (`ShellHeader`, one row, on for everyone once #1952 lands) and the **legacy header** (`Header.tsx`, wraps; reachable only via the kill switch). The app has a third: a transparent native-stack header (`ScreenHeaderTitle`: screen title + league name, centered) plus an in-content `BrandHeaderBar` (wordmark, star, more) and, on Today, a title row with search and bell. Fantasy Sim has its own header on both platforms.

| Page family | Header contents today (web shell) | Redundant / inconsistent | Height |
|---|---|---|---|
| Today | brand mark, "Today", league chip (name over lens), search, bell | "Today" is also the active pill label and the hero eyebrow "TODAY · WEEK 10": three times | 52 |
| Team (Roster, Players, Waivers, Matchup) | back/mark, page title, "?" slot, chip, search, bell | title ("My Team") + pill "Team" + family tab "Roster"; Waivers adds a module titled "WAIVERS" under a header "Waivers": three times | 52 + tab strip |
| Trades (Hub, Finder, Analyzer, History) | back, "Trade Hub", chip, search, bell | header "Trade Hub" vs pill "Trades" vs family tab "Hub": three names for one thing | 52 + strip |
| League (Rankings, Recaps, Games) | back, "League Rankings", chip, search, bell | header "League Rankings" vs pill "League" vs tab "Rankings"; Games has a native select styled as a title | 52 + strip |
| GM Plan, Draft Center, Live Draft, Portfolio, Commissioner | title + chip, no family strip | title only; Portfolio has no league so no chip | 52 |
| News, Portfolio, Home (outside a league) | brand mark, title, search, bell | pill already says News/Portfolio | 52 |
| Account, More, Premium, connect league, onboarding | own headers, some none | paywall/onboarding have no consistent back or title | varies |
| Player card (PQV) and Sheet | grip + title + close, bespoke per sheet | PQV has its own shell; Sheet title style differs from PQV | 56-72 |
| Sample league | sticky "Sample league" banner 114px, mark only | banner is taller than the header | 114 |
| Sim hub | `SimHub` page, no game header | hub has its own title row | - |
| Sim Home/Team/Players/Trades/League/Draft/Recap/Offseason | one icon row (back, "Wk 10/14", search, bell, more) + a full-width team row + status chips | 97px tall at every width; the team name wraps under its crest; season label only after the first season; Sim tab name lives in the orb/pill and again in content headings | 97 |
| App (all league screens) | native header title (screen + league) + in-content wordmark bar; Today has a title row too | two headers stacked; league name is `numberOfLines={1}` | 56 + 44 |

Scroll: every web header is `position: sticky; top: 0` and never collapses; the page tab strip pins under it, so tab pages carry two sticky bars (about 96px of 844). Safe areas: the web shell header has no `env(safe-area-inset-top)` padding (the app uses native insets); not testable headless, to verify on device.

## 2. The header system (proposal)

One component, five templates, one rule.

**Rule: a label appears once.** The bottom pill (and its family strip) names the page, so a tab page's header does not. The header answers "which league and what is the situation", not "which page". A page title appears only where nothing else names the page: detail pages, sheets, Sim game pages with the Sim orb off-screen. Hero eyebrows ("TODAY · WEEK 10") become situation text ("Week 10 vs Shiesty"). Section headings never repeat the page name.

| Template | Used by | Slots |
|---|---|---|
| Root | Today, Team (+Players, Waivers, Matchup), Trades (+Finder...), League (+Recaps, Games), News, Portfolio | `identity` (crest + league, tap = switcher sheet), `context` (chips: week, record, odds, lens), `actions` (search, bell), optional `help` ("?" popover) |
| Detail | Player, Pick, Manager, Trade offer, GM Plan sub-pages, Account | `back`, `title`, `subtitle`, `actions`, optional `avatar`/hero |
| Sheet | Sheet, PQV, switcher, filters | `grip`, `title`, `subtitle`, `close`; same chrome for PQV and `Sheet` |
| Immersive | Onboarding, paywall, recap story, sample league | no bar; floating close/back orb only |
| Sim game | all Sim game tabs | `back`, `team` (crest + record), `clock` (week, season), `actions`, status chips below |

API sketch (web `ui/AppHeader.tsx`, app `AppHeader.tsx`, logic twin `lib/appHeader.ts`): `<AppHeader template="root|detail|sheet|immersive|sim" identity context actions title subtitle back collapse />`. `lib/appHeader.ts` owns the pure rules (what chips a page may show, the no-duplicate-label check, collapse thresholds) and is covered by node tests on both platforms. `collapse`: `"none"` (sheet, detail), `"ribbon"` (root: the context row folds into the first row after 24px of scroll, 160ms, off under reduced motion). Safe area: top padding `env(safe-area-inset-top)` on web, native insets on the app. 44px targets, crest and league names wrap to two lines and never ellipsize. Shared with `PageTabBar`: when the header collapses the family strip pins directly under it so tab pages carry one sticky stack, not two.

League identity: the crest (Sleeper avatar, else the generated `TeamAvatar` crest) is the one place the league is shown; the switcher is a `Sheet` (league cards with crest, full name, platform, teams, record, Power rank, search at 6+ leagues, Connect a league, sample league, Sim saves, lens segmented control, retry state on a failed load, Escape/back/outside-tap through the overlay manager).

## 3. Three directions (mockups)

- **V1 Identity bar** (coridian_'s pick, refined): one 56px row, crest chip with the full league name (wraps) and a context line, search, bell. Lowest risk, smallest change, but chips for context have only one line.
- **V2 Context ribbon** (recommended): crest + league + lens, then a ribbon of glanceable chips (Wk 10, 7-1, Win 57%) that folds away on scroll; detail pages get a big 24px title with the avatar. Best glanceability and readable titles, keeps the glass look, about 96px expanded and 56px collapsed.
- **V3 Floating islands**: no bar; crest orb, live context capsule and an action capsule float over the content (blur once scrolled). Most content area (0px reserved) and the most distinctive, but the least conventional and the hardest to make accessible (focus order, contrast over moving backgrounds).

Sim gets the same three treatments (Sim home/team in the sheets); in every direction the Sim header is one row plus the status chips, 97px to 52px (V1/V3) or ribbon (V2).

## 4. Phased migration plan (after a pick)

1. **Foundations, no visual change**: `lib/appHeader.ts` (pure rules + tests, both platforms), `AppHeader` shells wrapping the existing `ShellHeader`, a source-scan guard that fails when a header title equals its pill label.
2. **Switcher sheet**: `LeagueSwitcherSheet` on the shared `Sheet` (web), app parity with the existing sheet; league avatars; error/retry; keyboard/overlay behaviour; guard tests. Ships first because it is independent of the header look.
3. **Root template on Today, Team, Trades, League** (web shell + app): chosen direction, title removed where the pill names the page, hero eyebrows rewritten, collapse behaviour, light/dark captures at 320/390/430 via `header_audit.mjs`.
4. **Detail + Sheet templates**: Player, Pick, Manager, Account; unify `Sheet` and PQV chrome.
5. **Sim game header** on one row (both platforms), Sim status chips unchanged.
6. **Immersive + remaining pages** (onboarding, paywall, sample league banner to a one-line pill), retire the legacy header and the app's in-content `BrandHeaderBar` (the app's stacked headers become one).
7. Update `docs/ui-patterns.md`, the module board and the audit scripts; remove the kill switch after one release.

Each phase is a small PR, web and app together, behind the shell flag until phase 3 lands.

## 5. Decisions needed

- Direction: V1, V2 (recommended) or V3. Sim: same direction or V3 for Sim only.
- Rule confirmation: no page title on tab pages (the pill names them). This is the biggest visible change.
- League crest source for leagues without an avatar.

## 6. Status (2026-11-17)

Phases 1 to 7 shipped: see docs/ui-patterns.md, "Header system", for what each delivered (4: SheetChrome, 5: Sim header, 6: immersive minimal chrome, 7: AppHeader + BrandHeaderBar retired, guard `scripts/check_legacy_header.mjs`). Open: the kill switch (`NEXT_PUBLIC_BOTTOM_NAV=off`) is kept for one more release; the sample-league banner to a one-line pill is not done.
