# UI module inventory (web-next first, mobile notes)

Audit date: 2026-10-21. Scope: `web-next/src/components` plus components
defined inline in `web-next/src/app/**/page.tsx` and inside the big
`*Content.tsx` page bodies. Mobile (`mobile/src`) gets a lighter pass at the
end. Standing rules this audit enforces: reuse shared components and design
tokens (`web-next/src/app/globals.css`), never duplicate a module per page,
semantic colors are fixed, and the GM orb is never redesigned per screen.

"Where used" lists routes (via any import chain). `/layout` means the root
layout, so every page. Page-body components (`XContent.tsx`) are listed once
under **Page bodies** and are not modules in their own right.

## 1. Canonical modules (use these, don't re-create them)

### Cards / panels
| Module | Where used | Props / variants |
|---|---|---|
| `.glass-surface` (CSS class in globals.css) | 59 call sites, every data page | The one card surface. Radius `--radius-panel`, glass fill. Every card below sits on it |
| `GamePlanCard` | /dashboard | Top-priority briefing card (one item, full CTA) |
| `WatchListCard` | /dashboard | Remaining briefing items grouped in one card, hairline-separated |
| `LeaguePulseCard` | /dashboard | League highlights (fetches its own team-rankings) |
| `TradeIdeaCardView` (+ `ReasoningTags`, `ShareTradeButton`) | /trade-hub, /trade-finder | One trade idea: rings, lean bar, exchange sides, share PNG |
| `PremiumUpsellCard` | /portfolio, /gm-plan, /trade-finder, /live-draft | `kicker`, `upsell`, `fallbackTitle/Body`, `bare` (no `<main>` wrapper) |
| `ReferralCard` | /account | Single-use, justified |
| `GuessThePlayerCard`, `GuessThePlayerNameMatchCard` | /dashboard | Mini-game cards, justified one-offs |

### Stat tiles / meters / gauges
| Module | Where used | Props / variants |
|---|---|---|
| `SnapshotTile` (+ `SnapshotTileGlyph`, `formatRank`) | /dashboard, /my-team, /waivers, /draft-center, /portfolio, /founder-analytics | `label`, `value`, `tone` neutral/risk/positive/premium, `note`, `glyph`, `wrapNote` |
| `OvrGauge` | 15 routes | The only OVR rendering. `rating` (null keeps width), `size` sm/md/lg |
| `ValueRing` | /my-team, /trade-hub, /trade-finder, /trade-analyzer | `percent`, `tone` low/mid/high, `display`, `size` sm/md |
| `ConfidenceMeter` (+ `confidenceLevelFor`) | /waivers, /college-scouting | 3-step bar meter |
| `LeanBarMeter` | /trade-hub, /trade-finder, /trade-analyzer | `sendScore`, `receiveScore` |

### Headers / section titles
| Module | Where used | Props / variants |
|---|---|---|
| `Header` (+ `EvaluationLensButton`) | /layout | App header, league switcher, page title |
| `DesktopSidebar` | /layout | Desktop nav (uses `NavDestinationGlyph`) |
| `GmOrb` | /layout | The GM orb + nav sheet. Never re-skinned per page |
| `SectionHeading` (new) | /my-team, /waivers, /matchup, /league-rankings, /player-compare | Uppercase `--type-section-title`. Optional `kicker`, `note`, `id`, wrapper `className` |
| `BeginnerHelp` | 6 routes | Beginner-only helper line (`term` or `text`) |

### Lists / rows
| Module | Where used | Props / variants |
|---|---|---|
| `TradeAssetRow` / `ExchangeSide` (TradeAssetExchange.tsx) | 9 routes | Player or pick asset row; `disableQuickView`. `ExchangeSide` = labelled tinted column |
| `PickRow` | /draft-center, /players | Draft pick row with tier/range/owner + confidence |
| `BriefingItemPlayers` | /dashboard, /portfolio | Player chips for a briefing item |
| `PlayerIdentityTrigger` | 17 routes | Wraps any player identity so a tap opens Player Quick View |
| `HighlightTarget` (new) | /my-team, /waivers | Scroll-to + outline for the `?playerId=` deep-linked row |

