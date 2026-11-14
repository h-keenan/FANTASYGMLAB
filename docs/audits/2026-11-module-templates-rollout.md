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
- [ ] Idea cards (`TradeIdeaCardView`, app `TradeIdeaCard`) are already tap-to-expand but are bespoke, not CompactModule; Analyzer, Finder, History not migrated.

## League (`/league-rankings`, app `TeamsScreen`)

- [x] Web: Standings and every rank board are `CompactModule`s ("1. Team 1 · You #4 · 8 teams"); Roster Power opens by default; a `#board-x` insight-link hash opens its board; anchors (`id="board-x"`) unchanged.
- [x] App: already one board at a time via the metric segmented control, which is the plan's target. Left as is.
- [ ] Playoff Odds and "Your standing" card are bespoke; Recaps, Games, Draft, Pick'em not migrated.

## Enforcement and verification

- [x] Row rule: `rowRightEdgeProblems` (trailing `list-actions` slot holds at most one control) + source scan that no `PlayerListRow actions={<>...</>}` exists on web or app (`ui/ModuleTemplates.test.tsx`). Number-vs-action mixing is not machine-checkable and stays a review rule.
- [x] `scripts/sim_layout_playwright/module_scan.mjs`: Today, Team, Trades, League at 360 and 390 with fixtures; checks overflow, collapsed-summary length, at most one tablist, module count, height. Result: clean (heights at 390: Today 900, Team 1159, Trades 2046, League 1679 px; one screen is 844).
- [x] Full web vitest (325 files, 2389 tests) green with deps installed by `npm ci`; the failures seen earlier were a stale shared node_modules, not this change. Mobile node tests 775 pass; twin check passes.

## Remains

- [ ] Trade idea cards as CompactModules (Trades page is 2046 px tall with 3 ideas; cards dominate). Analyzer, Finder, History, Matchup, Players, Waivers (control row), GM Plan inner tabs, League Recaps/Games/Draft/Pick'em.
- [ ] App family tab strip: `lib/pageFamilies.ts` has no mobile twin on main, so the app screens cannot show the single family tab row yet.
- [ ] Roster rows inside a module truncate long names on a 390 px phone ("T. ..." in the scan); row width inside modules needs a pass.
- [ ] No on-device check of the app screens (tsc, node tests and twin check only).
