# Fantasy Sim: the GM Game - Design and Scope (draft, 2026-11-12)

Design only. No code in this PR. Supersedes the "mock season on a real league"
framing in `docs/fantasy-sim-scope.md` for the interactive product; the
existing auto-GM season sim (`docs/fantasy-sim-api.md`, `modules/sim/`) stays as
is and becomes the engine core.

## TLDR
- A standalone, turn-based GM game: draft -> 14-week season + playoffs ->
  final grade. The user makes every decision each week, then taps "Advance".
- Not tied to a real league or Sleeper login. Lives in the portfolio-level
  menu next to tools that work signed out.
- Recommended engine: **simulated stats** (player-level draws from the
  projection mean/sd, which `modules/sim` already does), not real historical
  stats. Real-season replay is a later, separate mode.
- Recommended MVP: one season, 12-team snake startup draft, standard roster,
  AI managers with personas, weekly lineup/waiver/cut/trade. Pro-gated, with a
  free draft + 3-week preview.
- Everything is an event log over a frozen snapshot, so saves resume exactly and
  replays are byte-identical. Isolation rules from the existing sim carry over
  unchanged.
- Rough size: MVP about 5-6 weeks of one engineer (backend 2.5, web+mobile
  UI 3). Storylines and multi-season are later phases.

## 1. Product loop

```
New game -> Draft -> [ Week N: decide -> Advance -> results ] x14 -> Playoffs -> Season grade -> New game
```

Each week the user can, in any order, with no time limit:
1. Set the lineup (or tap "Auto-set").
2. Waiver pickups / drops, and cut players (roster limit forces cuts).
3. Propose trades to any AI team; respond to AI proposals (incoming offers).
4. Browse and search every player (projection, value, news, schedule).
5. Read the matchup preview and league inbox.
Then "Advance week": the engine resolves AI moves, lineups, scoring, injuries,
and shows a recap (score, box of your starters, standings, what AI teams did).

Why it is a game and not a tool: stakes (a season grade, a trophy case), no
real-league risk, and each week has a legible decision with visible feedback.

## 2. Screens (phone-first; web is the same layout widened)

| Screen | Purpose |
| --- | --- |
| Sim hub (menu entry) | Continue save, new game, past seasons, free-preview badge |
| New game setup | Teams (8/10/12), scoring (PPR/half/std), seed (hidden by default), difficulty |
| Draft room | Board (available by ADP/value), your picks, queue, auto-pick toggle, tick timer is cosmetic only |
| Team (home) | Lineup slots, bench, "Auto-set", injury/bye flags, projected points |
| Players | Full searchable table: pos filter, projection, value, age, team, status, owner (you/AI/free agent) |
| Player detail | Weekly projection + band, schedule, news, add/drop/trade buttons |
| Waivers | Free agents sorted by projected gain for YOUR lineup, drop picker |
| Trades | Pick a team (persona scouting report) -> build offer -> verdict preview -> send; inbox of AI offers |
| League | Standings, schedule, scores, transactions feed, power ranks |
| Week recap | Result, MVP/bust, what changed, "decisions that mattered" so far |
| Season summary | Grade, record, finish, decisions that mattered (reuse existing counterfactual output) |
| Storylines (Phase 3) | Inbox of player/news events with choices |

Navigation: bottom tabs on phone (Team, Players, Trades, League, More). The
persistent "Advance week" button lives in the header of Team and League. Reuse
the existing shared components and tokens (player row, position badge, verdict
chips) per the global UI consistency rule; do not build sim-only lookalikes.
Web parity ships with mobile in the same brief.

## 3. State model and saves

Principle: **append-only event log over a frozen snapshot**; current state is a
fold of the log. This already matches `sim_worlds`/`sim_snapshots`.

Persisted:
- `sim_games` (new; or `sim_worlds` with `kind='game'`): id, user_id, seed,
  engine_version, settings (teams, scoring, roster slots, weeks), status
  (`drafting|in_season|playoffs|complete`), current_week, difficulty,
  created/updated.