### Avatars / badges / pills / chips
| Module | Where used | Props / variants |
|---|---|---|
| `PlayerAvatar` | 17 routes | `playerId`, `tier` ring, `size` |
| `TeamAvatar` | 7 routes | `size` |
| `PositionBadge` | 19 routes | Square colored position badge |
| `PlayerInjuryBadge` | 9 routes (via TradeAssetRow, BriefingItemPlayers) | `status`; renders nothing when healthy |
| `TradeCategoryGlyph`, `NavDestinationGlyph`, `SnapshotTileGlyph`, `PremiumGlyph` | as named | Icon sets, one per domain |

### Empty / loading / error states
| Module | Where used | Props / variants |
|---|---|---|
| `LoadingScreen` | 29 routes | Branded splash, `status` text |
| `ErrorState` | /dashboard, /portfolio, /account, /founder-analytics | `message`, `onRetry` (Try again button) |
| `PqvBodySkeleton` (PlayerQuickView.tsx), `PortfolioLeagueSkeleton` | Quick View, /portfolio | Skeletons, justified per-layout |

### Modals / sheets
| Module | Where used | Props / variants |
|---|---|---|
| `PlayerQuickView` (+ exported `StatGroup`, `SubRatingRow`, `AwardsStrip`, `BioGrid`) | every route via `PlayerQuickViewProvider`, and /players/[id] | The one player modal/sheet |
| `EmbeddedCheckoutModal` | /, /premium | Stripe embedded checkout |
| `AgeGate` | / (via SignInForm) | Justified one-off |

### Charts
| Module | Where used | Notes |
|---|---|---|
| `WeeklyPointsChart` / `WeeklyPointsPanel` | /players/[id], /player-compare, Quick View | recharts. Justified |
| `ModelRadarChart` | Quick View / /players/[id] | Justified |
| `PlayerTrendsPanel` | Quick View / /players/[id] | Justified |

### CTAs / buttons
No shared button component exists. See band-aid B10.

### Tabs / toggles
| Module | Where used | Props / variants |
|---|---|---|
| `PillRow` | 8 routes | Segmented pill toggle: `options`, `active`, `onSelect` |
| `TradesTabBar` | /trade-hub, /trade-finder, /trade-analyzer | Link-based tabs with the same look as `PillRow` |

### Page bodies and shells (one per route, not reusable modules)
`AccountContent`, `AlertsContent`, `CollegeScoutingContent`,
`CommunityTradesContent`, `DashboardContent`, `DraftCenterContent`,
`FounderAnalyticsContent`, `GmPlanContent`,
`GuessThePlayerLeaderboardContent`, `LeagueRankingsContent`,
`LeagueRecapsContent`, `LiveDraftContent` (+ `LiveDraftTradeEvaluator`),
`MatchupContent`, `MyTeamContent`, `NewsContent`, `PlayerCompareContent`,
`PlayerProfileContent` (+ `PlayerCareerTab`, `PlayerScheduleTab`),
`PlayersContent`, `PortfolioContent`, `PremiumContent` (+ `PlanCard`),
`TradeAnalyzerContent`, `TradeFinderContent`, `TradeHistoryContent`,
`TradeHubContent`, `WaiversContent`. Landing/auth: `LandingAuthIsland`,
`SignInForm`, `SleeperImportForm`, `OnboardingCarousel`,
`OnboardingPaywall`, `AppStoreModules`. Plumbing: `AppContentShell`,
`RouteAnalytics`, `InlineScript`.

## 2. Band-aid list

Status: **Consolidated (PR #n)**, **Needs decision** (both variants
described), or **Justified one-off**.

