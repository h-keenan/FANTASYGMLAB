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
