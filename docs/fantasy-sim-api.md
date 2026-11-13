# Fantasy Sim API (backend MVP)

Status: shipped behind `SIM_ENABLED`. Off by default.

## What it is
Pick one of your real Sleeper leagues, set a strategy, and the sim plays out
the season against AI managers that trade and work the waiver wire, then grades
you and explains the 3-4 decisions that mattered. Single season. No live weekly
interaction: strategy in, result out. Shareable seeds are NOT exposed (the seed
is in the data model and engine so it can be added later).

## Season Outlook forecast (what the apps use)
Season Outlook (GM Plan tab, web `/fantasy-sim/[leagueId]`, app `FantasySim`) is a
one-tap forecast of the user's real league: no strategy, no setup, no storage.
Hands-on play is the GM game (`/v1/sim/games*`); the world endpoints below are
the older auto-GM API and no client calls them any more.

### `GET /v1/sim/forecast?league_id=<id>[&roster_id=<id>]`
Pro-only (Free gets the usual `premium_required` envelope and no sim work runs).
Snapshots the league, replays the rest of the season 48 to 80 times (fewer when many games remain) with the user on
their current roster and an auto-set lineup (no user trades or waiver moves), and
aggregates. Deterministic (fixed seeds); cached in-process for 10 minutes per
user and league. Not-ready reasons: `league_unavailable`, `team_not_found`,
`season_complete`, `players_unavailable`. 503 `server_busy` when the compute pool is full.
```jsonc
{"ok": true, "reason": "", "is_premium": true, "upsell": null,
 "mode": "remaining", "as_of": "2026-11-12T12:00:00+00:00", "notes": ["..."],
 "forecast": {
   "samples": 80, "start_week": 10, "regular_season_end": 14, "weeks_remaining": 5,
   "team": {"team_id": "1", "name": "..."}, "current": {"wins": 5, "losses": 4, "ties": 0},
   "odds": {"playoffs": 0.62, "finals": 0.2, "title": 0.09, "playoff_spots": 6},
   "record": {"wins": 8.6, "losses": 5.4, "wins_low": 7, "wins_high": 10, "projected": "9-5", "games": 14},
   "finish": {"median": 4, "low": 2, "high": 7, "teams": 12, "distribution": [{"finish": 1, "probability": 0.04}, ...]},
   "swing_factors": [  // up to 3, biggest first
     {"kind": "game|waiver|trade", "week": 11, "title": "...", "detail": "...",
      "playoff_delta": 0.35, "title_delta": 0.05, "players": []}
   ]}}
```
`low`/`high` are the 10th/90th percentiles. Swing factors come only from the sim
engine: a key game is the playoff odds conditional on winning vs losing it; a
waiver/trade factor replays the same seeds with the user's auto-GM switched on
and is shown only when the paired gain clears a noise floor.

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
- Tiebreakers (standings and playoff seeding, one rule): win pct (tie = half),
  then the game's `tiebreaker` setting. `points_for` (default, like Sleeper):
  points for, head-to-head among the tied group, fewer points against, then a
  fixed per-game coin. `head_to_head`: head-to-head among the tied group, points
  for, then the coin. The rule is saved in the game's settings; saves from before
  the setting existed load as `head_to_head`, so they replay unchanged.
- Waivers: claims resolve at Advance, worst record first, AI claims in the same
  order, before that week's games. Cuts are immediate. Trades resolve
  instantly (see Trades). Trade deadline: week 10; none in the playoffs.
