# Module templates rollout (2026-11)

Implements Phase 2/3 of `2026-11-information-architecture.md` for Today and Team, on top of the template catalog in
`web-next/src/lib/moduleTemplates.ts` (twin: `mobile/src/lib/moduleTemplates.ts`) and `docs/ui-patterns.md` "Module templates".
(The Fantasy Sim carousel work keeps its own checklist in `2026-11-universal-modules-audit.md`.)

Legend: [x] migrated, [~] partly (reason), [ ] bespoke, remains.

## Templates added

- [x] Catalog + collapsed-form rule in lib twin (`MODULE_TEMPLATES`, `collapsedVerdict`, `statStripParts`, `listSummaryParts`, `trendModel`, `heroParts`).
- [x] `Hero`, `StatStripModule`, `LinkModule` (web `components/ui/ModuleTemplates.tsx`, app `components/ModuleTemplates.tsx`). CompactModule stays the base.
- [x] Enforcement: `ui/assertCompactInformative.ts` + `ui/ModuleTemplates.test.tsx` (catalog self-check, verdict, component collapsed forms, source scan of web and app).

## Today (`/dashboard`, app `DashboardScreen`)

| Module | Before | Now |
|---|---|---|
| My Team strip | heading + 6 tiles always open, "Open" link | [x] `StatStripModule` "My Team": collapsed "Power #3 · Franchise #5 · Starters #2 · Bench #7", tiles + glossary on tap, Open link as the action. `data-fgl-dashboard-complete` marker kept on the wrapper (web) |
| Watchlist & Alerts | heading + full card list | [x] `CompactModule`: "3 alerts · <top headline>", list on tap, "All" link as the action |
| Trade ideas | heading + link row | [x] `LinkModule`: "2 trade ideas · Deadline 2 wks left · Trade Hub" (web + app); beginner help kept |
| More (league activity, mini-games, league type) | `<details>` / bespoke header | [x] `CompactModule` (children mount only when opened, as before) |
| Needs attention | list card | [~] stays a decision list (the one "do this now" list, deduped by `lib/dashboardLayout.ts`); a collapsible header would hide the urgent item |
| "Your team right now" (TeamStatusHero) | matchup + lineup + standing + rooms in one card | [x] `Hero` (win chance, else live score, else standing, else record; matchup as the context line) + `LinkModule` Lineup + `CompactModule` Standing and Position rooms. Pure model in `lib/teamStatusModules.ts` (twin, tested). Standing module is hidden when the Hero already is the standing and it adds no odds/projection (no decision twice). Web + app |
| StartHere, SinceLastVisit, DirectionCheckin, FirstValueOffer, Guillotine, GuessThePlayer | cards | [ ] bespoke, remain (one-off prompts, not repeating modules) |
| No duplicated decisions | | [x] unchanged: attention vs next moves vs trades block dedupe (`dashboardLayout.ts`); Watchlist headline shows only collapsed, body only expanded |

Reachability: every tile, insight link, alert, trade link and mini-game is still one tap away (tap the module). Tests: `DashboardContent(.beginner).test.tsx`, `SampleLeagueContent.test.tsx` (expand then assert), plus "no collapsed module is an empty header".

## Team (`/my-team`, app `MyTeamScreen`)

| Module | Before | Now |
|---|---|---|
| Tab rows | family strip + Starters/Bench/IR/Taxi/IDP pills (2 rows, web); roster segmented tabs (app) | [x] web: one tab row (family strip). Roster groups are `CompactModule` sections. App: roster tabs removed (the app has no family strip yet, see below) |
| Snapshot | Value ring + archetype + 6 tiles | [x] `Hero` (Team Value, percentile + starters value as context, archetype badge) + `StatStripModule` "Team Snapshot" ("Record 3-5 · Power #3 · Franchise #5 ...") |
| Team analysis | heading + list + notes | [x] `CompactModule`: "WR Thin · QB Strong ..." (web adds "Biggest need: RB"), rows + notes + "Act on a need" inside |
| Roster | tabbed list | [x] sections: "9 players · Value 6,120 · Gibbs, Chase"; Starters open by default; the section holding `?playerId=` opens (web `RosterSections`, app via `rosterTab` focus key) |
| Roster composition | heading + bar | [x] `CompactModule`: "Starters 50% · Bench 25% · IR 25%" |
| Keeper candidates | heading + list | [x] `CompactModule`: "4 candidates · Keep up to 3 · 2 recommended" |
| App "Team analytics" panel | toggle link | [x] `CompactModule` "Team Analytics" |
| Value ring (`ValueRing`, `CircularProgressRing`) | | [~] no longer on this page (Hero number replaces it); components remain for other pages |

