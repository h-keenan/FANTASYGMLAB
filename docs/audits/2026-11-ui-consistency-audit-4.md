# UI consistency audit 4 (2026-11-14): every page and module, web and app

Trigger: coridian_ asked for another end-to-end module audit and "overall, UI consistency throughout the whole site" (Fantasy Desk and Fantasy Sim, web and app).

Method
- Inventory: 38 web routes (`web-next/src/app/**/page.tsx`), 45 app screens, shared-template adoption counted per file.
- Rendered: `scripts/sim_layout_playwright/module_scan.mjs` (fixture league, Today, Team, Trades, League, Matchup, Waivers, Players, Trade Finder, Analyzer, GM Plan, Games, Recaps, Draft Center, public sample) at 360 / 390 / 430, dark and light, legacy header and the phone shell (`NAV=bottom`), full-page shots, plus a token census of what each page actually renders (radii, type sizes, weights, button heights, gold elements, headings, controls; `METRICS=1`). The app (React Native) cannot be rendered here, so it was audited from code and the shared twins; app findings are marked "code".
- Limits: fixture players have no photos (black avatar discs are fixture, not a bug). Sim tabs were audited from code and from `2026-11-sim-ui-pass.md` fixtures. Trade Analyzer renders its error boundary with the empty stub API, so it was read, not seen.
- Prior audits read and not repeated: ui-patterns, cross-product module audit, module-variant-sheets, live-site-qa, ui-pass-3. Items they already track are cross-referenced, not re-listed.

## (a) Inconsistency matrix

Legend: Fixed = shipped in this audit's PRs (#1939, #1941). D# = needs a decision (variants in `docs/audits/ui-pass-5/`). Open = clear, queued, not started.

