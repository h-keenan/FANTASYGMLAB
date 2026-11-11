# Fantasy Sim API (backend MVP)

Status: backend only. Web/mobile UI is a follow-up. Off by default.

## What it is
Pick one of your real Sleeper leagues, set a strategy, and the sim plays out
the season against AI managers that trade and work the waiver wire, then grades
you and explains the 3-4 decisions that mattered. Single season. No live weekly
interaction: strategy in, result out. Shareable seeds are NOT exposed (the seed
is in the data model and engine so it can be added later).

## Isolation (the hard rule)
- Code lives in `modules/sim/`. Real code never depends on it; the only real
  file that references it is one guarded mount in `services/mobile_api_service.py`.
- Registered only when `SIM_ENABLED` is truthy (`1/true/yes/on`). Flag off: every
  `/v1/sim/*` path is a plain 404 and `modules.sim` is not even imported.
- Reads real data only through `modules/sim/inputs.py` (read-only adapter that
  freezes a snapshot). `data/players.db` is opened `mode=ro`; `rankings.load_players`
  and `build_players_table` are never used.
- Writes only to `sim_worlds`, `sim_snapshots`, `sim_results` (own RLS, no FKs into
  real tables). Apply `docs/supabase_sim.sql` by hand in the Supabase SQL editor.
  Until applied, endpoints answer `reason: "sim_storage_unavailable"`.
- Enforced by `tests/test_sim_isolation.py` (AST import graph, per-file import
  allowlists, engine purity in a clean interpreter, real data files and real
  endpoint output unchanged after a sim run, flag-off 404s) and
  `tests/test_sim_engine.py::test_deterministic_replay_*`.

## Conventions
- All endpoints require the normal bearer token (`Authorization: Bearer <jwt>`).
- Pro-only, gated server-side with the same check as Playoff Odds/Draft Center.
  A Free caller gets HTTP 200:
  `{"ok": true, "reason": "premium_required", "is_premium": false, "upsell": {"title", "body"}}`
  and no sim work runs.
- Not-ready states are HTTP 200 with a `reason` (success has `reason: ""`),
  same as the other league endpoints. Every success body also carries
  `"is_premium": true, "upsell": null`.
