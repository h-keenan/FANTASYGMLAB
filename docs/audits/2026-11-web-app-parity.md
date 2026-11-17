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
| ADP surfaces | same: `AdpLine`, `RookieAdpBoard`, draft room, quick view. P2: app board is a plain list, web a collapsible module with summary chips. |
| Trade History rows, track record | same (`TradeSummaryRow`, `TrackRecordModule`, shared chips/lib). |
| "AI · Name" labels | same (`simManagerLabel` twin used in both team sheets). |

## Per surface

| Surface | Result |
|---|---|
| Today | differs P1: module order after Guillotine (web NextSteps before Alerts; app has Waiver suggestions strip and a bigger More group); League Activity Pro-locked in app only. Needs a product decision, not changed. |
| Matchup | same |
| Team | differs P1: extra "Team Analytics" module and no archetype badge on app; best-ball roster basis. P2 empty copy, Keeper order. Not changed (needs per-field check). |
| League Rankings | differs P1: web is stacked modules (standings, odds, boards), app is a view switch. Fixed: view switch is now tabs (was a dropdown). Open: no Standings section in the app. |
| Players | differs P1: app lacks Roster/Sort/Stat view filters and the Picks view (reported, unverified). P2 placeholder copy. Search fix owned by #2093. |
| Waivers | Fixed: view switch is tabs (was a dropdown). P2 copy/title differences remain. |
| Trades: Finder | Fixed (P0): Free accounts now get the Pro upsell card instead of a silent empty result. Open P1: result/picker order and section headings differ. |
| Trades: Hub | differs P1: app has For You / All trades and the free limit gate, web only the ideas board. |
| Trades: Analyzer | differs P1: Quick Compare mode is app-only. P2 verdict card labels. |
| Trades: History / track record | same; P1 app also appends the shared-trades feed. |
| GM Plan | same (tabs, Pro lock, empty states); P2 locked-body copy. |
| News | differs P2: player-filter header, empty-state copy. |
| Games / Pick'em | same order and tabs; P2 section titles; P1 app error states have no retry (reported). |
| Draft Center | same modules and Pro lock; P2 posture/signal cards are collapsible on web only. |
| Prospects | owned by the prospect-card agent; not audited. |
| Account / Premium | Fixed (P1): Free accounts get an "Upgrade to Pro" row (web: Upgrade to Pro button). P2: section order differs, paywall hero (trial title, Restore, Skip are app/onboarding exceptions). |
| Onboarding | same (lockstep test, shared copy). |
| Sim Home / Team / Players / League / draft room / player card | same (Players defaults to Waivers on both; weekly chart and PQV share a series). P2: error titles differ on about 8 states, Sim Home loading status text. |
| Nav menu / sheets | same content; exception: web NavSheet lacks current-row highlight and unread badges, app embeds a league switcher (web uses the header). P2: app `SheetHeader` has no eyebrow prop. |
| Footer | exception (see above). |

## Open work (not done in this pass)

- P1 Today module order / Waiver strip / League Activity gating: product decision needed.
- P1 League Rankings Standings section in the app.
- P1 Players filters (Roster, Sort, Stat view) and Picks view in the app (verify first).
- P1 Trade Hub "For You / All" and Analyzer "Quick Compare" are app-only; decide whether web follows.
- P1 Games error states: add retry.
- P2 copy and casing alignment (section headings Title Case in app, sentence case on web), Sim error titles, Rookie board summary chips.
