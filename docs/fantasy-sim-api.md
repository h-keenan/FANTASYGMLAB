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

---

# Fantasy Sim: the GM Game API (`/v1/sim/games*`)

Status: backend contract for the interactive game described in
`docs/fantasy-sim-game-design.md` (Phase 0 + 1). Same flag (`SIM_ENABLED`), same
isolation rules, same auth as everything above. The world/auto-GM endpoints
(`/v1/sim/worlds*`) are unchanged.

## What the game is
A standalone, turn-based GM game that is NOT tied to a Sleeper league: a
12-team snake startup draft of the whole NFL player pool (QB/RB/WR/TE/K) against
11 AI managers with personas, then a 14-week regular season and a real playoff
bracket, then a season grade. Every week the user sets a lineup, works the
waiver wire, trades with AI teams, and taps Advance. Everything is real rules:
roster slots plus bench (16-man rosters), bye weeks, injuries, standings with
tiebreakers, playoff seeding, waivers that resolve in priority order.

- Season: weeks 1-14 regular season; playoffs weeks 15-17 (6 of 12 teams, seeds
  1-2 get a first-round bye, fixed bracket, higher seed wins a tie). Playoff
  size is 4 for leagues of 8 or fewer teams.
- Starting lineup: `QB RB RB WR WR TE FLEX K` (FLEX = RB/WR/TE) + 8 bench spots.
  Roster limit 16, 14 draft rounds. No DEF/IDP, no IR, no FAAB, no picks as
  assets (those are later phases).
- Scoring presets: `ppr` (default), `half`, `std`.
- Tiebreakers: win pct (tie = half), head-to-head among the tied group, points
  for, then a fixed per-game coin.
- Waivers: claims resolve at Advance, worst record first, AI claims in the same
  order, before that week's games. Cuts are immediate. Trades resolve
  instantly (see Trades). Trade deadline: week 10; none in the playoffs.
- Randomness: a game has one seed. Every draw is keyed by `(seed, week, stream,
  key)`, so reverting a week and re-advancing with the same decisions gives the
  same result, and trade verdicts never change between preview and send.
- Weekly scoring comes from the sim's player model through
  `modules/sim/game_scoring.py` (swappable adapter). Each game records the
  model it was created with and keeps using it, so old saves never change.
- Not tied to the user's real data: the player pool is frozen into the game at
  creation (`sim_games.snapshot`), so a save is stable across `players.db`
  refreshes.

## Storage
`docs/supabase_sim_game.sql` (apply by hand, idempotent): `sim_games`,
`sim_events`, `sim_week_checkpoints`, RLS `auth.uid() = user_id`. Source of
truth is the append-only `sim_events` log over the frozen snapshot; the
checkpoint written at the start of each week is only a cache. Until applied,
endpoints answer `reason: "sim_storage_unavailable"`.

## Conventions
Same as above (bearer auth; not-ready is HTTP 200 with a `reason`; 404 unknown
or other user's game / malformed id; 422 bad input `{"ok": false, "error"}`; 503
`server_busy`), plus:

- Every body carries `"ok"`, `"reason"` (`""` on success), `"is_premium"`,
  `"upsell"` (null unless a paywall reason), and `"preview"`:
  `null` for Pro, else `{"weeks_left": n, "paywall_week": 4, "paywalled": bool}`.
- **Pro gate + free preview.** Pro: up to 3 games. Free: 1 game; the draft and
  advancing weeks 1-3 work; from week 4 every mutating call (advance, lineup,
  waivers, cut, trades, inbox respond, revert) answers 200
  `reason: "premium_required"`, `upsell`, `preview.paywalled: true`. Reads
  (`GET`) always work, so the paused season stays viewable. After upgrading the
  same save resumes at week 4. `weeks_left = max(0, 4 - current_week)` once the
  season started, 3 during the draft.
- HTTP 409 `{"ok": false, "reason": "conflict"}` when two writes raced on the
  same game; reload and retry. Writes are all-or-nothing.
- Ids: game id is a uuid (malformed -> 404); player ids are the strings in the
  player rows; team ids are `"1".."12"`.