- `sim_snapshots`: the frozen player pool (id, pos, team, age, value, ADP,
  weekly mean/sd, bye week) copied at game creation. Never refreshed, so a
  save is stable across `players.db` refreshes.
- `sim_events` (new): game_id, week, seq, actor (user|team_id|engine), type
  (`draft_pick|lineup_set|add|drop|trade_offer|trade_accept|trade_reject|injury|score|storyline`), payload jsonb.
- `sim_week_checkpoints` (new): game_id, week, folded state (rosters,
  standings, injuries) so resume does not replay from week 0. Written at each
  Advance. Events remain the source of truth; checkpoint is a cache and can be
  rebuilt.
- `sim_results`: final standings, grade, decisions (existing).

Resume: load latest checkpoint + events after it. Undo: only "revert to
start of this week" (drop events of the current week); no undo across an
Advance (prevents save-scumming; see section 9). Cap: 3 active games per user,
retention via existing `sim_prune_old_worlds` extended to games.

Anonymous users: a game belongs to a `user_id`. Signed-out preview uses a
device-local game (client holds the event log, runs against a read-only
`/v1/sim/preview` call) and offers to claim it on sign-up. Decision: see Open
Questions.

## 4. Draft engine

Recommendation: **startup snake draft of the whole NFL player pool** for the
MVP (not a rookie draft). It is the natural "start of a GM game", needs no
prior roster, and the existing sim valuation scale covers it. Rookie drafts
arrive with multi-season (Phase 4) and reuse `modules/sim/picks.py`.

- Format: 12 teams default, 14 rounds, snake; user slot random or chosen.
  Linear/auction later.
- Board: each player has `adp` (from the frozen valuation snapshot; consensus
  ADP where available, else rank by value-in-league-format) and a `value`.
- AI pick model (per team, per pick): score = `value_norm` blended with
  `roster_need` (starter slots unfilled, position scarcity, bench depth cap) and
  persona bias, then **sample** from the top-K (K=4-6) with softmax noise
  seeded by `(seed, round, pick)`. Hard rules: no K/DST before the late
  rounds, QB cap 3, never leave a starter slot empty by the last round. This
  gives realistic reaches/falls instead of everyone picking exact ADP.
- Persona effects: Contender takes proven vets, Rebuilder/Youth Hoarder takes
  under-24, Specialist over-drafts one position, Passive follows ADP closely,
  Wildcard has high K and noise.
- User tools: queue, auto-pick, "best available for my need" hint (reuse the
  `draft_assistant` need ideas through the inputs adapter), undo only the last
  pick before the next AI pick resolves.
- Output: a draft recap with per-pick value over ADP, team grades (cheap,
  value-based) shown at the end.

## 5. Weekly engine: simulated stats vs real historical stats

| | Simulated (draw from mean/sd) | Real historical replay (e.g. 2025 weekly) |
| --- | --- | --- |
| Realism of outcomes | Plausible, no true boom weeks tied to real games | Real, recognizable ("Week 7 Kelce goes off") |
| Replayability | High: new seed, new season | Low: memorizable, spoilers, one fixed season per year |
| Fairness/skill | Skill = decisions under uncertainty | Lookup-able; value rankings leak the future |
| Draft/ADP consistency | Pool and ADP are current-year, consistent | Requires pool and ADP from that past year, not what we have live |
| Data need | Already have it (projections, sd, byes) | Need clean weekly stats store, past-year ADP, past-year injuries; licensing/ToS risk is low but data work is real |
| Reuse | `modules/sim` engine as-is | New scoring path |
| Determinism | Seeded draws | Fully deterministic |

**Recommendation: simulated stats.** It reuses the proven engine, keeps ADP and
projections current and consistent, and makes decisions meaningful rather than
lookup. To address "it feels fake": add a shared NFL-team/game-script
correlation (already 15% in the engine), injuries with realistic durations,
hot/cold streaks that move a player's mean within the game (sim-local), and
bye weeks. Add **Replay 2025 mode** in Phase 4 as an alternate mode using a
historical dataset, labeled "classic", with the future-leak caveat shown.

Season shape: 14 regular-season weeks + 3 playoff weeks (default; configurable
to the 17-week NFL calendar later).

