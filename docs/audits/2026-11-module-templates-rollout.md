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
| "Your team right now" (TeamStatusHero) | matchup + lineup + standing + rooms in one card | [ ] bespoke, remains. Next: Hero (win chance + lineup line) + CompactModules for Standing and Position rooms; needs its 9 detail assertions rewritten on both platforms |
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

## Remains (not done in this PR)

- [ ] Trades family (Hub idea rows to sheets, Analyzer, Finder, History), League family (Standings, Recaps, Draft, Pick'em), Matchup, Players, Waivers (control row), GM Plan inner tabs: still bespoke; each is one page per PR on the same templates.
- [ ] TeamStatusHero rework (above).
- [ ] App family tab strip: `lib/pageFamilies.ts` has no mobile twin on main, so the app screens cannot show the single family tab row yet. Add the twin + `SegmentedTabBar` strip, then the app Team page has its one tab row.
- [ ] Row template: `PlayerListRow` right-edge rule (R4 "one action or number") is not yet enforced by a test.
- [ ] Playwright 390px height/overflow scan of Today and Team (no browser verification was done; static: tsc, vitest, twin check).
