# Mobile UI module inventory (2026-10-25)

App counterpart of `ui-module-inventory.md`. Counts are from grep over
`mobile/src` (static, no device run). Owner picks (all A) are the standard.
"Done" = merged into the shared module in this PR.

| Module | Shared standard (web / app) | Copies found | Plan / status |
|---|---|---|---|
| Section title | `SectionHeading` / `SectionHeading` (28 files use it) | Uppercase restyles remain in GuessThePlayer prompts (8 style keys), EspnLeagueImport (4), HowWeEvaluate (4), LegalPage (4), SampleLeague (4), LiveDraft (3), Home (3), Recap (2), Dashboard `cardLabel`/`sideLabel`. Waivers had 2 dead `sectionLabel` styles | Waivers dead styles removed (done). Next PR: migrate Home, SampleLeague, LiveDraft, Recap, Legal, HowWeEvaluate headings |
| Page title | `--font-page-title` h1 / **new `PageTitle`** | Dashboard header bar (22), Matchup (26), per-screen native header titles | Done: Dashboard + Matchup share `PageTitle`. Next: My Team, others use native header title |
| Primary button (dark ink on cyan) | `Button` / `Button` | Hand-rolled filled buttons: ProspectScoutingDetail submit, TradeIdeaCard "Share to Propose", AgeGate Continue; still: Paywall, Login, Onboarding, Home, share-preview modals (4), PlayerDetail watch pill | Done for the first three. Next PR: Login, Onboarding, Paywall, 4 share-preview modals |
| Secondary button | `Button secondary` | TradeHub gate "Watch ad" | Done |
| Badges / pills | `ToneBadge` (rounded pill) | "You"/"Default" accent badges x4 (Teams, PlayoffOdds, LeagueStandingStrips, Home; Home used hard-coded `#fff` ink on cyan) ; ~53 files define `radii.pill` styles, most are chips/toggles not badges | "You"/"Default" merged (done). Dashboard `tradeBadge` and MyTeam `outlookBadge` next |
| Text input | `Input` / `Input` | Raw `TextInput`: Waivers search, Players search, PlayerCompare, TradeAnalyzer, ProspectScouting (GmOrb is intentionally custom) | Waivers done. Next: Players, PlayerCompare, TradeAnalyzer, ProspectScouting |
| Empty state | `EmptyState` (21 uses) | Hand-rolled: Dashboard `emptyCard`, TradeHub `empty`/`notReadyText`, TradeAnalyzer, FounderAnalytics, WeeklyPointsChart | Next PR |
| Tab bar / segmented | `SegmentedTabBar` (27 uses) | Local active-chip styles: TradeAnalyzer `pillActive`, TradeHub `summaryTileActive`/`positionChip`, PlayerLeagueActions, ProspectScouting, ViewModeToggle | Next PR (TradeHub chips first) |
| Glass card | `AnimatedCard`/`AccentCard` + `lib/glass.ts` | ~31 files read `colors.glass` directly (Waivers `discoveryCard`, Players x3, TradeAnalyzer x4, GmPlan x3 ...) | Next: promote one `GlassCard` wrapper, replace per-screen |
| Player row | `PlayerIdentityRow` (24 uses) | Share cards/hero are intentionally separate | No further copies in the 5 target screens |
| Modal / sheet / backdrop | `scrim` token, `SwipeDismissSheet` | Backdrop all on `scrim` except `GmOrb` (0.75, intentional orb overlay); 5 files own a `<Modal>` (Home x8, PushPermissionPrompt, GuestCreateAccount, ManagerProfile, SwipeDismissSheet) | Home's 8 modals should move onto one sheet component. Next PR |
| Header chrome | web `Header` / `BrandHeaderBar`, native stack header | Header icon buttons had a bare hairline ring | Now glass fill + rim (done). App has no bottom tab bar (stack nav); not added |
| Stat tile / value | `MetricCard`, `ValueStat`, `DashboardStatRow` | Dashboard `valueLabel`/`valueNumber`, MyTeam `teamValueLabel`/`valueLabel` own 9-10px label styles | Next: switch to `ValueStat` |

Not verified on device. This PR is PR 1 of a split (inventory + first modules).