## 6. AI team behavior

All AI behavior reuses the existing persona system (contender, rebuilder, value
shark, youth hoarder, position specialist, passive, wildcard); it is already
deterministic and tested.

- **Lineups:** optimal by projected points via `modules/sim/lineup.py`; injured
  and bye players excluded; Passive personas set lineups with lag (sticky one
  week) so they are beatable.
- **Waivers:** run in worst-record-first order after your submissions resolve
  (user claims resolve at the same priority as their standing; no FAAB in MVP).
  AI claims only if projected lineup/depth gain exceeds the persona threshold.
- **Trade acceptance (user-proposed):** accept if
  `own_value_gain + lineup_need_fit + persona_bias + noise > persona_threshold`.
  Value uses persona horizon/age lens. The user sees a *verdict preview*
  (accept / counter / decline with a reason chip, e.g. "needs a RB", "wants
  picks") before sending; the actual roll is deterministic from the seed so
  previews are not a slot machine. Declines return a counter when
  `build_counter_offer_packages`-style logic finds one (our own pure
  implementation; the real analyzer is never mutated).
- **AI-proposed offers:** at most 1 per AI team per week and 3 league-wide,
  surfaced in the user's inbox, expiring on Advance. AI-to-AI trades continue
  (existing caps), and appear in the transaction feed.
- **Anti-exploit:** no single-asset extraction. A trade must pass a "fair
  floor" (the AI never accepts a loss beyond its persona's tolerance, which is
  capped), repeated offers of the same package within a week are blocked, and
  per-team season trade caps stay. Roster-limit and kicker rules apply to AI too.

## 7. What the user can do each week (rules)

- Lineup: any legal slot assignment; locked after Advance. Bye/injured starters
  score 0 (shown with a warning, not blocked).
- Roster: 16 spots default (starters + bench). Over-limit forces a cut before
  Advance. Cut players go to the free-agent pool.
- Waivers: unlimited adds subject to roster limit; claims resolve at Advance.
- Trades: unlimited proposals, 1 pending per partner, trade deadline at week
  10. Trade picks (future rookie picks) from Phase 4.
- Advance: validates (legal lineup, roster size) then resolves the week.
- Storylines (Phase 3): optional choices with small, disclosed effects (see 12).

## 8. Difficulty and fairness

- Difficulty only changes AI parameters, never hidden dice on the user:
  Easy (Passive-heavy, wide trade tolerance), Normal (mixed), Hard (more Value
  Sharks, tighter thresholds, smarter waivers). Same engine and same seeded
  scoring for the user's players at every level.
- Fairness guarantees: user and AI draw from the same player distributions;
  no rubber-banding; seed is stored so any result can be reproduced and
  audited; the existing counterfactual "decisions that mattered" explains
  outcomes, which discourages "rigged" perception.
- Anti-save-scum: results of an Advance are determined by `(seed, week,
  state)`; reverting to the start of a week and re-advancing with the *same*
  decisions yields the *same* result. Changing decisions changes only what
  that decision affects (SeedSequence keyed by stream, not call order). Starting
  a new game gives a new seed.
- Grade is on a curve (typical manager = C), already implemented.

## 9. Isolation rules (non-negotiable; unchanged from the existing sim)

1. Code lives in `modules/sim/` (draft, game, ai modules added inside). Real
   code never imports it; the one guarded mount in `mobile_api_service.py`
   remains the only reference.
2. Only `modules/sim/inputs.py` may import real `modules.*`, from an
   allowlist. Everything else in the package is stdlib/numpy/pandas + itself.
   The game adds one new adapter method (`player_pool(format) -> frozen`), not
   new real imports elsewhere.
3. `data/players.db` is only ever opened `mode=ro`; never call
   `rankings.load_players`/`build_players_table` (it can write back).
4. Writes only to `sim_*` tables (RLS per user, no FKs into real tables other
   than `auth.users`). No analytics events, notifications, decision memory,
   community trades, share cards, or league caches are touched.
