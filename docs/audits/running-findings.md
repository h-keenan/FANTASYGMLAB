# Running findings (retroactive sweep log)

Bugs and inconsistencies noticed while working on other tasks, with file refs. Newest first. Status: Fixed (PR), Open, Decision.

| Date | Finding | Where | Status |
|---|---|---|---|
| 2026-11-14 | League Recaps week strip: tab labels overlap ("S WEEK W9EEK 8"), active pill covers neighbours. Cause: `PillRow` scroll variant used `flex-1 shrink-0` (flex-basis 0), so every tab collapsed to its 44px minimum and the label overflowed. Same bug hits any scroll strip with labels wider than 44px (Position, Draft pick years, Recaps weeks, Filter history) | `web-next/src/components/PillRow.tsx` | Fixed (this PR, `flex-[1_0_auto]`, `pill_overlap.mjs`, `pillRowGuard.test.ts`) |
| 2026-11-14 | League Recaps page: "League memory / WEEK 9 RECAP / League memory - Week 9" repeats one label three times; a "Recaps" view select plus a "More weeks..." select beside the week strip; gold on every story card; tabs unlike the rest of the site | `LeagueRecapsContent.tsx` | Open (separate agent is rebuilding the page) |
| 2026-11-14 | Header titles repeat the pill label (Today, My Team/Team, Trade Hub/Trades, League Rankings/League) | `ShellHeader.tsx`, `PAGE_TITLE_BY_SEGMENT` | Open (header rewrite phase 1) |
| 2026-11-14 | Bell unread badge white on cyan, 10px | `AlertsDropdown.tsx` | Fixed (#1957) |
| 2026-11-14 | League switcher menu off-screen at 320px, 775px tall, no scroll | `Header.tsx LeagueLensPicker` | Fixed (#1957) |
| 2026-11-14 | Trade Finder names wrapped inside words | `TradeFinderContent.tsx` | Fixed (#1939, #1954) |
| 2026-11-14 | Mobile screens report failures with native `Alert.alert` | many | Fixed (#1952, `NoticeProvider`) |
| 2026-11-14 | `header_audit.mjs` selectors were tied to the legacy dropdown | `scripts/sim_layout_playwright/header_audit.mjs` | Fixed (header phase 1) |
| 2026-11-14 | Crest hue hash clustered consecutive Sleeper ids on one hue (a 12-league list came out all green) | `lib/leagueCrest.ts` | Fixed (FNV-1a + finalizer, test) |
| 2026-11-14 | Legacy `HeaderLeagueControls` and the shell both fetched `saved_leagues` (two requests per page) | `Header.tsx` | Fixed (`useSavedLeagues`, enabled for only one of them) |
| 2026-11-14 | A failed `saved_leagues` load looked like "No other saved leagues" | `Header.tsx` | Fixed (status + Try again in the sheet, web and app) |
| 2026-11-14 | Today hero kicker "TODAY · WEEK 10" and Team kicker "TEAM" repeated the page name | `lib/statusHeader.ts` | Fixed ("THIS WEEK", "YOUR TEAM") |
| 2026-11-14 | Waivers header module titled "Waivers" under a header and pill that also say Waivers | `WaiversContent.tsx` | Fixed ("Free agents") |
| 2026-11-14 | A 55-char league name needs 3-4 lines at 320px (header 86px) | `ShellHeader.tsx` | Open (edge case; cap at 2 lines with the full name in the sheet if it shows up in practice) |
| 2026-11-15 | Sim game header 97px at every width (icon row + full-width team row) | `SimGameHeader.tsx` web + app | Fixed (header phase 5: 52px row + folding ribbon) |
| 2026-11-15 | Trade Hub filter chips 40px tall (under the 44px target); Matchup "?" help button 22px and "Refresh" link 16px; Trade Finder pick-group headers 36px with a `+`/`-` glyph | `TradeHubFilters.tsx`, `MatchupContent.tsx`, `PickGroupList.tsx` | Fixed (44px targets, rotating chevron) |
| 2026-11-15 | `module_scan.mjs` now lists every visible control under 43px per page (`census.small`) so the next sweep is one command | `scripts/sim_layout_playwright/module_scan.mjs` | Fixed |
| 2026-11-15 | Labelled inline `BeginnerHelp` rows ("? waiver value", "? playoff odds", "? this matchup page") are 16px-tall targets | `WaiversContent.tsx`, `LeagueRankingsContent.tsx`, `MatchupContent.tsx` | Open (goes away with #1954, D3) |
| 2026-11-15 | Smart pill + footer + Sim footer geometry (`pill_geometry.mjs`, `footer_sheet_audit.mjs`) pass at 320/360/390/430 | harnesses | Checked, no findings |
