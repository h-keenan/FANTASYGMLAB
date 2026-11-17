# Web / app parity audit (2026-11-17)

Scope: web-next vs the Expo app, every main surface, before the next TestFlight build.
Method: read the render paths of each screen pair, grep labels, gating and empty/error copy, check recent web commits for ones that did not touch `mobile/`. Verified statically only (tsc, node tests, guards); the app cannot be rendered on a device here. Lib twins (`scripts/check_lib_twins.mjs`) and all `scripts/check_*.mjs` guards pass.

Legend: same / differs (P0 owner sees it at once, P1 visible mismatch, P2 minor) / exception (documented, intended). "Fixed" = fixed in this pass.

## Features that shipped web-only today

| Feature | Status |
|---|---|
| Footer hide-on-scroll, tap-to-top, More badge | exception: the app has no site-wide tab footer; navigation is the GM orb and the Sim pill (docs/ui-patterns.md, smart footer rules: "the app's footer does not hide"). `nextFooterScroll` lives in the lib twin for web only. Selection mode is the app's `SelectionActionBar`. |
| NavSheet look (PQV-opacity glass, avatars in search) | same: app sheet is opaque elevated surface and uses `PlayerIdentityRow` avatars. Content comes from the byte-identical `navSheet.ts`. |
| ViewTabs swipe | same (#2056 shipped web + mobile). |
| ADP surfaces | same: `AdpLine`, `RookieAdpBoard`, draft room, quick view. Fixed (P2): the app rookie board is now the same collapsible module with the same summary chips (`rookieBoardSummaryParts` in the `adpPresentation` twin). |
| Trade History rows, track record | same (`TradeSummaryRow`, `TrackRecordModule`, shared chips/lib). |
| "AI · Name" labels | same (`simManagerLabel` twin used in both team sheets). |

## Per surface

| Surface | Result |
|---|---|
| Today | differs P1: module order after Guillotine (web NextSteps before Alerts; app has Waiver suggestions strip and a bigger More group); League Activity Pro-locked in app only. Needs a product decision, not changed. |
| Matchup | same |
| Team | Verified: archetype badge is NOT missing (the app shows `archetype_label`, falling back to `strategy_label`). Fixed (P1): roster basis, the app did not position-order the bench/IR/taxi or the best-ball roster; both now use the `rosterBasis` twin. Open (product question): the app-only "Team Analytics" module (drill-down tiles into Teams / Draft Center / Age) looks deliberate, not accidental. P2 empty copy, Keeper order unchanged. |
| League Rankings | differs P1: web is stacked modules (standings, odds, boards), app is a view switch. Fixed: view switch is now tabs (was a dropdown). Fixed (P1, verified real): the app now has the Standings module (`LeagueStandingsModule`, shared `leagueStandings` twin). |
| Players | Fixed (P1, verified real): the app now has the Roster, Sort by and Stat view filters (shared `playersPresentation` twin) and the Draft picks module. Note: on web Picks is a module under the list, not a view, and the app now matches. P2 placeholder copy. Search fix owned by #2093. |
| Waivers | Fixed: view switch is tabs (was a dropdown). P2 copy/title differences remain. |
| Trades: Finder | Fixed (P0): Free accounts now get the Pro upsell card instead of a silent empty result. Open P1: result/picker order and section headings differ. |
| Trades: Hub | differs P1: app has For You / All trades and the free limit gate, web only the ideas board. |
| Trades: Analyzer | differs P1: Quick Compare mode is app-only. P2 verdict card labels. |
| Trades: History / track record | same; P1 app also appends the shared-trades feed. |
| GM Plan | same (tabs, Pro lock, empty states); P2 locked-body copy. |
| News | differs P2: player-filter header, empty-state copy. |
| Games / Pick'em | same order and tabs; P2 section titles. Fixed (P1, verified real): Season Sim and Pick'em error states now retry. |
| Draft Center | same modules and Pro lock; P2 posture/signal cards are collapsible on web only. |
| Prospects | owned by the prospect-card agent; not audited. |
| Account / Premium | Fixed (P1): Free accounts get an "Upgrade to Pro" row (web: Upgrade to Pro button). Fixed (P2): section order and titles now follow the `accountSections` twin (Identity, Billing, Preferences, ..., Account actions). Paywall hero (trial title, Restore, Skip are app/onboarding exceptions). |
| Onboarding | same (lockstep test, shared copy). |
| Sim Home / Team / Players / League / draft room / player card | same (Players defaults to Waivers on both; weekly chart and PQV share a series). Fixed (P2): all Sim load-error titles now come from the `simErrorCopy` twin ("Could not load ..."). Sim Home loading status text unchanged. |
| Nav menu / sheets | same content; exception: web NavSheet lacks current-row highlight and unread badges, app embeds a league switcher (web uses the header). P2: app `SheetHeader` has no eyebrow prop. |
| Footer | exception (see above). |

## Casing rule

Sentence case for headings, buttons and labels; named product surfaces keep their capitalization. Documented in `docs/ui-patterns.md` (Copy casing and shared copy). Guard: `scripts/check_copy_casing.mjs` (also run by the mobile tests). Fixed the three heading mismatches found: "Choose your plan", "What you want back", "Your roster". The app's other Title Case headings have no web counterpart with the same text, so the guard does not flag them; convert them when each screen is next touched.

## Open work (owner decisions, intentionally not changed)

- Today module order after Guillotine, the app's Waiver suggestions strip, and League Activity Pro-locked in the app only.
- Trade Hub "For You / All" and Analyzer "Quick Compare" are app-only; decide whether web follows.
- My Team: keep or drop the app-only "Team Analytics" module.
- Trades Finder result/picker order and section headings (P1, not touched here).
