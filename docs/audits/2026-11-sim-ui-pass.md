# Fantasy Sim UI pass (2026-11-14)

Trigger: coridian_ over the day: sim pages "visually dead", modules that say nothing collapsed, bespoke components, "we need to find an
identity". Method: `scripts/sim_layout_playwright/sim_ui_pass.mjs` (full-page 390px screenshots of every reachable sim screen on the
`simmock.mjs` fixtures, with page height and overflow) plus `pqv_sheet.mjs` for the player sheet. Screenshots were deleted after reading.
The mock has no offseason / dynasty or draft-recap payload, so those screens were audited from code only (marked "code").

Template rules: `docs/ui-patterns.md` (Module templates, CompactModule, Visual identity, PlayerBadge, Row anatomy, TrendChart). Legend:
[x] fixed in this PR (web + app), [ ] remains.

## Defects found, by screen (390px)

| Screen | Defect | Status |
|---|---|---|
| Hub, "Your games" row | one line ("Week 4 of 14") + "12 teams - PPR - Normal" and a bare "Continue" word: nothing about phase, progress or recency; 96px of dead card | [x] `SavedGameCard`: phase glyph, title, phase/grade chip, season progress bar (weeks played of regular + playoff), setup, "Played 2d ago", Continue. Pure model `lib/simHub.ts` (twin, tested) |
| Home | modules are already CompactModules with summaries; lineup problem is said four times (chip, matchup warning, checklist, Set lineup button) | [ ] left: each is a different entry point; dedupe belongs with the Home "needs attention" rework |
| Team tab | week card is a bespoke AccentCard; Lineup and Bench are bare headers (not collapsible, no summary), 2368px tall | [x] week is a `Hero` (projection big, opponent + matchup line as context); Lineup and Bench are `CompactModule`s ("8 starters - proj 121.4 - 1 issue", "8 bench - 16/16 spots - WR5 RB2 - 2 on bye"), Auto-set is the module's one action. `simLineupParts`, `simBenchParts` |
| Standings (League) | a plain table, no answer to "where am I?" | [x] `Hero` "Your standing": `#3`, record, rank in points, games clear of / back of the cut. `simStandingHero` (no trend line: the league payload has no rank history) |
| Scores / Feed | fine (rise + sweep already, shared cards) | [ ] none |
| Teams / Players (League) | long lists, rows are shared | [ ] none |
| Trades: Inbox | cards are expanded/collapsed per offer, fine | [ ] none |
| Trades: Make an offer (partner picker) | 12 team cards at about 185px, each a stack of three player rows (2223px page) | [x] `SimTeamCard dense`: the top assets run in one wrapping strip (position, surname, OVR); each card loses two of its three rows (not re-measured in a browser) |
| Game menu (More) | three bare headings ("This week", "League rules", "Game") over prose cards, no season context | [x] `Hero` "Your season" (Week 4 of 14, record, rank, scoring, difficulty) + `CompactModule`s with summaries (`simMenuHero`, `simRulesParts`) |
| Final / season review | "Champion path" and "Standings journey" collapse to a title and a "+": empty headers; the other sections were `Collapsible` (bespoke) | [x] every review section is a `CompactModule` with a real summary: "2-0 after a bye - 3 rounds - Zach (you), the #2 seed", "#5 -> #2 - Peak #1 - Low #5 - 14 weeks", "3 items - Week 5 trade ... - +1 W". `reviewSectionParts` (twin, tested); shared with the real-league season review |
| Player sheet header | **showed a "Value / No market value yet" tile and a "Usage" tile in the sim** (breaks the no-"Value" rule) and the beginner help said "What do Value, Overall and Tier mean?" | [x] sim hero tiles: This week (projection, or Out / Bye) and ADP (with the gap to the sim); help copy drops Value |
| Player sheet Outlook | week 1: one line "Rest of season: 26.0 ppg" and no chart (a flat projection drew nothing) | [x] four tiles (Per game, Range, Games left, Availability) + the weekly chart always draws (steady mean line with floor/ceiling band, bye and out weeks are gaps, actual points join it as they are played); loading/empty/error use `SkeletonRows` / `EmptyState` |
| Player sheet Scouting | only generated rookies had anything | [x] every other player gets a "Scouting read" section in Overview (age phase for his position, steadiness, ADP vs sim, production). Built only from fields the game sends; no value. A sixth tab was rejected (the tab strip already overflows at 390px) |
| Draft room | done earlier (CompactModule, mini board) | [ ] none |
| Draft recap, offseason, dynasty setup (code) | recap/offseason already on CompactModule/Hero from the earlier pass | [ ] not re-audited visually: no fixture |
| Chrome-wide | none new: bottom bar and orb unchanged | |

## Shared pieces added

- `SimProgressBar` (web + app `SimGameParts`): the one thin progress bar (hub row; the Home checklist still has its own copy, to migrate).
- Lib twins (byte-identical, `check_lib_twins.mjs`): `simHub.ts` (new), `simPlayerSheet.ts`, `simSummaries.ts`, `simReview.ts` (additions).
- `PlayerHeroHeader` / app `PlayerHero` take `simTiles`; `SimPqvSections.heroTiles` feeds it.

## Measurements (390px, mock, from the harness)

Hub saved-game row: about 65 -> 75px, carrying 6 facts instead of 3. Team tab page: 2233 -> 2368px (the hero is new; collapsing Bench
saves roughly 650px). League standings page: 962 -> 1074px (the hero). Final page: 1561 -> 1610px, three sections that were empty
headers now carry a summary. The partner picker, Game menu and player sheet were not re-measured after the change.

## Remains

- [ ] Home: lineup issue stated four times; the checklist progress bar is hand-rolled (use `SimProgressBar`).
- [ ] Team tab slot rows: "Bye 10" wraps under the name at 390px (row width inside a module); IR/taxi groups not re-shot (no fixture).
- [ ] Draft recap, offseason and dynasty screens need a fixture in `simmock.mjs` to audit visually.
- [ ] Trade builder forms (give/get summaries, verdict card) and the offers views were not restructured, only the partner picker.
- [ ] The app was checked with tsc, lint and node tests only; no on-device pass.
- [ ] League Teams / Players views are long uncollapsed lists (shared rows, so no new component, but no summaries per team).