5. Free-agent pool, rosters, injuries, and "news" in the sim are the sim's own
   copy; nothing flows back to real data. Sim-time player values evolve only
   in the sim copy.
6. `SIM_ENABLED` flag-off keeps every `/v1/sim/*` path a plain 404 and the
   package un-imported.
7. Keep and extend `tests/test_sim_isolation.py` (AST import graph, per-file
   allowlists, engine purity in a clean interpreter, real files and real
   endpoint output unchanged after a game, flag-off 404s) and
   `test_deterministic_replay_*`. New required tests: draft determinism,
   full-game replay equals checkpointed resume, advance idempotency, and
   "no write outside sim_*" after a complete game.
8. Draft + weekly compute runs under the sim's own bounded semaphore (503
   `server_busy`), never the real admission control.

## 10. Pro gating and free preview

- Pro gate is server-side, same check as Playoff Odds/Draft Center. A Free
  caller gets the existing `premium_required` 200 body.
- **Free preview (recommended):** Free users can run a full draft and play
  **weeks 1-3** of a game (single save, "Preview"). On week 4 they hit the
  paywall with their season in a "paused" state; subscribing resumes the same
  save (no lost progress). This sells the loop rather than a screenshot.
- Signed-out users: can open the hub and browse players/projections; starting
  a game prompts sign-up (free preview then applies).
- Pro: 3 active games, all difficulties, storylines, replay modes later.

## 11. API shape (extends `/v1/sim/*`; same conventions as the existing doc)

Auth bearer; 200 + `reason` for not-ready; 404 unknown/other user's; 422 bad
input; 503 busy. Free preview adds `preview: {weeks_left}` on responses.

| Method + path | Purpose |
| --- | --- |
| `POST /v1/sim/games` | Create game (settings, difficulty); builds snapshot + AI teams; returns game in `drafting` |
| `GET /v1/sim/games`, `GET /v1/sim/games/{id}` | List / state (status, week, your team, standings summary) |
| `GET /v1/sim/games/{id}/draft` | Board state, available players (paged), your queue |
| `POST /v1/sim/games/{id}/draft/pick` | `{player_id}`; engine then auto-resolves AI picks until the user's next turn |
| `POST /v1/sim/games/{id}/draft/auto` | Auto-pick rest of draft |
| `GET /v1/sim/games/{id}/players?q=&pos=&status=&sort=&page=` | Search all players with owner, projection, value |
| `GET /v1/sim/games/{id}/players/{pid}` | Detail: week-by-week projection + bands, schedule, news |
| `GET/PUT /v1/sim/games/{id}/lineup` | Read/set lineup for current week; `POST .../lineup/auto` |
| `POST /v1/sim/games/{id}/waivers` | `{add, drop}` claims (resolved at advance) |
| `POST /v1/sim/games/{id}/cut` | `{player_id}` |
| `POST /v1/sim/games/{id}/trades/preview` | Verdict preview for an offer |
| `POST /v1/sim/games/{id}/trades` | Send offer; response is accept/decline/counter (deterministic) |
| `GET /v1/sim/games/{id}/inbox` | AI offers, storylines (Phase 3) |
| `POST /v1/sim/games/{id}/inbox/{item}/respond` | Accept/decline/choose |
| `POST /v1/sim/games/{id}/advance` | Validate, resolve the week, write checkpoint; returns recap. Idempotent per `(game, week)` |
| `POST /v1/sim/games/{id}/revert-week` | Drop this week's pending events |
| `GET /v1/sim/games/{id}/league` | Standings, schedule, scores, transactions |
| `GET /v1/sim/games/{id}/result` | Final grade + decisions that mattered |
| `DELETE /v1/sim/games/{id}` | Delete |
| `GET /v1/sim/preview/players` | Signed-out browse (projections only, no state) |

Latency: draft pick and lineup calls are cheap (read state + one event);
`advance` resolves one week (target < 300 ms; existing full season is ~0.5 s).

## 12. Storylines (Phase 3, design intent only)

