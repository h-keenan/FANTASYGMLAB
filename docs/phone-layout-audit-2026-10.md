# Phone-width layout audit (website), 2026-10

Method: production build (`next build` with the CI placeholder env) driven by headless Chromium
(Playwright, iPhone Safari user agent, touch, DPR 2) at 360, 390 and 430 px. A fake Supabase session
is seeded into localStorage and every API call is intercepted by a mock whose fixtures are generated
from the TypeScript response types in `web-next/src/lib/api.ts`, with deliberately awkward data
("Amon-Ra St. Brown", "The Long Island Iced Teas of Doom", Questionable injury pills, 5-player
trades). Per page the script records: horizontal overflow, ellipsis/clamp truncation, elements whose
content spills past their box, controls under 40 px, inputs under 16 px, fixed/sticky elements, and
whether the last content clears the floating GM orb. Scripts and screenshots live in the session
scratchpad (`.../scratchpad/phone-audit/`, not committed; screenshots are named
`before-<page>-390.png`, `after-...`, `final-...`, `*-sheet-<name>-390.png`).

Fixture caveat: generated strings like "Sample text value" are not real copy; findings that only
appear because of such strings are excluded from the table.

## Findings

| Page | Issue | Severity | Status |
|---|---|---|---|
| My Team, Trade Hub/Finder, Matchup, Waivers, Rankings, Live Draft, Trade History, Alerts, News, Scouting, Compare, GM Plan, Recaps (shared `PlayerRow`/`PlayerIdentity`, 20 components) | Player, team and manager names cut with an ellipsis ("Kenneth Walke...", "Jaxon Smith-N...", "The Long Island Iced Teas o..."); the injury pill squeezed the name. Up to 73 truncated labels per page at 390 | High | Fixed (#1416). `before-myteam-390.png` / `final_my-team_L1-bot` |
| Player sublines (`PlayerMetaLine`) | "PHI - Age 24.6" truncated beside the injury pill at 360 | Medium | Fixed (wraps, pill keeps width) |
| Players list | At 360 the row put value, ring, rank chip, Compare and Add to Trade on one line and squeezed the name to 7 px (invisible) | High | Fixed: row wraps, actions drop under the name |
| Trade History, Community | Send/receive sides forced into two columns on phones; each side was about 35 px wide, so names were illegible | High | Fixed: one column below `sm` |
| Trade Hub / Finder idea cards | Long partner name next to the fairness badge collided with it | Medium | Fixed: badge wraps below the name |
| All signed-in pages | Floating GM orb (52 px, 12 px from bottom) overlapped the last line of content (footer "Values informed by FantasyCalc", last list row): only 32 px bottom padding on most pages | High | Fixed: 48 px extra bottom padding on phones (`AppContentShell`) |
| Header (every page) | League, lens and MENU buttons 30 px high, brand link 28 px, menu items about 36 px | Medium | Fixed: 40 px targets |
| Header | Page title was truncated at 360 ("LEAGUE RANKINGS") | Low | Fixed: wraps |
| Tab/pill rows (`PillRow`) | 34-36 px tall | Low | Fixed: 40 px |
| Players, Trade Analyzer, Connect League, Account, landing/sign-in, filter selects | Inputs/selects at 14 px: iOS Safari zooms the page on focus and does not zoom back | High | Fixed: 16 px on phone widths (global CSS) |
| Players list | Compare / Add to Trade links about 26 px high | Medium | Fixed: 40 px |
| Dashboard / Trade-outcome prompt ("Did this trade happen?") | Fixed bottom card is about 400 px of an 844 px screen with a 5-player trade (long names stack) and sits over page content until answered | Medium | Recommendation: cap height or collapse the trade lists to a one-line summary |
| Player profile tab bar | Stats / Trends / Schedule / Career / Model wraps to two rows, leaving an orphaned "MODEL" tab | Low | Recommendation: horizontal scroll or shorter labels |
| Dashboard (4 snapshot tiles at 360) | Labels "Franchise Rank" / "Average Age" spill 2-11 px past the tile | Low | Recommendation: 2x2 grid below 380 px |
| Waivers (360) | Priority Adds / Top Waiver Target card contents 11 px wider than the card | Low | Recommendation |
| Rankings (360) | Team rows: three stat chips plus a long manager name squeeze the name column to about 77 px | Medium | Recommendation: stack chips under the name |
| Not-found page | "Back to FantasyDesk" is dark text on a dark teal button (low contrast) | Low | Recommendation |
| Remaining small targets | Inline text links ("FantasyCalc", "View all", "Upgrade ->", "TRADE HISTORY ->") 15-20 px high; Search/Alerts icon buttons now 40 px | Low | Recommendation: pad links to 40 px hit area |
| Landing / sign-in | Decorative background layer is wider than the viewport but clipped; no page scroll | None | OK |
| iOS safe areas | No `viewport-fit=cover`, so insets are 0 and Safari keeps the home bar clear; no 100vh usage found | None | OK. If `viewport-fit=cover` is ever added, the orb needs `env(safe-area-inset-bottom)` |

Horizontal page scroll: none on any route at 360/390/430.

## Rendered routes

Rendered at 360/390/430: landing, sign-in, Dashboard, My Team, Trade Hub, Trade Finder, Trade
Analyzer, Waivers, Matchup, Players, Player profile, League Rankings, GM Plan, Portfolio (and
Exposure data), Alerts, Draft Center, Live Draft, News, College Scouting, Account, Premium, Connect
League, GM Targets, League Recaps, Player Compare, Trade History, Community, Methodology, Legal,
Guess-the-Player leaderboard. Sheets/dropdowns at 390: Player Quick View, GM orb sheet, Alerts
dropdown, league and lens menus, main menu, manager profile sheet, trade-outcome prompt (all within
the viewport; the orb sheet and PQV scroll internally).

Not rendered: Percentile Explorer sheet and the Matchup swap-planner sheet (generated fixtures did
not enable their triggers), the onboarding carousel (needs the fresh-user state), Portfolio Exposure
view beyond its data endpoint. These need hand-written fixtures.

## Mobile follow-ups (not changed here)

The orb/last-content clearance, 40 px header controls, and wrapping of long player/team names in
side-by-side trade columns should be checked in `mobile/` screens that share these layouts (Trade
History, Community, Players list actions).
