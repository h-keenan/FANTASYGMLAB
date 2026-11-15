# Public Sim Leagues: multiplayer Fantasy Sim on a real-time clock (design, 2026-11-14)

Ask (coridian_): "public sim leagues, especially for the app, where each week is 2 days or a day or something." Follow-up requirements
(same day): a fictional storyline layer (later extended to storylines with real consequences), privacy settings, trade-spam safeguards, league chat,
usernames, and "make Fantasy Sim more immersive" as the general theme. **Design only: no product code changed.** Mockups:
`docs/audits/ui-pass-6/public-sim-leagues.html` (390px, liquid glass, shared templates).

Method: read of `modules/sim/*` on `origin/main` (event-log fold in `game_state.py`, commands in `game_actions.py`, weekly engine in
`game_engine.py`, store in `game_store.py`, API in `game_api.py`, `game_rules.py`), `docs/fantasy-sim-scope.md`, the 2026-11 sim audits
(hidden-value oracles, AI managers, injuries and usage), `docs/ui-patterns.md`, `render.yaml`, `modules/push_triggers.py`. Counts of single-owner touch
points come from grepping `user_team|is_user|USER_PARAMS` (19 of 28 `game_*.py` files; about 150 hits).

## TLDR

- The engine is already 80% of the way: state is a pure fold over an append-only `(game_id, seq)` event log, events already allow
  `actor = <team id>`, commands validate against state, a week is one `advance()`, and a lost write race is a `GameConflict`.
  A public league is "N seats, several humans, a scheduler that appends `advance`". The hard part is everything around the clock: seats,
  hidden information, human-human trades, moderation, notifications.
- Three variants: **V1** open public lobbies that fill with AI GMs on a schedule, **V2** private invite-code leagues (commissioner, friends,
  dynasty), **V3** seasonal public ladder with divisions and promotion.
- **Recommendation: build the multiplayer league core once, ship V2 (invite code) first with a thin "Quick Match" lobby on top (V1) behind
  a flag, V3 last.** Private leagues have no stranger-to-stranger UGC at launch, no cold-start problem, and every piece (clock, seats, autopilot,
  push) is what V1 and V3 need too.
- Default clock: **48h week**, tick at a fixed league-local evening time, 24h "Fast" option, live draft night with a 45s pick clock,
  idle humans fall to AI autopilot after 2 missed ticks, nothing ever blocks the league.
- Chat: **quick-react presets and templated offer notes in MVP; free-text league chat in Phase 3**, behind the full Apple 1.2 kit
  (filter, report, block, contact, 24h action). Chat-off leagues are a first-class setting. No DMs.
- Storylines have two layers: **narrative** (headlines, rivalries, awards, history, AI GM voices: a pure read-side projection, never feeds the engine) and
  **consequences** (rare doghouse/benching/suspension/leave/holdout/trade-request events that DO change usage and availability): logged `story_event`s behind a new
  `story_v` flag (old saves byte-identical), realistic rare rates with caps, public-info only, equal for AI and humans, with response choices and calibration. Labelled
  fictional, generated names only. Consequences ship first in **single-player Sim**, not in the league MVP.
- Cost is small: a 12-team league tick is milliseconds of compute; 10k leagues is a few hundred dollars a month at most. The real cost is moderation and push, not CPU.

---

## 1. Concept and product variants

### 1.1 Concept

Today Fantasy Sim is a single-player save: one `user` actor, one `is_user` team, "Sim week" is a button, time is whenever you tap.
A **Sim League** is the same game with:

- **Seats.** A league has N teams (default 12, same as `DEFAULT_TEAMS`). Each seat is `human`, `autopilot` (a human who is away), or `ai`.
- **A shared clock.** Weeks advance on a schedule (24h / 48h / 72h per sim week), not on a tap. Everyone sees the same countdown.
- **Real opponents.** Matchups, trades and waiver priority involve other people. AI GMs fill empty seats and cover absent humans.
- **Atmosphere.** Headlines, rivalries, hot streaks, trade-deadline drama, awards, league history, and rare consequential drama (section 5).

Why it matters: the product is seasonal (real NFL). A sim week on a 2-day clock makes a 17-week season about 5 weeks, so the sim can be an
**always-on, year-round engagement loop** (daily push-worthy moments) and a retention hook through the real offseason.

### 1.2 Variant overview

| | V1 Open lobbies ("Quick Match") | V2 Private invite leagues ("Friends league") | V3 Seasonal public ladder ("Divisions") |
|---|---|---|---|
| Who | strangers, one tap | friends via link or 6-char code | strangers, matched by tier |
| Start | fixed start slots (e.g. Fri and Mon 8pm league time); starts at the slot with at least 4 humans, AI fills the rest | commissioner picks draft night; starts when the commissioner says or all seats are claimed | seasons start on a published calendar; auto-placed into a division |
| Length | one season, 14 weeks + 3 playoff, no dynasty | single season or dynasty (multi-season) | season 1 of a ladder; promotion/relegation between divisions |
| Cadence | 48h default, "Fast" 24h lobbies | commissioner chooses 24/48/72h | fixed by division tier |
| Commissioner | none (platform rules) | yes (2.11) | none (platform rules + mods) |
| Moderation exposure | highest (strangers) | low (known people) | highest |
| Cold start | needs lobby traffic: solved by AI fill | none | needs hundreds of active players per tier |
| Monetization | free with limits | free to join, Premium to commission dynasty / extra leagues | Premium cosmetics/stats |
| Build size | M on top of core | the core itself | L on top of V1 |

### 1.3 Player experience per phase

**Join.**
- V1: lobby list (cadence, open seats, next start, "AI fills" badge). One tap Join, pick a generated team name, done. You see who is in (handle + crest). You can leave before start.
- V2: commissioner creates (name, cadence, seats, dynasty on/off, chat mode), gets a link and code. Joiners open the link (web) or the app (deep link `fantasygmlab://sim/join/<code>`), pick a seat/team name. Unclaimed seats at draft time become AI.
- V3: "Enter the season": placed in a division by tier (new users start in the bottom division).

**Draft.** A scheduled **draft night**: a live room with a 45s pick clock (30s from round 8), shown as the pinned clock bar of the existing draft room. Absent or
timed-out humans are picked by their **queue** (existing `draft/queue`), then the public-information auto-pick (`auto_for_user`, hint_v 1: ADP, need, byes; never the hidden value).
Reminder push 60 and 5 minutes before. About 25 minutes for 12 teams x 15 rounds when everyone is present.

**Weekly cycle (48h clock; exact anatomy in 2.2).**
1. Tick N fires: week N is played (existing `advance`), recap and headlines are published, waivers resolve.
2. The window for week N+1 opens: lineup (or leave auto), waiver claims, trades, news, reactions.
3. Last-call push at T-4h if your lineup has a hole; lock at the tick.

**Trades.** Human-to-human: propose, counter, accept; the recipient accepting executes immediately (validated against live state). Human-to-AI: the existing `TradeDesk` verdict, unchanged. Safeguards in 2.8.

**Waivers.** One run per tick in `waiver_order` (reverse standings priority, existing). Claims are sealed until they resolve.

**Offseason / dynasty continuity.** V2 dynasty: after the final the league enters the existing `offseason` status: retirements/aging, rookie class, rookie draft (a scheduled draft night, 72h
offseason clock), then `start-season`. The league keeps its history (champions, records, rivalries), picks and seats across seasons. V1 leagues end after the season with a Season in Review and a
"Run it back" button that starts a V2-style league. V3 ends with promotion/relegation.