### Extra `reason` codes (games)
| reason | meaning |
| --- | --- |
| `premium_required` | Free caller past the preview (or no Pro for a 2nd game: `game_limit_reached`) |
| `game_limit_reached` | 1 game (Free) / 3 games (Pro); body has `max_games` |
| `players_unavailable` | the player pool could not be built |
| `wrong_phase` | e.g. draft call after the draft, lineup call during the draft; body has `phase` |
| `not_your_turn` | `draft/pick` while an AI team is on the clock (cannot normally happen; picks auto-resolve) |
| `player_taken` | player already drafted / rostered |
| `roster_over_limit` | `advance` with more than 16 players; body has `cuts_needed` |
| `trade_deadline_passed` / `trades_closed` | after week 10 / in the playoffs |
| `duplicate_offer` | the same package to the same team already tried this week |
| `partner_trade_limit` | that AI team hit its season trade cap |
| `offer_invalid` | inbox offer no longer valid (players moved, expired) |
| `week_mismatch` | `advance` body `week` is ahead of the game |
| `not_complete` | `GET result` before the season ended |

## Endpoints

### `GET /v1/sim/games/options`
Works for Free callers (no `premium_required`). Setup form + limits.
```json
{"ok": true, "reason": "", "is_premium": false, "upsell": null, "preview": {"weeks_left": 3, "paywall_week": 4, "paywalled": false},
 "engine_version": "game-1.0.0", "max_games": 1,
 "options": {"teams": {"values": [8, 10, 12], "default": 12},
             "scoring": {"values": ["ppr", "half", "std"], "default": "ppr"},
             "difficulty": {"values": ["easy", "normal", "hard"], "default": "normal"},
             "user_slot": {"min": 1, "max": 12, "default": null},
             "auto_lineup": {"default": false}},
 "season": {"regular_weeks": 14, "playoff_weeks": 3, "playoff_teams": 6, "trade_deadline_week": 10,
            "roster_limit": 16, "draft_rounds": 14, "slots": ["QB","RB","RB","WR","WR","TE","FLEX","K"]},
 "personas": [{"id": "contender", "label": "...", "blurb": "..."}]}
```

### `POST /v1/sim/games`
Body (all optional): `{"teams": 12, "scoring": "ppr", "difficulty": "normal", "user_slot": null, "auto_lineup": false, "team_name": "My Team"}`.
Builds the frozen pool, the AI teams (names + personas), the schedule, byes, and
runs AI picks until the user's first turn. `user_slot` null = random (seeded).
Returns `{"game": game, "draft": draft}` (see below). 422 on bad options.

### `GET /v1/sim/games` / `GET /v1/sim/games/{id}`
`{"games": [game_lite], "max_games": n}` / `{"game": game}`. `game_lite` is the
cheap list row: `{id, seed, engine_version, scoring_model, settings, status,
current_week, difficulty, grade_letter, event_count, created_at, updated_at}`
(no standings/roster; open one to get the full `game`).
```jsonc
game = {
  "id": "uuid", "status": "drafting|in_season|playoffs|complete", "week": 4,   // week to be played next (0 while drafting)
  "phase": "draft|regular_season|playoffs|complete", "round": null,             // playoff round of `week` when in playoffs
  "seed": 123, "engine_version": "game-1.0.0", "scoring_model": "...",
  "settings": {teams, scoring, difficulty, regular_weeks, playoff_teams, playoff_weeks, trade_deadline_week, roster_limit, rounds, slots, user_slot, auto_lineup},
  "you": {"team_id": "3", "name": "...", "wins": 2, "losses": 1, "ties": 0, "pf": 301.2, "pa": 280.4, "rank": 4, "seed": null},
  "this_week": {"week": 4, "opponent": {"team_id": "7", "name": "...", "persona_id": "passive"}, "bye": false,
                "your_projection": 121.4, "opponent_projection": 117.9} | null,
  "pending": {"claims": 1, "inbox": 2, "lineup_warnings": 1, "roster_size": 15, "roster_limit": 16, "cuts_needed": 0},
  "can_trade": true, "trade_deadline_week": 10, "grade_letter": null,
  "created_at": "...", "updated_at": "..."
}
```