| # | Dimension | What differs | Evidence (file / measurement) | Status |
|---|---|---|---|---|
| S1 | Spacing scale | Web tokens `--space-*` exist, but 2040 inline `style={{` blocks in components; app uses `spacing.*` plus literals. Page gaps agree on phone (16px gutter, 12px between modules) in all 14 captured pages | `web-next/src/components/*` | Open (no visual defect found; migrate when touching) |
| R1 | Radii | Web captured radii: 20px cards, 14px controls, 12px tiles, pill chips; consistent. Outliers: `.filter-input/.filter-select` were 0 (square) next to 14px `Select`; non-glass `PillRow` is square while app `SegmentedTabBar` is `radii.pill`; hand-rolled outline buttons were 0 | `globals.css` `.filter-input`; `PillRow.tsx`; census `controls` | Controls fixed (#1939); segmented shape = **D1** |
| T1 | Type scale | App: 8 fontSize literals dominate (13.5, 12, 12.5, 14.5, 15.5, 16.5) beside a `typography` role table; floor tests exist both sides (`typographyMinimums`, `uiSizingGuard`). Web 11px text: 102 sites (`text-[0.6875rem]`), allowed floor | `mobile/src/theme.ts`, tests | OK (guarded) |
| T2 | Section titles | `SectionHeading` default = 21.6px/900 uppercase on League, Matchup, Waivers, Games; Today "Do next" = 18px/800 (`size="compact"`). Two scales for one role | census `headings` per page | **D2** |
| T3 | Weights | 500/650/750/800/900 all in use for titles; census shows 800 for card/module titles, 900 only on `SectionHeading` default | census | rides D2 |
| C1 | Colors, semantic tokens | Gold (premium token or amber) on non-premium roles: lens name "Dynasty" in the header of all 13 pages, rank tiles (`T-1`, `#1`), posture chip, "Need WR", Top Waiver Target border/star/chip, playoff odds `60%`. Waivers 7 gold elements, GM Plan 5, Today 2. Premium token referenced in 48 web / 68 app files | census `gold`; `Header.tsx:257,174` | **D5** |
| C2 | Hard-coded colors | Web 1 component file with hex literals (outside share cards), app 6; rgba in 5 web / 10 app files | grep | OK |
| H1 | Page help "?" | Two mechanisms: header slot (`PageTitle info`) vs labelled inline row (`BeginnerHelp` on My Team, Matchup, League Rankings, Waivers x2, Today) which reads as an orphan line | `MyTeamContent.tsx:273`, `MatchupContent.tsx:96`, `LeagueRankingsContent.tsx:365`, `WaiversContent.tsx:255` | **D3** |
| H2 | Headers | Legacy `Header.tsx` is `flex-wrap`: on Trade Hub and League Rankings at 390 the search/bell/account icons wrap to a second row; Today does not. Phone shell (`ShellHeader`) is one 52px row everywhere but on for the founder only | `Header.tsx:456`, `lib/shellNav.ts shellNavEnabled`; legacy vs shell captures | **D4** |
| E1 | Empty states | `EmptyState` 51 web / 45 app files, `ErrorState` 42 / 55; bespoke "No ... yet" text remains in Sim tabs and Recaps | ui-pass-3 #9 | tracked |
| E2 | Error states | App reports failed saves with `Alert.alert` at 11 "Could not ..." sites (GM Targets, rename/remove league, export, test notification); web uses inline/in-app toast. No generic app toast outside Sim | `PlayerDetailScreen.tsx:1163`, `MoreScreen.tsx:218,363`, `HomeScreen.tsx:194`, `PlayerLeagueActions.tsx:89` | **D7** |
| E3 | Retry verb | "Retry" (7 sites) vs "Try again" (35) | `ConfirmInPlace`, `PublicTradeAnalyzer`, app Portfolio/ESPN/Paywall | Fixed #1939 + guard |
| L1 | Loading states | Skeleton set landed (#1932). Residual "Loading" text in 9 web files (auth/boot screens, LoadingScreen itself) and `ActivityIndicator` in 13 app files (buttons, login, paywall) | grep | OK / mostly intentional |
| B1 | Button styles | Hand-rolled cyan-outline buttons (square, 36 / 44px / chip sizes): Waivers + GM Plan "View details", Trade Analyzer + Trade idea "Share"; app GM Plan actions, Paywall retry | `WaiversContent.tsx:210`, `GmPlanContent.tsx:223`, `TradeAnalyzerContent.tsx:246`, `TradeIdeaCard.tsx:105`, `GmPlanScreen.tsx:action` | Fixed #1939 (`accentOutline`, web + app) + guard |
| B2 | Button states | Disabled filled button = muted fill on black, no edge: "Find Realistic Trades" looked like a stray label | `Button.tsx`, census | Fixed #1941 |
| B3 | Button heights | Census: 44 (standard), 40 (Trade Hub chips), 54 (hero/pill), 36 (Trade Finder pick actions), 16/22 (text links), 56-214 (Waivers cards). 16px text links are inside 44px hit areas | census `btnH` | OK; 36px Trade Finder actions open |
| K1 | Module trailing control | `->` navigate, `+` / `-` expand, `Open ->`, `All ->`, `+ All ->`, `Full analysis` + `+`, `View all` + `-`, "Review" beside `+` | Today, GM Plan, Team, Waivers captures; `DashboardContent.tsx`, `TodayModule.tsx`, `StatusHeader.tsx` | **D6** |
| K2 | Verbs | "View all" (5) vs "Show all" (7) vs "See all" (6); "Open"/"View details"/"Details" for the same jump; "Value"/"Trade value"/"Score" for one stat | grep | Value fixed #1939; link verbs ride D6 |
| V1 | Chips / badges | `PlayerBadge`/`ToneBadge` consistent in captures; posture/lens chips use gold (C1) | census | rides D5 |
| V2 | List rows | Player rows on the approved template: Players, My Team, Sim parts. Own rows: Trade Finder (checkbox rows), Waivers (4 row types), Live Draft, Analyzer pickers, Matchup lineup, Recaps. Trade Finder names were wrapping inside words at 390 | `TradeFinderContent.tsx RosterPickRow`, capture | Squeeze fixed by `Value` caption (#1939, re-captured); template move = **D9** |
| V3 | Cards | `glass-surface` / `CompactModule` everywhere on phone; hand-rolled glass in 7 web / 70 app files; app `GlassCard` 14 files, web none | grep | tracked (ui-pass-3 #10) |
| V4 | Sheets / popups | One `Sheet` + `useSheetDragDismiss`, heights 56-80% (ui-patterns). App uses native `Alert.alert` (E2) for 24 sites incl. confirms | grep | E2 |
| V5 | Toasts | `UndoToast` (GM targets) + Sim `notify`; app same. No shared success/error toast | `ui/UndoToast.tsx`, `SimRealism.tsx` | **D7** |
| I1 | Icons | Nine parallel glyph files (ui-pass-3 #21); header uses emoji-free SVG; `?` help is a text glyph in a circle, `+`/`-`/`->` are text characters | | tracked |
| P1 | Tab / pill rows | One page tab row per page holds (module_scan: no page exceeds its allowed tablists; GM Plan and Trade Finder carry a second strip by design, flagged `maxTablists: 2`). Inline segmented controls are square vs app pill; `League` / `Games` / `Recaps` use a native select as their view switch | `PillRow.tsx`, `ViewSelect.tsx` | **D1** |
| N1 | Number formatting | `toFixed(1)` 70, `(0)` 3, `(2)` 2; money via `Money` (green); ranks `#n`; mixed `Round(...).toLocaleString()` | grep | OK |
| N2 | Dates | 6 `toLocaleDateString` + 2-3 `Intl.DateTimeFormat` per platform, no shared helper | grep | Open (low) |
| Y1 | Copy tone / casing | Titles: UPPERCASE kicker + Title Case in `SectionHeading`, sentence case in Dashboard/GM Plan; button labels sentence case except "Find Realistic Trades", "Share Trade" | `TradeFinderContent.tsx:467`, `TradeIdeaCard.tsx` | rides D2; button Title Case = Open (2 labels) |
| Y2 | Links | Link style: accent text with `->` (Open, All, Full GM Plan), accent text no arrow (View all), `Sleeper ↗` external | `DashboardContent.tsx` | rides D6 |
| F1 | Focus / pressed | Global focus ring + one-press feedback verified by existing tests (`pressFeedback.css.test.ts`); no new gaps | tests | OK |
| X1 | Dark / light parity | module_scan `THEME=light` runs clean (no overflow, same module counts); light gold uses `--color-premium` darker amber | shell-light run | OK |
| W1 | Web vs app parity | Segmented shape (P1), Alert vs toast (E2), `Value` caption and `accentOutline` now twins, `Retry` copy now twins, PlayerName ladder in compare chips now twins, `TrendChart`/skeletons parity per #1932 | | partly fixed |

## (b) Module-by-module remaining problems

Where the page is already on the shared stack and clean in captures: Today, My Team, Trades Hub, League Rankings, Matchup, Players, Games, Recaps (empty), Draft Center, public sample. Remaining per module:

- **Today**: `Top priority` card shows `+` and a "Review" button side by side (K1); `Position rooms` word-level red/green/amber text mixes with gold rail (C1).
- **My Team**: orphan "? My Team and value tiers" row above the hero (H1); `Franchise T-1` tile is gold-outlined (C1).
- **Trades Hub**: `Trade ideas 3` module has no expand glyph while sibling modules do, gold rail (C1/K1). Legacy header wraps (H2).
- **Trade Finder**: row is a special case (V2/D9); name wrap fixed; `Find Realistic Trades` edge fixed; title-case button label; pick sub-cards nest a third border level inside the module.
- **Trade Analyzer / Multi-team**: not on `TradeCompactCard`, error boundary only under the stub API (read, not seen); inline styles 40 / 30 blocks.
- **Waivers**: only page with its own hero (gold card, D8), 21.6px section titles (D2), two stacked orphan "?" lines (H1), recommended-add rows 127px at 360 (scan limit is 96; wraps "Strong Opportunity" onto two lines, clean at 390/430), position-snapshot tiles hand-rolled, `Drop candidate` card header misaligned, square select/search (fixed: radius).
- **League Rankings**: heading scale (D2), orphan "? playoff odds", `Franchise/Draft Capital/Starters/Bench` bars hand-rolled.
- **Matchup**: "Week 10 (?) this matchup page" orphan row; `Fix a weak spot` 21.6px title.
- **GM Plan**: five gold elements, `+` plus "Full analysis" link in one module (K1), two tab rows (stance picker + page tabs) by design.
- **Games / Recaps**: view switch is a native select styled as a page title (P1).
- **Players**: square position row (D1); otherwise on template.
- **Account / Portfolio / Commissioner / Premium / Founder**: no `CompactModule`/`Hero` (ui-pass-3 #14), unchanged.
- **App**: `Alert.alert` errors (E2), 70 files hand-roll glass, `ActivityIndicator` in 13 files (mostly in buttons), `PlayerCompareScreen` 676 lines with no shared template, `TradeAnalyzerScreen` 1259 lines.
- **Fantasy Sim**: no numeric OVR or trade value found in Sim components (grep clean); letter grades hold. Remaining: tabs without `CompactModule` (ui-pass-3 #9), `SimDraftGrid` hand-rolled surface, `SimRecapStory` fallback fact prints a bare full name in the app and web (`SimRecapStory.tsx:139,185`, only when the player object is missing).

## (c) What shipped

- **#1939** `accentOutline` Button variant (web + app) replaces 4 web and 4 app hand-rolled outline buttons; "Retry" becomes "Try again" everywhere; `.filter-input/.filter-select` take the control radius; `ValueStat` caption "Value" (this alone fixed the Trade Finder name wrap, re-captured at 390); Player Compare chips use `PlayerName`; `uiConsistencyGuard.test.ts` (5 source-scan rules); `module_scan.mjs` audit knobs (`NAV`, `FULL`, `METRICS`, `THEME`).
- **#1941** disabled filled buttons keep a hairline edge (web + app); the last two raw `<select>`s use `Select`; `uiControlsGuard.test.ts`.
- This PR: this document and the mockups.

Not started on purpose: anything that changes a visible pattern across many screens without your pick (D1-D9), the Trade Finder row migration (D9), a shared app Toast (D7).

## (d) Decisions for coridian_

Mockups: `docs/audits/ui-pass-5/*.html` (open at 1290px). Recommended variant is outlined in cyan.

| # | Question | Sheet | V1 (recommended) | V2 | V3 |
|---|---|---|---|---|---|
| D1 | Inline segmented control shape | sheet 1 | pill track like the app | square + underline (today) | underline only |
| D2 | Section title scale | sheet 1 | compact 18/800 everywhere | big 21.6/900 | kicker + sentence case |
| D3 | Page "?" explainer | sheet 1 | header "?" only | uniform inline row | move to More + first-run tip |
| D4 | Phone header | sheet 2 | shell for everyone | legacy, never wrap | legacy, wrap by design |
| D5 | Where gold is used | sheet 2 | premium + primary only | "best" markers only | as shipped |
| D6 | Module trailing control | sheet 2 | chevron / arrow only, no text links | `+` and an "Open" pill | as shipped |
| D7 | App failure feedback | sheet 3 | shared in-app toast | inline error + Try again | native alert |
| D8 | Waivers Top target | sheet 3 | on the Hero template, cyan | first row of the list | as shipped |
| D9 | Trade Finder roster row | sheet 3 | approved player row + leading check | two-line row | selectable chips |
