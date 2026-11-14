# Live site visual QA (2026-11-14)

Read-only pass over https://app.fantasygmlab.com (no sign-in, no forms). Chromium 1248 via playwright-core
(WebKit in the local cache is incomplete, so iPhone emulation is Chromium at 390x844, touch + mobile UA).
Viewports: 390x844 and 1440x900. Screenshots at top, middle and bottom scroll of each page.

## Coverage and limits

- Covered: `/` (landing), `/sample-league` (all 4 tabs: Today, Roster, Top moves, Trade), `/methodology`,
  `/dynasty-tools`, `/dynasty-trade-value-chart`, `/dynasty-rankings/qb`.
- `fantasygmlab.com` (apex) returns 404 for `/features`, `/news`, `/community`; on `app.` those routes return 200 but
  client-redirect a signed-out visitor to `/` (title/height identical to the landing page). `fantasydesk.app` 301s to
  `app.fantasygmlab.com`. `/my-team`, `/trade-hub`, `/league-rankings`, `/dashboard` return 404 signed-out.
- NOT verifiable without an account: the page tab strip on real pages, the bottom footer / GM orb pinning, CompactModule
  collapsed forms on My Team / Trades / League, charts. The sample league shows none of these (see D1). Checks 1, 2 and
  6 below are therefore only partly covered; recommend a signed-in pass by the owner or the fixture-based
  `scripts/sim_layout_playwright/module_scan.mjs`.
- Horizontal overflow: none on any page/viewport (scrollWidth == clientWidth everywhere).

## Defects

| # | Sev | Page / viewport | Description | Suspected file |
|---|---|---|---|---|
| D1 | High (coverage) | `/sample-league`, phone + desktop | The public sample is the only thing a prospect can see, and it shows none of the shipped standards: no bottom footer / GM orb at any scroll position, no page-aware bottom bar. Tab strip is a 4-tab row (full width, opaque, one row: OK) but it scrolls away with the page instead of staying reachable. A visitor on Roster/Trade never sees the pinned chrome the real app has. | `web-next/src/components/SampleLeagueContent.tsx`, `app/sample-league/page.tsx` |
| D2 | Medium | `/sample-league`, 390 | Sticky "Sample league" banner is 114px tall (13% of the screen) and stays pinned over every tab. Its top edge sits flush at y=0 with no gap, and the next heading ("THIS WEEK") starts directly under it with no spacing, so content visibly slides under the glass. Collapse to a one-line pill after first scroll. | `web-next/src/components/SampleLeagueBanner.tsx` (`glass-surface sticky top-0 z-20 ... p-3`) |
| D3 | Medium | `/sample-league` Today, both | "League Activity" rows show empty grey circles where team avatars should be (three identical blank discs), so the module looks broken/dull. Also its chevron is a small thin `>` while sibling modules use `+` and `Open ->` (inconsistent expand affordance in the same list). | `SampleLeagueContent.tsx` league-activity rows; `ui/CompactModule.tsx` |
| D4 | Medium | `/sample-league` Today, both | Fully tappable rows carry a trailing arrow (Lineup, Needs attention, Later this week, Trade ideas) while Taps are disabled in the sample ("Taps are turned off here"): arrows promise navigation that does nothing. Per ui-patterns, a fully tappable row should not carry a chevron; here the row is not tappable at all. Trade ideas row also wraps "Trade Hub" onto a second line at 390. | `SampleLeagueContent.tsx` |
| D5 | Low | `/sample-league` Roster, 390 | First roster row has a doubled top rule (card border plus the row divider 12px below), looks like a stray line. Names render in full ("Alex Sampleton", "Casey Placeholder") rather than the J. Surname rule; they are not ellipsized, so this is acceptable only if the rule is scoped to real rosters. | `SampleLeagueContent.tsx` roster list |
| D6 | Low | `/sample-league` Trade tab, 390 and 1440 | Page ends after one card; ~230px (phone) and the whole lower half of desktop are empty. Dull ending, no CTA to connect a league below the offer (the only CTA is the sticky banner). | `SampleLeagueContent.tsx` |
| D7 | Low | `/` landing, 1440 | Hero content sits in the left 800px and the right half of the first screen is empty (only the rain texture). Header wordmark "FANTASYDESK" and the large hero logo repeat the brand twice within 100px. | `web-next/src/app/page.tsx` |
| D8 | Low | all pages, 390 | Phone header shows only the FD mark (no wordmark) and an account icon, while desktop shows "FANTASYDESK". No page title or back affordance in the header on content pages; `/methodology` has its own "<- FANTASYDESK" back link instead. | shared header in `app/layout.tsx` / header component |
| D9 | Low | Theme consistency | Landing and sign-up block are dark; every SEO/public page and the sample league are light (default light with a blue-grey field). Moving from "Try a sample league" (dark) to the sample (light) is a jarring theme flip. | `globals.css` theme resolution for public routes |
| D10 | Low | `/dynasty-rankings/qb`, `/dynasty-trade-value-chart`, 390 | Row meta ("QB · BUF · age 30 · trend stable") wraps to two lines on every row and the Superflex rank `#1` is squeezed under the value; table feels dense and each row is two-line. Names are full, underlined links (not ellipsized, OK for an SEO page). Consider dropping "trend stable" when stable. | `web-next/src/app/dynasty-rankings/[position]/page.tsx`, `dynasty-trade-value-chart` |
| D11 | Info | `/news`, `/community`, `/features` on app host | Signed-out visitors get the landing page after a client redirect; SSR `<title>` is "News · FantasyDesk" but the final title is the landing title. Fine, but they flash a blank/loading state first and the apex host 404s for the same paths. | `app/news/page.tsx`, `app/community`, `app/features` |

## Passed

- No horizontal scroll anywhere; no clipped text/tags on public pages; method page reads cleanly.
- Sample tab strip: full width, opaque, centered labels with icons, single row, active tab clearly filled.
- No double header on desktop (single bar with wordmark + account).
- Position badges (QB/RB/WR/TE) and FAIR tag render unclipped.
- Sample Today collapsed modules show real info (My Team "Power #3 · Franchise #2 · Starters #4 · Bench #7", Watchlist "3 alerts · Taylor Exampleton is trending up").