### Draft
`GET /v1/sim/games/{id}/draft?page=1&page_size=40&pos=&q=` ->
```jsonc
{"draft": {"status": "in_progress|complete", "pick_no": 14, "round": 2, "total_picks": 168,
           "on_the_clock": {"team_id": "3", "name": "...", "is_you": true},
           "your_pick_numbers": [3, 22, ...], "picks_until_you": 0,
           "order": [{"pick_no": 1, "round": 1, "team_id": "5"}, ...],
           "picks": [{"pick_no": 1, "round": 1, "team_id": "5", "player": {player}, "adp": 3.0, "value_over_adp": 2.0, "auto": false}],
           "queue": ["pid"], "your_roster": [player], "teams": [{"team_id","name","persona_id","is_you"}]},
 "available": {"items": [player], "total": 520, "page": 1, "page_size": 40},
 "hint": {"player": player, "why": "Best available for your need: RB"} | null}
```
`POST .../draft/pick` `{"player_id": "..."}` -> `{"picks": [pick, ...] /* yours + every AI pick until your next turn */, "draft": {...same as above without order/picks lists}, "completed": false, "recap": null}`.
When the last pick lands `completed: true`, the game moves to week 1 and
`recap` is `{"picks_value": [...], "teams": [{"team_id","name","grade","starter_projection","best_pick","worst_pick"}], "your_team": {...}}`.
`POST .../draft/auto` (`{}`): auto-picks for you (your queue first, else best
value + need) until the draft ends; same response as the last pick.
`PUT .../draft/queue` `{"player_ids": ["..."]}` (<= 30): saves your queue; used by
auto-pick. (Extra endpoint; not in the design doc table.)
Wrong phase -> `reason: "wrong_phase"`. Both calls also return `game` (the full game object). Retrying a pick that
already landed answers `reason: "player_taken"`; reload the draft.