### Headers / section titles
- **B1. Five local `SectionHeading` copies.** MyTeam, Waivers, Matchup and
  LeagueRankings each defined the same uppercase `--type-section-title` h2.
  LeagueRankings added a kicker and note, and PlayerCompare had the same
  thing as `SectionHeader`. **Consolidated (PR #1325)** into
  `components/SectionHeading.tsx`. Rendered markup is byte-identical.
- **B2. Sentence-case vs uppercase section titles.** Dashboard, Draft
  Center, Live Draft, GM Plan, Premium and Onboarding use a plain
  sentence-case `<h2 style={{font: var(--type-section-title)}}>`. The five
  pages in B1 use UPPERCASE with 0.02em tracking. **Needs decision:** pick
  one casing, then fold the inline h2s into `SectionHeading`.
- **B3. AccountContent's local `SectionHeading`** is a caption-sized muted
  label (xs/bold/uppercase), not a section title. It is a kicker-style
  label, used only on /account. **Justified one-off** for now (same role as
  the `SectionHeading` kicker; could merge if B2 settles).

### Lists / rows
- **B4. `HighlightTarget` duplicated** byte-for-byte in MyTeam and Waivers.
  **Consolidated (PR #1325)** into `components/HighlightTarget.tsx`.
- **B5. About ten local player rows re-implement the left half of
  `TradeAssetRow`.** The pattern is PositionBadge + 40px PlayerAvatar +
  bold name + injury label + muted team line + OvrGauge + value. Copies:
  `PlayersContent.PlayerRow`, `MyTeamContent.LineupRow`,
  `WaiversContent.WaiverIdentity`/`FreeAgentRow`/`PriorityAddCompactRow`,
  `MatchupContent.SuggestedStarterRow`/`RealStarterRow`,
  `GmPlanContent.ProtectPlayerRow`/`TargetRowView`,
  `LiveDraftContent.RankingRowView`, and
  `TradeFinderContent.RosterPickRow`. They differ in gaps (gap-2 vs gap-3,
  name/injury gap-1 vs gap-2 flex-wrap) and in how value is labelled
  (B6). **Needs decision:** a shared `PlayerIdentityBlock` (badge, avatar,
  name, injury, subline) with trailing slots is the right end state.
  Adopting it changes spacing by 4px on some pages, so the owner should
  pick the canonical spacing first.
- **B6. Value label drift.** My Team puts "VALUE" under the number (accent
  color). Players puts a small "Value" label above it. Waivers'
  best-available tile puts "Value" inline to the left. `TradeAssetRow`
  shows the number with no label, in text-primary. **Needs decision**
  (coridian_ asked 2026-10-19 for a small "value" caption everywhere).
- **B7. Pick rows.** `PickRow` (shared), `TradeAssetRow`'s pick branch
  (plate + label) and `LiveDraftContent.PickRowView` (draft-board pick,
  `#pick_no` + player) all render picks. LiveDraft's is a pick *result*
  row (who was taken), a different role. **Justified one-off.** PickRow
  vs the TradeAssetRow pick branch: **Needs decision** (two pick looks:
  text-only with confidence vs square "R1/#3" plate).
- **B8. `LeagueRecapsContent.AssetChip`** is an inline-chip version of a
  trade asset for transaction history. **Justified one-off** (inline-chip
  density is the point there).

### Badges / pills / chips
- **B9. Tinted status badges, two drifting shapes.** Outlined square
  (tinted fill plus 1px border): `LeagueRankingsContent.RankBadge`,
  `WaiversContent.RecommendationPill`, and the Leaderboard's inline "You"
  badge. Rounded pill (tinted fill, badge tracking, no border):
  `TradeHistoryContent.Badge`, Portfolio's signal badge, and Alerts' roster
  relationship badge. Each is byte-identical within its group. (Being
  consolidated in the badges PR; see that PR for status.)
- **B10. Injury label re-implemented inline 8 times.** In PlayersContent,
  WaiversContent, GmPlanContent ×2, MyTeamContent and MatchupContent ×2,
  next to the shared `PlayerInjuryBadge`. (Being consolidated in the
  badges PR; see that PR for status.)
- **B11. Verdict callout duplicated.** A 35% border plus 8% tint box with
  the verdict label and detail appears in TradeHistoryContent and
  CommunityTradesContent. (Being consolidated in the badges PR; see that PR
  for status.)
- **B12. Player Compare `ValuePill` / `TextPill`.** These are compare-cell
  winners, a different role. **Justified one-off.**

### Empty / loading / error states
- **B13. 21 page files hand-roll a bare error block.** It is
  `<main><p role="alert" style={{color: var(--color-danger)}}>` with no
  retry. `ErrorState` exists for exactly this, and its docstring asks
  callers to swap in. Pages: alerts, college-scouting, community,
  draft-center, gm-plan, league-rankings, league-recaps, live-draft,
  matchup, my-team, news, player-compare (×3), players, players/[id] (×2),
  premium, trade-analyzer, trade-finder, trade-history, trade-hub, waivers.
  (See the states PR for status.)
- **B14. `CollegeScoutingContent.EmptyState`** is the only named empty
  state. Other pages show a bare muted `<p>`. **Needs decision:** whether
  the glass-card empty state should be the sitewide pattern (it would add a
  card around every empty message).

### Tabs / toggles
- **B15. `LeagueRecapsContent.TabBar`** re-implements `PillRow` as a
  full-width bar. It has the same colors and active underline, but uses
  `flex-1`, `py-2.5` and `--letter-spacing-badge` tracking instead of
  `0.03em`. (See the states PR for status.)
- **B16. `TradesTabBar`** restates `PillRow`'s style object, but uses
  `<Link role="tab">` instead of buttons. **Justified** (navigation, not
  state). It could share a style helper.

### Cards
- **B17. Accent-rail cards.** These are cards with a 3px colored left
  border: `GmPlanContent.FactCard`, `TradeOpportunityCard`,
  `TradeAnalyzerContent.VerdictCard`, `TradeIdeaCardView`,
  `LeagueRecapsContent.RecapStoryCard`, and MyTeam's `.tone-*` cards. Some
  use the `--border-width-semantic` token and some hard-code `3px`. (See
  the badges PR for the token fix.) A shared `AccentCard` is **Needs
  decision**: padding and gap differ per page.
- **B18. Waivers `BestAvailableTile`.** It is a vertical player tile
  (badge, avatar, md gauge, name, value). It overlaps `SnapshotTile` in
  shape but shows a player. **Justified one-off.**
- **B19. `PlayersContent.SortedStatTile`** is an inline label/value stack
  inside a row, not a card tile. **Justified one-off** (same visual as
  B6's value stack, so it would merge with B6).

### Hard-coded colors / spacing / radii
- **B20. White CTA text on cyan accent.** Trade Analyzer's "Analyze Trade"
  and Live Draft's "Evaluate Trade" use `color: "#fff"` on
  `--color-accent`. Every other primary CTA (ErrorState, Account,
  Premium, SignIn, AgeGate, Onboarding) uses `--color-brand-mark-ink` on
  `--color-accent-strong`. **Needs decision** (visible change: white text
  becomes dark ink. The current pairing is also low-contrast).
  There is no shared `Button`, and primary/secondary/link CTAs are
  hand-styled per page (about 30 call sites).
- **B21. Sign-in "glass" literals.** `SignInForm.tsx` hard-codes
  `rgba(255,255,255,…)` fills and borders and `22px` / `12px` radii
  instead of `.glass-input` / `--radius-*`. **Needs decision:** it is the
  landing page's own approved look, but it drifts from the token radii
  (14/20).
- **B22. Modal scrims.** GmOrb uses `rgba(0,0,0,0.55)` and
  EmbeddedCheckoutModal uses `rgba(0,0,0,0.6)`. There is no scrim token.
  **Needs decision** (pick one value and add `--color-scrim`).
- **B23. Onboarding step-number ink colors** (`#061014`, `#1a1400`,
  `#06210f`). These are per-step dark inks on accent, premium and success
  circles. **Justified** (onboarding-only art). Could use
  `--color-brand-mark-ink`.

### Justified one-offs (unique by design)
`ModelRadarChart`, `WeeklyPointsChart`, `PlayerTrendsPanel`,
`PlayerCareerTab`/`PlayerScheduleTab`, `LeaguePulseCard`, the
GuessThePlayer cards, `EmbeddedCheckoutModal`, `AgeGate`,
`OnboardingCarousel`/`OnboardingPaywall`, `AppStoreModules`,
`ReferralCard`, `PlanCard`, `LiveDraftTradeEvaluator.CheckList`,
`TradeFinderContent.SelectionCheck`, `PlayerCompareContent`'s
compare-grid rows/`IdentityCard`/`OpponentPicker`,
`MatchupContent.MatchupHero`/`VersusSide`, `LeagueRecaps` storylines.

## 3. Share cards (input for the pending redesign; not changed here)

There are two pipelines and they share no tokens. web-next renders no share
card itself. It only fetches the server trade PNG
(`TradeIdeaCard.tsx` `ShareTradeButton` → `api.getTradeHubIdeaShareCardBlob`
→ `GET /v1/leagues/{id}/trade-hub/{rec_id}/share-card.png`), and falls back
to text-only `navigator.share` or the clipboard.

| Card | Path | Tech | Consumers |
|---|---|---|---|
| Trade / waiver / player | server `modules/share_card_renderer.py` (+ `share_recommendation_cards.py`, `share_card_qr.py`) | Pillow PNG, 2160px wide, variable height | Web trade share (HTTP), Streamlit player/offer/waiver |
| Trade grade, power rankings | server `modules/growth_share_cards.py` | Pillow 1080×1350 | Streamlit only, no HTTP route |
| Player, Compare | mobile `PlayerShareCard.tsx`, `CompareShareCard.tsx` on `ShareCardChrome.tsx` | RN view + `react-native-view-shot` + `expo-sharing` | PlayerDetail, PlayerCompare |
| Trade, Portfolio, Recap | mobile `TradeShareCard.tsx`, `PortfolioShareCard.tsx`, `RecapShareCard.tsx` | same | TradeAnalyzer/TradeHub, Portfolio, Recap |

How they differ from the current UI:
- **Server PNG colors.** It uses hard-coded RGB tuples
  (`share_card_renderer.py` ~L25-36). They are commented "matches design
  tokens", but `modules/design_tokens.py` is never imported. The
  background is `(5,6,7)` instead of `#000`. The accent is `#38BDD2`
  instead of the current `#67e8f9`.
- **Server PNG shapes.** It has the old flat look: a full-bleed rectangle
  with no glass, small 8-18px radii and a square "WHY" marker. It has no
  OVR gauge, no square position badge and no app avatar. It uses an
  Inter/Noto/DejaVu font chain instead of the system SF stack.
- **Mobile chrome.** `ShareCardChrome` is a fixed 360×540 dark card with
  `radii.lg` (20, matches tokens) and a cyan rim. Its wordmark still reads
  "FANTASY**GM** LAB", while the QR line says "FantasyDesk". That
  mixed-brand leftover is copied into Trade, Portfolio and Recap, which
  each re-implement the chrome instead of using `ShareCardChrome`.
- **Mobile components.** The mobile cards use `CircularProgressRing` (not
  web's `OvrGauge` look), a rounded `PositionBadge` (`radii.sm`; web's is
  square), `TierBadge`, and `TradeValueBar` instead of web's
  `TradeAssetRow`.
- **Same card, two looks.** Server and mobile trade cards look nothing
  alike: the server is a tall poster with a value-edge bar, WHY and a QR
  footer; mobile is a compact 360×540 card. The player card differs the
  same way.

## 4. Mobile notes (lighter pass; no mobile changes in this audit)

There are 36 screens. The shared layer is healthy: `AppText` 35,
`GridBackground` 33, `AnimatedCard` 20, `BrandedSpinner` 22, `EmptyState`
15, `PlayerIdentityRow` 11, `SegmentedTabBar` 9, `SectionHeading` 9. Main
one-offs:
- **Uppercase section kicker restyled in 7 screens.** It is 12/700/
  uppercase/0.5 tracking: DraftCenter, TeamRoster, MyTeam, Matchup,
  TradeFinder and More use textTertiary; Waivers uses textSecondary. The
  local wrappers are `WaiversScreen.SectionHeader` and
  `MyTeamScreen.SectionHeaderRow`. `theme.typography.kicker` (11/600/0.8)
  matches none of them. **Needs decision** on size and color, then extract.
- **`StatCell`/`StatGrid` duplicated** in PickDetailScreen and
  PlayerDetailScreen. PlayerDetail's is a superset. This is MetricCard's
  role. Promote one copy, after a visual check.
- **Local pick/player rows.** `DashboardScreen` has a local
  `TradeAssetRow`. `TradeFinderScreen` and `TradeHubScreen` each define a
  different `ExchangeAssetList`. `DraftPickAssetRow` notes that Dashboard
  and TradeAnalyzer still have their own pick rows.
- **Local badges and tiles.** `TradeHubScreen.CategoryBadge`/`ImpactBadge`,
  `PlayerDetailScreen.UsageTrendChip` (a bigger `UsageTrendPill`),
  `DraftCenterScreen.PostureTile`, `TradeFinderScreen.MeterRow`, and
  `PercentBar`/`BucketBar`, while the shared `PercentileBar` has 0 users.
- **Hard-coded styles.**
  - Numeric font sizes are worst in PlayerDetail (33), TradeHub (25),
    Recap (23) and PickDetail (23). `typography.*` is used in only 5
    screens.
  - `'#fff'` appears on accent buttons (Login, Home, TradeAnalyzer).
    `colors.onAccent` is the token, but check the light theme first.
  - The modal scrim `rgba(0,0,0,0.6)` is copied in 4 screens and there is
    no theme token. This mirrors web B22.
- **Trivially safe fixes:** none. No mobile screen holds a byte-identical
  copy of a shared component, so every mobile consolidation needs a
  visual check on device. Per the TestFlight limits, that is out of scope
  for this pass.