Player-centric events generated from seeded tables, not LLM-decided:
injury scare, contract holdout, trade request, breakout hype, off-field news,
rookie buzz. Each has 2-3 choices with disclosed, bounded effects (e.g.
"Start him anyway" / "Bench"; "Sell now at +X value" / "Hold"), applied only in
the sim copy. LLM use, if any, is flavor text only, generated async and cached
per storyline template, so determinism and cost stay under control. Must never
use real private news; use templated, clearly fictional framing.

## 13. Phased delivery (sizes for one engineer; backend / UI)

| Phase | Scope | Size |
| --- | --- | --- |
| 0 | Decisions below; add `sim_games`/`sim_events`/`sim_week_checkpoints` SQL (applied by hand); frozen player-pool adapter | 3-4 days |
| 1 MVP | Startup snake draft + AI pick model; weekly engine refactor to step one week at a time from checkpoint; lineup/waiver/cut; AI waivers; trade proposals with verdict preview and deterministic accept/counter; standings, recap, playoffs, grade. Pro gate + free preview. Web and mobile screens. Isolation + replay + resume tests | 5-6 weeks (backend 2.5, UI 3) |
| 2 | AI-initiated offers inbox, power ranks, transaction feed, better recaps, difficulty levels, trophy case/past seasons, share card of final grade (sim-only, never feeds real systems) | 2-3 weeks |
| 3 | Storylines engine + inbox, injury/hot-streak depth, news feed | 3-4 weeks |
| 4 | Multi-season: aging/progression, rookie draft, picks as assets, contracts-lite; Replay 2025 "classic" mode; FAAB; auction draft | 6-8 weeks |

MVP cut line: no storylines, no multi-season, no FAAB, no auction, no
leaderboards.

## 14. Risks and mitigations

- **Scope creep toward a full fantasy platform:** the cut line above; every
  Phase-2+ item needs an owner decision.
- **AI trades feel dumb or exploitable:** fair-floor, repeat-offer block,
  persona-driven reasons shown in the verdict; tune with a headless harness
  that runs 1000 auto-played seasons and checks that a "trade spammer" does not
  beat a balanced strategy by more than a set margin.
- **Simulated stats feel fake:** correlation, injuries, streaks; replay mode
  later. Playtest with owner/coridian_ before Phase 2.
- **Valuation coupling/drift:** frozen snapshot per game; adapter is the only
  coupling; golden tests compare in-process pre/post, not stored fixtures
  (players.db drifts).
- **Compute on the FastAPI box:** per-week stepping is small; bounded
  semaphore; checkpoints avoid replays.
- **Storage growth:** events are small; 3-game cap; 90-day prune; checkpoints
  pruned to last 2 weeks + season end.
- **Cannibalizing real-league tools or confusing users:** clear "Sandbox"
  labeling, no real-league names, separate entry in the menu.
- **Store review:** a pure-fiction game with no real-money stakes; confirm
  App Store/Play framing (not gambling; no cash prizes) before submission.
- **Data licensing for headshots/team logos in a game context:** same as the
  existing app; confirm no new terms are triggered.
- **Web/app parity cost:** ship both together or ship neither (house rule).

## 15. Open questions

1. Default format: redraft-style one-season (recommended) vs dynasty startup
   from day one?
2. Preview limit: 3 free weeks (recommended) vs free draft only?
3. Signed-out: allow a local-only game, or sign-up required to start?
4. Season length: 14 + 3 playoffs (recommended) or full 17 NFL weeks?
5. Do we want any competitive layer (leaderboards, shared seeds) later? It
   changes fairness requirements (identical seeds, anti-cheat).
6. Replay 2025 mode: worth the data work, or drop?
7. Should AI managers have names/avatars/personalities visible from day one
   (recommended: yes, it is the cheapest source of charm).
8. Naming/branding: "Fantasy Sim" vs "GM Mode" in the FantasyDesk rebrand.

## 16. The decisions that unblock work (recommendations in bold)

1. Weekly stats source: **simulated** vs real historical replay.
2. MVP scope: **one-season redraft-style startup draft** vs dynasty/multi-season first.
3. Gating: **Pro with a free draft + 3-week preview, resumable on upgrade** vs fully Pro vs fully free.
