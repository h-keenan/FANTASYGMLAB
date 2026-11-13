# Fantasy Sim: phone layout consolidation

The game got rich on desktop, and on a 390px phone (the web app on iOS Safari,
and the native app) every screen became a long scroll. This is the plan and what
shipped. Heights are total page scroll height in viewport heights (844px tall),
measured with Playwright at 390x844, dark theme, against a mocked API
(12-team league, 16-man rosters, 200-player pool).

## Before / after (web, 390px)

| Screen | Before | After | What took the space |
| --- | --- | --- | --- |
| Final grade / Season in Review | 8.26 | 2.15 | 13 sections stacked (grade parts 0.45, stats 0.55, decisions 0.9, moves 1.2, leaders 1.1, standings 1.2) |
| Home | 6.00 | 2.52 | matchup with 8 lineup rows 3.1, injuries, standings, hot/cold, every card open |
| Draft room: Players | 5.05 | 2.73 | 185px rows, 25 rows per page, 1 screen of header |
| Players tab | 5.98 | 2.80 | 25 two-line rows per page |
| Trades: build an offer | 3.33 | 1.63 | flat roster lists on both sides |
| Team | 2.60 | 2.25 | wrapping lineup rows, tall bench rows |
| League | 1.96 | 1.39 | two-line standings cards |
| Week recap | 2.35 | 2.06 | |

Draft board / queue panels were already short (1.6 / 1.1) and are unchanged.
The native app shares the same structure, so the same rules apply there.

## Principles

1. **Summary first, detail on demand.** Every secondary card is a shared
   `Collapsible` (web `Collapsible.tsx`, app `Collapsible.tsx`): a header with a
   title and an always-visible summary badge ("3 out - 1 starting"), a body that
   opens on tap. `aria-expanded` / `accessibilityState.expanded`, no animation (so
   reduced motion needs nothing). The open state is remembered per id
   (`fgl:sim-open:<id>` in localStorage / AsyncStorage). `SimFold` adds the glyph
   title and the rule: open on desktop, closed on phones unless the card needs
   action (inbox with offers, waivers with targets, standings).
2. **Sub-tabs inside long pages.** Home: This week / League. Season in Review:
   Overview / Awards / Stats / Standings (`simReviewViewFor` maps sections to
   tabs). Built on the shared `PillRow` / `SegmentedTabBar`, which now take an
   optional `icon` slot and a `count` pill so tab icons are added in one place.
3. **Carousels for lists of cards.** Awards, decisions, leaders and hot/cold
   are horizontal snap strips on phones (84% wide cards), grids on desktop.
4. **Previews, not dumps.** `simPreview` + "See all (n more)" for waivers,
   offers, byes, league moves. Long lists are windowed: 20 rows, then "Show 20
   more on this page" (`simWindow`), on top of server paging.
5. **Density.** 32px avatars in rows, one-line rows, 4-column stat strips that
   share a template with their header, 40px icon buttons instead of text buttons,
   one fixed grid for every lineup row.
6. **Always-reachable action.** A bottom action bar on the in-season tabs:
   `Advance Wk 4 -> 5` (disabled with the reason: "Fill 1 empty slot", "Cut 2
   players first") and a secondary `Auto-set` pill. Fixed above the safe area with a
   notch for the floating GM orb; page content gets matching bottom padding so
   the orb and bar never cover the last row.
7. **Desktop is untouched.** At >= 1100px the original two-column layouts and
   open cards render; every phone rule is gated on that breakpoint.
8. **No horizontal overflow, ever.** Playwright checks `scrollWidth <= viewport`
   at 360, 390, 600, 820, 1024 and 1099px for every game screen.

## Shared building blocks

- Lib twins (byte-identical, checked by `scripts/check_lib_twins.mjs`):
  `simLayout.ts` (open state, preview/window, review tabs, trade asset groups,
  advance state, auto-set diff), plus additions to `simDraft.ts` / `simGame.ts`.
- Components: `Collapsible`, `SimFold`, `SimSeeAll`, `SimIconButton`,
  `SimActionBar`, `useSimAutoSet`, `SimPlayerChip` (`onOpen` / `quick`),
  `SimOpenPlayerContext`.
- Trade picker groups are `SimAssetGroup { kind: "player" | "pick" }`, so a
  dynasty "Picks" group is one more group, no picker changes.

## Draft board fixes

- Edge was `pick on the clock - ADP`, so a board sorted by ADP showed a red
  arrow that grew with rank. It is now ADP vs the model's value rank
  (`value_rank` / `adp_edge` from `players_page`): green = the market lets him
  fall past where we rank him, red = the market is ahead of us, nothing within 3.
- Value is the sim's 0-100 model scale (top player = 100), not the main app's raw
  market value; the header says so.
- An injured or bye player projects 0.0 for the current week; the board shows
  his per-game mean (`ros_mean`) and dims the row. Display only, engine unchanged.

## Player detail

The game's player detail is the main app's Player Quick View with a sim overlay
(`simOverlay`, `remote` props): real Sleeper ids load real data; synthetic
players render the same layout without remote sections. Overlay sections are
collapsibles: In this game, Week by week, Results so far, Game news.
