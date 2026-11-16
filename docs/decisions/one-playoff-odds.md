# One playoff-odds number

Status: decided 2026-11-16 (product owner). Audit refs: P1-4 and P1-5 in
`docs/audits/2026-11-sim-desk-logic-realism-audit.md`.

## Decision

The app has exactly one playoff-odds number per league. It comes from the
Roster-Power Monte Carlo in `modules/playoff_simulator.py`, served through one
service function, `_shared_playoff_odds` (and `_shared_playoff_odds_row`) in
`services/mobile_api_service.py`. The Playoff Odds screen, GM Plan, Dashboard,
the Season Simulator and its what-if, Trade Odds and Season Outlook all read it.
The player-level replay engine (`modules/sim/forecast.py`) no longer produces
odds, record or finish; it only produces swing factors.

## Why this model won

- It is the only one with measured evidence: its win-probability slope is a
  penalized fit against real results, scored on held-out games
  (`modules.projection_calibration.PLAYOFF_SLOPE_*`, Brier 0.2265 to 0.2336
  against 0.2447 to 0.2553 for the old default). The replay forecast has no
  calibration against past seasons in the repo.
- It models the whole league: every team, real tiebreakers, divisions, league
  median games, certified clinch/elimination, title bracket. The replay forecast
  returns the user's team only, is Pro-only, and is behind `SIM_ENABLED`.
- It can answer what-ifs (a roster change shifts Roster Power and the same draw
  is re-run), which Trade Odds and the Season Simulator need.
- It is cheap and already cached per league, lens and 3-hour bucket.

What it gives up: Roster Power is a value total (draft capital, age), not
current-season production with injury and bye noise, so for a dynasty roster it
can over- or under-state this season. The replay model is the more physically
grounded one for "this season", but it is unvalidated and cannot serve the other
surfaces. **The size of the gap between the two on a real league was never
measured (needs a connected league), so this choice rests on measured
calibration plus coverage, not on a head-to-head.** If a backtest later shows the
replay strengths beat Roster Power, the right move is to feed those strengths
into the shared model's `power_scores`, still keeping one number.

## What changed

- One seed (`shared_odds_seed`, crc32 of league, lens, trials and cache bucket)
  draws every odds number. Before, the league table used a per-process
  `hash(...)` seed and the what-if and Trade Odds baselines used a different
  fixed seed, so even those disagreed by Monte Carlo noise. Baselines now are the
  shared result itself and scenarios reuse its seed, so a what-if is a paired
  difference against exactly what the other screens show.
- Season Outlook echoes the shared row for odds, projected record and median
  finish. The old "finals" odds, wins and finish ranges and the finish
  distribution came only from the replays and are removed (web and app).
- Season Outlook uses the `Dynasty` lens (the default of every odds endpoint).

## Swing threshold (P1-5)

The fixed 3-point move threshold sat inside the sampling noise of 20 to 30
replays. A swing is now real only if it is at least 2 standard errors of its own
estimate: the paired standard error of the per-replay difference for waiver and
trade moves, the two-rate standard error for key games. Smaller effects come
back as `small: true` with no number and clients show "Small effect".

## Tests

`tests/test_games.py::test_one_league_one_playoff_odds_number_on_every_surface`
(same league, same number on every surface) and the swing-noise tests in
`tests/test_sim_forecast.py`.
