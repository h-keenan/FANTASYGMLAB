# Universal modules and motion audit (2026-11-14)

Trigger: coridian_ (phone) asked for an end-to-end audit so modules and tap animations are universal. Method: static survey
of `web-next/src` (341 components) and `mobile/src` (289 components) with grep counts, plus a read of the shared components
named in `docs/ui-patterns.md`. Counts are files, not call sites. Nothing here changes real valuation or sim logic.

## 1. Tap and motion feedback

**Before.** Web had no shared press feedback: `.bottom-tab`, `.ui-insight`, `.ui-srow-tap`, `.ui-why` each invented their own
(`scale(.96)`, `opacity .8`, `scale(.98)+.7`) and `SimGameParts` used Tailwind `active:scale-95`; every other button/card/row/pill/tab
had none. The app had 93 files on `TouchableOpacity` with five different `activeOpacity` values (0.7, 0.75, 0.8, 0.85, 1) and six
files with hand-rolled `Pressable` pressed styles (opacity .7/.8, scale .95/.98).

**Now: the ONE press** (`lib/motion.ts` `PRESS`, `pressFeedback`, byte-identical twins): 3% shrink + slight fade, 120ms, released on lift;
reduced motion keeps the fade, drops the shrink.

| Surface | How it is routed |
| --- | --- |
| Web: every `button`, `[role=button]`, `[role=tab]`, `[role=menuitem]`, `summary`, `a[href]`, `label[for]`, `[data-press]` | one zero-specificity rule in `globals.css` ("Press feedback") using `scale` + `opacity` (its own property, so it never fights a component's `transform`). Opt out with `data-no-press`. Disabled controls are excluded. |
| Web components that had their own | `.bottom-tab`, `.ui-insight`, `.ui-srow-tap`, `.ui-why` now use `--press-scale` / `--press-opacity`; `active:scale-95` removed from `SimGameParts`. |
| App: all 93 `TouchableOpacity` files | replaced by `components/PressableScale` (drop-in; ignores `activeOpacity`; `pressFeedback={false}` to opt out). 27+ ad hoc `activeOpacity` values are gone. |
| App: hand-rolled `Pressable` pressed styles | `SimDraftBoard` icon button, `StructuredRow`, `FilterSheet` trigger, `ConfirmInPlace` (3), `TapForWhy`, StoryCarousel segments and close, all moved to `PressableScale`. |
| App: `AnimatedCard` | already scale .97 spring (same number as `PRESS.scale`); left as is. |

Other transitions, now named once in `lib/motion.ts` (`TRANSITION_MS`): page 240, sheet 300, tab 180, toast 240, list 180, press 120.
Number count-up: `CountUp` (450ms, `COUNT_MS`). Success pulse: `SUCCESS_PULSE` / `.motion-success` (web), `PulseOnIncrease` (counts). One-shot
hero glow: `HERO_GLOW`. All honour reduced motion.

**Still not routed (prioritized)**
1. Web: tappable `div`/`li` with `onClick` and no role. They do not press. Fix by giving them `role="button"` + keyboard handling or `data-press` (needs a per-component look, not a blanket change). Highest-volume offenders: clickable cards in `SimGameHome`, `TradeFinderContent`, `LeagueRecapsContent`.
2. Web: components whose Tailwind `transition-*` class overrides the press transition (press still applies, but snaps instead of easing). Cosmetic only.
3. App: ~62 remaining `Pressable` files with no pressed style at all (tap zones such as StoryCarousel's page tap target must stay without scale). Convert the visible controls, keep overlays/tap zones on `Pressable`.
4. App: `GmOrb` (never redesigned per screen, press is its own animation) and `PremiumGlow` buttons (glow already animates).
5. List/sheet/tab/toast enter and exit curves exist as tokens, but several web components still hard-code `150ms`/`200ms`/`ease` in `globals.css` and `ui.css`; migrate one family per PR.

## 2. Universal modules

Shared building blocks and how widely they are used (files, web / app):
`EmptyState` 49 / 43, `ErrorState` 38 / 52, `ToneBadge` 67 / 71, `SectionHeading` 39 / 46, `CompactModule` 5 / 5,
`PlayerListRow` 2 / 2 (reached mostly through `SimPlayerLine`), `StructuredRow` 1 / 1, `LoadingScreen` 37 / 1,
`SkeletonBlock` (app) on 17 files, web `Skeleton` on the main pages, `GlassCard` (app) on 13.

### Fixed in this PR
- Weekly recap story (web + app): the page chrome is now the shared set (`MotionIn`, `CountUp`, `Confetti`, `TeamAvatar`, `PlayerAvatar` via
  `SimPlayerLine`, `OvrGauge` via the `rating` stat, position colours from `positionColorVar` / `positionColor`) instead of its own
  `Hero`/`Fact` text-only rows.
- Recap injuries: one marker per player (the `OUT` chip from `SimPlayerChip`), the trailing text is only the duration.
- Recap matchup rows now carry the OVR gauge like every other player row.

### Remaining, prioritized
**P1 (visible, repeated, cheap per file)**
1. Bespoke "No ... yet" empty copy instead of `EmptyState`. Web: `SimPlayerHistory`, `SimTeamHistory`, `SimGameDynasty`, `SimDraftOverview`, `PlayerCareerTab`, `PlayerScheduleTab`, `PlayerCardKit`, `PlayerProfileContent`, `PlayerHeroHeader`, `TradeAnalyzerContent`, `LiveDraftTradeEvaluator`, `seo/PublicTradeAnalyzer`. App: `SimPlayerHistory`, `SimTeamHistory`, `SimGameDynasty`, `SimDraftOverview`, `PlayerCardKit`, `PlayerTrendsPanel`, `PlayerHero`, `PlayerCard`, `WeeklyPointsChart`, `LiveDraftTradeEvaluator`, `MoreScreen`, `PlayerDetailScreen`, `PaywallScreen`, `ProspectScoutingDetailScreen`.
2. Inline error text (`color: var(--color-danger)` / `role="alert"`) instead of `ErrorState`. Web: `SimGameHomeCards`, `SimGameRecap`, `SignInForm`, `AccountContent`, `SavedLeaguesSection`, `MatchupPlanner`, `PremiumContent`, `TradeAnalyzerContent`, `SeasonReviewSections`, `FounderAnalyticsContent` (several of these are field-level validation, which is correct inline; the page-level failures are the ones to move).
3. Loading: web screens still print "Loading..." text (19 files, e.g. `WaiversContent`, `PortfolioContent`, `PlayerNewsTab`, `SimGameHome`, `SimGameOffseason`) rather than `LoadingScreen` or a skeleton; the app uses `ActivityIndicator` directly in 13 files (`GmGameScreen`, `GmPlanScreen`, `MoreScreen`, `PaywallScreen`, `EspnLeagueImport`, `TradeOutcomePrompt`, `GuessThePlayer*`) instead of `SkeletonBlock` / `BrandedSpinner`. Button spinners are fine.
**P2 (surface and card duplication)**
4. App: 57 files hand-roll `backgroundColor: colors.glass` + `glassBorder` instead of `GlassCard` / `AnimatedCard` / `AccentCard`. Worst: `TradeFinderScreen` (4), `PlayerCompareScreen` (4), `TradeAnalyzerScreen` (3), `VetoCalculator`, `MultiTeamTradePanel`, `HomeScreen`, `GmPlanScreen`, `DraftCenterScreen`, `TradePickerSheet`, `TradeIdeaCard`.
5. Web: 38 files set `background: var(--glass...)` / `var(--color-surface...)` inline instead of the shared card classes: `SuggestedDrop`, `SimDraftGrid`, `LeagueRecapsContent` (3 each), `TradeIdeaCard`, `TradeAnalyzerContent`, `SimGameHome`, `SimDraftHero`, `PortfolioContent`, `LiveDraftContent`, `CommissionerContent`, `PublicTradeAnalyzer`.
6. Section headers: pages not using `SectionHeading` / `CompactModule` (web 39, app 46 adopters out of 341 / 289 components). `CompactModule` is on 5 pages each side; migrate one page per PR (the IA audit's plan).
**P3 (charts and glyphs)**
7. Charts are all hand-rolled SVG: web `WeeklyPointsChart`, `ManagerTendenciesCard`, `MatchupLineup`, `PlayerCompareContent`; app `WeeklyPointsChart`, `RatingHistoryChart`, `ModelRadarChart`, `CircularProgressRing`. There is no shared axis/tooltip/empty-state wrapper; each draws its own. Extract a `ChartFrame` (title, empty/loading, legend, reduced-motion draw-in) before adding any more charts.
8. Glyph sets: `SimGlyph`, `SimReviewGlyph`, `SimDraftGlyphs`, `TabGlyph`, `NavDestinationGlyph`, `SnapshotTileGlyph`, `EventTypeGlyph`, `PremiumGlyph`, `TradeCategoryGlyph`, and the new `TrophyIcon`. Nine parallel icon files; consolidate behind one `Glyph` registry (also the natural home for the PlayerBadge system when #1880 lands).

### Dependencies and coordination
- PR #1880 (universal PlayerBadge) is open and not on `main`. The recap uses the existing shared chips and `SimPlayerChip`, so it stays compatible: when #1880 lands, swap `SimPlayerChip`'s status chip, nothing in the recap page code changes.
