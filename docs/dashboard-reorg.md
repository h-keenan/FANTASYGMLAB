# Dashboard reorganization (trades-first)

Why: coridian_ called the Dashboard "a mess", and the advertising push is
trades around the NFL deadline. The Dashboard must lead to trades and show
what matters this week without scrolling. Same order on web and the app:
`DASHBOARD_MODULE_ORDER` in `web-next/src/lib/dashboardLayout.ts` and
`mobile/src/lib/dashboardLayout.ts` (the block between the SHARED markers is
byte-identical; `mobile/src/lib/dashboardLayout.test.ts` fails if they drift).

## Audit (before)

Web order: Start here, Guillotine, platform notice, Today (lineup/waiver/trade
rows + top-priority cards), 4-tile rank strip, Watchlist and Alerts, League
Activity, Team Snapshot (3 tiles), Guess the Player x2, league type control.

App order: info note, college prompt, push prompt, check-in banner, Start
here, Today, 4-tile rank strip, Watchlist and Alerts, free-limit notes,
Storylines, Waiver suggestions, recap-ready card, Guillotine or Weekly
Matchup, 8-tile Quick Actions, league type control, League Activity, Team
Snapshot (3 tiles), Guess card, standing strips.

Problems found:
- The trade idea was one card among many in "Today", and the trade row
  repeated it (deduped only by headline). Nothing said "Analyze a trade".
- No deadline anywhere, though the server knows `settings.trade_deadline`.
- Team data split in two (rank strip near the top, Team Snapshot near the
  bottom) with two glossary notes.
- App: three stacked prompts and an explanation note above the first card; 8
  Quick Action tiles that duplicate the tab bar; mini-game and standings
  strips mixed with decision modules. Web: Guillotine above everything.
- Quick Actions, mini-games and league type were as prominent as the lineup.

## After

| # | Module | Notes |
|---|--------|-------|
| 1 | Start here | first-run only, dismissible (unchanged) |
| 2 | Now strip | chips: Lineup status, Trade deadline, Alerts to watch, Waivers; each one tap to its fix |
| 3 | Trades | best trade idea (real give/get, value, confidence) + one primary "Analyze a trade" + quiet "More trade ideas" |
| 4 | Next moves | what is left of the week's plan (risk lineup row, waiver row, other top-priority cards, offseason next step) |
| 5 | My Team | rank strip and strength/injury strip merged under one heading, one "Open" link |
| 6 | Watchlist and Alerts (+ waiver suggestions on the app) | news and waivers that affect my players |
| 7 | League Activity | league pulse |
| 8 | More (collapsed) | recap/storylines, weekly matchup, quick actions (app), league type control, mini-games, standings strips; the one-off college and push prompts sit after it |

Guillotine leagues show their card right after My Team (it replaces the
matchup card in More on the app).

## Removed or merged

- Trade row and trade top-priority card no longer repeat in Next moves; a
  "lineup set" row moves into the Now strip (a risk lineup row stays as an
  action). Source: `nextMoveRowFilter`, `isTradeItem`.
- Two team strips merged into one My Team section; the duplicate glossary
  note is gone on web (one button).
- App: info note only for beginners and only under More; prompts moved below
  the content; check-in banner moved next to the alerts it refers to.
- Mini-games, league type, Quick Actions and standings strips collapsed.

## Deadline

The deadline is a Sleeper week number, not a date. The dashboard response now
carries `trade_window` (`modules.league_calendar.trade_window`, additive). The
chip shows "N wks left (Wk X)" from the real current week, turns red at one
week or less, and is omitted when the league has no deadline, it has passed,
or the server did not send it. After the deadline the Trades block says
trades reopen after the season and hides the board link.

## Tiers

`experience_tier` (new_to_fantasy/beginner => guided; advanced/unset =>
veteran) and `goal` (win_now/rebuilding/exploring) from PR #1556 control copy
only. Guided users get a short explainer under Trades (plus a one-line goal
note), the existing rank term help, and the app info note. Veterans get the
call and the numbers only.

## States

Trades: skeleton while the progressive first pass has no verdict; one line of
plain text when no idea stands out (or the engine's hold reason); closed after
the deadline. Now strip and sections render nothing when there is no real
data. The app keeps its full-page loading and error states.

## Known limits

- Trades shows the one idea the dashboard engine produces (cap is 3 if it ever
  returns more); the full board is one tap away.
- Visual QA at 390px was not done (no simulator/browser). Tests are
  structural: order, deadline logic, tiers, shared-constant sync.