**Humans go inactive (autopilot).**
- A human is "present" in a week if they sent any command (lineup, claim, trade response, queue) or opened the league after the window opened (a lightweight heartbeat, not an event).
- 1 missed tick: nothing visible besides a push ("Your lineup auto-set").
- 2 consecutive missed ticks: the seat flips to `autopilot` (event `seat_autopilot`). An AI manager with a neutral persona runs lineup (`auto_lineup`), waivers and trade responses; the seat shows an "On autopilot" chip. The human takes control back with one tap (`seat_resume`).
- After 4 missed ticks in V1/V3 (or commissioner decision in V2) the seat is **open for adoption** at the next natural boundary (offseason or the week-3 cut-off): listed in the lobby ("Open team: 6-2, WR heavy"). The original owner keeps a "reclaim within 7 days" right.
- Vacation: each human gets 2 "away" tokens per season (one tick of autopilot that does not count as missed, announced to the league).

---

## 2. Clock design

### 2.1 Cadence options

A sim week is one `advance()` (existing). Cadence is how often the scheduler calls it.

| Cadence | Sim week | 14 + 3 week season | Fit |
|---|---|---|---|
| Blitz | 12h | 8.5 days | enthusiasts; two touches a day; optional, not default |
| **Fast** | 24h | 17 days | daily habit; V1 "Fast" lobbies |
| **Standard (default)** | 48h | 34 days | coridian_'s "2 days"; one session per day pair; best for phone users with jobs |
| Slow | 72h | 51 days | dynasty/friends leagues; offseason steps |

Plus fixed phases: **draft night** (scheduled, about 25 min), **offseason stages** (rookie draft, start-season) on a 72h clock, a **pre-draft lobby** of 24 to 72h (fill window),
and **playoffs** at the same cadence (round names already exist). Recommendation: default **48h**, a **24h Fast** lobby type, V2 commissioner picks 24/48/72.

### 2.2 Tick anatomy (48h example; all UTC instants, shown in device time)

| When | What | Mechanism |
|---|---|---|
| T(N-1) | Tick N-1 done. Recap published, waivers resolved, new window opens | `advance` result |
| T(N-1) to T-5m | Lineups, claims, trades, reactions open | commands accepted |
| T-4h | "Last call" push if your lineup has a hole or an offer is about to expire | notification job |
| T-5m | **Command cutoff**: commands received after this server time get `week_locked` | server check |
| T (e.g. 21:00 league time) | Scheduler appends, in order: `lock_in` (auto-fill empty slots for humans; `fill_empty_slots` exists), `advance` (play week N: results, injuries, AI trades, waivers), headlines | `run_tick` |
| T + about 1s | Push "Week N recap is in" | notification job |

Why a 5-minute cutoff buffer: it removes "I tapped at 8:59:58" races and gives the scheduler a quiet window. The authoritative order is the log, not the wall clock:
the `advance` event records `tick_no` and `scheduled_for`; a command is either before it in the log (counted) or after (next week). Every command carries
`expected_week` (the existing `AdvanceBody.week` pattern, reason `week_mismatch`), so a late retry from yesterday cannot land on today.

Lineup lock: **all lineups lock at the tick** (the sim has no real kickoffs). Trades execute at accept time but freeze at T-5m with the rest. Waivers resolve at the tick.
Offers expire at the next tick or 48h after sending, whichever is first.

### 2.3 Time zones

- Every instant is stored UTC. The league has one **anchor**, e.g. `21:00 America/New_York`; the client renders in the device zone ("Locks Thu 6:00 PM" for Pacific).
- Each tick's `scheduled_for` is **computed once and stored** in `sim_league_ticks`, so DST never changes replays or past records; only future ticks re-anchor.
- V1 lobbies offer 3 anchors by audience (Americas evening, Europe evening, Late night), not per-user zones: a league cannot be 9pm for everyone, and per-user locks would break fairness.
- Push respects the existing device-timezone quiet hours (`push_triggers.py`); the league clock does not.

### 2.4 Catch-up policy (scheduler down or late)

- Under 2 minutes late: run the tick, `scheduled_for` unchanged.
- Outage: **never silently skip, never run many ticks at once.** On recovery, for each overdue league the scheduler first appends `clock_shift {minutes, reason: "platform"}`
  which pushes the lock and all future ticks later by the lost time (rounded up to 15 minutes), then runs normally. Players see "Server hiccup: week extended 3h" and a push. Deterministic because the shift is an event.
- A league never runs more than one tick per scheduler pass (hard guard), so a bug cannot burn weeks.
- Draft clocks: an outage pauses the draft (`draft_pause`/`draft_resume`) and restarts the current pick clock at full length.

### 2.5 Skip, vacation, pause

Away tokens (2 per season), autopilot after 2 missed ticks, `seat_resume` anytime. Commissioner (V2) can `league_pause` (clock freezes and shifts like an outage; max 7 days per season) and mark a holiday
`tick_skip`. The platform can pause any league (moderation/outage).

### 2.6 How weeks advance server-side, deterministically, through the existing event log

```
users --commands--> API (JWT -> member of league -> seat tid) --validate--> append events (seq gate)
scheduler --run_tick(league)--> load checkpoint+tail -> Emitter -> [lock_in, advance...] -> commit (seq gate)
```

Reuse unchanged: the `apply_event` fold (the only place state changes), `Emitter`, `advance`/`run_week`, `_resolve_waivers`, `_ai_trade_phase`, the draft engine (`run_ai_picks`,
`choose_pick`), `TradeDesk` verdicts, standings/playoffs, SeedSequence RNG per (week, subsystem, team) (outcomes depend on the log, not call order), weekly checkpoints, the state digest.

Determinism contract: `outcome = f(snapshot, seed, engine_version, settings flags, ordered event log)`. The scheduler's only inputs are the log and the stored `scheduled_for`.
Wall-clock time never enters a fold or a decision (it only gates *whether* a command is accepted, and is recorded as data in the event when it matters). Replays fold the log with no clock.

### 2.7 Concurrency, ordering, idempotency

1. **One log per league, one total order**: `(league_id, seq)` primary key (the existing optimistic gate). Users, scheduler and moderation all append through it.
2. **Command = load state, validate, append, commit.** On `GameConflict` the server retries up to 3 times with fresh state (re-validation catches semantic conflicts, e.g. the player was just traded). After 3: `409 busy`, client retries.
3. **Idempotency**: every command carries a client `command_id`; a unique index on `(league_id, command_id)` makes a double tap or retry a no-op returning the original result (extends `_already_written`).
4. **Tick idempotency**: `sim_league_ticks(league_id, tick_no)` is unique and written in the same transaction as the `advance` event; a second scheduler instance fails the insert and moves on.
5. **Single-flight**: the scheduler claims leagues with `SELECT ... FOR UPDATE SKIP LOCKED` where `next_due_at <= now()`, sets `locked_until = now() + 60s`; a crashed worker's lease expires.
6. **Order within a tick**: human commands accepted before the cutoff precede `lock_in`, which precedes `advance`. Two humans acting on one asset: whoever wins the seq gate wins; the loser gets `asset_gone`.
7. **Waiver tiebreak** is `waiver_order` (existing), never arrival order.
8. **Drafts**: only the on-the-clock seat may write a pick; the worker writes `auto` picks at the deadline.

### 2.8 Trade negotiation between humans, with AI fallback, and anti-spam safeguards

**Flow.** `trade_offer` (seat A to seat B: give/get, optional templated note) creates a pending offer in `state.offers` (the existing inbox model, now addressed to any seat). B can accept, decline,
counter, or ignore. Accept executes through the same `execute_trade` validation (roster limits via `check_roster_room`, tradability, pick-ownership conservation). If B is `autopilot` or `ai`, the existing
`TradeDesk` answers. A human who does not answer before expiry: the offer expires (no auto-accept, ever).

**Safeguards (coridian_ (c)); server-side, plain-language reasons.**

