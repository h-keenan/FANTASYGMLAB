# App vs site audit, 2026-11-04

Scope: `mobile/` (Expo 54, RN 0.81) vs `web-next/`. Trigger: coridian_ reported a blue tint at the top of the app.
Related older docs: `docs/app-web-parity-audit.md`, `docs/web-app-parity-audit-2026-10.md`. This one is fresh from code at commit 14cc0517.

## A. The blue tint

- Source: `mobile/src/components/AppBackground.tsx` (the single page background behind every screen) painted a vertical wash from `gradients.hero` (`theme.ts`, dark: `#16202C` navy at the top fading to `#000000`) plus a radial "bloom" in `colors.accent` (cyan, 10-12% opacity) centered at the top edge. Light mode used `lightGradients.headerWash` (`#D2FAFF`, cyan-blue) at the top.
- It was current code, not only an old build. The navy stop dates to 0d1cdea8 (2026-09-15, "dark, glass-styled theme"); the light cyan stop was added in ebe2700b (2026-10-06, "header becomes invisible in light mode"). The 2026-10-27 palette sync (c88b0a27, #1564) made all flat tokens match the web but left the gradient and bloom, so the top stayed tinted.
- Web: `body { background: var(--color-bg) }` (`#000000` dark, `#eef3f6` light), no top wash.
- Fix (this PR): `hero` is now `#000000 -> #000000`, `headerWash` is `#EEF3F6 -> #EEF3F6`, and the bloom is a neutral 5% white (3% ink in light) instead of cyan. The animated grid lines and sweep are kept (they mirror web). A new test in `mobile/src/lib/webTokenSync.test.ts` asserts both wash stops equal web `--color-bg`.
- Not causes: `app.json` splash is `#FFFFFF` light / `#000000` dark (native splash only); `BrandHeaderBar` and the nav theme use `colors.background`.
- A device on an already-published build keeps the tint until a new build ships.

## B. Screen and feature parity

Web routes in `web-next/src/app/*`; app screens in `mobile/src/screens/*`.

| Site feature | Site route | App | Notes |
|---|---|---|---|
| Landing / marketing | `page.tsx`, `features`, `methodology` | `FeaturesScreen`, `HowWeEvaluateScreen`, `OnboardingScreen` | Parity (condensed in app). |
| Login / connect league | `connect-league` | `LoginScreen`, `OnboardingScreen` | App adds Apple sign-in (`expo-apple-authentication`). |
| Dashboard / home briefing | `dashboard` | `DashboardScreen`, `HomeScreen` | Parity. |
| My Team | `my-team` | `MyTeamScreen`, `TeamRosterScreen` | Parity. |
| Matchup | `matchup` | `MatchupScreen` | Parity. |
| Waivers | `waivers` | `WaiversScreen` | Parity. |
| Trade analyzer | `trade-analyzer` | `TradeAnalyzerScreen` | Parity. |
| Trade finder / hub / offer / history | `trade-finder`, `trade-hub`, `trade-offer`, `trade-history` | `TradeFinderScreen`, `TradeHubScreen`, `TradeOfferScreen`, `TradesScreen`, `TradeHistoryScreen` | Parity. Web "Build an offer" (#1656) is the newest; verify the app matches. |
| Player pages / compare | `dynasty-players`, `players`, `player-compare` | `PlayersScreen`, `PlayerDetailScreen`, `PlayerCompareScreen` | Parity. |
| Rankings / trade value chart | `dynasty-rankings`, `dynasty-trade-value-chart`, `league-rankings` | `PlayersScreen`, `TeamsScreen` (partly) | No dedicated trade value chart screen in the app. |
| Portfolio | `portfolio` | `PortfolioScreen` | Parity. |
| News / alerts | `news`, `alerts` | `NewsScreen`, `AlertsScreen` | Parity; app adds push. |
| Draft / live draft / college | `draft-center`, `live-draft`, `college-scouting` | `DraftCenterScreen`, `LiveDraftScreen`, `CollegeProspectsScreen`, `ProspectScoutingDetailScreen`, `PickDetailScreen` | Parity. |
| GM plan / GM targets | `gm-plan`, `gm-targets` | `GmPlanScreen` | Targets not a separate app screen; confirm they are folded in. |
| Playoff odds, recaps | `league-recaps` | `PlayoffOddsScreen`, `RecapScreen` | Parity. |
| Commissioner | `commissioner` | `CommissionerScreen` | Parity. |
| Community, games, leaderboard | `community`, `games`, `guess-the-player-leaderboard` | `CommunityScreen`, `GamesScreen`, `GuessThePlayerLeaderboardScreen` | Parity. |
| Sample league | `sample-league` | `SampleLeagueScreen` | Parity. |
| Premium / paywall | `premium` | `PaywallScreen`, `TrialLapsedScreen` | Web Stripe; app RevenueCat (`react-native-purchases`). Intentional split. |
| Legal | `legal` | `LegalPageScreen` | Parity. |
| Design page | `design` | `DesignScreen` | Both. |
| Founder analytics | `founder-analytics` | `FounderAnalyticsScreen` | Both. |
| Share cards | `share-card/{player,trade,public-trade}` | `components/ShareCardChrome.tsx` (view-shot + sharing) | App renders an image and shares it; web has public URLs. |
| Dynasty tools, team situation, account | `dynasty-tools`, `team-situation`, `account` | `MoreScreen` / partial | Not confirmed one-to-one; check each. |
| SEO (`sitemap`, `robots`, public trade pages) | yes | n/a | Web-only by nature. |

Only on the app: push notifications (`lib/pushNotifications.ts`), Apple sign-in, RevenueCat, GM orb with haptics, offline query cache (`@tanstack/react-query-persist-client`), iOS Live Activity / widget code (`mobile/native/live-activity`, `lib/liveActivity.ts`), shipped dark behind a flag.
Only on the site: SEO and public share pages, Stripe checkout, account page, dedicated trade value chart.

## Visual language

| Area | Site | App | Gap |
|---|---|---|---|
| Colors | `globals.css` tokens, single cyan accent | `theme.ts`, byte-synced and tested (`webTokenSync.test.ts`) | Aligned. The top tint was the one divergence (fixed). |
| Glass | `rgba(31,34,38,.6)` + backdrop blur on cards | `lib/glass.ts`, `GlassPanel.tsx` (`expo-blur`) | Aligned in spirit; app card rim is cyan (`AnimatedCard`), web rim is neutral. Documented divergence. |
| Typography | system sans via CSS vars | Inter (`@expo-google-fonts/inter`) | Different face; sizes from tokens. |
| Spacing / radii | CSS vars | `theme.ts` scales, asserted in the sync test | Aligned. |
| Icons | web icon set | `@expo/vector-icons` | Different sets; check consistency per screen. |
| Player art | headshots via `<img>` | `PlayerAvatar.tsx` with `expo-image` | Aligned. |
| Charts | HTML/SVG, hover | `react-native-svg`: `RatingHistoryChart`, `WeeklyPointsChart`, `ModelRadarChart` | App charts are static; no scrub or tooltip. |
| Background | flat `--color-bg` + animated grid | `AppBackground` animated grid, now neutral base | Aligned after the fix. |

## Behavior differences

- Navigation: web is route-based with URLs; the app is a native stack with no `linking` config on `NavigationContainer` (`RootNavigator.tsx:258`), so URLs do not open screens. Notification taps do route via `routeNotificationTap`.
- Sharing: the app QR points at the web apex `https://fantasygmlab.com/?utm_source=share...` (`ShareCardChrome.tsx:12`), not at the specific card or an app deep link.
- Haptics are used in only 2 files (`GmOrb.tsx`, `PercentileExplorerSheet.tsx`).
- Pull-to-refresh (`RefreshControl`) is on 8 files, not every list screen.
- Light mode exists on both; the app has a Day/Night/Auto setting, web follows system.
- Billing: Stripe on web, RevenueCat on app; entitlements must stay in sync.

## C. Ranked native-ability recommendations

Installed (package.json): expo-haptics, expo-notifications, expo-blur, expo-image, expo-sharing, expo-web-browser, expo-apple-authentication, expo-auth-session, expo-file-system, expo-device, gesture-handler, reanimated, react-native-purchases, react-native-view-shot, qrcode-svg, query persist client. Not installed: expo-local-authentication, expo-store-review, expo-contacts, @shopify/react-native-skia.

| # | Item | Value | Effort | Status |
|---|---|---|---|---|
| 1 | Universal links and `fantasygmlab` scheme deep links for trade/player/share cards; share QR should point at the card URL, not the apex | High: shared cards open the app | M | Not done. Scheme is set in `app.json`; no `linking` config; QR targets the apex. Needs the associated-domains entitlement and an apple-app-site-association file on web. |
| 2 | Haptics on key moments (verdict reveal, save/accept, refresh release) through one shared helper | High, feels native | S | Partial: module installed, used in 2 files. |
| 3 | Actionable push categories ("Open matchup", "Waiver ends soon") plus a priming screen before the OS prompt | High: opt-in and re-engagement | M | Partial: push and tap routing exist; no categories or actions; priming not confirmed. |
| 4 | Home-screen widgets and Live Activities (matchup score, waiver deadline); Dynamic Island rides on the same ActivityKit work | High, visible | L (native Swift) | Scaffolded and dark: `mobile/native/live-activity`, `plugins/withLiveActivities.js`, flag `EXPO_PUBLIC_LIVE_ACTIVITIES_ENABLED`. Needs a native build. |
| 5 | Instant launch (stale-while-revalidate cache) | High | S | Done: react-query persist installed and tested (`queryClient.test.ts`). Audit that every screen renders cached data first. |
| 6 | Swipe actions and long-press menus on rows (watch, drop, compare) | Medium | M | Not done. gesture-handler and reanimated are installed. |
| 7 | Face ID lock / quick re-auth | Medium | S | Not done. Needs `expo-local-authentication`. |
| 8 | In-app review prompt after a win (trade verdict, 3rd session) | Medium | S | Not done. Needs `expo-store-review`. |
| 9 | Share sheet for trade cards carrying a deep link | Medium | S | Partial: image share exists. Pair with #1. |
| 10 | Share extension (send a Sleeper link into the app) | Medium | L (native extension) | Not done. |
| 11 | Interactive charts (scrub rating history) | Medium | M | Static SVG today. Reanimated plus svg is enough; skip Skia unless needed. |
| 12 | Paywall polish with RevenueCat offerings, trial copy, restore | High (revenue) | M | In place (`PaywallScreen`, `lib/revenuecat.ts`); see `docs/paywall-audit-2026-10.md`. |

Deferred: App Clips (L, needs #1 first), Siri / App Shortcuts (L, native), Lock Screen controls (rides on #4), contacts-based league invites (needs `expo-contacts` and a privacy review), native sheet detents (react-native-screens 4.16 supports them; modals exist in `RootNavigator.tsx`).

Rule for all of these: ship each as a visible button or screen, never a gesture-only or hidden feature.