## Trades (`/trade-hub`, app `TradeHubScreen`)

- [x] `Hero` "Trade ideas": count + top idea (partner, gain) when there are ideas (web + app).
- [x] 3-team ideas and Buy low / Sell high are `CompactModule`s whose collapsed form is built from the loaded data ("2 3-team deals · fair for every team", "3 signals · 2 buy low · 1 sell high · Name"); loading and error states have a real sentence too (web + app).
- [x] One tab row: the Trades family strip (web).
- [x] Idea cards (`TradeIdeaCardView`, app `TradeIdeaCard`) are CompactModules (rollout 3); Finder, History, Analyzer verdict migrated on web.

## League (`/league-rankings`, app `TeamsScreen`)

- [x] Web: Standings and every rank board are `CompactModule`s ("1. Team 1 · You #4 · 8 teams"); Roster Power opens by default; a `#board-x` insight-link hash opens its board; anchors (`id="board-x"`) unchanged.
- [x] App: already one board at a time via the metric segmented control, which is the plan's target. Left as is.
- [ ] Playoff Odds and "Your standing" card are bespoke; Recaps, Games, Draft, Pick'em not migrated.

## Matchup, Waivers, Players (pass 2, 2026-11-14)

Root cause of the doubled desktop header (coridian_ Matchup screenshot, "Today > Matchup" bar above the "FANTASYDESK MATCHUP" bar): `ShellHeader` is `.shell-header md:hidden`, but `.shell-header { display: flex }` is unlayered CSS and Tailwind v4 utilities live in `@layer utilities`, so the component rule won and the phone header rendered on desktop above the real `Header` on EVERY page under the shell flag. Fixed at the source with one `@media (min-width: 768px) { .md\:hidden { display: none !important } }` guard in `globals.css` (it also covers `.bottom-stack` and `.sim-game-header`, same bug class). Test: `app/phoneChromeCss.test.ts`; scan: desktop fails if the ShellHeader is visible or more than one header bar shows.

| Page | Before | Now |
|---|---|---|
| Matchup (`/matchup`, app `MatchupScreen`) | 48rem column, scoreboard card, Insights card with the position list far from its sentence, Lineup card, Moves toggle | [x] `Hero` (win chance, else score, else projections; both teams in the context line), `CompactModule` Insights (open: sentence + edge chips right beside it; collapsed "You're favored · RB +16.7 · WR -4.6"), Lineup Comparison (open; collapsed "Suggested · 118.3 vs 109.7 · +8.6 · 9 slots"), Teams & values (avatars, split bar, value tiles; collapsed "Value 45,719 vs 48,673 · -2,954 · Proj margin +8.6"), Suggested Moves (collapsed "3 moves · Start Gibbs +4.2 pts"). `page-shell-wide` (72rem) and a two-column `matchup-grid` from lg (Insights + Teams + Moves left, Lineup right); one column on phone. Pure model `lib/matchupModules.ts` (twin). Web + app |
| Waivers "More recommended adds" | per row: Value + gauge, bid + "of $81 remaining" + chevron, 2-3 loud chips, "DROP X" block | [x] row = name / position / team + ONE bid number at the right, reasons as one line of small icon pills, whole row is the tap target (expands in place, no chevron). Expanded: Value + gauge, bid context, why, usage, this add's roster move, Player details. The cut shared by the group is one "Drop candidate" note above the list (`SharedDropNote`), a row names its cut only when it differs; "Bid ranges are of $81 remaining" once. `lib/waiverGroups.ts` (twin). Web + app |
| Players | Players / Picks pill row (second tab row) + Sort row under the filter row | [x] web: Picks is a `CompactModule` under the list ("12 picks · 2026-2028 · Top 2026 1st"), Sort sits in the Filters row. App already has one control row and no Picks view (nothing to migrate) |

Reachability: nothing removed; every Matchup block, waiver value/gauge/why/usage/drop and every pick is one tap away. Scan (`module_scan.mjs`, 390 and 1440, fixtures for Matchup/Waivers/Players): clean; Matchup is 1140 px wide at 1440, a Waivers recommended row is 77 px at 390 (was about 150).