| Safeguard | Rule (starting values, tunable) |
|---|---|
| Pending-offer cap | max 3 open outgoing offers per user per league, max 2 open to the same person |
| Rate limit | 10 offers per user per league per 24h; 30 per user per day across leagues; API limiter on top |
| Cooldown after decline | the same pair cannot re-offer the same (or a near-duplicate) asset set for 24h; 3 declines in a week from one recipient pauses offers from that sender to that recipient for 48h |
| Auto-restrict repeat offenders | a user reported or auto-flagged for offer spam by 3 different people/leagues in 7 days loses proposals for 7 days (can still respond) |
| Mute / block | muting a sender hides their offers (they see "sent"); block also stops chat (4.3) |
| Report | one tap on any offer or message: spam, abusive, collusion, other |
| **AI fairness gate** | the engine's own private valuation (`TradeDesk` view of both sides; **never shown as a number**) blocks an offer from being *sent or accepted* when it is obviously exploitative. The sender sees "That one is not close to even; make it closer" (no value, no delta); the recipient never sees it. Near-misses can be sent; a flagged-but-accepted trade needs a second "Yes, I understand" tap from the giving side |
| Collusion guard | repeated one-way lopsided trades between two accounts (or accounts sharing device/payment identifiers) are flagged for review; trades appear publicly in the league feed with both teams |
| Trade block etiquette | the existing public trade block is the polite channel ("Looking for WR"); offers matching a block entry are exempt from the cooldown; block entries carry no free text in MVP |
| Deadline | trades close at the league trade deadline (existing `trade_window`) |

The gate reads the hidden valuation **as a gate, not a hint**: the user receives no signal beyond "not close enough" (one bit, the same bit an AI decline already gives; the oracle audit classes AI verdicts as
opponent behaviour). Required test: a scrambled-values test (as in the hidden-value oracle audit) proving the gate text carries no value-dependent content.

### 2.9 Reuse vs change: single-owner assumptions

| Area | Today | Change for leagues |
|---|---|---|
| Ownership | one `user` actor, `GameTeam.is_user`, `snap.user_team`, `USER_PARAMS`; store scoped by `user_id` (one owner per game); about 150 touch points in 19 files | add `state.seats {tid: {user_id, mode: human/autopilot/ai, since_week}}` as **fold state driven by events** (`seat_join`, `seat_autopilot`, `seat_resume`, `seat_replace`); `snap.user_team` becomes `snap.team_of(viewer_tid)`; every "user" read takes a `viewer`; events use `actor = tid` (the `game_state.py` header already allows it) with `"user"` kept as the single-player alias; AI phases iterate "seats not actively human" instead of `not t.is_user` |
| Storage scope | rows keyed `(user_id, game_id)` | league tables keyed by `league_id`; a membership table maps `user_id` to seat; every command authorizes membership then maps to `tid` |
| `auto_lineup` | one game-level boolean | per-seat preference (`seat_prefs` event) plus lock-time `fill_empty_slots` for any human |
| `sim-to`, `undo-sim`, `revert-week`, `realism-upgrade` (user commands) | single-player time travel | **disabled in leagues** (`not_in_league`); time moves only via the scheduler; undo would rewrite other people's weeks |
| Rules flags (`game_rules.py`) | user appends `realism_upgrade`; flags gated by version with boundary now/week/season | a league is created at the newest versions; updates only at the **offseason boundary**, appended by the platform (or accepted by commissioner vote in V2), never mid-season. The registry already stores the boundary in the event so old leagues replay forever |
| Engine versions over months | frozen snapshot + versions in settings | same; policy: a league finishes on its pinned engine version; an old version is retired by fast-forwarding at the league's next offseason |
| Hidden info | single player sees all AI rosters (public) | see 2.10 |
| Inbox/offers | addressed to the user | addressed to a `tid`, visible to the parties only |
| Achievements, grade, Season in Review, `game_home` | for the user | computed per seat from the same log (read-side); the sim shows letter grades, never a number |
| Notifications (`game_notifications`) | per game feed | per seat feed + push jobs |
| Premium gating | `ctx.is_pro` in `game_view.paywalled` | gate league **create/join count**, not week play (3.7); members are never locked out mid-season |

### 2.10 Hidden-information and oracle rules

