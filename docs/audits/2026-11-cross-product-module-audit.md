# Cross-product module audit: FantasyDesk and Fantasy Sim (2026-11-14)

Trigger (coridian_): "do an end-to-end module audit. See what's cross FantasyDesk and Fantasy Sim and see how they can be improved into the
compact and expanded window style." Status: research and plan. **No product code changed.** The "compact and expanded window style" is the
shipped `CompactModule` contract (`docs/ui-patterns.md`, `lib/moduleTemplates.ts`): collapsed = title + 1-2 line summary of real data + at most one trailing
action; expanded = inline body or a shared `Sheet`.

**Basis.** Everything below is read from `origin/main` at `9b42fc98` (PR #1892 merged), fetched at the start of this task. Other agents are migrating
Waivers, Trades, GM Plan, League and Fantasy Sim screens right now; anything they land after `9b42fc98` is not reflected here, so
re-run the counts (script in 1.1) before cutting a PR from section 5. Open PRs at start (#1659, #1579, #1361, #1161) do not touch UI modules.
Docs read: `CLAUDE.md`, `docs/ui-patterns.md`, `2026-11-module-templates-rollout.md`, `2026-11-universal-modules-audit.md`,
`2026-11-information-architecture.md`, the sim audits (`2026-11-sim-*.md`; they are model/engine audits and contain no UI findings beyond the projection
presentation notes). No `data/players.db` access, no `rankings.load_players`, no `npm install`.

**Confidence.** "Measured" = grep/wc on the tree. "Read" = I opened the file. "Est." = judgment, to be re-measured in Phase 0. File counts are files, not call sites.
App import counts use single-quote relative imports (`from './X'`). Where a count looks surprising I say so.

---

## TLDR

- Sim is NOT a separate UI stack. Of 239 web / 237 app component files, about 51 web / 37 app are `Sim*`; they import the shared atoms (`ToneBadge` 14 sim files,
  `PositionBadge` 9, `EmptyState` 14, `Skeleton` 16, `PillRow` 11, `AccentCard` 16, `SectionHeading` 14 incl. sim wrapper, `CompactModule` 6, `ui/Sheet` 5) and the
  Sim player row is already a thin adapter over `PlayerListRow`. The Sim player sheet is already an adapter onto the real Player Quick View (`lib/simPlayerSheet.ts`).
  That adapter pattern is the model for everything else.
- The duplication is at the **second layer**: composite modules. Sim built its own sheet shell (`SimSheet`), fold (`SimFold`/`SimCollapse`), notice/banner
  (`SimNotice`, `SimPreviewBanner`), stat tile (`SimStat`, `Fact`, `Tile`), notification bell, team sheet, standings, draft room, trade inbox/builder,
  recap, and header, while FantasyDesk has parallel versions of each. ~10,000 lines of sim UI per platform (web 10,008, app 9,196).
- The reverse is just as true: **`PlayerListRow` (the good row) is used only by Sim and `TradePickerSheet` on both platforms**. The real pages (Players, Waivers, My Team, News,
  Live Draft, Trade Finder, GM Plan) still use `PlayerIdentity`/`PlayerRow` plus 6+ local row components. So "unify Sim onto real" is half wrong: on rows, Sim is ahead.
- Biggest unshared pieces: (1) pop-up shells, (2) the stat tile (4 copies of `Fact`), (3) team sheet / manager profile, (4) draft room, (5) trade inbox/builder/verdict,
  (6) notifications, (7) recap (`StoryCarousel` is used ONLY by the Sim recap; `LeagueRecapsContent` is 1,116 lines with no CompactModule), (8) standings, (9) header and
  orb chrome, (10) charts/gauges (6 hand-rolled).
- Recommended order (section 5): finish module adoption on real pages that already have the template (Waivers, Trade idea cards, GM Plan, Recaps), **in the same PRs** swap the matching
  Sim screen onto the same module via an adapter, and do sheet-shell + stat-tile + feedback-state consolidation first because they are small, risk-free and touch everything.

---

## 1. Inventory of module families

### 1.1 Method and headline counts

- Counted with `grep -rlE` over `web-next/src` and `mobile/src` (`*.tsx`, non-test); "sim" = a `Sim*.tsx`/`GmGame*` file, "real" = everything else. Cells are `sim/real` file counts.
- Totals (measured): web `components/` 239 files, 48,312 lines (Sim 10,008); app `components/` 237 files, 39,514 lines (Sim 9,196); app `screens/` 45 files, 25,880 lines (`GmGameScreen` 1,215).
- Largest Sim files, web/app: `SimGameContent` 1,208 / n/a (app: the screen), `SimGameParts` 768/746, `SimGameTeam` 640/630, `SimGameOffseason` 595/583, `SimGameTrades` 527/583, `SimGameDraft` 441/453.
- Reproduce: the regexes in the "Matches" column of the table below, run from the repo root.

### 1.2 Family table

Legend: SHARED = one implementation used by both; PARTIAL = Sim wraps or reuses it in places; SPLIT = two implementations of the same job. Counts are `sim/real` files (web | app).

| Family | FantasyDesk renders it with | Fantasy Sim renders it with | Shared? | Near-duplicates (same job, different code) | Counts (web, app) |
|---|---|---|---|---|---|
| **Player row** | `PlayerRow.tsx` (`PlayerIdentity`, 107 ln), local rows `PlayersContent#PlayerRow`, `MyTeamSections#RosterRow`, `WaiversContent#RecommendedRow/FreeAgentRow`, `NewsContent#NewsIdentityRow`, `TradeAssetExchange#TradeAssetRow`, `GmPlanContent#ProtectPlayerRow`, `SuggestedDrop#DropPlayerLine`, `MatchupLineup#SlotRow`; app `PlayerIdentityRow` (541 ln), `PlayerInsightRow`, `CompactPlayerModule`, `TradeAssetRow` | `SimPlayerLine`, `SimRosterLine`, `SimMiniPlayer`, `SimDraftRow`, `SimAssetLine` -> all wrap `PlayerListRow` (268 ln) | PARTIAL, reversed: the shared row is Sim-led | 7+ real row implementations vs 1 sim wrapper; `PlayerListRow` imported by 2 sim files + `TradePickerSheet` (web and app), 0 real pages | `PlayerIdentity` 1/14 web; `PlayerAvatar` 1/18; `PositionBadge` 9/30 web, 9/30 app |
| **Pick / asset row** | `PickRow.tsx` (100), `PickGroupList` (92), `TradeFinderContent#OwnedPickRow/RosterPickRow`, `GamesContent#RosterPickRow`, app `DraftPickAssetRow` (149) | `SimPickLine`, `SimPickGroup`, `SimTeamHistory#PickRow` | SPLIT | `PickRow`, `SimPickLine`, `SimTeamHistory#PickRow`, 2 `RosterPickRow` copies | 7 web impls |
| **Stat tile / stat strip** | `StatRows` (153), `StatStrip` (39), `SnapshotTile` (133), `ValueStat` (34), `TeamStatusHero#Fact`, `SeasonReviewSections#StatTile`, `LeagueRoundupTab#Stat`; app `MetricCard` (200), `DashboardStatRow` (60), `StatRows` (159) | `SimStat`, `SimGameDynasty#Fact`, `SimRecapStory#Fact`, `SimGameTeamSheet#Fact`, `SimToControl#Tile` | SPLIT | **4 local `Fact` components** (web: `TeamStatusHero`, `SimGameDynasty`, `SimRecapStory`, `SimGameTeamSheet`; app: same four files), plus `Tile`, `StatTile`, `Stat` | stat tiles 7/37 web, 9/25 app |
| **Card / surface** | `AccentCard` (42), `GlassCard`/`GlassPanel`/`AnimatedCard` (app), inline `var(--glass...)` | `AccentCard` 16 sim files; inline glass in 4 sim files (web) | SHARED (mostly) | inline glass: web 4/2 files, app 13/51 (the `colors.glass` hand-roll the universal audit counted) | `AccentCard` imported by 16 sim files (web); app 16/34 |
| **Chips / badges** | `ToneBadge` (61), `PositionBadge` (40), `PlayerBadge` (134, `PlayerBadges`, `BadgeLegend`), `PostureChip`, `WeatherReasonChip`, `PlayerInjuryBadge`, `NavProMarker` | `SimToneBadge` (thin wrapper over `ToneBadge`), `SimPlayerChip` (wraps shared), `SimGeneratedChip`, `SimStatusChips` | SHARED | `PostureChip`/`SimGeneratedChip`/`SimStatusChips` are label+tone chips re-drawn locally | `ToneBadge` 14/54 web, 14/59 app |
| **Collapsible / compact module** | `ui/CompactModule` (156), `ModuleTemplates` (`Hero`, `StatStripModule`, `LinkModule`; 213), legacy `Collapsible` (96, 1 file), 8 raw `<details>` files | `SimFold`, `SimCollapse` (both render `CompactModule`), `SimSectionTitle`, `SimSeeAll` | PARTIAL | `SimFold` (`SimGameParts:625`), `SimCollapse` (`SimGameDynastyParts:36`), `Collapsible`, `<details>` x8 | `CompactModule` 6/12 web, 6/8 app; real pages with zero: `LeagueRecapsContent`, `TradeAnalyzerContent`, `TradeFinderContent`, `GmPlanContent`, `LiveDraftContent`, `DraftCenterContent`, `PortfolioContent`, `AlertsContent`, `NewsContent`, `CommissionerContent`, `GamesContent`, `PlayerCompareContent`, `MultiTeamTradeContent`, `TradeHistoryContent` (14 pages, ~8,200 lines) |
| **Sheets / popups** | `ui/Sheet` (187), `PopupShell` (86), `PlayerQuickView` (742), `ManagerProfileSheet` (265), `PercentileExplorerSheet` (554), `TradePickerSheet` (499), `AlertsDropdown` (205), `EmbeddedCheckoutModal`, `TradeOutcomePrompt`, `FilterSheet`, `MatchupPlanner#SwapSheet`; app `Sheet` (128), `SwipeDismissSheet` (284), 33 files using `SheetModal`/`SwipeDismiss`/`<Modal` | `SimSheet` (`SimGameParts:407`; 7 call sites in 6 files), `SimPlayerSheet`, `SimTeamSheet`, `SimToSheet`, `SimMatchupSheet`, `ClaimSheet`, `SimGeneratedNoticeSheet`; sim uses `ui/Sheet` in 5 files | PARTIAL | web has **10 files wired to `useSheetDragDismiss`** (`Sheet`, `PopupShell`, `SimSheet`, `PlayerQuickView`, `TradePickerSheet`, `AlertsDropdown`, `EmbeddedCheckoutModal`, `GmOrb`, `TradeOutcomePrompt`, `SheetHandle`) = 6 shells that should be 1 `Sheet` plus a `size`/`bare` prop; `ui-patterns.md` lists 8 un-migrated | `ui/Sheet` 5/6 web, 3/5 app |
| **Tabs / filters** | `PageTabBar` (39; family strip), `PillRow` (281), `Tabs` (115), `TradesTabBar` (18), `FilterSheet` (153), `TabGlyph`; app `SegmentedTabBar` (176), `ViewModeToggle` (88), `FilterDropdownButton` (130), `FilterSheet` (184) | `PillRow` 11 sim files (tabs and pills), `Tabs` 1, tab plans in `lib/sheetTabs.ts` (real) vs `simPlayerSheet.ts`/`SimGameTeamSheet` (own plan) | PARTIAL | `PageTabBar` 0/9: Sim has no family strip; Sim screens stack 3 control rows (Players tab: search + position pills + 2 selects + All/Waivers toggle, per IA audit 1.4) | `PillRow` 11/30, `PageTabBar|SegmentedTabBar` 0/9 web, 11/31 app, `role=tablist` 0/3 web, 0/4 app |
| **Empty / error / loading** | `EmptyState` (105), `ErrorState` (99), `LoadingScreen` (39), `Skeleton` (60) web; app `EmptyState`, `ErrorState`, `SkeletonBlock` (157), `BrandedSpinner` | `EmptyState` 14 files, `Skeleton` 16, `SimNotice` for errors, local `SimLeagueWho#Loading` | PARTIAL | `ErrorState` 1/39 web, 15/38 app: **web Sim uses `SimNotice`/inline text for errors**; `Loading...` text 0/11 web, 0/5 app; `ActivityIndicator` 1/14 app; bespoke "No ... yet" lists in `2026-11-universal-modules-audit.md` P1 | `EmptyState` 14/36 web, 11/32 app |
| **Banners / notices** | `SampleLeagueBanner` (100), `FreeLimitNote`, `FreeLeagueLimitNote`, `LimitWall`, `EspnUnavailableState`, `LeagueWarmupProgress`, `PremiumUpsellCard`, `UsageProTeaser`, app `ScreenInfoNote` | `SimNotice` (`:506`), `SimPreviewBanner` (`:471`), `SimGeneratedChip`, `SimRookieNoticeGate` | SPLIT | 9 real + 4 sim banner shapes, none shares a `Banner` primitive (tone, icon, one action, dismiss) | 2/11 web, 2/4 app by name regex (est.: undercounts) |
| **Toasts / undo** | `ui/UndoToast` (97), `ConfirmInPlace` (318) | toast inside `SimGameParts` (portal + `noticeDismissMs`), `ConfirmInPlace` 2 files | PARTIAL | `UndoToast` vs the Sim toast: same timing lib (`lib/compactModule.ts#noticeDismissMs`), two renderers | `ConfirmInPlace` 2/10 web, 2/8 app |
| **Forms / setup** | `Input` (45), `OptionRadioGroup` (71), `Toggle` (68), `SleeperImportForm` (424), `EspnImportForm` (373), `SignInForm` (507), `NotificationControls` (284) | `SimSetupParts` (194: `SetupCard`, `SetupField`, `SetupToggleGroup`, `SetupToggleRow`, `DifficultyTiles`, `SetupSummaryCard`, `SetupStickyBar`) | SPLIT | `SetupToggleRow` vs `Toggle`+`NotificationControls#Row`; `SetupToggleGroup` vs `OptionRadioGroup`/`PillRow`; `SetupField` vs `Input` | `Input` 5 sim files |
| **Headers / shell** | `Header` (579), `ShellHeader` (52), `AppShellBar` (103), `PageTitle` (70), `BottomTabBar` (75), `GmOrb` (391 web, 1,153 app); app `BrandHeaderBar`, `ScreenHeaderTitle` | `SimGameHeader` (104) + `SimStatusChips`, `SimGameOrb` (117 web, 189 app), `SimOffseasonBar` | SPLIT (on purpose: sim has its own orb and phone shell) | `SimGameOrb` vs `GmOrb`: ~5 shared concepts (nav items, badge dot, press) with 2 implementations; app `GmOrb` is 1,153 lines | n/a |
| **Action bars** | `ShellActionSlot` (24), `.bottom-stack`, app `QuickActionsGrid` (91) | `SimActionBar` (104), `SimOffseasonBar` (102), `SimToControl` (231), `SetupStickyBar` | SPLIT | the template catalog already names `SimActionBar` as THE action bar (`moduleTemplates.ts`), real pages do not use it | 1/0 |
| **Charts / gauges** | `ui/TrendChart` (235, shared via `WeeklyPointsChart`, `RatingHistoryChart`, `SeasonReviewSections`, `ModuleTemplates`), `ManagerTendenciesCard` (89), `ModelRadarChart` (59), `PercentileExplorerSheet` (own chart), `MatchupLineup`/`PlayerCompareContent` (own bars), `OvrGauge` (29), `ValueRing` (42), `ConfidenceMeter` (66), `LeanBarMeter` (35), app `CircularProgressRing`, `PercentileBar`, `TradeValueBar` | `WeeklyPointsChartLazy` (2 files), `OvrGauge` via the `rating` stat, `SimDraftHero` progress bar, `SeasonReviewSections` charts, `SimDraftGrid` | PARTIAL | 5 distinct gauge/meter components (`OvrGauge`, `ValueRing`, `ConfidenceMeter`, `LeanBarMeter`, `CircularProgressRing`) | chart/gauge files 3/19 web, 3/20 app; `<svg` files 7/42 web (mostly glyphs) |
| **Glyph / icon sets** | `NavDestinationGlyph` (298), `TabGlyph`, `SnapshotTileGlyph`, `EventTypeGlyph`, `PremiumGlyph`, `TradeCategoryGlyph`, `OffseasonGlyph`, `IconRow`, `TrophyIcon` | `SimGlyph` (116), `SimReviewGlyph`, `SimDraftGlyphs`, `SimCrest` (team crest; shared into real `TeamAvatar` by 10 files) | SPLIT | 10 parallel glyph files per platform (already in universal audit P3 item 8) | |
| **Notifications** | `AlertsDropdown` (205) in `Header`, `AlertsContent` (330), `NotificationControls`, app `PushPermissionPrompt` | `SimNotificationBell` (161 web, 166 app), `lib/simNotifications` | SPLIT | bell + dropdown + unread dot + row: 2 implementations; no shared `NotificationRow` | |
| **Recap / story** | `LeagueRecapsContent` (1,116), `LeagueRoundupTab` (262), `SeasonReviewSections` (292, shared by 8 sim files), app `RecapScreen`, `RecapReadyCard`, `RecapShareCard` | `SimRecapStory` (330) on `StoryCarousel`, `SimGameRecap` (351), `SimFinalView`, `SimGameOffseason#ReviewStage` | PARTIAL | `StoryCarousel` is wired only to the Sim recap (1/1 files); real recap is a long page | |
| **Draft** | `LiveDraftContent` (587), `DraftCenterContent` (402), `DraftScoutingTab`, `CollegeScoutingContent` (432) | `SimGameDraft` (441), `SimDraftBoard` (230), `SimDraftGrid` (89), `SimDraftHero` (153), `SimDraftOverview` (133), `SimScoutingSections` | SPLIT | on-the-clock card, board grid, best-available, queue, recommendations exist twice; Sim draft room already uses `CompactModule` (6/6 files) and real does not | |
| **Trade** | `TradeAnalyzerContent` (1,074), `TradeIdeaCard` (375 web / 705 app), `TradeAssetExchange`, `TradeOddsEffect`, `VerdictTrust`, `TradePickerSheet` (499), `MultiTeamTradeContent` (741), `TradeHubContent` (204) | `SimGameTrades` (527: `Inbox`, `OfferCard`, `VerdictCard`, `Builder`, `PlayerList`), `SimTradeBlock` (205) | PARTIAL | picker shared (`TradePickerSheet`); inbox, offer card, verdict, builder, block are Sim-only code of the same jobs | |
| **Team / manager sheet** | `ManagerProfileSheet` (265, tabs from `sheetTabs.ts`), `OpponentProfileCard` (149) | `SimTeamSheet` (276: `TeamBody`, `Fact`, tabs inline), `SimTeamCard` (91), `SimLeagueTeamsView` | SPLIT | same job (scout a team: strengths, needs, roster, record) twice | |
| **Player quick view** | `PlayerQuickView` (742 web, 579 app) | `SimPlayerSheet` via adapter | SHARED | no duplicate; but sim sheet fills hero tiles from `simHeroFeed` (ranks only) | |
| **History / transactions** | `TradeHistoryContent` (126), `PlayerCareerTab` (128), `PlayerScheduleTab` (171), `AlertsContent`, `LeagueRecapsContent` history | `SimPlayerHistory` (122), `SimTeamHistory` (132), `SimRealHistory` (105), `SimGameDynasty` (156), `SimLeagueWho` | SPLIT | year/season rows (`SimGameDynasty#YearRow`, `SimTeamHistory`, `PlayerCareerTab`) each draw their own | |
| **Standings / rankings** | `LeagueRankingsContent` (545; `RankingRow`, `PlayoffOddsRow`), app `LeagueStandingStrips` | `SimStandingsList`, `SimStandingsCard`, `SimScoreCard`, `SimLeagueTab` | SPLIT | | |
| **Matchup / schedule** | `MatchupContent` (831), `MatchupLineup` (460), `WeeklyMatchupCard` (app), `PlayerScheduleTab` | `SimMatchupCard`, `SimMatchupSheet`, `SimScoreCard` | SPLIT | `MatchupLineup#SlotRow/CompactSlotRow` vs `SimGameTeam#LineupRow` vs `SimRosterLine`+slot column | |
| **Waivers / free agents** | `WaiversContent` (849), `WaiverRecommendationCard` (app 471), `SuggestedDrop` (508/435) | `SimPlayerBrowser`, `ClaimSheet`, `SimWaiverCard`, `SimByeCard`, `SimGameReserves` | SPLIT | | |
| **News / feed** | `NewsContent` (278), `PlayerNewsTab`, `PlayerQuickViewNews`, `LiveFeedPanel` (134) | none for real news; Sim "Feed" tab + `SimGameHomeCards#SimLeagueMovesCard`/`SimInboxCard` | SPLIT (by design: no real news in sim) | | |
| **Share cards / modals (app)** | `*ShareCard`, `*SharePreviewModal` x7 | `SimReviewShareCard`/`Modal` | PARTIAL | `ShareCardChrome` (160) is the shared frame | |

### 1.3 Reading the counts

1. **Atoms are shared; composites are not.** Row/badge/state atoms have 10-60 users. Everything that composes them (sheet shell, tile, fold, banner, toast, bell, team sheet) exists twice.
2. **Sim is ahead on three patterns** the real product should adopt: `PlayerListRow` (aligned stat columns, single trailing action, badges), `CompactModule` in the draft room/home (8/12 sim screens), `StoryCarousel` for recaps.
3. **Real is ahead on three** Sim should adopt: `ErrorState` (39 real files vs 1 sim web), the page-family tab strip (`PageTabBar` 0 sim files), and `InsightLink` taps (0 sim files; stat-to-board navigation).
4. **Naming smell**: shared code carries sim names (`simOpenKey` in `ui/CompactModule.tsx`, `simLayout` import, `fgl:sim-open-change` event, `lib/simSummaries.ts` feeding the shared module). Harmless now, but it makes "shared" look sim-owned and will trip the twin check on rename. Rename in the same PR as the first real-page persisted-open fix (est. S).

---

## 2. The cross-product set

Rules every module below follows (from `docs/ui-patterns.md` and `moduleTemplates.ts`, restated so each spec is self-contained):

- **Compact** = Tier T0/T1 (56-96 px): one title line, at most 2 lines of real data, at most one trailing action, whole header is the tap target. Never an empty header (`collapsedVerdict`, `MIN_COLLAPSED_CHARS`).
- **Expanded** = one of three, chosen by body size: **inline** (body under ~1.5 screens, no navigation needed), **sheet** (`expandIn="sheet"` or `Sheet`: long, tabbed or independent of the page), **page** (a destination with its own URL/deep link: PQV profile, trade analyzer).
- **Adapter rule** (the Sim player sheet precedent, `lib/simPlayerSheet.ts`): the shared module takes a presentation model; each product writes a pure `lib/<module>Model.ts` adapter that turns its payload into that model. No product conditionals inside the component.
- **Sim data rules** (read from `lib/simGame.ts:111`, `docs/fantasy-sim-*.md`, `lib/simSeasonLabel`): (a) the model's internal rating (`value`, the 0-100 trade value scale) is never shown, no label, no sort; use `overall` (OVR) for anything the player sees; (b) no real news, no real values/market, no Pro gating inside the game; (c) every season is named `S3 2028` (`simSeasonLabel`); (d) projections for bye/out show "Bye"/"Out" (`f79adbde`). Real: values/trade value/market ranks and Premium locks are allowed.
- **Adapter contract fields** every adapter must supply: `id`, `title`, `parts[]` (the compact summary), `action?`, `rows[]` (typed), `states` (`loading|error|empty|ready`), `source` (`"real"|"sim"`), and a `hidden: string[]` list the module asserts it never renders (the Sim leak guard, see 4.3).

### 2.1 Spec table (modules that exist in both products)

| # | Shared module | Real source today | Sim source today | COMPACT (1-2 lines, real data, one trailing action) | EXPANDED (form, adds, tabs) | Adapter differences |
|---|---|---|---|---|---|---|
| M1 | **PlayerRow / PlayerCard** | `PlayerIdentity` + 7 local rows | `SimPlayerLine`/`SimRosterLine` -> `PlayerListRow` | Line 1: avatar, name, POS badge, one `PlayerBadge` max. Line 2: `TEAM . Age . Bye` + injury pill. Right edge: ONE number OR one action (per `rowRightEdgeProblems`). Stats are aligned labelled pills only in list context (PROJ, OVR). | **Inline expand** for in-list detail (waiver row pattern from rollout 2026-11-14): value + gauge, why, usage, this add's roster move, "Player details" link. **Sheet** = Player Quick View (tabs Overview, Model, News, Schedule/Career). **Page** = `/players/[id]`. | Real: value/trade value, market rank, News tab. Sim: `overall`, projection, Bye/Out, no News tab, `SimPlayerSheet` adapter. Both already share PQV. |
| M2 | **PQV sheet** | `PlayerQuickView` (742) | `SimPlayerSheet` adapter | n/a (the Expanded of M1) | Sheet 56-80% height, tabs; hero tiles Value/OVR/Usage each `TapForWhy`; `Sheet` migration listed as pending in ui-patterns | Real: Value tile, News. Sim: rank tiles only (see U3 below), `seasonLabel` S3 2028, as-of cut of real data via `startYear` |
| M3 | **RosterLineup** | `MyTeamSections#RosterRow`, `MatchupLineup` slot rows | `SimGameTeam#LineupRow`, `SimRosterLine`+slot | `CompactModule` per group: "Starters . 9 players . Value 6,120 . Gibbs, Chase" / sim: "Starters . 9 . Proj 118.3 . 1 Out" ; action = "Set lineup" | Inline: slot-labelled `PlayerRow`s (slot column 3.25rem, FLEX keeps position badge); swap opens `SwapSheet` (shared `Sheet`). Tabs: none (groups are modules: Starters open, Bench, IR, Taxi) | Real adds value sums, IDP group. Sim adds taxi/reserves, auto-set lineup, soft roster limit |
| M4 | **TradeBuilder** | `TradeAnalyzerContent` (1,074), `TradePickerSheet` | `SimGameTrades#Builder`, `TradePickerSheet` (shared) | `CompactModule` "Trade builder . You send 2 . You get 1 . Fair" ; action = "Analyze" / "Send" | Page (a flow, not a window): two `AssetColumn`s of `Row`s (M1/pick row), verdict callout, odds effect, lineup warnings. Picker = `TradePickerSheet` | Real: trade value, odds, Premium share. Sim: net value as a verdict word ("Fair", "You win") never a number, roster-limit check, AI counter. |
| M5 | **TradeInbox / TradeIdea** | `TradeHubContent` idea cards (`TradeIdeaCard` 375/705) | `SimGameTrades#Inbox/OfferCard`, `SimTradeBlock` | One line: "Gibbs for Chase + 2027 R2 . Taco Tuesday . Fair for both" ; action = "Review" | **Inline expand** (idea cards are already tap-to-expand; rollout lists them as next): assets both sides, why, odds effect, Accept/Counter/Decline via `ConfirmInPlace`. Verdict `VerdictCard` -> shared `VerdictCallout` | Real: "Analyze in Trade Analyzer", share. Sim: expires, AI personality reason, no share |
| M6 | **WaiverList** | `WaiversContent` (849) rows via `lib/waiverGroups.ts` | `SimPlayerBrowser` (Waivers toggle), `ClaimSheet`, `SimWaiverCard` | Row = M1 + ONE bid/claim number or "Claim" button; group header module: "3 adds . Top: Gibbs +$12 . $81 left" | Inline expand = waiver recommended-row expansion; Claim opens `ClaimSheet` -> shared `Sheet` with drop picker (shared "Drop candidate" note) | Real: FAAB bid, recs, Watchlist. Sim: claim order or FAAB per game settings, reserves |
| M7 | **StandingsTable / RankingBoard** | `LeagueRankingsContent#RankingRow` (CompactModule per board) | `SimStandingsList/Card` | "1. Team 1 . You #4 . 8 teams" ; action = "Open" | Inline: rows = crest/avatar, name, record, PF, trailing metric; tap -> team sheet (M13). Metric selector at top (one control row) | Real: Power/Franchise/Starter/Bench boards, playoff odds (Pro). Sim: standings, scores, playoff odds without gating |
| M8 | **MatchupCard** | `MatchupContent` `Hero` + modules | `SimMatchupCard`, `SimScoreCard`, `SimMatchupSheet` | `Hero`: win chance (else score, else projections), both teams in context line, "Open" | Page/columns on wide; sheet on phone for past games: comparison rows, position edges, moves | Real: win %, value tiles. Sim: result of simulated game, OVR gauges only |
| M9 | **ScheduleStrip** | `PlayerScheduleTab` (171), bye/opp in rows | bye card, `SimGamePreview`, week pills | "Wk 7 vs DAL . Bye Wk 9 . 3 of next 4 home" | Inline list of upcoming weeks with opp + projection band | Sim: `S3 2028`, no real schedule beyond sim fixtures |
| M10 | **HistoryTimeline** (transactions, trades, seasons) | `TradeHistoryContent`, `PlayerCareerTab`, `LeagueRecapsContent` history | `SimGameDynasty#YearRow`, `SimTeamHistory`, `SimPlayerHistory`, `SimRealHistory` | "6 seasons . 2 titles . Best 12-5 (S2 2027)" | Inline year rows; Sheet for a single season; tabs: Seasons / Trades / Picks | Season label via `simSeasonLabel`; Sim `SimRealHistory` is the real-data as-of cut |
| M11 | **DraftBoard** | `LiveDraftContent`, `DraftCenterContent` | `SimGameDraft`, `SimDraftBoard`, `SimDraftGrid`, `SimDraftHero` | On-the-clock `CompactModule`: "You pick 4.07 . 6 away . Best: Gibbs" ; action = "Draft Gibbs" (already shipped for Sim) | Inline body: progress, ETA, best-available strip, needs; tabs inside page: Players, Board (grid), Queue, Roster, Picks (one tab row) | Real: live draft sync, ADP, trade evaluator. Sim: auto-pick, queue, simulated picks |
| M12 | **NewsOrFeed** | `NewsContent`, `PlayerNewsTab`, `LiveFeedPanel` | Sim Feed tab, `SimLeagueMovesCard`, inbox | "3 new . Gibbs Q to P . 2h" | Inline list of event rows; filter pills (tab row); row opens PQV tab | Sim: **league events only** (trades, claims, injuries), never player news; the module takes `source: "events"` and renders no external link |
| M13 | **TeamSheet / ManagerProfile** | `ManagerProfileSheet` (tabs Overview/Tendencies/Trades) | `SimTeamSheet` (tabs inline) | Row: crest, name, record, one strength/need chip, "Scout" | Sheet 56-80%: Overview (record, strengths/needs, roster), Trades, History; Premium Tendencies only real | Real: tendencies (Premium), real trades. Sim: roster, needs, trade history, AI "personality" label |
| M14 | **Projection / OVR / Gauge** | `OvrGauge`, `ValueRing`, `ConfidenceMeter`, `LeanBarMeter`, `RangeCompare` | `OvrGauge` via `rating` stat, `SimProjection`, `RangeCompare` | One gauge only: OVR ring + PROJ pill ("10.8", band on tap) | Sheet/tap-for-why: floor/median/ceiling band, ROS, weekly points chart | Real: value tile and percentile. Sim: no value ever; Bye/Out replaces a number |
| M15 | **Notifications** | `AlertsDropdown`, `AlertsContent` | `SimNotificationBell` | Bell + count; row: icon, line, time | Dropdown on desktop, sheet on phone (shared `Sheet`); rows deep link via `InsightLink` | Real: push, watchlist. Sim: game inbox, tick-based times |
| M16 | **RecapCarousel** | `LeagueRecapsContent` (long page) | `SimRecapStory` on `StoryCarousel` | "Week 4 . Won 118-109 . +2 spots" with "Story" action | Full-screen `StoryCarousel` (max 3 items per page, pure `lib/*Story.ts`) + "Full details" page | Real: weekly league recap, share card. Sim: result, injuries, around the league, season complete |
| M17 | **Charts (TrendChart, bars, radar)** | `ui/TrendChart` + 5 hand-rolled | `WeeklyPointsChartLazy` | Sparkline 40 px + signed delta in a `Hero`/stat tile | Inline chart ~180 px with legend, axis, a11y table; tap point -> tooltip | Same component; sim feeds sim weeks (as-of) |
| M18 | **Form / Setup** | `*ImportForm`, `SignInForm` | `SimSetupParts` | Summary card: "10 teams . PPR . Normal . Seed hidden" ; action "Edit" | Sheet or page with `Field` / `ToggleRow` / `ChoiceGroup`; sticky primary | Sim hides seed by default; real has credentials fields |
| M19 | **Banner / Notice** | 9 shapes | `SimNotice`, `SimPreviewBanner` | one line + tone + optional action + dismiss | none (a banner never expands; it links) | Sim banners never mention Premium |
| M20 | **Header + tab strip** | `Header`, `PageTabBar` | `SimGameHeader`, `PillRow` tabs | n/a | One tab row per page rule; the strip is the only tab row | Sim keeps own orb nav; its tab labels follow `pageFamilies`-style naming (no new rows) |

### 2.2 Adapter layout (concrete)

```
shared component   web-next/src/components/ui/<Module>.tsx      twin mobile/src/components/<Module>.tsx
presentation model web-next/src/lib/<module>Model.ts            byte-identical twin (scripts/check_lib_twins.mjs)
real adapter       web-next/src/lib/<module>Real.ts  (or inline in the page lib: waiverGroups.ts, matchupModules.ts)
sim adapter        web-next/src/lib/sim<Module>.ts  (simPlayerSheet.ts is the pattern)
leak test          sim adapter test asserts none of {value, trade value, S\d+ missing} reaches the DOM; real adapter test asserts parts non-empty
```

Existing adapters you can copy: `lib/simPlayerSheet.ts`, `lib/simSummaries.ts` (sim parts for `CompactModule`), `lib/teamStatusModules.ts`, `lib/matchupModules.ts`, `lib/waiverGroups.ts`.

### 2.3 Uncertain / needs a product call

- U1. `lib/simGame.ts:111` says the internal rating is "NEVER shown", yet `SimGamePlayers.tsx:254` feeds `overall_rank`/`position_rank` from `value_rank`/`pos_value_rank` (ranks derived from that same internal value) into the PQV hero. Whether a rank derived from the hidden value is a leak is a product call. I did not find a UI that prints the value number itself; I did not test every surface (est. low risk).
- U2. The IA audit (1.4) recorded Sim draft sorting by "Trade value" and "Value 91" hints; on `9b42fc98` I find no `Trade value` string in `Sim*.tsx` and `simDraft.ts:187` says it is never shown, so this was fixed after the IA audit. Mobile not re-verified in the app UI (no device).
- U3. Web `SimNotice` as the error surface: I did not trace whether Sim errors satisfy `role="alert"` and a retry; verify in Phase 0.
- U4. The rows for "% of real pages with a collapsed summary" are measured on `CompactModule` imports only; pages that build their own collapsible (8 `<details>` files, `Collapsible`, `SimFold`) are counted as non-adopters.

---

## 3. Gaps ranked by user impact

Impact = how often a phone user (about 95% of users, per IA audit) sees it x how much it confuses or costs time. Size: S (<1 day, one PR), M (1-3 days), L (3+ days or multi-PR). Risk: product (visual/behavior change), tech (twin/test churn), data (leak or wrong number).

| Rank | Gap | Evidence | Impact | Size | Risk |
|---|---|---|---|---|---|
| 1 | **Real player rows are 7+ bespoke implementations; `PlayerListRow` is Sim-only.** Players, Waivers, My Team, News, Live Draft, GM Plan rows differ in chip order, right edge and name truncation (rollout "Remains": roster rows truncate on 390 px) | `PlayerListRow` importers: `SimDraftBoard`, `SimGameParts`, `TradePickerSheet` only; real rows listed in 1.2 | Highest: every page has rows | L (5+ pages, web+app) | tech: golden DOM tests; product: rows get taller/shorter; do waivers first (pattern exists) |
| 2 | **14 real pages with no `CompactModule`** (~8,200 lines): Recaps, Trade Analyzer/Finder/History, GM Plan, Live Draft, Draft Center, Portfolio, Alerts, News, Commissioner, Games, Compare, Multi-team trade | 1.2 row "Collapsible" | High: the stack-of-open-cards problem the owner named | L (one page per PR; Recaps/GM Plan/Trades are already in other agents' hands) | product: hides content behind a tap; mitigated by the `collapsedVerdict` rule |
| 3 | **Pop-up shells: 6 hand-rolled** (`PopupShell`, `SimSheet`, `PlayerQuickView`, `TradePickerSheet`, `AlertsDropdown`, `GmOrb` + others) vs `ui/Sheet`; app has `Sheet` 128 + `SwipeDismissSheet` 284 and 33 `SheetModal` users | `useSheetDragDismiss` in 10 web files; ui-patterns "Not migrated yet" list of 8 | High (drag/dismiss/scroll-lock bugs recur, e.g. sheet over keyboard `495940b6`) | M (`SimSheet` -> `Sheet` first: 6 files; then `PopupShell`) | tech: focus trap + `overlayStack`; low product risk |
| 4 | **Stat tile: 4 local `Fact` + `SimStat` + `Tile` + `StatTile` + `Stat`** (web and app) | 1.2 | Medium-high (every hero/summary) | S (one `StatTile` in `ui/` with `tone`, `label`, `value`, `why?`; replace in 8 files per platform) | tech only |
| 5 | **Team sheet vs manager profile** (`SimGameTeamSheet` 276 vs `ManagerProfileSheet` 265) | 1.2 | Medium (League tab; opened from standings and trades) | M | product: tab plan differs (`sheetTabs.ts` says Sim keeps own plans); decide one plan |
| 6 | **Draft room twice** (Sim 1,046 lines vs `LiveDraftContent` + `DraftCenterContent` 989) | 1.2 | Medium (seasonal; high during draft season) | L | product: live draft sync is real-only; share only the on-the-clock module, best-available strip, board grid |
| 7 | **Trade: inbox/offer/verdict/builder Sim-only; idea cards bespoke** (`TradeIdeaCard` 705 app lines) | 1.2 | High on Trades (page is 2,046 px tall at 390 per rollout scan) | M-L | data: Sim must never show trade value numbers; verdict words only |
| 8 | **Feedback states: web Sim uses `SimNotice` instead of `ErrorState` (1/39); `Loading...` text in 11 web real files; `ActivityIndicator` in 14 app files; bespoke "No ... yet" lists in 12 web + 14 app files** | `2026-11-universal-modules-audit.md` P1 | Medium (seen on every cold load and error) | S-M (one PR per state, mechanical) | low |
| 9 | **Notifications: bell + list twice**; no shared row; Sim bell is 161/166 lines | 1.2 | Medium | S-M | low |
| 10 | **Recap**: only Sim uses `StoryCarousel`; real `LeagueRecapsContent` 1,116 lines, 4 control rows (worst case, IA 1.2) | 1.2 | Medium-high on League tab | L (needs a real `lib/leagueRecapStory.ts`, like `simRecapStory.ts`) | product: new story form; keep old page behind "Full details" |
| 11 | **Banners/notices: 9 real + 4 sim shapes** | 1.2 | Low-medium | S (one `Banner` + migrate) | low |
| 12 | **Gauges/meters: 5 components; charts: `TrendChart` shared but 5 hand-rolled bars/radars** | 1.2; universal audit P3 | Low-medium | M (`ChartFrame`, then migrate) | tech |
| 13 | **Forms: `SimSetupParts` vs `Input`/`Toggle`/`OptionRadioGroup`** | 1.2 | Low (setup is seen once per game) | S-M | low |
| 14 | **Sim has no page family strip / real has no Sim-style single action bar**; control-row stacking: Sim Players 3 rows, Recaps 4, Waivers 4, Players 4 | IA 1.2/1.4; rollout "Still open" | Medium-high | M (blocked on the shared tab strip owned by another agent: `PillRow`/`PageTabBar`) | product |
| 15 | **Glyph sets (10 per platform), glass hand-roll (app 51 real files, web 4 sim)** | universal audit P3, P2 | Low (consistency) | M | low |
| 16 | **Naming: shared modules import sim-named helpers (`simOpenKey`, `simLayout`)** | `ui/CompactModule.tsx:9` | Dev velocity only | S | tech (twin rename) |
| 17 | **Taps: tappable `div`/`li` with no role** (SimGameHome, TradeFinder, LeagueRecaps) | universal audit "Still not routed" 1 | a11y + press feedback | S-M | low |

---

## 4. Module spec sheets

One sheet per shared module (the ones with a build action in section 5). Each uses the same fields. Names follow existing files; "new" means the file does not exist yet.

Common to all (do not repeat per module):
- Web file under `web-next/src/components/ui/`, app twin `mobile/src/components/`, pure logic in a byte-identical lib twin (`scripts/check_lib_twins.mjs`).
- Tokens only: `--color-*`, `--radius-*`, `--space-*`; glass look; fixed semantic tone colors (`success/danger/warning/muted/accent/action`).
- 44 px minimum tap target. Reduced motion: no scale, no slide; fades only (`lib/motion.ts` `PRESS`, `TRANSITION_MS`: sheet 300, tab 180, list 180, toast 240, press 120).
- Press feedback comes from the global `[role=button]/button/a/[data-press]` rule (web) or `PressableScale` (app); never hand-roll `activeOpacity`.
- Tests: a component test for collapsed + expanded + loading/error/empty; an adapter test per product; the source scan in `ui/ModuleTemplates.test.tsx` extended with the new file.

### S1. CompactModule (exists; spec of record)
- **Props**: `id`, `title`, `label?`, `parts[]` (max 6, empties dropped), `tone`, `action?` (ONE), `expandIn: "inline"|"sheet"`, `defaultOpen`, `persist`, `testId`, `glow`, `children`.
- **States**: collapsed (summary >= `MIN_COLLAPSED_CHARS`), expanded inline, expanded in `Sheet`, loading (a real sentence, not a spinner only), error (`ErrorState` inside), empty (summary says "None", body `EmptyState`).
- **A11y**: header is a `button` with `aria-expanded`, `aria-controls`, label from `compactAriaLabel`; the action sits outside the header button (no nested interactive).
- **Motion**: body height 180 ms; chevron rotate; open state persisted per `id` in `localStorage` (try/catch).
- **Tap**: header toggles; trailing action does its own thing without expanding; deep link hash opens the module.
- **Test**: `CompactModule.test.tsx`, `assertCompactInformative`, `module_scan.mjs` at 360/390/1440.

### S2. Sheet (exists; absorbs `SimSheet`, `PopupShell`)
- **Props**: `open`, `onClose`, `title`, `description?`, `footer?`, `size: sm|md|lg`, plus new `tabs?: SheetTabPlan[]` (reuses `lib/sheetTabs.ts` plan type) and `bare?` (PQV chrome).
- **States**: open, closing, loading body (skeleton keeps min height via `nextPanelMinHeight`).
- **A11y**: `role="dialog" aria-modal aria-labelledby`, focus in/out, tab trap, Esc/back, scroll lock.
- **Motion**: rise 300 ms, swipe dismiss (`useSheetDragDismiss`), off under reduced motion.
- **Tap**: backdrop closes; sheets never stack (`overlayStack`).
- **Test**: `Sheet.test.tsx`, `sheet_drag.mjs`.

### S3. StatTile (new; replaces 4 `Fact`, `SimStat`, `Tile`, `StatTile`, `Stat`)
- **Props**: `label`, `value`, `tone?`, `delta?`, `why?` (TapForWhy key), `align?: "start"|"end"`, `size: "sm"|"md"`.
- **States**: value present, value missing ("—" plus `note`), loading (skeleton same size).
- **A11y**: one `dl`-style label/value pair; tone is never the only signal (delta sign or text).
- **Motion**: `CountUp` on first mount only (450 ms), `PulseOnIncrease` optional.
- **Tap**: `why` opens `TapForWhy`; `insight` makes it an `InsightLink`; else inert.
- **Test**: renders `—` for null; Sim adapter never receives `value`.

### S4. PlayerRow (exists as `PlayerListRow`; promote to the one real+sim row)
- **Props**: `name`, `position`, `headshotId`, `meta[]`, `chip?`, `tags[]`, `stats[]` (PROJ, OVR gauge, ADP, EDGE), `badges`, `suppressBadges`, `alignColumns`, `actions` (ONE control), `selected`, `onOpen`, `density`.
- **States**: default, selected, hurt/out, loading skeleton row, "no data" meta.
- **A11y**: whole row one `button` (or `link`), `openLabel`, actions outside it; row name never ellipsised (name-fit ladder, `47192508`).
- **Motion**: press only.
- **Tap**: row opens PQV (real) or the game's player sheet (sim); action tap does not open.
- **Test**: `rowRightEdgeProblems`; existing `PlayerListRow` tests; per-page adapter test; scan that no `PlayerListRow actions={<>...</>}`.

### S5. TradeCard (new: wraps idea card, inbox offer, verdict; `TradeIdeaCard` + `SimGameTrades#OfferCard`)
- **Props**: `give[]`, `get[]` (row models), `partner`, `verdict {word, tone}`, `reason`, `actions[]` (max 2: primary + overflow), `expandIn` default inline.
- **States**: pending, accepted/declined (undo toast), expired, loading, error.
- **A11y**: summary text reads "You send X, you get Y, verdict"; actions via `ConfirmInPlace`.
- **Motion**: inline expand 180 ms; success pulse on accept.
- **Tap**: header expands; Accept/Decline need `ConfirmInPlace`.
- **Test**: Sim adapter: verdict is a word, no number; real adapter: shows value delta.

### S6. TeamSheet (new: `ManagerProfileSheet` + `SimTeamSheet`)
- **Props**: `team {name, crest, record}`, `tabs[]` (Overview, Trades, History, optional Tendencies), `rows`, `actions`.
- **States**: loading, empty roster, Premium-locked tab (real only).
- **A11y**: tablist inside dialog, roving tabindex.
- **Motion**: tab 180 ms; keeps tallest panel height.
- **Tap**: opened from standings rows and trade partner names (`SimTeamLink`, `PlayerIdentityTrigger`).
- **Test**: adapter tests; Sim never lists Tendencies.

### S7. DraftClock + BoardGrid (new shared pieces; draft room)
- **Props**: `pick`, `picksAway`, `etaMs`, `bestAvailable[]`, `needs[]`, `action`.
- **States**: on the clock, waiting, complete (recap), paused.
- **A11y**: `role="progressbar"` with text value, live region for pick changes (`aria-live=polite`).
- **Motion**: progress bar linear; one-shot glow when on the clock.
- **Tap**: header expands; action drafts with `ConfirmInPlace`.
- **Test**: `SimDraftHero` existing tests moved to the shared one; real live-draft fixture.

### S8. NotificationBell + NotificationRow (new)
- **Props**: `items[]`, `unread`, `onOpen`, `onMarkRead`, `rowRenderer`.
- **States**: none, unread, loading, error.
- **A11y**: button `aria-label="Notifications, 3 unread"`, list `role=list`.
- **Motion**: dot pulse once on new item; dropdown (desktop) / `Sheet` (phone).
- **Tap**: row deep links (`InsightLink`).
- **Test**: unify `SimNotificationBell.test.tsx` and Header tests.

### S9. Banner (new)
- **Props**: `tone`, `icon?`, `text`, `action?` (ONE), `onDismiss?`, `id` (remember dismissal).
- **States**: visible, dismissed (persisted), action pending.
- **A11y**: `role="status"` (info) or `role="alert"` (danger).
- **Motion**: slide 240 ms; none under reduced motion.
- **Tap**: action only; the banner never expands.
- **Test**: tone x dismiss; source scan bans new `SimNotice`-style local banners.

### S10. StoryCarousel (exists) + RecapModel
- Spec as in `docs/ui-patterns.md` "StoryCarousel" (page = hero + at most 3 items, no scroll, tap zones, overlay stack). New requirement: any recap/summary a user is told about ("Week 4 recap ready") must be a story with a "Full details" page, built from a pure `lib/*Story.ts` with tests.

### S11. Charts: TrendChart (exists) + `ChartFrame` (new)
- **Props**: `points`, `name`, `variant: compact|full`, `height`, `legend?`, `emptyText`, `data table` for a11y.
- **States**: loading skeleton, empty with sentence, flat series (`isFlatProjection`).
- **A11y**: `role="img"` + `aria-label` summary + hidden table.
- **Motion**: draw-in once, off under reduced motion.
- **Tap**: point -> tooltip; no navigation.
- **Test**: `TrendChart.test.tsx`.

### S12. Form kit: `Field`, `ToggleRow`, `ChoiceGroup`, `StickyActionBar` (new; from `SimSetupParts`)
- **Props**: standard; `ChoiceGroup` options with `description`.
- **States**: default, invalid (inline text + `aria-describedby`), disabled, submitting.
- **A11y**: label association, error text linked, 44 px targets.
- **Motion**: none beyond press.
- **Tap**: sticky bar holds the one primary.
- **Test**: keyboard nav; invalid state.

### 4.13 One-page checklist: a new module must pass

1. **Compact form is informative**: title + >= `MIN_COLLAPSED_CHARS` of real data (`collapsedVerdict`), at most 2 lines, at most ONE trailing action, 56-96 px.
2. **Expanded form chosen by size**: inline (<= ~1.5 screens), `Sheet` (long/tabbed/independent), page (own URL). Never two expansions for one module.
3. **One implementation**: no local copy of a row, tile, banner, sheet, toast or bell exists in `Sim*` or a page file; the module lives in `ui/` with an app twin and a lib twin that passes `check_lib_twins.mjs`.
4. **Adapter, not branch**: product differences live in `lib/<x>Real.ts` / `lib/sim<X>.ts`; the component has no `isSim` / `source ===` conditional.
5. **Sim leak guard**: Sim adapter test proves no internal rating/`value`/trade-value number and no real news reaches the DOM; season is `S# YYYY` via `simSeasonLabel`; no Premium copy.
6. **All four states** use the shared primitives (`Skeleton`/`LoadingScreen`, `ErrorState` with retry, `EmptyState` with a next step); no "Loading..." text.
7. **One tab row** per page; filters in `FilterSheet`; no new pill row.
8. **Row right edge** holds one control or one number (`rowRightEdgeProblems`); no `actions={<>...</>}`.
9. **Tap**: whole header/row is one 44 px target, trailing action outside it; no `div onClick` without `role` and key handling; press feedback is the global rule or `PressableScale`.
10. **A11y**: `aria-expanded/controls`, dialog roles, focus return, `role=alert` only for real errors, color never the only signal.
11. **Motion**: only `lib/motion.ts` tokens; reduced motion respected; no looping animation.
12. **Overlay rule**: sheets/stories register with `overlayStack`; never stack two.
13. **Responsive**: no horizontal overflow at 360 / 390 / 1440 (`module_scan.mjs` fixture added); names never ellipsised (name-fit ladder).
14. **Web + app together**: both ship in one PR or the exception is written down.
15. **Tests**: component, adapter x2, source-scan entry, and a `module_scan` fixture; pre-existing golden failures on `test` are verified on a clean clone before blaming the PR.

---

## 5. Recommended rollout (dedupes what is already merged)

Already merged (do NOT redo): `CompactModule`, `Hero`/`StatStripModule`/`LinkModule`, Today, Team, Trades hub (hero + 3-team + signals), League Rankings boards, Matchup, Waivers recommended rows, Players picks (`2026-11-module-templates-rollout.md`); universal press feedback and `TrendChart`; Sim recap story, `PlayerBadge` (#1880), name-fit ladder, season label `S3 2028`, Sim draft room on `CompactModule`, Sim player sheet adapter. In flight elsewhere (do not touch until they land): Waivers/Trades/GM Plan/League page migrations and Sim screens.

Phase 0 (S, 1 day, no visual change)
- Re-run the 1.1 counts on the then-current `main`; add the `isSim` / local-copy source scans to `ModuleTemplates.test.tsx` (checklist items 3 and 4) so new duplicates fail CI.
- Rename `simOpenKey`/`simLayout` usage out of `ui/CompactModule.tsx` (gap 16).

Phase 1 (S-M, mechanical, each its own PR, web+app)
1. `StatTile` replaces the 4 `Fact` + `SimStat`/`Tile`/`StatTile`/`Stat` (gap 4).
2. `SimSheet` -> `ui/Sheet` (6 call sites), then `PopupShell`; document `tabs` and `bare` props (gap 3).
3. Feedback states: web Sim `SimNotice` page-level errors -> `ErrorState`; `Loading...` -> `LoadingScreen`/`Skeleton`; app `ActivityIndicator` -> `BrandedSpinner`/`SkeletonBlock`; bespoke empties (gap 8).
4. `Banner` + migrate `SimNotice`, `SimPreviewBanner`, `SampleLeagueBanner`, limit notes (gap 11).

Phase 2 (M, pairs of real+sim in the SAME PR so they cannot diverge)
5. Player rows: finish Waivers (pattern exists), then Players, My Team, News, Live Draft all onto `PlayerListRow` via adapters; delete the local rows (gap 1).
6. `TeamSheet` (manager profile + sim team sheet) with one tab plan (gap 5).
7. `NotificationBell`/`NotificationRow` (gap 9).
8. Standings: `RankingRow` with Sim adapter (M7).

Phase 3 (L, one page per PR; coordinate with owners of the in-flight work)
9. Trade idea cards + Sim inbox/offer as `TradeCard`; Analyzer, Finder, History headers (gaps 2, 7).
10. Recaps: `lib/leagueRecapStory.ts` + `StoryCarousel` for the real weekly recap; `LeagueRecapsContent` shrinks behind "Full details" (gap 10).
11. GM Plan, Draft Center, Live Draft: `CompactModule` per section; share `DraftClock` with Sim (gap 6).
12. One tab row on Waivers/Recaps/Players/Sim Players once `PillRow`/`PageTabBar` work lands (gap 14).

Phase 4 (M, opportunistic)
13. `ChartFrame` + gauge consolidation; glyph registry; setup form kit; glass hand-roll cleanup (gaps 12, 13, 15).

Risks to watch: golden test drift on the `test` job; app has no on-device verification (static tsc/node tests only, per memory); every sheet/row change must keep `overlayStack` and `sheet_drag.mjs` green; Sim PRs must not alter model output (all of the above is presentation only).

---

## 6. Top 10 consolidation opportunities (by impact / effort)

1. **One player row** (`PlayerListRow`) for every real list; today only Sim and the trade picker use it. L, highest impact.
2. **One `Sheet` shell**: fold `SimSheet`, `PopupShell`, bespoke PQV/picker chrome into `ui/Sheet` (+ `tabs`). M.
3. **One `StatTile`**: delete 4 local `Fact` + 4 lookalikes on both platforms. S.
4. **CompactModule on the 14 real pages that have none** (Recaps, Trade Analyzer/Finder/History, GM Plan, Draft, Portfolio, Alerts, News, Commissioner, Games, Compare, Multi-team). L, page by page.
5. **Shared `TradeCard` / inbox / verdict** across Trade Hub idea cards and the Sim trade inbox. M-L.
6. **One `TeamSheet`** for manager profile and sim team scouting. M.
7. **Shared feedback states**: `ErrorState` in Sim, `LoadingScreen`/`Skeleton` over "Loading..." text and raw spinners, bespoke empties. S-M.
8. **Real recap as a `StoryCarousel`** (only Sim uses it today). L.
9. **`Banner` + `NotificationBell`/`NotificationRow`**: 13 banner shapes and two bells collapse to two components. S-M.
10. **Draft room module set** (`DraftClock`, best-available, board grid) shared between Sim draft and Live Draft/Draft Center. L.

(Also queued: `ChartFrame` + one gauge, one form kit, glyph registry, and renaming sim-named helpers out of shared modules.)
