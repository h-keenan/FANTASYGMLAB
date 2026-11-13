# Player card system

One props-driven player card for web and the app, so a player looks the same
everywhere. Never a bare "photo + name + number": every variant carries
position, team and a status chip, and tapping opens Player Quick View (PQV).

Files (twins, keep in sync):

| | Web | App |
|---|---|---|
| Model + rules (pure, byte-identical) | `web-next/src/lib/playerCard.ts` | `mobile/src/lib/playerCard.ts` |
| Slot comparison logic (identical) | `web-next/src/lib/lineupSlots.ts` | `mobile/src/lib/lineupSlots.ts` |
| Renderer | `components/PlayerCardKit.tsx` | `components/PlayerCardKit.tsx` |
| Tick number (count-up + green flash) | `components/TickNumber.tsx` | `components/TickNumber.tsx` |
| Matchup comparison | `components/MatchupLineup.tsx` | `components/MatchupLineup.tsx` |

Look: nested liquid glass (the input-glass fill and rim), a 3px left accent in
the position color (`--color-position-*`), cyan win emphasis, existing
`PositionBadge` / `ToneBadge` / `PlayerAvatar` atoms. No new design language.

## Variants

- `compact`: list row. Photo (32), name, position badge, team, status chips,
  1-2 trailing stats (`stats=[{label, value}]`).
- `matchup`: head-to-head row. Photo (40), name, position badge, status chip
  (LIVE / FINAL / UPCOMING / BYE / OUT, plus QUESTIONABLE / DOUBTFUL), game line
  (`@ DAL · ~Q3`, `vs DAL · Final 24-17 W`, `@ NO · Sun 3:25 PM`), live points
  big (count-up, flashes green on increase), "Proj final" with a green/red trend
  arrow against the pre-game projection, a thin game-progress bar, and an
  expandable detail (pre-game projection, points so far, OVR, slot, injury).
  `mirror` faces the numbers toward the center on wide screens; `pulseKey` re-runs
  the "points just changed" pulse; `sideTag` shows YOU / OPP on phones.
- `list`: THE list row (`components/PlayerListRow.tsx`, web + app; pure model in
  `lib/playerListRow.ts`, byte-identical twins). Line 1: position badge, 40px photo
  (32 in `density="compact"`), name (one font size smaller past 18 chars before it
  truncates; a clean seam for the shared `<PlayerName/>`), one status chip only when
  it matters (OUT, Q, ...). Line 2, muted: `TEAM · Age 24 · Bye 7` (the bye is
  ALWAYS shown, warning-colored only inside the next 3 game weeks). Line 3: page
  `tags=[...]` (at most 2, then `+N`) on the left and LABELED stat pills
  (`PROJ 10.8`, `VAL 49`, `ADP 38`, `EDGE ▲6` only when |edge| >= 3) in fixed-width
  slots on the right, so a bare number never appears. `actions` slot for compact
  40-44px icon buttons, `onOpen` for tap-row-to-open, `done` for the optimistic
  "Drafted ✓" slide-out. Injured rows are never dimmed: a red chip plus a dot on the
  photo. Fantasy Sim maps its players onto it through `SimDraftRow` (draft Players /
  Board, rookie draft, Players tab, Waivers) and `SimPlayerLine` (queue, roster,
  bench / lineup pickers, trade rows, inbox), using `simDraftMeta` and
  `simListStats` in `lib/simDraft.ts`.
- `card`: larger tile (photo 56) with the value ring (`OvrGauge`) for rosters and
  grids; up to 3 stats.

Avatar scale tokens: `PLAYER_CARD_AVATAR_SIZE = { compact: 32, matchup: 40, card: 56, list: 40 }`.

## Model rules (lib/playerCard.ts)

- A pre-kickoff `0.0` is never shown as a score: points are only set once the
  player's game started; before that the projection leads ("PROJ").
- Chips: BYE > OUT (out / IR / suspended ...) > LIVE > FINAL > UPCOMING; then
  QUESTIONABLE / DOUBTFUL when not already out.
- Trend: live `projected_final` (or final points) minus the pre-game projection;
  within 1.0 point is flat.
- Game line uses `game_opponent`, `game_is_home`, `game_team_score`,
  `game_opponent_score` (score only once nflverse has a final), kickoff time, and
  an estimated quarter from `game_progress` (wall-clock; there is no live game
  clock in our data, so it is always marked `~`).

## Tap behavior

Web: `PlayerIdentityTrigger` opens PQV (`identity` prop). App: `onPress` calls
`usePlayerQuickView().openPlayer`. In the Matchup planner the tap swaps the player
instead. The "TapForWhy" affordance from the Wave 0 pattern components plugs in as
`trailing` once it lands; the card does not render a bare "?".

## Where each variant should be adopted

| Surface | Variant | Status |
|---|---|---|
| Matchup lineup comparison | `matchup` | done (web + app) |
| Matchup suggested moves (start player) | `compact` | done (web + app) |
| GM Plan injured starters (web) | `compact` | done |
| My Team lineup / bench | `compact` (starters), `card` (grid view) | follow-up |
| Waivers recommendations / targets | `compact` with Proj + Value stats | follow-up |
| Trade builder summary assets | `compact` | follow-up |
| Players list / rankings | `compact` (replaces PlayerRow identity half) | follow-up |
| Dashboard lists (needs attention, opportunities) | `compact` (replaces CompactPlayerModule) | follow-up |
| Fantasy Sim lists (draft Players/Board/Queue, rookie draft, Players, Waivers, roster / bench pickers, trade rows, inbox) | `list` via SimDraftRow / SimPlayerLine | done (web + app) |
| Real app Waivers, Players, My Team roster | `list` (add `tags` for waiver target / trending / hot streak) | follow-up: each page has its own row today (`PlayerRow`, `CompactPlayerModule`); swap them to `PlayerListRow` one page at a time |
| Fantasy Sim headers / chips (`SimPlayerChip` in cards) | `compact` | follow-up |

Rule: new player UI uses this kit; do not hand-roll a photo + name + number row.