1. **Lineups are sealed until lock.** Before the tick you see only your own lineup; after lock the week's lineups are in the recap. `view_for(viewer)` strips other seats' `lineups`, `queue`, `claims`, `offers`.
2. **Sealed claims** until resolution; the feed says only "won / lost" afterwards.
3. **Draft queues are private**; the public survival line uses public data (existing).
4. **No value/rating, ever** (existing rule): projection, ADP, letter grades. Leagues are created with `hint_v` at the newest version. The AI fairness gate is the only reader of hidden values and emits no number.
5. **The seed and future randomness never leave the server.** Future injuries and scoring draws are a function of the seed; a leaked seed lets users pre-compute outcomes. Never expose `seed`, engine internals or other seats' raw events; replay tooling is staff-only.
6. **AI persona identity**: AI managers show a public scouting-style bio (style, tendencies as flavor); numeric persona parameters stay private. A human on autopilot shows as "Autopilot".
7. **Realtime/push payloads carry no hidden data**: generic text ("Your trade offer was answered"), no names or values on the lock screen (mirrors the push-safety rule).
8. **CI**: a sealed-view test per hidden surface (another seat's lineup/queue/claims absent from every API response for a non-member and for another member) and a scrambled-values test for helpers.

### 2.11 Commissioner powers (V2 only; V1/V3 use platform rules)

Create/edit before start (name, cadence, seats, chat mode, dynasty), set draft night, kick/replace a seat before the draft or after 4 missed ticks, pause (max 7 days), skip a tick (holiday), reset a stuck draft
clock, mute a member in league chat, remove a team name (platform filters first). **Cannot**: edit scores, veto/revert trades after the fact, change rules mid-season, see sealed lineups/queues, undo weeks.
A leaving commissioner transfers to the longest-active member; the platform can always step in. Commissioner actions are events (`commish_*`), auditable in league history.

---

## 3. Architecture

### 3.1 Storage

Option A, reuse `sim_games`/`sim_events`: rejected for leagues (every policy and query is `user_id`-scoped for one owner). Option B (recommended): **league tables in the existing Supabase project**, hand-applied SQL
(`docs/supabase_sim_leagues.sql`, like every migration; no runner exists, do not assume it ran), same fold code, same checkpoint idea.

| Table | Purpose |
|---|---|
| `sim_leagues` | id, name, variant (open/private/ladder), status, settings jsonb (frozen), seed (server-only), engine_version, snapshot_ref, cadence_hours, anchor_tz/time, next_due_at, locked_until, current_week, season_no, invite_code, chat_mode, story_mode, created_by |
| `sim_league_members` | league_id, user_id, tid, role, status (active/autopilot/left/removed), missed_ticks, away_tokens_left, joined_at; unique (league_id, user_id) and (league_id, tid) |
| `sim_league_events` | league_id, seq, week, actor, type, payload, command_id, created_at; PK (league_id, seq); unique (league_id, command_id) |
| `sim_league_ticks` | league_id, tick_no, scheduled_for, ran_at, digest, events_from, events_to; PK (league_id, tick_no) |
| `sim_league_checkpoints` | rebuildable folded state per week |
| `sim_league_snapshots` | frozen player pool (large, compressed), one per league |
| `sim_profiles` | user_id, handle (unique, citext), crest, privacy settings (section 6) |
| `sim_reports`, `sim_blocks`, `sim_mutes` | moderation (section 4) |
| `sim_league_messages` | chat (Phase 3) |
| `sim_story_items` | optional cache of generated narrative text (derivable; section 5) |

Access: the backend (FastAPI on Render) is the only writer and uses the server credential the sim store already uses; **RLS is defense in depth**: members may `select` league rows where they are in
`sim_league_members`; **no client insert/update on events or leagues at all** (writes go through the API so validation and sealed-view stripping cannot be bypassed). Sealed data is never in a client-selectable
table; clients read API responses (which strip). Chat messages are the one table a client may read through realtime, scoped by membership, with no sealed data. No service-role key in the app or web bundle (add the sim
to the existing secret scan). Size: a folded 12-team state is small; about 1.5 to 4k event rows per league-season; checkpoints replace replay on every read.

### 3.2 Scheduler

Reality check: the API runs on **Render** web services; the old cron jobs moved to **GitHub Actions** (best-effort, 5-minute minimum, can slip many minutes). Fine for weekly ticks, **not** for a 45s draft pick clock.

| Option | Cadence | Pros | Cons | Verdict |
|---|---|---|---|---|
| GitHub Actions cron hitting an internal endpoint | 5 min best effort | exists, free | late; no draft clock | watchdog only |
| Supabase `pg_cron` + `pg_net` calling `/internal/sim/run-due` | 1 min (seconds on newer pg_cron) | survives API deploys | extension, per-minute | good secondary |
| **Render Background Worker (always on)** loop every 5s | seconds | exact draft clocks; simple (`modules/sim/league_worker.py`) | one more always-on service (about $7 to $25/mo) | **primary** |
| Cloud Run / Edge Function per league | n/a | scale to zero | new platform; cold starts hurt the draft clock | no |

Design: the worker loop does `claim_due(limit=20)` (SKIP LOCKED, 60s lease); per league `run_due` runs a draft auto-pick, a tick, a seat-autopilot sweep, an offer-expiry sweep, or enqueues notifications. A **watchdog**
(GitHub Actions every 5 min and `pg_cron` every minute) calls the same idempotent endpoint so a dead worker is covered. Merging to `main` auto-deploys: the worker must tolerate being killed mid-tick (the commit is atomic, the lease
expires, the next claim resumes). Failure recovery: alert if `now - next_due_at > 3 min` for any league; catch-up is the `clock_shift` rule (2.4). Replay-ability: any league's state at any tick can be rebuilt from events plus the
snapshot and compared to `sim_league_ticks.digest`; a nightly sample detects engine drift.

### 3.3 Real-time updates

- **Push (primary).** Reuse `push_tokens` and the push-safety layer (rolling-7-day cap, quiet hours in device timezone, batching, generic text). Sim push types: draft starting soon / on the clock (high priority, bypasses
  batching), trade offer received/answered, lineup hole at T-4h, week recap in, a story event hitting your player, deadline tomorrow, seat flipped to autopilot, clock shifted. Per-type toggles in notification settings.
  The 7-day cap must exempt "on the clock" and "offer received" (decision 9).
- **In-app: polling, not websockets, for MVP.** League home polls `GET /league/{id}/pulse` (tiny ETag'd payload: current_week, seq, next_due_at, unread counts) every 20s foregrounded and on focus; full views refetch when `seq`
  changes. The draft room polls every 2s while open.
- **Websockets later** (draft room, chat): Supabase Realtime broadcast per league, no sealed payloads, clients refetch via the API (Phase 3).

### 3.4 Scaling and cost estimate

Assumptions: 12-team leagues, 48h cadence, 5 humans per league, 17 ticks per season.

| | 1,000 leagues | 10,000 leagues |
|---|---|---|
| Humans | about 4k | about 40k |
| Ticks per day | 500 | 5,000 |
| Compute per tick (ms-level; AI trade search under 100 ms target) | about 0.2 s | about 0.2 s |
| Worker CPU | under 2 min a day | about 17 min a day: one worker |
| Event rows per season | 4M | 40M |
| Storage (about 300 B a row incl. index) | about 1.2 GB | about 12 GB (TTL 180 days after completion keeps it flat) |
| Snapshots (100 to 300 KB each) | about 0.2 GB | about 2 GB |
| Polling reads, all foregrounded (worst case) | 14M/day (mostly 304s) | 140M/day: cache `pulse` per league in-process, foreground only |
| Push | about 10k/day | about 100k/day |
| Rough infra delta | worker $7 to $25 on existing Supabase: **under $50/mo** | worker + Supabase compute upgrade + read cache: **about $200 to $500/mo** |

The dominant risks are the read path at scale (cache pulse), push volume against caps, and moderation labor. Load-test target: 200 leagues ticking at once; **jitter the anchor per league** (9:00 + hash(league) mod 20
minutes, shown honestly as "locks 9:07 PM").

### 3.5 Security

- **Auth per league member**: verify JWT, load the membership row, derive `tid` server-side; never accept a `team_id` as "who I am" from the client.
- **RLS** as 3.1; minimal read-only direct table access; sealed fields never in a selectable table or realtime payload.
- **No service-role key leaks**: server only; the worker has its own config loader (the push-sweep pattern: each backend-only job gets its own).
- **Anti-cheat / multi-account**: the main exploit is feeding a "main" team from your own accounts. Mitigations: the lopsided-trade fairness gate and public trade feed (2.8); one seat per user per league; a device/account soft-link
  (platform user id, push token, RevenueCat id) used only to flag, never displayed; accounts under 7 days old cannot trade with each other in public leagues for their first 2 ticks; ladder only counts verified-identity accounts.
- **Rate limits** at the API (per user per route, existing admission-control posture) and per game (2.8); body size caps; `command_id` required.
- **Clock abuse**: users cannot trigger ticks; `/internal/*` requires a shared secret and is not publicly routed.
- **Staff tools**: read-only league viewer, freeze/pause, remove user, delete message; every action logged.

### 3.6 Privacy, data, App Store review

We were rejected earlier under **5.1.2(i)** over the privacy label. Plan:

- **Newly collected/linked data**: handle (user content, linked), crest, league membership and in-game activity (gameplay content, app functionality), chat messages (user content, linked), reports/blocks (user content, linked, safety),
  push token (already declared), account/device identifiers for abuse flagging (identifiers, fraud prevention/app functionality, linked). No contacts, no precise location (time zone is not location).
- **Label changes** (App Store Connect, App Privacy): add User Content (Gameplay Content, Other User Content; linked, app functionality, not tracking); confirm Identifiers (User ID/Device ID; linked, app functionality, not used to track);
  keep Usage Data as today. The privacy policy gets a Sim Leagues section (what league-mates see, retention, deletion). `PrivacyInfo.xcprivacy` and `docs/account-deletion.md` must cover the new tables (delete or anonymize on account deletion:
  handle freed, messages replaced with "deleted", the seat flips to AI autopilot so the league continues).
- **ATT**: do **not** add tracking; abuse flagging stays first-party, so no ATT prompt and "Data used to track you" stays as today. Future ad attribution (`docs/ad-attribution.md`) must never join Sim identities.
- **Retention**: chat 90 days, reports 1 year, events per the TTL above, deleted accounts scrubbed within 30 days.
- **Review notes**: demo account; state that leagues contain UGC with the 1.2 controls in 4.3; in-app Report/Block; support contact; no real-money prizes or paid entries (keeps gambling guidelines out; ladder rewards are cosmetic).
- **Android**: the Play Data safety form needs the same updates; Play's UGC policy requires report/block.
- **Timing**: iOS is mid-review; leagues are a **new binary**. Do not mix them into the in-review build.

### 3.7 Monetization fit

The existing premium gating is untouched: `/v1/sim/*` single-player gating (`ctx.is_pro`, `paywalled`) stays; leagues are new endpoints.

- **Free**: join public lobbies and be invited to any private league; play a full season; 1 active public league + 1 private as a member; quick-react chat; standard feed.
- **Premium**: more concurrent leagues (e.g. 4), **commission** a private league with dynasty/custom cadence, deeper history and rivalry stats, cosmetic crest packs, Season in Review depth. Gold only on Premium markers.
- **Never gated**: playing out a week you are in. A lapsed subscription never locks a member mid-season (creating new leagues is what lapses).
- Decision 3 asks whether commissioning is Premium or free.

---

## 4. Moderation, chat, UGC (Apple guideline 1.2)

UGC surfaces: **usernames, team names, crests, trade-offer notes, chat, reactions**. Apple 1.2 requires: (1) filtering objectionable content, (2) a report mechanism with timely responses, (3) blocking abusive users,
(4) published contact information. Google Play has the same pattern.

### 4.1 Does chat exist? Decision

Recommendation: **phase it.**
- **MVP**: no free text between users except a **short filtered username and team name**. Communication = **quick-react presets** on trades and recaps ("Nice trade", "Good game", "Rematch?", "Ouch", "Run it back", "GG"; fixed, localizable, zero moderation exposure) and **templated offer notes** ("Need a WR", "Fair deal?").
- **Phase 3**: league chat and **trade-offer chat** (a thread on one offer, visible to the two parties) with the full kit below; default **on for private (V2), off for public lobbies** until a moderator rota exists. Every league can be **chat-off**.
- **DMs**: not planned (the highest-harassment surface; trade-offer chat covers the legitimate need). Opt-out is moot without DMs.

### 4.2 Chat feature set (Phase 3)

League room, offer thread, reactions (fixed set of 6), reply-to, no images/links/GIFs (links stripped: kills most spam/phishing), 280 chars, 1 message per 3s, 20 per minute per user per league, new accounts (under 24h)
read-only for the first hour in public leagues. Quick-react presets stay available when free text is off.

### 4.3 Moderation kit

| Layer | Detail |
|---|---|
| Filter on send | profanity/slur list (multi-language; leetspeak normalization; Unicode confusables), PII filter (emails, phone numbers, addresses, other-platform handles, URLs), a hosted toxicity classifier as a second pass. Blocked content is not delivered; the sender sees "That message was not sent" (no list leak). Shadow-mute repeat spammers |
| Report | long-press any message/name/crest/offer: harassment, hate, sexual, spam, impersonation, cheating, other + optional note; `sim_reports` row with a content snapshot and 10 messages of context; a message auto-hides after 3 distinct reports pending review |
| Block | per user: hides their messages/offers/reactions from you and stops their messages to you; **a blocked user in the same league cannot trade with you** (the league still runs). Blocks list in settings |
| Mute | league-level mute of chat or of a person, silently |
| Moderator tools | staff queue (reports, auto-hidden, repeat offenders); actions: hide message, warn, mute chat 24h/7d/permanent, force-rename, remove from league (seat to AI), suspend sim features, ban; every action logged with a reason |
| Commissioner tools (V2) | mute a member in the league, remove a team name, turn chat off |
| Response time | high-severity reports (hate, threats, sexual content) within 24h, others within 72h; **objectionable users ejected** (Apple: act on reports within 24h) |
| Contact | support email in Settings and the league menu ("Report a problem") and on the store listing |
| Retention | chat 90 days, reports 1 year |
| Terms | accept Sim Leagues terms (zero tolerance for objectionable content or abusive users) on first join |
| Age rating | UGC raises the rating (assume 12+ to 17+ via the questionnaire); chat default accordingly (decision 8) |

### 4.4 Privacy controls (coridian_ (b))

Settings: **Sim profile** screen (mockup 8).

| Setting | Options (default) |
|---|---|
| Who can see my profile (handle, crest, record) | Everyone / League-mates / Nobody ("Hidden": appears as a generated alias in lists) (**league-mates**) |
| Who can see my record and trophies | Everyone / League-mates / Only me (**league-mates**) |
| Who can see my trade history | Everyone / League-mates / Only me (**league-mates**; trades inside a league are public to that league in its feed regardless: that is the league's history) |
| Hide my username | on = a generated alias ("Gridiron Falcon 42") everywhere outside leagues you commission or were invited to; league-mates in a private league always see the handle |
| Private leagues | joinable by code only; not listed |
| Chat | Everyone in the league / Quick-reacts only / Off (**quick-reacts only** in MVP) |
| Who can send me trade offers | League-mates (default) / People I have traded with / Nobody except AI |
| Discoverability | whether the handle appears in search and lobby member lists |

Never exposed: email, real name, sign-in provider, Pro status, device. The Sleeper username is **never** linked to the Sim handle unless the user opts in.

---

## 5. Storylines and immersion layer (coridian_ (a), (f), and the consequences extension)

Goal: make a league feel like a living place: identity, history, rivalry, atmosphere, **and drama that matters**. Two layers with a hard
wall between them:

| | Layer N: narrative (display-only) | Layer C: consequences (`story_v`, sim logic) |
|---|---|---|
| What | headlines, press recaps, rivalries, awards, history, GM voices (5.3) | rare player/team events that change availability, usage, trade willingness (5.4) |
| Source of truth | pure function of the folded state + log; regenerated, optionally cached | **first-class logged events** (`story_event`) that the fold applies |
| Affects outcomes | never; not in the digest | yes, so it is gated, versioned, calibrated, replayable |
| Gate | `story_text_v` (templates; free to change, old items served from cache) | `story_v` in `GameSettings` (new games only, or the Realism update) |
| Randomness | none (templates keyed by a salted hash of the fact) | one SeedSequence branch per (week, "story", team); no other stream is touched |

### 5.1 Hard rules (both layers)

1. **Narrative text is display-only and never read by the engine.** Consequences are logged events; the text that describes them is generated after
   from the event's fields, so rewording a template can never change a result.
2. **Deterministic.** Same log, same seed, same version gives the same events and the same words. Layer C draws only from its own seed branch
   so adding or removing it never perturbs the scoring, injury, or AI streams (the property that kept the other `_v` gates replayable).
3. **Clearly fictional.** A persistent "Fictional league coverage" label on the feed and on every story card, with a one-time explainer. Stories
   are about **sim players in the sim**, not about the real people: the generated news is "the simulation's league", never a claim that
   something happened to the real player. Real player names are the sim's existing premise; consequences are phrased as sim events
   ("Doghouse: Sim week 7") with no invented quotes, no medical, legal, criminal, or family specifics (see 5.4 tone table), no real coaches/agents/teams' people, and
   no real-person defamation. Coaches, agents, reporters and GMs are **generated characters with generated names**.
4. **Humans are never the subject of drama.** Human managers appear only as handle + team crest; no invented quotes, scandals, or "reportedly"
   about a person. Rivalries are between **teams**.
5. **Public information only, no oracle.** An event's visible facts (who, what, expected duration range) are public; the sim's hidden value never
   decides who is hit and is never shown (consequence selection reads only public info: team, position, depth role, age, games played, usage).
6. **Equal treatment.** The same rate applies to AI and human teams. No bias by team quality, human/AI, Premium, or standing. Tested (5.9).
7. **Opt-out-able narrative, not opt-out consequences**: a league setting `story: off | flavor | full`. `off` and `flavor` have no Layer C (so every
   league can choose a drama-free game); `full` enables consequences. Public lobbies default `flavor`; the single-player default is `full` for new games after calibration.

### 5.2 Consequence events (`story_v`): design

**A first-class event.** `story_event {id, kind, week, tid, pid, severity, status, duration: [lo, hi], resolves_week, cause, response_window}`
applied by `apply_event` like `injury` (`state.out` is the existing analogue). New fold state `state.story`: active conditions per player and team
(`doghouse`, `leave`, `holdout`, `suspended`, `request`, `refusal`), a ledger of resolved ones, and per-team/per-user counters for the caps.
`story_v` is a `GameSettings` field (0 on every save made before it, serialized only when non-zero, state digest leaves `story` out while empty) exactly
like `ai_v`/`hint_v`; every branch is `settings.story`. Old saves and replays are byte-identical (pinned golden digests, as for `world_v`).
`story_v` can be added to an existing single-player game through the **Realism update** (`UPGRADABLE_FLAGS["story_v"] = (1, "week")`), so the flag
applies from the event's position on, undo removes it. In leagues it is chosen at creation (or the offseason boundary), never mid-season.

**Where the engine reads it (the only consequences):**

| Consequence | Engine hook | Effect |
|---|---|---|
| Doghouse / coach dispute: snaps down | the team-role scaling in `team_roles` / `game_usage` (the week's role scale + added points) | the player's role scale drops by a fixed fraction for N weeks; the freed usage goes to the next men on the depth chart **through the existing usage conservation** (`USAGE_CAP`), so a team never gains points from it (the ball is conserved) |
| Benched / healthy scratch | `ev.status(pid, w)` ("healthy" / "out" / "bye") gains a `benched` reason | like a bye for N weeks: zero points, AI and auto-lineup plan around it (`game_ai_depth` already plans byes) |
| Suspension | same as bench, with a known return week (public, exact) | out N games (1 to 6), shown from the start |
| Personal leave / family leave (kept generic) | same as out, duration range with a return window | out 1 to 4 weeks, can end early; cause shown only as "Personal leave" |
| Holdout (offseason/preseason in dynasty, and week 1-3 in season sims) | availability for the first weeks | out until resolved, resolves by a seeded date inside the range |
| Retirement (rare, age-conditioned) | existing `retired` ledger and aging model (`aging_v` hazard curves) | no new mechanism: the story layer only **narrates and times** a retirement the aging model already produces, and adds a small `early_retirement` hazard for 31+ players; consequences are the existing ones |
| Trade request (player wants out) | trade engine (`TradeDesk`) price/availability | the player is flagged `requested`; AI managers price him with a discount (`ECON_VERSION` economy hook: same shape as the injury discount) and he is **tradable even if on the block-restricted list**; staying on the team has a morale penalty (small usage drag, see below) |
| Trade refusal / counterpart dispute | `validate_offer` | a named team will not deal with another named team for a window (a "feud"), AI-only, both public; never blocks human-human trades |
| Rumor-driven requests | story generator, not engine | a **rumor** card ("Reports: Team X shopping a WR") is Layer N; it can raise the chance of a real `request` in the next 2 ticks only if the same public facts (depth, age, role) apply, never as a free signal |

Everything above is bounded by the existing usage and injury machinery so total team output cannot grow, and nothing introduces a new random draw
on the scoring or injury streams.

### 5.3 Narrative (Layer N) content types

| Type | Trigger (derived from the log) | Example |
|---|---|---|
| Weekly headline | biggest result of the tick (upset, record score, blowout, seed swing) | "Crows steal one: 8-point upset sends Wolves to 3-5" |
| Press recap | per matchup, 2-sentence wire report by a named generated writer | "By the Gridiron Ledger: ..." |
| Hot / cold streaks | 3+ wins/losses; best/worst 3-week PPG | "4th straight W for the Titans" |
| Rivalries | pair with 2+ meetings, trades between them, h2h (`state.h2h` exists) | badge, series record, "Rematch in Week 11" |
| Trade-deadline drama | final 2 ticks: buyers/sellers board, count of trades, biggest swap by a public measure | "Deadline watch: 4 teams have shopped WRs" |
| Awards | per tick: Manager of the Week, Waiver Hero, Boom of the Week; season: MVP, ROY, Exec of the Year, Comeback Team | trophy shelf |
| League history | champions, finals, records, all-time h2h, Hall of Fame (dynasty) | History tab |
| AI GM personalities | generated GM characters (name + voice per persona archetype); numeric parameters stay private | Value Shark: "I only deal when the math is clean." |
| Power rankings | weekly, by public stats | rank + one-liner |
| Atmosphere | crest/team colours, "Game of the Week", season chapters (Opening Week, Deadline Day, Playoff Push) | theme on the Hero |
| **Story cards** (Layer C) | each `story_event` produces one card with a headline, a plain "what it means" line, expected duration, and the response sheet | see 5.5 |

Surfaces: a **News tab** in the league (`PageTabBar`), the recap `StoryCarousel` (add "Headlines" and "Rivalry" pages), a Hero line on league home,
player-row chips (5.6). Reuses `CompactModule`, `StoryCarousel`, `RecapCard`, `PlayerAccordionRow`, `PlayerAvatar`.

### 5.4 Rates, caps, tone (realistic and rare)

Real-NFL anchors (rough, to be re-fit from sources in the calibration step, 5.8; targets are per **league of 12 teams** and about 60 relevant fantasy
players per team on a 53-man scale; a 12-team sim league is about 1/2.7 of the NFL): public discipline suspensions run in the dozens of players league-wide per
season (most are short, few are fantasy-relevant); public contract holdouts/holdins are a handful a year; public trade requests are a handful a year; healthy
benchings and role demotions are common but mostly not "disputes"; personal/family leave and mid-career retirements are a few a year.

| Kind | Target per 12-team league per 17-week season | Duration | Tone / severity | Visible cause text |
|---|---|---|---|---|
| Doghouse (coach dispute, snaps cut) | about 2 to 4 | 2 to 4 weeks, role scale -35% to -60% | light, newsroom | "Coach unhappy with practice habits (fictional)" |
| Benching (healthy scratch / demotion) | about 3 to 6 | 1 to 3 weeks | light | "Benched for a week" |
| Suspension | about 2 to 4 (mostly 1 to 3 games) | exact, announced | serious, factual | "Suspended N games (league policy)" |
| Personal leave | about 1 to 2 | 1 to 3 weeks, range shown | **sensitive**: generic text only, no detail, no speculation | "Personal leave. No timetable beyond the range." |
| Holdout (in-season, early weeks / offseason) | about 0 to 1 | until resolved, range shown | light | "Holding out for a new deal" |
| Trade request | about 1 to 3 | stays until moved or resolved (up to 8 weeks) | light | "Wants a change of scenery" |
| Counterpart refusal (feud) | about 0 to 2 | 3 to 6 weeks | light, AI teams only | "Teams are not on speaking terms" |
| Retirement (early) | about 0 to 1 (dynasty only, 31+) | permanent | sober | "Announces retirement" |

Caps and guards (all enforced in the generator, deterministic):
- Per team: at most 1 active consequence at a time and 2 per season; per **user** (human seat) at most 1 per season-quarter across their active leagues
  and never two in consecutive ticks; never the same player twice in 8 weeks; none in a team's first 2 weeks (learn the game first) or in the playoffs'
  final 2 rounds (no outcome swings at the finish).
- Cooldown: a human seat that was hit gets a quiet period of 4 ticks; a human with a single-star dependency is not specially treated (no pity, no pile-on).
- **Severity tone**: sensitive kinds (personal leave, suspension) never use jokes, never mention family, health, legal or criminal detail, and are suppressed in
  leagues for under-17 profiles if an age gate exists (decision 8); light kinds may use wry newsroom copy.
- A global rate ceiling per league per tick so a league never sees a run of events in the same week.
- The generator uses the team/position/role and **age and workload** (public) as covariates with mild weights, not hidden value or standing, so "good teams are hit as often as bad".

### 5.5 User agency: responses with trade-offs (never mandatory)

Every consequence that touches a human's player opens a **response sheet** with 2 to 4 options, each with a plain trade-off. Ignoring is allowed (the default
resolves on its own schedule), responses change the **speed or shape** of resolution, never the existence of the event:

| Event | Options | Trade-off |
|---|---|---|
| Doghouse | **Bench him** (stop the bleeding: shortens the doghouse by 1 week, you start the next man), **Stick with him** (default, no change), **Address it** (a one-time "Team meeting": 50/50 style resolution by seeded draw: ends 1 week earlier or +1 week; once per player per season), **Shop him** (adds a trade-block entry; the AI discounts him) | agency without a guaranteed fix; "address" has real variance |
| Trade request | **Trade him** (block entry, AI discounts), **Hold** (stays, small usage drag each week he stays, up to 8 weeks then resolves), **Promise a role** (commit to starting him for 3 weeks: lineup lock hint, resolves the request) | a held player is a mild liability; a promise costs lineup freedom |
| Holdout | **Wait**, **Trade him**, **Pay up** (resolves now; in the sim this is a small "cap-free" cost: a roster-slot freeze for 2 weeks, since the sim has no cap or contracts) | no money system, so the cost is a slot |
| Suspension / Leave | **Move to IR/taxi** if eligible (frees a spot, existing `move_player`), **Stash** (keep) | information only, no resolve action (you cannot influence it) |
| Retirement | **Acknowledge** | final |

Options are plain buttons; the `ConfirmInPlace` pattern guards the irreversible ones. Responses are commands that append `story_response` events, subject to the
usual lock/cutoff and sealed rules (an opponent never sees your response, only the public status).

### 5.6 Transparency

- **Player status chips** (shared `PlayerBadge`, symbols plus short word): `Doghouse`, `Personal leave`, `Suspended (3)`, `Holdout`, `Trade request`,
  `Benched`. Visible on every player row (`PlayerAccordionRow`), the lineup, waiver lists, the player sheet; opponents see them too (public). A
  tooltip/peek explains: what happened (one line), expected duration range, what it does to usage, and what you can do.
- **News feed**: each event is a card (kicker, headline, what it means, duration, "Respond" if it is your player).
- **Notifications**: a push only for events that hit **your** player ("Doghouse: one of your starters"), generic text on the lock screen, respecting caps.
- **Forecast honesty**: expected duration shown as a range; an unknown is "No timetable". No hidden countdowns.
- The sim still shows letter grades and projections only; a chip's effect is reflected in the **projection** (the shown number already includes the status)
  so users reason from public numbers.

### 5.7 Interaction with injuries, usage budgets, `world_v`, and the economy

- **Injuries**: a consequence and an injury never stack on one player (a player with an active injury is excluded from the draw); the existing `state.out` stays the injury
  ledger, `state.story` the consequence ledger; both feed `ev.status` in one place. An injury during a doghouse ends neither: the longer one governs.
- **Usage budgets / `world_v`**: consequences reduce a player's role scale; the freed share flows through `team_roles` and is bounded by `USAGE_CAP`; the QB exemption stays
  (a QB doghouse = a bench event under `world_v` bench-QB rules). `story_v` requires `world_v >= 1` (otherwise the usage conservation that protects totals is absent). Required test: team group points over a
  season are unchanged within noise with and without `story_v` (consequences move production, they do not create it).
- **Economy (`econ_v`)**: AI managers price a `request` player with a discount (analogous to the injury discount: the share of the season he is expected to be unhappy), and a
  doghouse player at the share of the remaining doghouse weeks; suspensions use the injury path. Because AI selling prices are the market floor for a human deal, a request
  player is a real buy-low or sell-low decision, not a trap. Humans see no number: acceptance meter wording only.
- **AI behaviour**: AI auto-lineup (`auto_lineup`) and `game_ai_depth` already plan around byes/injuries; `benched`/`leave`/`suspended` simply become "out" statuses, so no new AI code beyond the discount.

### 5.8 Calibration plan

Harness (to build, modelled on `injury_usage_report`/`realism_sweep`): `python -m modules.sim.calibration.story_report --seeds 200 --league-teams 12 --seasons 3 --story-v 0|1`.
Measures per league-season: event counts by kind (vs the table in 5.4), distribution of events per team (max, p99, share of teams with 2+), per human seat across leagues (cap check), duration distributions, the
share of events on starters vs depth, **impact**: expected weekly points lost per event, season win-probability shift for the affected team (target: a single event moves a typical
contender's title odds by about 1 to 4 points, not 10+), league-wide points conservation (usage conservation holds), and fairness (event rate by team strength quartile and by AI vs human seat: chi-square within tolerance;
the rate by pre-season rank quartile must be flat).
Acceptance thresholds before it ships on: rates within +-25% of the target; no team with 3+ events per season in 99% of leagues; no human with more than 1 event in 4 consecutive weeks; title-odds shift p95 under 6 points; no outcome change at `story_v=0` (digest identical for all pinned goldens); determinism (two runs byte-identical, the Emitter
order independent); points conservation error under 1% at the league level. Real-world anchors re-fit from public NFL transaction and suspension data each season (a recorded input, not a live dependency).

### 5.9 Tests and rollout

- Golden digests for `story_v=0` (all existing goldens) unchanged; new goldens for `story_v=1`.
- Replay test with `story_event`/`story_response` interleaved with human commands; undo/revert past an event removes it (single-player).
- Sealed-view and oracle tests: story selection inputs are public fields only (scrambled-values test: permuting hidden values leaves the event stream identical).
- Layer N copy lint: banned-words list (medical/legal/family/criminal detail), no real coach/agent names, generated-name allowlist.
- Rollout: ship in **single-player Fantasy Sim first as `story_v 1`** (new games only; an Update button through the Realism update for existing saves), measure, then enable in leagues at creation (`story: full`) once the harness passes. It is **not** in the public-league MVP.

### 5.10 Immersion beyond the feed (the general theme)

Identity (crest, generated names, trophies), history (per-seat career log), rivalries (auto-labelled h2h), atmosphere (weekly theme, Game of the Week), ceremonies (draft-night intro,
season finale, a sim-specific championship card), manager voices (AI GM bios), and now **stakes** (consequences with a choice). All Layer N pieces are additive/read-side;
Layer C is the only part that touches outcomes and is separately versioned.

---

## 6. Usernames and identity (coridian_ (e))

- **Unique handle** (3 to 16 chars, letters/digits/underscore, case-insensitively unique via `citext`), separate from account email, Sleeper username and display name. Shown as `@handle`.
- **Filter**: profanity + slur list with normalization, reserved words (staff, admin, support, fantasydesk, coridian, ocyws, and NFL team/player-name patterns that imply endorsement), no PII shapes (email/phone/link),
  an impersonation check (confusables vs existing handles and staff), and the same filter on team names.
- **Change policy**: free at creation; one change per 30 days after; the old handle is reserved 30 days for its owner (prevents squatting to impersonate); a forced rename by moderation any time. Events store `user_id`/`tid`,
  not the handle, so a rename never rewrites the log.
- **Display vs legal name**: Sim never collects a legal name; Apple/Google "hide my email" and the account name are never shown or stored in the sim profile.
- **Avatar/crest**: auto-generated crest (existing `SimCrest`, seeded from the team name) and a **preset library** (shape/pattern/colour). **No image uploads** (no image moderation or CSAM obligations).
- **Link to the existing account**: `sim_profiles.user_id` references `auth.users`; the API never returns email or provider; the handle is the only public identity; Premium status is never shown.
- **Team names**: generated options first (`game_names.py` already generates names); custom allowed (20 chars, filtered) in private leagues at MVP and in public leagues after the moderation queue exists (decision 6).
- **Hidden-profile alias**: a deterministic generated alias derived from `hash(user_id, salt)`: stable, not reversible.

---

## 7. Phased roadmap

Sizes: S under 3 days, M about 1 week, L 2 to 3 weeks, XL 4+ weeks (web + app twins counted together). Risk: H/M/L.

| Phase | Scope | Size | Risk |
|---|---|---|---|
| 0 Spike | seat model + `viewer` plumbing in a branch (`snap.team_of`, actor = tid, `state.seats`); run a 12-seat league with 3 scripted humans through the existing engine; sealed-view tests; deterministic replay test with two human actors | M | M (the ~150 touch points) |
| **1 MVP: Friends league** (V2 core, the smallest valuable slice) | league tables SQL; create + invite link/code + join; handle + preset crests (username picker, profile with the privacy basics); scheduled draft night (queue + auto-pick + live clock via worker); 48h/24h tick via worker + watchdog; lineups with lock; waivers; human-human trades with the 2.8 safeguards (caps, cooldowns, fairness gate, report/mute/block); AI autopilot after 2 missed ticks; league home with countdown; recap + standings; push (offer, on the clock, recap, last call); quick-react presets; narrative news feed v1 (headlines, streaks, awards); chat off; flag `SIM_LEAGUES_ENABLED`; web + app | XL (about 6 to 8 weeks) | H (touch points, push, new binary) |
| 1.5 Quick Match (V1-lite) | public lobby list with fixed start slots, AI fill, generated team names only in public, report + block on names/crests, a simple staff report queue, open-seat adoption | L | H (UGC review, cold start) |
| 2 Depth | dynasty continuity in leagues (offseason clock, rookie draft night, rollover), commissioner tools, history tab + rivalries + trophy shelf, press-style recaps, AI GM bios, the full privacy set, away tokens | XL | M |
| **2b Story consequences (not league MVP; can ship BEFORE leagues, in single-player Sim)** | `story_v` flag, `story_event` fold, engine hooks (role scale, status, trade pricing), caps, status chips, response sheet, `story_report` calibration harness, Realism-update upgrade path; leagues get it at creation after it passes | XL (about 4 to 6 weeks; the harness is most of it) | H (touches outcomes; mitigated by the flag, calibration, goldens) |
| 3 Chat | league chat + trade-offer chat with the full 4.3 kit, toxicity classifier, mod tools v2, realtime (Supabase Realtime broadcast), chat-off default for public | L | H (moderation labor, age rating) |
| 4 Ladder (V3) | divisions, tiers, promotion/relegation, seasonal calendar, leaderboards (verified accounts), cosmetic Premium | XL | M |
| Later | LLM rephrasing of fixed story facts (cached, filtered), shareable season cards, spectators, tournaments | L | M |

**MVP rationale.** The core (seats, clock, scheduler, sealed views, human trades, push) is everything every variant needs. V2 exposes the fewest strangers to each other, needs no cold start, and gives the owner
immediate play with real friends on phones. V1 follows once report/block and a staff queue exist. This also sequences the Apple 1.2 work: the MVP already ships filtered handles/team names, report, block and contact (the
minimum kit) even with chat off, because names and offer notes are still UGC. Story consequences are the main immersion win that does **not** depend on multiplayer, so they are best proven in single-player first.

---

## 8. UX mockups

`docs/audits/ui-pass-6/public-sim-leagues.html` (390px frames, liquid glass, cyan structure and cyan primary action, gold only for Premium markers; shared templates `Hero`/`StatusHeader`, `CompactModule`,
`PlayerAccordionRow`, `PageTabBar`, `PlayerAvatar`, `SimTeamIdentity`). Screens: 1 lobby/join, 2 league home with countdown, 3 draft with turn timer, 4 week-lock lineup, 5 human trade offer, 6 recap with standings,
7 chat, 8 profile and privacy, 9 storyline/news feed, 10 username picker, 11 story consequence card + doghouse/leave/suspended chips on player rows, 12 story response sheet; plus V1/V2/V3 sheets for lobby and league home.
Rendered PNGs (not committed; regenerate with Chromium at 1290px viewport, element screenshots of `#var-lobby`, `#var-home`, `#screens`) are listed in the PR description.

---

## 9. Open decisions for coridian_ (with recommendations)

1. **Which variant first?** Rec: V2 (invite-code friends leagues) as MVP, V1 Quick Match fast-follow, V3 later.
2. **Default cadence and league size?** Rec: 48h week, 12 teams (same as single-player), 24h Fast as a lobby type, 9pm ET anchor with 3 regional anchors.
3. **Premium line?** Rec: joining and playing is free; Premium = commission leagues (dynasty/custom cadence), more concurrent leagues, deeper history, cosmetics. Never lock a member mid-season.
4. **Is chat in MVP?** Rec: no free text in MVP; quick-react presets and templated offer notes; free-text league chat in Phase 3 with the full moderation kit; no DMs.
5. **Who moderates?** Rec: a staff queue run by Zach/ocyws at first with a 24h SLA on high-severity; do not open public lobbies with free text until a named owner and rota exist.
6. **Custom team names and uploads?** Rec: filtered custom names in private leagues only at MVP, generated names in public; **no image uploads**, preset crests only.
7. **Storylines: template-only or LLM?** Rec: template-driven and deterministic; consider an LLM later only to rephrase a fixed fact set (cached, filtered, labelled).
8. **Age rating and age gate?** Rec: raise the app rating for UGC (12+ or 17+ via Apple's questionnaire), chat off by default for public, suppress sensitive story kinds if an age gate exists; confirm with Zach before submission.
9. **Push budget for sim?** Rec: exempt "you are on the clock" and "offer received" from the 7-day global cap; keep the cap for everything else; per-type toggles.
10. **Autopilot thresholds?** Rec: 2 missed ticks to autopilot, 4 to open-for-adoption, 2 away tokens per season; commissioner override in V2.
11. **Human-human fairness gate: block or warn?** Rec: block the obviously exploitative (plain message, no numbers), warn with a second tap on borderline; log all for collusion review.
12. **Scheduler infra?** Rec: an always-on Render background worker plus pg_cron/GitHub watchdog; confirm the budget (about $7 to $25/mo).
13. **New binary vs the in-review build?** Rec: do not touch the in-review iOS build; ship leagues in the next build behind `SIM_LEAGUES_ENABLED`, web first for a private beta with the owner's group.
14. **Real-money / prizes?** Rec: never (cosmetic rewards only); keeps the app out of gambling rules.
15. **Consequence rates and tone?** Rec: the 5.4 table (a handful per 12-team season), `story: off | flavor | full` per league, sensitive kinds generic-only, ship single-player `story_v` first and enable in leagues after calibration; confirm suspensions and personal leave are acceptable subject matter for the age rating.
16. **Do feuds and request discounts affect human-human trades?** Rec: no; feuds are AI-only, request discounts apply to AI buyers only, humans price freely.
17. **Do handles appear on share cards?** Rec: no handles on share cards without opt-in; crest + team name only.

## 10. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| ~150 single-owner touch points regress single-player | breaks a shipped feature | phase 0 spike; keep the `user` alias; golden digests unchanged for old saves; separate league endpoints |
| UGC/App Store rejection (1.2) or 5.1.2 again | blocks the build | minimum kit in MVP, label updated before submission, review notes, demo account |
| Scheduler outage during synchronized ticks | missed weeks | worker + watchdog, lease, `clock_shift` instead of skipping, alert on overdue, anchor jitter |
| Cold start in public lobbies | empty lobbies | AI fill, fixed start slots, friends league first |
| Collusion / multi-account | unfair leagues | fairness gate, public trade feed, one seat per user, soft-link flags, ladder counts verified accounts |
| Hidden-info leaks (seed, other lineups) | cheating | sealed `view_for`, never return seed/events, CI tests |
| Harassment in chat | brand and review risk | phased chat, filters, report/block/mute, chat-off, staff SLA |
| Consequences feel unfair or random (the doghouse hit my star) | churn, support load | rare, capped, equal rates, response choices, visible reason and duration, none in a team's first 2 weeks or the final playoff rounds, `story: off` option |
| Consequence logic breaks determinism or old saves | replay drift | `story_v` gate (0 on old saves), own RNG branch, golden digests, calibration harness, conservation test |
| Story text touches sensitive real-life topics or real people | reputation, review | generic wording for sensitive kinds, copy lint, fictional label, generated characters, no human-targeted drama |
| Long-lived league vs engine changes | replay drift | pinned versions; offseason-only updates via event; nightly digest check |
| Push fatigue / over-cap | churn | per-type toggles, batching, generic text, quiet hours |
| Players dislike waiting 2 days | churn | 24h Fast option, draft night, a daily-readable news feed, quick reacts |
| Scope swallows the roadmap (Premium lifecycle P0, mobile QA) | opportunity cost | MVP cap, flag, phase gates; revisit after Phase 1 |
| Data deletion obligations | privacy | seat to AI, handle freed, messages scrubbed, new tables in the account-deletion flow |
