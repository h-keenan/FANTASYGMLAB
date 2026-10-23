# UI consistency audit, 2026-10 (web-next, phone 390px + desktop 1280px)

Method: headless Chromium (Playwright) against `next dev` with a mocked API
(type-generated sample league, so long "Sample text value" strings appear in
screenshots; those are fixture artifacts, not product copy). Every route was
captured at 390px (iPhone UA, 2x) and the main routes at 1280px, with
automatic checks for horizontal overflow, clipped/truncated text, tap targets
under 40px and input font size. Screenshots live in the (uncommitted) harness
dir `/private/tmp/claude-501/-Users-turbo-dev-FANTASYGMLAB/deb66d78-91dd-4a35-a695-410d86619e13/scratchpad/uiaudit/`
(`a390-<route>-390.png` before, `f390-*` after, `d1280-*` desktop, `m1/m2/m3.png`
and `dA/dB/dC.png` contact sheets). Standards checked: the 11 owner decisions
in `docs/ui-module-inventory.md` section 0.

Severity: H = breaks a standard or accessibility, M = visible inconsistency,
L = polish. "Fixed" = changed in this PR.

## Summary table

| Area | Finding | Sev | Status |
|---|---|---|---|
| All primary buttons, light theme | Dark ink (#0b1220) on deep teal (#08616e) is about 2.7:1 contrast (Subscribe, Manage Billing, Load my leagues, sign-in, age gate, onboarding). Mobile already uses white `onAccent` in light theme | H | Fixed (`--color-on-accent`) |
| Header (31 routes) | MENU, league chip, lens chip were 38px tall | M | Fixed (44px, `--touch-target-min`) |
| `Button` (shared) | `sm` buttons rendered 30 to 36px tall | M | Fixed (min 44px) |
| My Team rows | "Open <player>" chevron was 24x24 | M | Fixed |
| Player Compare | Bare red text, no next step | M | Fixed (`EmptyState` + Browse players) |
| Live Draft, League Recaps | Bare muted paragraph empty state | M | Fixed (`EmptyState`; Recaps has Open History) |
| Position badge | Known pending redesign; only listed (see below) | n/a | Not touched |
| Many pages | One-off primary button copies (SignInForm x3, AgeGate, SleeperImportForm, EspnImportForm x2, EspnUnavailableState, OnboardingPaywall, PremiumContent, ThisWeekStrip, error.tsx, not-found.tsx, `.onboarding-next`) instead of `Button` | M | Partly: ink now tokenized; migrate to `Button` is follow-up |
| Player Profile | Stat tile row: Value/Usage tiles uneven widths, long text overflows page (document 442px wide on 390 viewport) | M | Open |
| Players list | Row wraps to two lines; Compare / Add to Trade are about 30px tall; "PLAYERS/PICKS" tab bar does not fill width unlike My Team/Waivers/Recaps | M | Open |
| Players filters | Selects wrap unevenly ("Any roster status" orphaned) at 390 and 1280 | L | Open |
| Draft Center | Pick values show a bare "R4" plate, not the "R1 #3" plate (decision 4) | M | Open (needs pick number in payload) |
| Trade Hub / Rankings | Pick plate text overflows its box with long labels (45px content in 34px plate) | L | Open |
| Account, Premium | "Manage Billing" uses the gold premium fill, not primary cyan | L | Owner decision |
| Connect League | Segmented control (Sleeper/ESPN/Flea/MFL) wraps into two uneven rows | M | Open |
| GM Plan (desktop) | "Plan Snapshot" single tile sits half-width with empty right half; Waivers stat chips same | L | Open |
| Matchup | Own row/tile styles (known, being redesigned separately) | L | Open |
| Footer links ("FantasyCalc", "Full analysis", "View all", Upgrade) | 15 to 20px tall inline links | L | Open |
| Hard-coded colors | None in components except AlertsDropdown (1 rgba) and `shareCard` tokens (intentional) | L | OK |
| Overflow | No horizontal page overflow on any route except Player Profile (above) | n/a | OK |

## Per page (390px unless noted)

- **Landing / Sign-in**: no overflow. One wide decorative div (off-screen by design). Three copied primary buttons in SignInForm (now readable, still not `Button`). Sev L.
- **Dashboard** (`a390-dashboard-390.png`): StatStrip tiles even; section titles uppercase and tight. "Upgrade" link 20px tall; "View All" 20px. Premium upsell card uses the gold tone (consistent with other upsells). Watchlist rows use the shared tags. Sev L.
- **My Team** (`a390-myteam-390.png`): position badges (QB/RB/WR/TE) used in Team Analysis rows and roster rows. Snapshot tiles wrap 3+2 with a half-empty last row (same on desktop). Chevron tap target fixed. Sev L/M.
- **Matchup**: tiles even; hero uses its own card; "Edit lineup" 30px. Sev L.
- **Waivers**: uses shared tabs, `AccentCard`; "View details" 36px (fixed by Button). Position badges in rows. Sev L.
- **Trade Hub / Finder / Analyzer / History**: tab bar OK; pick plates overflow with long labels; "Analyze Trade" and "Find Realistic Trades" 36px (fixed). Position badges in exchange rows. Sev L/M.
- **GM Plan**: Team Situation card heading is large uppercase with the help link wrapping beside it; "View all" 16px. Sev L.
- **Players**: see summary (row wrap, tab bar width, selects). Position badges per row. Sev M.
- **Player Profile + Quick View**: overflow (M). Tile row uneven. Position badge in hero.
- **League Rankings (+ manager sheet)**: long names clip correctly; pick plate overflow only with long labels. Sev L.
- **Playoff Odds / Percentile Explorer**: reachable only via GM Plan and profile; no layout deviations seen at 390 beyond tap-size items.
- **Alerts**: renders list when linked; unlinked state is a bare paragraph (`lib/alertsPresentation.ts` `linkAccount`), not an `EmptyState` with a next step. Sev M, open (needs a destination decision).
- **Portfolio / Live Draft / Recaps / Compare**: empty states now `EmptyState` (Portfolio free state is an upsell card, consistent).
- **Draft Center / College Scouting**: College Scouting is the reference empty/card style. Draft Center plate issue above.
- **Community / News / Trade History**: community has 27 small controls (reaction chips under 40px). Sev M, open.
- **Premium / Account / More**: contrast fix; gold Manage Billing noted.
- **Connect League / onboarding**: segmented control wrap (M).
- **Error / not-found**: use primary ink token now; no retry on not-found by design.
- **Desktop 1280 spot check**: no card stretched to a sibling's height found on Dashboard, My Team, Trade Hub, Waivers, Matchup, GM Plan, Players, Account, Premium. Half-empty rows: My Team snapshot (3+2), GM Plan Plan Snapshot (one tile), Waivers stat chips. Premium plans grid leaves a 2-card second row. Sev L.

## Position badge usage (redesign pending, untouched)

`PositionBadge` (single shared component) renders in: PlayerRow/PlayerIdentity
(Players, My Team, Waivers, Dashboard watchlist, Trade Hub/Finder exchange
rows, College Scouting, News), My Team Team Analysis rows, Matchup position
edges, Player Profile hero, Draft Center signals.

## Fixed in this PR

- `--color-on-accent` token (dark in dark theme, white in light theme, mirrors mobile `colors.onAccent`); `Button` and every one-off primary button now use it.
- 44px tap targets: Header chips and MENU, `Button`, My Team row chevron.
- `EmptyState` adopted in Player Compare, Live Draft, League Recaps.
- Tests: `SharedModules.test.tsx` updated and extended. Mobile already had the equivalents (`onAccent`, `EmptyState`), so no mobile change was needed.

## Remaining

Player Profile overflow, Players row/tab bar, Draft Center `R# #n` plate, Connect League segmented wrap, Alerts unlinked state, Community chip sizes, migrating the one-off primary buttons to `Button`, Manage Billing color decision.
