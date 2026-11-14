# Menu consolidation: generalized pages with top tabs (2026-11)

Trigger (coridian_): the phone footer looks bland, and the product is moving to generalized pages with tabs at the top.
Scope: web (`web-next/`); the app shares the pure twin (`lib/pageFamilies.ts`) and already has the `SegmentedTabBar`
glass strip. The app has no footer tab bar (GM orb + `MoreScreen`), so the footer restyle is web-only.

## 1. Audit: where destinations live today

| Surface | What it lists |
|---|---|
| Footer (in a league) | Today, Team, Trades, League, More |
| Footer (outside a league) | Home, Portfolio, Fantasy Sim, News, More |
| More sheet | League: Today, Alerts, My Team, Matchup, Waivers, League Rankings, Players. GM tools: Trade Hub, GM Plan, Draft Center, Live Draft, League Recaps, Games, Commissioner. General: Home, Portfolio, Fantasy Sim, News, Community. Account: Pro, Account |
| Header | back (named parent), page title, league chip, search, alerts bell |
| Orb / sidebar | same catalog (`navCatalog.ts`), plus "Page > Tab" search rows |

Finding: the footer tabs Team / Trades / League each stand for several pages, but those pages were reachable only by
leaving the tab (More sheet rows or in-page links). Only Trades had a sibling strip (`TradesTabBar`).

## 2. Consolidated IA

Three families, defined once in `lib/pageFamilies.ts` (byte-identical twin, tested against `shellActiveTab`):

| Family (footer tab) | Tabs (route kept as is) |
|---|---|
| **Trades** | Hub `/trade-hub`, Finder `/trade-finder`, Analyzer `/trade-analyzer`, History `/trade-history?league=` |
| **Team** | Roster `/my-team`, Players `/players`, Waivers `/waivers`, Matchup `/matchup` |
| **League** | Rankings `/league-rankings`, Recaps `/league-recaps`, Games `/games` |

Stays as it is: Today and Alerts (Today tab), GM Plan, Draft Center, Live Draft, Commissioner (More sheet, lit under
Team/League by the existing mapping), Home / Portfolio / Fantasy Sim / News / Community, Pro, Account.

## 3. How it is built (and why URLs cannot break)

Each tab keeps its own route. The strip (`PageTabBar` over the shared `PillRow` in its new `glass` look) is rendered at
the top of every member page, so no URL changes and no redirect is needed: every old link, bookmark, `?tab=` deep link,
the orb "Page > Tab" rows and the share links open exactly where they did, now with the sibling tabs visible. Nav-active
mapping is untouched (`shellActiveTab`, `shellParent`); `pageFamilies.test.ts` pins that every member segment still
lights its family's footer tab.

Top-tab design (`.pill-row-glass`): frosted glass strip, sticky under the shell header (offset by the header height when
present), horizontal scroll-snap, cyan glass pill for the active tab with a gold hairline, optional count badges
(`counts`), 160ms transitions, off under `prefers-reduced-motion`, 44px targets, keyboard arrows/Home/End from `PillRow`.

Footer restyle (`.bottom-tab-bar`): same glass tokens (translucent surface tint, 24px blur, lit top hairline, soft cyan
glow), every tab has the same 24px icon slot and label; the active tab is a cyan glass pill with a gold top highlight.
The More button's mismatched backing was the native `<button>` defaults (font, appearance) versus the links; tabs now set
`appearance: none`, `font-family: inherit` and an identical transparent border. Safe-area padding stays on the bar.

## 4. Left for a later pass (deliberately not done: needs product input)

- Merging Players/Waivers/Matchup into literal single pages with `?tab=` (would change the URL the whole app, orb, share
  links and emails point at; the route-per-tab approach gives the same UX without that risk).
- Moving GM Plan / Draft Center under Team, and Alerts under Today, as tabs.
- Trimming the More sheet rows that are now tabs (kept for discoverability until the strips are seen in use).
- App: put the same strip on the matching screens (`SegmentedTabBar` + `lib/pageFamilies.ts`); the app has no footer bar.
- No on-device/visual screenshots were taken (verification: tsc, unit tests, twin check).
