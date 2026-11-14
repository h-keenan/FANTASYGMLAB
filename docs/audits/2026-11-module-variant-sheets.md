# Module variant sheets (2026-11-14)

Side-by-side design options for the shared modules, in the format used for the footer pick:
390px frames, three genuinely different variants per topic (V1/V2/V3), COMPACT and EXPANDED
state each, tap behaviour in words, data density, and a recommendation. Docs and mockups only;
no product code changes. Tokens are copied from `web-next/src/app/globals.css` (liquid-glass dark,
cyan accent, gold highlight); no new colours.

Related: `2026-11-cross-product-module-audit.md`, `2026-11-universal-modules-audit.md`,
`2026-11-ia-mockups.html`, `docs/ui-patterns.md`.

## Sheets (HTML sources, self-contained; open in a browser at 1290px wide)

| Sheet | Topics | Source |
|---|---|---|
| 1/4 | Player row/card (FantasyDesk + Fantasy Sim), PQV sheet header and tabs | `module-variants/sheet-1-players.html` |
| 2/4 | Hero + compact module stack (Today, Team, Sim Home), stat strip | `module-variants/sheet-2-stacks.html` |
| 3/4 | Trade card (idea/offer/inbox), waivers add row, standings/rankings row | `module-variants/sheet-3-trades-waivers-standings.html` |
| 4/4 | Matchup hero, Sim draft clock, recap carousel page | `module-variants/sheet-4-matchup-draft-recap.html` |

PNG renders (2x) are for Discord and are intentionally not committed.
Render: `Google Chrome --headless=new --force-device-scale-factor=2 --window-size=1340,<h> --screenshot=out.png file.html`.

## Recommendations at a glance

| Topic | Pick | Why (short) | Shared FD / Sim |
|---|---|---|---|
| 1a Player row | V2 aligned stat columns | comparable down a list; most facts collapsed | one PlayerRow, column config (FD PROJ/VAL/TRD, Sim GRD/ADP/PROJ) |
| 1b PQV sheet | V2 peek sheet + pill tabs | keeps list context; reuses the one tab row | same sheet; Sim swaps ring for grade |
| 2 Hero + stack | V1 hero + accordion stack | matches shipped Sim CompactModule; sentences carry the why | Hero + CompactModule[] contract |
| 3 Stat strip | V2 one divided strip | one row, expands to rank bars | one StatStrip |
| 4 Trades | V3 row with fairness meter | inbox triage; reasoning on expand | one TradeRow |
| 5 Waivers/standings | V2 bar rows | relative gap at a glance | one RankRow |
| 6 Matchup | V3 ticker on stacks, V1 on Matchup page | page-appropriate hero | one MatchupModule |
| 7a Draft clock | V1 pinned bar | shipped shape, least churn | one DraftClock, different feeds |
| 7b Recap page | V2 card with 3 stat rows | same card language, comparable facts | one RecapPage template |

Each sheet states data density per variant and the sharing plan in full. Data in the mockups
(players, scores, probabilities) is illustrative.