Still open from this pass:
- [x] Waivers: ONE tab row (family strip) + ONE control row (`ViewSelect` + the view's filters), web and app (rollout 3, below).
- [ ] Row highlight deep link does not auto-expand the app row (web does).

## Rollout 3 (2026-11-14): waivers, app family strip, trade pages, GM Plan, league pages, desktop

Heights from `module_scan.mjs` (390 / 1440, fixtures, same script run on `origin/main` before and on this branch after):

| Page | Before | After | Change |
|---|---|---|---|
| Trades (`/trade-hub`, 3 ideas) | 2737 / 2442 | 1070 / 959 | [x] idea cards are CompactModules, collapsed 3 ideas fit one screen |
| Waivers | 2064 / 2204, 2 tab rows | 2008 / 2205, 1 tab row | [x] family strip + one control row |
| GM Plan | 1588 / 1728 | 1284 / 1236 | [x] Team Situation, Plan Snapshot, Trade ideas, Protected Core, focus areas = CompactModule; Season outlook = LinkModule; trade opportunity cards use the idea summary |
| Games | 1545 / 1808, 2 tab rows | 844 / 900, 1 tab row | [x] `ViewSelect`; league odds, What-if, Pick'em leaderboard = CompactModule |
| Draft Center | 1071 / 930 | 951 / 900 | [x] posture, pick values, signal sections = CompactModule |
| Sample league | main 840 px at 1440 | main 1140 px, two columns from lg | [x] `.sample-grid` + sticky right rail (connect CTA); sidebar shows the sample views, News, Fantasy Sim, Community, Pro, Account (founder item kept) |
| Trade Finder | 1238 / 1292, 3 tab rows | 1487 / 1409, 2 | [~] sections are CompactModules (players/picks open, "what you want back" collapsed); heights are higher only because the baseline run had not finished loading the roster |

- [x] Web: Trade Finder, Trade History (each trade a module: outcome · verdict · net · swap), Trade Analyzer verdict (lineup and odds / next move / confidence and risk are modules; verdict, matchup and balance stay open), League Recaps view selector, Live Draft (on the clock, recommendations, rankings, team rankings, board).
- [x] App: `PageFamilyTabs` (+ `lib/pageFamilyRoutes.ts`) on MyTeam, Players, Waivers, Matchup, Trades, Teams, Recap, Games; Teams / Recap / Games inner views and Teams "Rank by" are `FilterDropdownButton`s; Waivers control row; `TradeIdeaCard` and GM Plan sections are CompactModules.
- [~] Desktop: sample league uses the width; Trade Hub idea cards are two columns from lg. The Trade Hub filter row overflows 4 px at 1140 px (`-mx-4` scroller), so `page-shell-wide` stays off it.
- [ ] Not migrated: League Recaps story cards / History / Storylines bodies, Live Draft trade evaluator, Draft Center scouting tab, Trade Analyzer multi-team builder, app Trade Analyzer / Finder / History / Draft Center / Live Draft inner sections (only the family strip and dropdowns landed there), app Players position pills (a filter row, not a tab row).
- [ ] Teams (app) has "View" and "Rank by" dropdowns in two places (header and panel); merge into one row when the panels are hoisted.
- [ ] `Hero` for the Games odds and the Live Draft clock (they stay bespoke cards; tests pin their testids).

## Enforcement and verification

- [x] Row rule: `rowRightEdgeProblems` (trailing `list-actions` slot holds at most one control) + source scan that no `PlayerListRow actions={<>...</>}` exists on web or app (`ui/ModuleTemplates.test.tsx`). Number-vs-action mixing is not machine-checkable and stays a review rule.
- [x] `scripts/sim_layout_playwright/module_scan.mjs`: Today, Team, Trades, League at 360 and 390 with fixtures; checks overflow, collapsed-summary length, at most one tablist, module count, height. Result: clean (heights at 390: Today 900, Team 1159, Trades 2046, League 1679 px; one screen is 844).
- [x] Full web vitest (325 files, 2389 tests) green with deps installed by `npm ci`; the failures seen earlier were a stale shared node_modules, not this change. Mobile node tests 775 pass; twin check passes.

## Remains

- [x] Trade idea cards as CompactModules, App family tab strip (see Rollout 3). Still open: League Recaps bodies, app Analyzer / Finder / History / Draft inner sections.
- [ ] Roster rows inside a module truncate long names on a 390 px phone ("T. ..." in the scan); row width inside modules needs a pass.
- [ ] No on-device check of the app screens (tsc, node tests and twin check only).