- Real errors: 401 (auth), 404 (unknown/other user's world, malformed id),
  422 (bad input, body `{"ok": false, "error": "..."}`), 503 `server_busy`
  (`Retry-After: 5`) when the simulator's own bounded compute pool is full.

### `reason` codes
| reason | meaning |
| --- | --- |
| `""` | success |
| `premium_required` | caller is not Pro |
| `sim_storage_unavailable` | sim_* tables missing or Supabase unreachable |
| `league_unavailable` | Sleeper league/rosters could not be read |
| `team_not_found` | no roster matched the caller's Sleeper username (pass `roster_id`) |
| `season_complete` | `mode: "remaining"` but the regular season is over |
| `players_unavailable` | player valuation table could not be read |
| `invalid_mode` | mode not `remaining`/`full` |
| `world_limit_reached` | 10 worlds per user; delete one first |
| `not_simulated` | `GET .../result` before a run |
| `sim_busy` | (on the 503) compute pool full |

## Strategy object
```json
{
  "posture": "balanced",              // "win_now" | "balanced" | "rebuild"
  "trade_aggressiveness": 0.5,        // 0..1; 0 = auto-GM never trades
  "waiver_aggressiveness": 0.5,       // 0..1; 0 = ignores the wire
  "lineup_auto_set": true,            // false = set-and-forget lineup (sticky), only fixes injuries
  "protected_player_ids": []          // <= 50 ids on your roster; never traded or dropped
}
```
All fields optional (defaults above). Posture sets the win-now vs future
horizon the auto-GM values players with; aggressiveness sets how often it
looks for trades and how thin an edge it accepts.

## Endpoints

### `GET /v1/sim/status`
Options for building the setup UI.
```json
{"ok": true, "reason": "", "is_premium": true, "upsell": null, "enabled": true,
 "engine_version": "sim-1.1.0", "modes": ["remaining", "full"], "max_worlds": 10,
 "strategy_options": {"posture": {"values": [...], "default": "balanced"}, "trade_aggressiveness": {"min": 0, "max": 1, "default": 0.5}, ...},
 "personas": [{"id": "contender", "label": "Contender", "blurb": "..."}, ...]}
```

### `POST /v1/sim/worlds`
Snapshot a real league and create a world (does not simulate).
Body: `{"league_id": "123", "mode": "remaining", "roster_id": "", "strategy": {...}}`
- `mode`: `remaining` (default) keeps the real record and plays the remaining
  regular-season weeks; `full` replays the whole season on today's rosters.
  Offseason / week 1 leagues fall back to `full` (see `notes`).
- Your team is matched by the account's Sleeper username; pass `roster_id` to
  pick another team.
```json
{"ok": true, "reason": "", "is_premium": true, "upsell": null,
 "world": {"id": "uuid", "source_league_id": "123", "league_name": "...", "mode": "remaining",
           "seed": 4611686018427387, "engine_version": "sim-1.1.0", "status": "ready",
           "strategy": {...}, "grade_letter": null, "created_at": "...", "updated_at": "..."},
 "team": {"team_id": "3", "name": "My Team"},
 "notes": ["schedule_estimated_weeks:9,10"]}
```
`notes` are honest caveats about how the snapshot approximates the real league:
`bye_weeks_unavailable` (no complete NFL schedule on hand, so nobody is on bye;
`bye_weeks_not_modeled` on worlds created before engine 1.1.0),
`draft_picks_unavailable` (picks are not traded in this world), `def_idp_slots_not_modeled`, `offseason_full_season`,
`schedule_estimated_weeks:<weeks>`, `projection_fallback_players:<n>`,
`playoff_format_approximated:<why>`, `playoff_reseed_not_modeled`.

### `GET /v1/sim/worlds`
`{"worlds": [world, ...], "max_worlds": 10}`, newest first.

### `GET /v1/sim/worlds/{id}`
`{"world": world}`. 404 for unknown ids and other users' worlds.

### `PUT /v1/sim/worlds/{id}/strategy`
Body: `{"strategy": {...}}`. Replaces the strategy, clears any stored result and
sets status back to `ready`. The seed is unchanged, so the same dice replay
under the new strategy (a fair A/B). Returns `{"world": world}`.

### `POST /v1/sim/worlds/{id}/run`
Simulates the season (about 0.5 s) and stores the result. Idempotent: a world
that already has a result returns it. Returns `{"world": world, "result": result}`.

### `GET /v1/sim/worlds/{id}/result`
Stored result, or `reason: "not_simulated"` with the world.

### `DELETE /v1/sim/worlds/{id}`
Deletes the world, snapshot and result.

## Result object
```jsonc
{
  "engine_version": "sim-1.1.0", "seed": 1234, "mode": "remaining", "start_week": 6,
  "strategy": {...},
  "standings": [  // final regular-season order (seed 1 first)
    {"team_id": "3", "name": "...", "owner": "...", "is_user": true, "persona_id": "you",
     "wins": 9, "losses": 5, "ties": 0, "pf": 1620.4, "pa": 1500.2, "seed": 3,
     "made_playoffs": true,
     "playoff_result": "missed|lost_round_1|lost_round_2|semifinal|runner_up|champion"}
  ],
  "weekly": [{"week": 6, "games": [{"home": "1", "away": "2", "home_pts": 101.2, "away_pts": 98.7}]}],
  "playoffs": [{"round": 1, "week": 15, "games": [{"home","away","home_pts","away_pts","winner"}]}],
  "champion": "team_id",
  "events": [  // transaction log, source of truth for the season
    {"week": 7, "seq": 0, "type": "waiver", "team": "3", "involves_user": true,
     "add": {"player_id","name","pos"}, "drop": {...}|null, "key": "...", "gain": 12.3},
    {"week": 8, "seq": 1, "type": "trade", "team": "3", "partner": "5", "involves_user": true,
     "gives": [asset], "gets": [asset], "initiator_gain": 9.1, "partner_gain": 6.4, "key": "..."},
    {"week": 8, "seq": 2, "type": "drop", "team": "5", "involves_user": false, "player": asset}
  ],
  "personas": [  // scouting report per team
    {"team_id": "5", "name": "...", "is_user": false, "persona_id": "rebuilder",
     "label": "Rebuilder", "blurb": "...", "power_percentile": 0.42, "avg_age": 25.8}
  ],
  "user": {"team_id": "3", "wins": 9, "losses": 5, "ties": 0, "pf": 1620.4, "pa": 1500.2, "seed": 3,
           "playoff_result": "lost_round_2", "made_playoffs": true,
           "lineup_efficiency": 0.91, "expected_wins": 8.1, "games": 9},
  "grade": {
    "letter": "B+", "score": 71.3, "grade_points": 89.2,
    "components": [{"key": "record", "label": "Record and seeding", "score": 80, "weight": 0.35}, ...],
    "summary": {"record": "9-5", "finish": 3, "points_rank": 2, "playoff_result": "lost_round_2",
                "lineup_efficiency": 0.91, "luck_wins": 0.9}
  },
  "decisions_that_mattered": [  // 3-4, largest effect first
    {"kind": "trade|waiver|strategy_trades|strategy_waivers|strategy_lineup", "week": 8,
     "title": "Week 8 trade: sent A, got B",
     "detail": "That deal helped your season (+1 wins, +3.2 points per game, ...).",
     "impact": {"season_value": 1.5, "wins": 1, "points_per_game": 3.2,
                "playoff_result_with": "semifinal", "playoff_result_without": "missed"}}
  ]
}
```
Notes for UI:
- Grade is on a curve (a typical manager is about a C); `score` is the raw
  weighted score, `grade_points` the curved one the letter comes from.
- `decisions_that_mattered` come from counterfactual replays with the same dice
  (one decision removed or flipped). They are single-season what-ifs, not
  probabilities; a decision can "hurt" while showing more wins when it changed
  playoff luck downstream. `season_value` = wins + playoff depth.
- `luck_wins` = actual wins minus all-play expected wins (positive = lucky).
- `playoff_result` for non-playoff teams is `missed`.

## How the simulation works (short)
- Per week: injury + form roll, AI waivers (worst record first), trades, lineups,
  player-level score draws (mean/sd from the projection estimator, 15% shared
  NFL-team correlation), standings; then a single-elimination playoff bracket
  with byes by seed.
- Player means/sd come from `player_projections.baseline_weekly_points` in the
  league's scoring, falling back to table ppg then a value-derived estimate
  (counted in `notes`). Market value is the dynasty value column, normalized.
- Trades: an AI manager proposes when it gains at least its persona's minimum
  (value with a persona horizon/age lens plus lineup-need from the projected
  lineup); the partner accepts when its own gain plus persona noise clears its
  threshold. Max 3 trades per week league-wide, per-team season caps, deadline
  from the league settings, kickers never traded. Seven personas (contender,
  rebuilder, value shark, youth hoarder, position specialist, passive,
  wildcard) assigned deterministically from the seed and team strength/age.
  This follows `trade_offer_analyzer`'s idea (value delta plus roster fit) but
  is its own pure implementation, so nothing real is called or mutated.
- Randomness: `SeedSequence(seed, spawn_key=(week, subsystem, key))` per
  stream, so results never depend on call order. Same snapshot + strategy +
  seed gives a byte-identical result.

## Not in the MVP (by design)
Draft sim, multi-season/aging, draft picks as trade assets, FAAB, IDP/DEF slots,
bye weeks, live weekly interaction, shareable seeds/leaderboards, UI.

## Ops
- Enable with `SIM_ENABLED=1`. Kill switch: unset it and restart.
- At most 2 sim computations at once per worker (own semaphore, 503 beyond
  that); the real admission-control middleware is untouched.
- Retention: `select public.sim_prune_old_worlds();` (90 days idle), manual.

## Bye weeks and draft picks (engine 1.1.0)
- **Byes.** The snapshot freezes each NFL team's bye week from the app's cached
  nflverse schedule, read-only (`data/nfl_games.csv` is never refetched or
  rewritten by the sim). A player on bye scores 0 and is excluded from that
  week's lineup, so the best eligible bench player starts. A set-and-forget
  lineup gets a one-week substitute and the starter returns afterwards. AI
  waiver/trade valuation is season-long and does not look at byes. Teams with no
  single clear bye week are left without one rather than guessed.
- **Picks.** Each team's picks for the next two rookie drafts (rounds from the
  league's `draft_rounds`, default 4) are tradable assets, with real traded
  ownership from Sleeper. Pick assets appear in trade `gives`/`gets` as
  `{"player_id": "pick:2027:1:3", "name": "2027 round 1 pick (via Team X)", "pos": "", "kind": "pick"}`.
  Values come from `modules/sim/picks.py` (the sim's own scale: slot from the
  original team's strength for the next draft, mid-round after that, discounted
  per year). Rebuilders value picks above contenders. Picks have no on-field
  effect in a one-season sim, so the grade does not score their future value; a
  trade that moves one says so in its "decisions that mattered" text.
- Older stored worlds keep their snapshot (no byes/picks) and replay unchanged
  apart from the engine version.