- Empty starting slots never block Advance. Order inside one Advance: the
  user's claims (and AI claims) resolve first, worst record first, and a
  winning claim with `start_slot` is already in the lineup; then AI lineups are
  set and the user's still-empty slots are auto-filled from the healthy bench;
  then the week is scored. A slot nobody can fill scores 0 (`starters[].flag:
  "empty"`). So a user whose WRs are all hurt can claim a free agent this week
  and have him play this week. The API never rejects Advance for an empty slot
  (only `roster_over_limit`, `drafting`, `offseason`, `complete`), and cuts are
  always allowed, so an over-limit roster is always fixable. Rule (kept
  claims-only, no instant free-agent signing, matching the engine and keeping AI
  teams on the same waiver path): clients warn on an empty slot ("WR2 is empty
  and will score 0 unless a healthy bench player fits. Advance anyway?") with
  shortcuts to the bench / free agents; only an over-limit roster disables
  Advance. No engine behavior changed, so no version gate and old saves replay
  identically.
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

### `GET /v1/sim/games/{id}/home`
Read-only dashboard for the Home tab (in-season and playoffs; `wrong_phase` during the draft and after the season).
Keys: `matchup` (opponent with record/persona, `you_projection`, `opp_projection`, `win_prob`, slot-by-slot `rows`
`{slot, you, opp}` with out/bye players flagged via `status`), `checklist` (set lineup, cuts, waivers, byes, offers; each
with `done`, `severity`, `target` tab), `inbox` (count + up to 3 offers), `waiver_suggestions` (free agents that fix a
hole or upgrade a starter, each with `gain_now`, `gain_ros`, `reasons`, optional `drop`/`covers`), `bye_alerts`
(starters on bye in the next 3 weeks with `covered_by` bench cover or free-agent `replacements`), `injuries`,
`hot_cold` (`hot`, `cold`, `wire`), `standings` (rows, cut line `margin`) and `league` (`recent` moves + a
`spotlight` trade). Everything is derived from the frozen snapshot and state; nothing is written.

### `GET /v1/sim/games/{id}/teams/{team_id}`
Scouting view of any team (yours included): `players` (unchanged), plus `team` (record, persona, power rank),
`lineup` and `projected_total` (an AI team's is the lineup its manager will start), `positions` (league rank and
`strength`/`ok`/`need` level per position), `strengths`, `needs`, `injuries`, `recent` moves, `next_game`, `trade.open`.

### `GET /v1/sim/games/options`
Works for Free callers (no `premium_required`). Setup form + limits. **Quick
start** is every `default` below (12 teams, half-PPR, standard lineup, redraft);
the client hides the rest behind a collapsed "Advanced options".
```json
{"ok": true, "reason": "", "is_premium": false, "upsell": null, "preview": {"weeks_left": 3, "paywall_week": 4, "paywalled": false},
 "engine_version": "game-1.1.0", "max_games": 1,
 "options": {"mode": {"values": ["redraft"], "default": "redraft", "modes": [{"id": "redraft", "label": "Redraft", "available": true}, {"id": "dynasty", "label": "Dynasty", "available": false}]},
             "teams": {"values": [8, 10, 12, 14], "default": 12},
             "scoring": {"values": ["ppr", "half", "std"], "default": "half"},
             "te_premium": {"values": [0.0, 0.5, 1.0], "default": 0.0},
             "superflex": {"default": false}, "include_k": {"default": true}, "include_def": {"default": false}, "tiebreaker": {"values": ["points_for", "head_to_head"], "default": "points_for"},
             "bench": {"min": 4, "max": 10, "default": 8},
             "difficulty": {"values": ["easy", "normal", "hard"], "default": "normal"},
             "user_slot": {"min": 1, "max": 14, "default": null},
             "auto_lineup": {"default": false}},
 "layout": {"base_slots": ["QB","RB","RB","WR","WR","TE","FLEX"], "draft_spare_spots": 2},
 "start_modes": [{"id": "fresh", "available": true}, {"id": "league", "available": true},
                 {"id": "season_start", "available": false, "reason": "no_roster_history"}],
 "season": {"regular_weeks": 14, "playoff_weeks": 3, "playoff_teams": 6, "trade_deadline_week": 10,
            "roster_limit": 16, "draft_rounds": 14, "slots": ["QB","RB","RB","WR","WR","TE","FLEX","K"]},
 "personas": [{"id": "contender", "label": "...", "blurb": "..."}]}
```
Lineup, roster size and draft rounds are **derived** from the toggles (the
client mirrors `derive_layout`): starters = QB, 2 RB, 2 WR, TE, FLEX, plus
SUPER_FLEX / K / DEF when on; roster = starters + `bench`; draft rounds =
roster - 2 (the spots left for the wire). League sizes are even so every team
plays every week. Settings are stored inside the existing `sim_games.settings`
and `snapshot` JSON, so there is no SQL migration for them.

### `POST /v1/sim/games`
Body (all optional): `{"teams": 12, "scoring": "half", "te_premium": 0, "superflex": false, "include_k": true,
"include_def": false, "tiebreaker": "points_for", "bench": 8, "mode": "redraft", "difficulty": "normal", "user_slot": null, "auto_lineup": false,
"team_name": "My Team"}`.
Builds the frozen pool (projected in this league's scoring, TE premium included), the AI
teams (names + personas), the schedule, byes, and runs AI picks until the user's
first turn. `user_slot` null = random (seeded). Returns `{"game": game, "draft": draft}`
(see below). 422 on bad options (odd league size, unknown mode, `dynasty` while unavailable, ...).

**Start from one of my leagues**: `{"start": "league", "league_id": "...", "roster_id": "" , "difficulty": "normal",
"auto_lineup": false, "team_name": ""}`. Reads (read-only, through `RealSimInputs.league_import`) the league's size,
lineup, bench, scoring (full `scoring_settings`) and playoff field plus every team's current roster, freezes them into a
new 14-week season starting in week 1 (no draft): returns `{"game": game}` with `status: "in_season"`. Everything
else in the body (teams, scoring, ...) is ignored: the league decides. `roster_id` is only needed when the Sleeper
username cannot identify the team. Extra `reason` codes: `team_not_found`, `league_unavailable`,
`league_platform_unsupported` (ESPN/Fleaflicker/MFL ids), `league_size_unsupported` (odd or outside 4-16 teams), `league_lineup_unsupported`, `league_scoring_unavailable`,
`def_unavailable` / `k_unavailable` (the league plays one but the pool has none). Rostered players the pool cannot
project (IDP, retired, unmatched) are dropped from their team and counted in the game's notes. IR counts as
roster, taxi does not, and `roster_limit` is raised to the largest roster so nothing has to be cut.

**"Start of this season" rosters** (`start_modes[].id == "season_start"`) are reported unavailable
(`no_roster_history`): we store no per-week roster snapshots, so there is nothing to start from.

Team defenses (`DEF-<NFL team>`) are estimated from points allowed in the cached nflverse schedule
(`def_estimated_from_points_allowed` in the notes); there is no real DEF projection source. K and DEF are
singletons: drafted in the last 3 rounds, never traded.

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
`GET .../result` (when complete; else `reason: "not_complete"`) -> `{"result": {"champion", "final_standings": [...with playoff_result], "grade": {"letter","score","grade_points","components","summary"}, "decisions_that_mattered": [...], "draft": {"grade","picks_value"...}, "user": {...}}}`. Computed once at the end (counterfactual replays) and stored. `result.review` (Season in Review, `modules/sim/game_review.py`, pure and read-only, no replays; results stored before it existed are backfilled on read) carries `awards` (best/worst trade, best waiver pickup, best/worst draft pick, boom, bust, injury cost, each `{key,kind,tone,label,headline,players,delta,detail,outcome}`), `season_stats`, `injuries`, `leaders` (`league` by position, `yours` by stat), `games` (closest yours/league), `rank_journey`, `champion_path`, `your_path`. Every key is optional for clients; decisions also carry `players`.
`DELETE .../{id}` deletes the game and its events/checkpoints.

### `GET /v1/sim/preview/players` (signed-out)
No auth, no Pro check, no state. `?q=&pos=&sort=&page=&page_size=&scoring=ppr` ->
`{"ok": true, "reason": "", "players": [player-lite], "total", "page", "page_size", "scoring"}` with projection, value, age, NFL team, bye. Cached pool; a plain 404 when the flag is off.

## GM game: decisions, internals and ops

Owner decisions this backend implements: 14-week regular season plus a real
playoff bracket; real rules everywhere (slots, bench, byes, waivers, trades,
standings, tiebreakers, seeding); standalone (no Sleeper league, whole NFL pool);
solo against AI teams; 12-team snake startup draft; Pro with a free preview
(draft + weeks 1-3, paywall from week 4, upgrade resumes the same save);
risk-free (nothing real is ever touched) and instant (trades and cuts resolve
immediately, a week advances in well under a second).

Where this differs from or settles the design doc:
- 14 draft rounds, 16-man rosters (so two free spots for waivers), 8 starter slots
  (no DEF/IDP), kickers drafted only in the last three rounds.
- Playoffs: 6 of 12 (4 of 8) with a fixed bracket (no reseed), seeds 1-2 bye.
  Week 17 is the final. No consolation bracket.
- Waiver priority is the standings (worst first), not rolling; user claims and AI
  claims share it. A claim may start the player (`start_slot`).
- Trade acceptance is `value gain + lineup need + persona noise > threshold`
  (convex value, the same idea as the season engine), then a fair-floor check
  so an AI never takes a lopsided loss. Noise is keyed by (seed, week, team),
  never by the offer, so preview == send and re-asking changes nothing.
- AI lineups are optimal by projection (bye/injured out); passive managers
  sometimes carry last week's lineup over. Difficulty only moves AI parameters
  (trade tolerance, waiver activity, lineup lag); the user's dice are identical.
- Projections update during the season: a player's rest-of-season mean blends
  his frozen projection with his actual results (5 games of prior weight), for
  the AI and for the `projection` field alike. The hidden season profile (true
  talent) never leaves the engine.

Internals worth knowing:
- State is a pure fold of `sim_events` (`modules/sim/game_state.py`); resume =
  latest checkpoint + later events, replay = all events; both are tested to be
  byte-identical, including through JSON storage. A week's outcome is a function
  of `(seed, week, state)`; every draw is keyed by `(seed, week, stream, player or
  team)`, so a counterfactual (the "decisions that mattered" replays, one user
  trade/waiver removed) shares every unaffected die.
- Writes are one insert of the whole command's events; `(game_id, seq)` is the
  primary key, so a racing writer gets HTTP 409 `conflict` and nothing is lost.
- `GET result` computes the grade and the counterfactual replays once (about 1-2
  season-sims each, at most 6) under the sim's compute pool and stores them in
  `sim_games.result`.
- Weekly scoring goes through `modules/sim/game_scoring.py`. `player_model`
  (`draw_season_profile` / `draw_week_points`) is used when `modules/sim/player_model.py`
  exists, else a labelled mean/sd fallback. The model id is stored per game
  (`scoring_model`), so swapping models never changes an existing save.

Ops: apply `docs/supabase_sim_game.sql` by hand (idempotent); `select
public.sim_prune_old_games();` deletes games idle 90 days (manual). Flag off
(`SIM_ENABLED` unset) keeps every `/v1/sim/*` path a plain 404.

Event log reference (type: actor): `draft_pick` (user|team), `draft_queue`,
`draft_complete`, `lineup_set` (user|team|engine), `waiver_claim`, `waiver_cancel`,
`waiver_result`, `cut` (user) / `drop` (team), `trade` (user|engine),
`trade_reject`, `trade_counter`, `inbox_offer` (engine), `inbox_response`,
`advance` (user marker), `week_scored`, `injury`, `playoff_seeded`,
`season_complete`, `week_advanced` (carries the recap; closes a week).

## Dynasty mode and IR / taxi squads (game engine 1.2.0)

Everything here is additive: a game made before it (rules < dynasty, no `reserve_v`)
loads, replays and plays exactly as before. No SQL is needed: the new state lives in the
`settings` and `snapshot` JSON columns and in new event types; the `status` column only ever
holds its four existing values (the offseason is stored as `in_season`, the real status is
computed from the event log and returned in `game.status`).

### Setup

`POST /v1/sim/games` accepts `mode: "dynasty"` (it is listed as available in
`GET /games/options`) plus `seasons` (3, 4 or 5; default 5, the initial cap), `rookie_rounds`
(2-5; default 4), `start_year`, and for every mode `ir_slots` (0-4; default 2),
`taxi_slots` (0-8; default 0 in redraft, 4 in dynasty) and `taxi_years` (1-4; default 2:
rookies and second-years). A league import (`start: "league"`) with `mode: "dynasty"` carries the
league's rosters, its real reserve (IR) and taxi squads, the real traded-pick ownership for the next
three rookie drafts, its draft length, scoring, and runs as dynasty; without a mode it is the redraft
import as before, but the real reserve/taxi squads are now kept apart from the active roster.

### Picks as assets

Pick ids are `pick:<year>:<round>:<original team id>`. They can appear in the `give`/`get` lists of
`POST /trades/preview`, `POST /trades`, in inbox offers and in counters; a trade side holds up to 4 assets
in dynasty. `GET /games/{id}/picks` lists every team's picks with value and an early/mid/late slot hint.
A pick row is shaped like a player row with `kind: "pick"`. AI managers value picks by stance
(rebuilders pay up, contenders sell) and the usual veto/fair-floor checks apply.

### Offseason

After the season's last playoff week a dynasty game with seasons left enters `status: "offseason"`:
players are aged one year (position age curves calibrated on the player-model panel;
`python -m modules.sim.calibration.age_curve`), some retire, the incoming rookie class exists.
`GET /games/{id}/offseason` returns the stage (`review` -> `rookie_draft` -> `cutdown`), last season's
archive, retirees, the aging report for your roster, the draft board and the roster check.
`POST /offseason/rookie-draft/start`, `/rookie-draft/pick {player_id}`, `/rookie-draft/auto` and
`POST /offseason/start-season` (refused with `roster_over_limit` until you cut). Trades and cuts are open
in the offseason (not for the current year's picks once the draft is under way). The last season ends in
`status: "complete"`; `GET /games/{id}/dynasty` (and `/result`) return the summary: titles, finish by year.

### IR and taxi

`POST /games/{id}/roster/move {player_id, to: "roster"|"ir"|"taxi"}`. IR takes an injured (out) active
player while a slot is open; the taxi squad takes eligible (rookie / low-experience) players; activating or
promoting needs an open roster spot (`roster_full`). IR and taxi players do not score and do not count toward the
roster limit; they can be traded and cut. `lineup` and `teams/{id}` return `ir[]`, `taxi[]` and a `reserves` block.
Reasons: `ir_full`, `ir_ineligible`, `taxi_full`, `taxi_ineligible`, `roster_full`, `reserves_unavailable`.

## Player detail additions (sheet consistency, rookie scouting)

`GET /v1/sim/games/{id}/players/{pid}` now also returns: `ros` (`mean`, `floor`, `ceiling`, `weeks_left`, `playable_weeks`,
`bye_week`, `out_weeks`), `projection_flat` (every playable week carries the same projection: clients show one
"Rest of season" line, never a week-by-week list), `player.value_rank` / `player.pos_value_rank`, and for generated rookies
`scouting` (see `docs/fantasy-sim-player-model.md` section 8).