### Players
`GET .../players?q=&pos=&status=&team=&sort=&page=&page_size=` -> `{"items": [player], "total", "page", "page_size"}`.
`pos`: QB|RB|WR|TE|K. `status`: `available` (free agents), `rostered`, `mine`,
`injured`, `bye`. `team`: roster owner team id. `sort`: `projection` (default),
`value`, `adp`, `age`, `name`, `last_week`, `season`.
```jsonc
player = {"id": "9509", "name": "...", "pos": "RB", "team": "ATL" /* NFL */, "age": 24.0,
          "adp": 3.0, "value": 91.2, "projection": 17.4, "floor": 9.1, "ceiling": 27.7,
          "status": "healthy|out|bye", "out_weeks": 0, "bye_week": 9,
          "owner": {"type": "you|ai|free_agent", "team_id": "3", "name": "..."},
          "last_week": 12.4, "season_points": 51.0, "games": 3, "ppg": 17.0}
```
`projection` is this week's expected points (0 on bye / while out), blended with
his results so far this season.
`GET .../teams/{team_id}` -> `{"team_id", "players": [player]}` (any team's roster with projections; you need it to build offers; extra endpoint).
`GET .../players/{pid}` -> `{"player": player, "weeks": [{"week": 4, "projection": 17.4, "floor", "ceiling", "bye": false, "out": false}], "history": [{"week": 1, "points": 18.2, "stats": {...}|null}], "news": [{"week": 3, "text": "..."}]}`. Unknown pid -> 404.

### Lineup
`GET .../lineup` ->
```jsonc
{"week": 4, "slots": [{"slot": "QB", "player": player|null}, ...],   // in slot order
 "bench": [player], "projected_total": 121.4,
 "warnings": [{"code": "bye|out|empty_slot", "slot": "RB", "player_id": "..."}],
 "roster_size": 15, "roster_limit": 16, "opponent": {...}|null, "locked": false}
```
`PUT .../lineup` `{"slots": [{"slot": "QB", "player_id": "..."|null}, ...]}` (exactly the league's slots, in order; 422 if a player is not on your roster, wrong position for the slot, or duplicated). Bye/injured starters are allowed (they score 0; shown as warnings). Returns the same as GET.
`POST .../lineup/auto` -> best projected legal lineup (bye/out excluded), same body.
Lineups persist week to week; a player who leaves the roster empties his slot.

### Waivers and cuts
`POST .../waivers` `{"add": "pid", "drop": "pid"|null, "start_slot": "RB"|null}` queues a claim (422 if `add` is not a free agent or `drop` is not yours; `drop` may be omitted when there is roster room at resolution). `start_slot` puts him in that lineup slot if the claim wins. Returns `{"claim_id", "claim": {id, add: player, drop: player|null, start_slot}, "claims": [pending claims]}`. `DELETE .../waivers/{claim_id}` cancels one (extra endpoint) and returns `{"claims": [...]}`.
At Advance each claim becomes `ok: true` or `ok: false` with `reason` `taken | drop_not_owned | roster_full` in the recap.
A starter you cut/drop/trade leaves his slot empty; at Advance empty slots are auto-filled with the best healthy bench
player of the right position (listed in the recap's `auto_filled_slots`), else they score 0.
`POST .../cut` `{"player_id": "pid"}` cuts immediately -> `{"roster": [player]}`.

### Trades
`POST .../trades/preview` and `POST .../trades`, body `{"partner": "7", "give": ["pid"], "get": ["pid"]}` (1-3 players per side, no kickers).
```jsonc
{"verdict": {"decision": "accept|counter|decline",
             "reason_code": "fits_need|wants_more_value|needs_position|fair_floor|roster_fit|...",
             "reason": "Needs a RB", "chips": ["needs RB"],
             "counter": {"give": [player], "get": [player]} | null},   // set when decision = counter
 "executed": false, "trade": null}
```
`preview` never changes anything. `trades` returns the same verdict (identical to
the preview: the decision is deterministic from the seed) and, on `accept`,
executes immediately: `executed: true`, `trade: {...}`, plus `roster` and updated
`pending`. A `counter` is a package the AI will accept: send it with `POST
.../trades` to take it. Anti-exploit: AI never takes a loss beyond its persona's
tolerance, repeated identical offers are blocked in a week, per-team season
trade caps, kickers are not tradable. After a roster-size breach you must cut
before advancing.

### Inbox
`GET .../inbox` -> `{"items": [{"id", "type": "trade_offer", "from": {"team_id","name","persona_id"}, "you_give": [player], "you_get": [player], "message": "...", "expires_week": 4}]}`.
AI managers send at most 1 offer each and 3 league-wide per week; unanswered
offers expire on Advance. `POST .../inbox/{item}/respond` `{"action": "accept"|"decline"}` -> `{"ok", "executed": bool, "items": [...]}`; a stale offer answers `reason: "offer_invalid"`.

### Advance and revert
`POST .../advance` (body optional `{"week": 4}`; clients should always send the week they are advancing so a double tap
cannot play two weeks). Validates (roster size), resolves
the week (AI moves, lineups, waivers, scoring, injuries), writes the checkpoint,
returns:
```jsonc
{"recap": {"week": 4, "kind": "regular|playoff", "round": null,
           "your_game": {"opponent_id", "opponent_name", "your_pts", "opp_pts", "result": "win|loss|tie|bye",
                         "starters": [{"slot", "player", "pts", "stats": {...}|null, "flag": "bye|out|null"}],
                         "bench": [...], "optimal_pts": 131.2, "efficiency": 0.93},
           "scores": [{"home", "away", "home_pts", "away_pts", "winner": null|"id"}],
           "standings": [...top rows], "waivers": [{"team_id","name","add":player,"drop":player|null,"ok": true,"reason": ""}],
           "transactions": [...AI trades/drops this week], "injuries": [{"player", "weeks", "team_id", "is_yours"}],
           "mvp": {...}, "bust": {...}, "playoffs": null | {"seeds": [...], "bracket": [...]},
           "season_complete": false, "champion": null, "next_week": 5},
 "also_played": [recap, ...],   // playoff weeks played in the same call once you are out of the bracket
 "replayed": false,             // true when `week` was already played (stored recap returned, nothing written)
 "game": game}
```
Idempotent per `(game, week)`: `week` lower than the game's current week returns
that week's stored recap without advancing; higher -> `reason: "week_mismatch"`.
Playoffs: each advance plays one round; once you are eliminated (or missed) the
remaining rounds are played in the same call and the game completes.
`POST .../revert-week` drops this week's pending decisions (lineup edits, claims,
cuts, trades done and offers answered since the last Advance) back to the start
of the week. No undo across an Advance. -> `{"game": game, "reverted": n}`.

### League and result
`GET .../league` -> `{"standings": [{"rank","team_id","name","owner","is_you","persona_id","wins","losses","ties","pf","pa","streak","seed","playoff_status": "in|out|clinched|..."}], "schedule": [{"week", "kind", "games": [{"home","away","home_pts": null|n,"away_pts": null|n,"winner"}]}], "transactions": [...last 60], "teams": [{"team_id","name","owner","persona": {"id","label","blurb"},"is_you","power_rank","avg_age"}], "playoffs": null | {"seeds": [...], "rounds": [...], "champion": null}}`.
`GET .../result` (when complete; else `reason: "not_complete"`) -> `{"result": {"champion", "final_standings": [...with playoff_result], "grade": {"letter","score","grade_points","components","summary"}, "decisions_that_mattered": [...], "draft": {"grade","picks_value"...}, "user": {...}}}`. Computed once at the end (counterfactual replays) and stored.
`DELETE .../{id}` deletes the game and its events/checkpoints.

### `GET /v1/sim/preview/players` (signed-out)
No auth, no Pro check, no state. `?q=&pos=&sort=&page=&page_size=&scoring=ppr` ->
`{"ok": true, "reason": "", "players": [player-lite], "total", "page", "page_size", "scoring"}` with projection, value, age, NFL team, bye. Cached pool; a plain 404 when the flag is off.
