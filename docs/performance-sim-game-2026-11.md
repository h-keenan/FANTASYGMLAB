# Fantasy Sim GM game: interactive latency (2026-11)

Owner report: adding a waiver claim, or accepting/declining a trade, "takes a while".
This note records the measurements, what was slow, what changed, and how to re-measure.

TLDR

- The compute was never the problem (a claim is ~12 ms of Python). The cost was **store round
  trips and re-reading a 150-200 KB checkpoint on every request**: 5 serial Supabase calls per
  action, 3 per read, each on a fresh TLS connection.
- Now: reads are **1** store call (a ~1 KB version check) and actions are **3** (version check,
  event insert, bookkeeping write that overlaps response building). Nothing is replayed, no
  checkpoint or snapshot is re-parsed on a warm game.
- Modeled at 30 ms per store call: claim / cancel / trade accept / decline **~210 ms -> ~118 ms**,
  every GET **~145 ms -> ~40 ms**, advance **~400-570 ms -> ~190-220 ms**.
- Server CPU per action 12-15 ms -> 2-3 ms; GETs 11-19 ms -> 0.3-4.4 ms.
- Results are unchanged: same events, same state digests (new equivalence tests + the existing
  golden digests).
- Client: actions return a `delta` (header counts), the screens stop awaiting a second
  `GET /games/{id}`, and cancel / decline / claim are optimistic.

## How to measure

```
python scripts/bench_sim_game.py --fixture /tmp/sim_fixture.pkl -n 12 --detail --json out.json
python scripts/bench_sim_game.py --fixture /tmp/sim_fixture.pkl -n 12 --rtt-ms 30      # store calls cost 30 ms
python scripts/bench_sim_game.py --fixture /tmp/sim_fixture.pkl --scenario redraft --only x --profile waiver_add
```

`--fixture` builds the two games once (12 teams; a redraft at week 8 with seven played weeks, and a
dynasty at season 3 week 8: 1,442 events, 200 KB checkpoint) and re-loads them on later runs, so two
code versions are compared on **identical saves** (the "before" column below ran the pre-change
code on saves it built itself; the new code read those old saves unchanged).

Method: the real FastAPI router and sim code, the repo's synthetic pool (570 players) and an
instrumented in-memory store (the fake from `tests/test_sim_game_api.py`). Handlers run inline, so
the numbers are the serving thread's CPU time (receive -> last body byte) and are stable on a busy
machine. Store calls are counted, and calls that overlap in time count as one **round** (serial
depth). `--rtt-ms N` makes every store call take N ms so the cached and parallel paths show their
real value; Supabase from the API host is typically 20-60 ms per REST call. Wall p50 below is the
measured request time with `--rtt-ms 30` (CPU + rounds x 30 ms). Samples: n=8 per endpoint (4 for
the restore-heavy ones), quiet machine. What the fake cannot show: TLS handshakes, JSON transfer of
the checkpoint over the network (both only make "before" worse), and a multi-worker deployment.

## Where the time went (before)

Per request, from the phase breakdown (`--detail`):

| Cost | Before | Why |
|---|---|---|
| Store round trips | 3 per read, 5 per action, 8 per advance, all serial | `get_game`, then `latest_checkpoint`, then `load_events`, then (actions) `append`, `touch`; advance adds checkpoint upsert + list + delete |
| Rows read | 150 KB (redraft) / 196 KB (dynasty) per request | the latest checkpoint JSON, every request, including reads |
| State build | `GameState.from_dict` ~4-5 ms + store row copy 5-7 ms | `copy.deepcopy` of the whole state |
| Events replayed | only the tail since the checkpoint (0 at the start of a week, +1 per action), so not a factor | checkpoints are taken after each `advance` |
| Snapshot | already cached per process (`SNAPSHOTS`); 121-128 KB, read once | not a factor warm |
| `RealSimInputs` pool rebuild | never on these paths | the pool is read only to create a game; a save freezes its own snapshot |
| Evaluator construction | < 0.1 ms (the `now_scale` table is memoized on the frozen snapshot) | not a factor |
| `_lock_for(gid)` | held across the whole load + action + commit, 64 stripes | with 5 round trips inside the lock, a double tap or a refetch burst queues behind it |
| Trade eval / AI response | `verdict` < 1 ms, `build_counter` small; `advance` spends its time in the player model (week simulation) | not a factor for claim / accept / decline |
| Serialization | FastAPI's recursive `jsonable_encoder` was ~25% of a 25 KB reply (`GET home`) | fixed below |
| Parallel refetch | the client fires game + home + players at once: three independent full loads | single-flight now |

cProfile top self-time after the load fix, for `GET home` (5 calls): FastAPI response encoding, then
`isinstance`, `Evaluator.ros_mean`, `pick_lineup`, `player_row`. No single hot loop remains; the
O(n) `GameSnapshot.team()` / `user_team` scans and the per-page `value_ranks` sort were replaced by
per-snapshot memos.

## Before / after

Server CPU p50 (ms), store calls (rounds = serial depth), and wall p50 at 30 ms per store call.

### Redraft, 12 teams, week 8

| Endpoint | CPU before | CPU after | Rounds before > after | Wall @30ms before > after | Response KB |
|---|---|---|---|---|---|
| GET game | 10.9 | 0.4 | 3 > 1 | 150 > 39 | 1.3 |
| GET home | 15.1 | 3.2 | 3 > 1 | 160 > 45 | 25.0 |
| GET team (you / other) | 12.2 / 12.3 | 1.0 / 1.0 | 3 > 1 | 151 > 37 | 10.7 / 11.9 |
| GET players (25 / 60) | 12.5 / 13.4 | 1.2 / 1.1 | 3 > 1 | 150 > 42 | 11.1 / 27.1 |
| GET league | 13.1 | 1.2 | 3 > 1 | 141 > 39 | 24.2 |
| GET lineup | 11.3 | 0.5 | 3 > 1 | 143 > 40 | 6.4 |
| GET inbox | 11.0 | 0.4 | 3 > 1 | 142 > 41 | 2.2 |
| POST waivers (add claim) | 11.6 | 1.9 | 5 > 3 | 212 > 119 | 2.0 |
| DELETE waivers/{id} | 11.5 | 1.8 | 5 > 3 | 219 > 117 | 0.2 |
| PUT lineup | 12.2 | 2.0 | 5 > 3 | 218 > 117 | 6.5 |
| POST lineup/auto | 12.2 | 2.0 | 5 > 3 | 218 > 119 | 6.5 |
| POST trades/preview | 12.1 | 0.8 | 3 > 1 | 130 > 41 | 1.5 |
| POST trades (send, accepted) | 13.0 | 2.8 | 5 > 3 | 203 > 117 | 7.5 |
| POST inbox respond (decline) | 12.4 | 2.4 | 5 > 3 | 207 > 113 | 1.3 |
| POST inbox respond (accept) | 11.8 | 2.0 | 5 > 3 | 199 > 115 | 0.3 |
| POST cut | 12.7 | 2.3 | 5 > 3 | 209 > 118 | 5.6 |
| POST advance | 81.7 (p95 139) | 60.4 (p95 120) | 8 > 3 | 402 > 191 | 12.7 |
| POST draft/pick | 9.7 | 10.2 | 5 > 3 | 207 > 125 | 10.5 |
| POST draft/auto | 83.7 | 97.6 | 7 > 4 | 376 > 250 | 116 |

### Dynasty, 12 teams, season 3 week 8 (1,442 events, 200 KB checkpoint)

| Endpoint | CPU before | CPU after | Rounds before > after | Wall @30ms before > after |
|---|---|---|---|---|
| GET game | 14.1 | 0.5 | 3 > 1 | 132 > 39 |
| GET home | 18.4 | 4.4 | 3 > 1 | 143 > 41 |
| GET picks | 19.2 | 1.9 | 3 > 1 | 142 > 39 |
| POST waivers (add claim) | 14.8 | 3.0 | 5 > 3 | 206 > 127 |
| DELETE waivers/{id} | 14.6 | 2.7 | 5 > 3 | 202 > 122 |
| PUT lineup | 15.3 | 3.3 | 5 > 3 | 210 > 123 |
| POST trades/preview | 14.7 | 0.5 | 3 > 1 | 132 > 39 |
| POST trades (send, accepted) | 15.4 | 2.7 | 5 > 3 | 214 > 117 |
| POST cut | 15.8 | 3.1 | 5 > 3 | 220 > 120 |
| POST advance | 111.5 (p95 170) | 98.8 (p95 173) | 8 > 3 | 568 > 219 |

Store bytes read per request: 151 KB / 196 KB before, ~1 KB after (a warm game). Eight simultaneous
`GET home` calls on one game: 150 ms -> 44 ms (redraft), 182 ms -> 49 ms (dynasty), now one load.

Targets: claim / trade accept / decline server time p95 < 150 ms on the fake store: 2-3 ms CPU, 113-127 ms
with 30 ms store calls. Store round trips per action: 5 -> 3 (reads 3 -> 1).

Not improved on purpose: `advance` and `draft/auto` are the engine itself (week simulation through the
player model, AI picks): 60-100 ms of real CPU. The player model's results must stay bit-identical, so
it was left alone; the round trips around it dropped from 8 to 3.

## What changed

Server (`modules/sim`)

1. **In-process state cache** (`game_store.STATES`, `GameStore.load_game`). The folded `GameState` of
   the 12 most recently used games (`SIM_GAME_STATE_CACHE`, 0 turns it off; ~1-2 MB each) is kept
   per process. It is trusted only while its **version** equals the save row's: every request reads
   the row first (`event_count` + `updated_at`, ~1 KB, also the ownership check), so a write by
   another worker, a revert or a delete is noticed on the next request. Guards on top: the cached
   state's `seq` must equal the row's `event_count`, any conflicting/failed write drops the entry,
   `updated_at` is compared as microseconds (Postgres prints trimmed fractions, `isoformat` does not).
   Loads are single-flight per game, so a burst of parallel GETs costs one load.
2. **Copy on write.** A read gets the shared, never-mutated instance. A command works on
   `state.clone()` (marshal round-trip, value-identical to `to_dict` + `from_dict`; 0.8-1.0 ms against
   4-5 ms for `deepcopy` on the benchmark saves) and publishes the result as the new entry after its events are written. The draft
   "heal on read" path clones before it writes.
3. **Cold loads read in parallel**: snapshot and checkpoint together, then the event tail
   (3 rounds instead of 4), and `to_dict` / `from_dict` use the marshal copy.
4. **Overlapped bookkeeping.** After the (conflict-gating) event insert, the list-view update and the
   weekly checkpoint (upsert, plus pruning older checkpoints with one `week=lt.N` delete instead of
   list-then-delete) run in a small thread pool while the response is built, and are joined before
   replying; a failed bookkeeping write still fails the request as before, a failed checkpoint is
   still only a cache miss later.
5. **Slim action responses.** `delta` = `{status, week, pending, can_trade}` on lineup, waivers, cut,
   roster move, trades and inbox respond (`view.game_delta`; `pending_block` is shared with
   `game_view`, so the two cannot disagree).
6. **JSON straight from the handler** (`_fast_json`): skips FastAPI's recursive `jsonable_encoder`
   for plain-dict payloads, with the old path as the fallback.
7. **Memos on the frozen snapshot**: team index, user team, value ranks.
8. **Supabase transport** (`modules/sim/backend.py`): one keep-alive `requests.Session` with a
   pooled adapter replaces `requests.get/post` per call (a new TCP + TLS handshake each time), and
   upserts ask for `return=minimal` (the old `return=representation` echoed the whole 150 KB
   checkpoint row back). The fake store cannot measure this; it removes a handshake from every
   call and a payload from every checkpoint write.
9. `InMemoryBackend` serializes its calls with a lock (the store now issues independent calls from
   several threads).

Client (web-next and mobile, same files in both)

- `lib/simGame.ts`: `SimGameDelta`, `simApplyDelta`, `simWithout`, `simOptimisticClaim`.
- `useSimGameCall` / `useSimGameRequest`: an optional `onDelta` handler gets the delta of every
  successful action. `SimGameContent` / `GmGameScreen` apply it to the header state, and for 2 s after
  one `reloadGame()` returns immediately and confirms with the server in the background (1.5 s later)
  instead of making the sheet wait on a second `GET /games/{id}`. A 409 still reloads at once.
- Optimistic: cancelling a claim and declining an offer remove the row immediately (restored if the
  call fails); queuing a claim shows it and closes the sheet immediately (removed if the call fails).
  A trade accept is not optimistic: the AI can refuse it, so it shows the server's answer.
- Perceived latency per action = one request: ~40 ms (cancel / decline optimistic: 0 ms to the
  screen) + network, plus ~120 ms of store time at 30 ms per call, against the previous
  action + refetch of game, then home / roster / inbox, each at 140-210 ms.

## Safety

- Same events => same state: `tests/test_sim_game_perf.py` plays a scripted game (draft, advances,
  claim, cancel, lineup, cut, inbox, trade preview + send) with the cache **off and on** and asserts
  identical event logs, identical replay digests and identical `home` payloads; asserts the cached
  state equals a fresh from-scratch replay after every kind of write, that no GET mutates the shared
  state, that a write by another worker, a lost write race (409), a revert (same sequence numbers,
  different events) and a delete are all seen, that another user cannot read a cached game, that
  `clone()` is value-identical and independent, that a burst of cold reads loads once, that a warm
  claim costs exactly one read + two writes and a warm read exactly one call, and that the cached loader
  reproduces the golden player-model-1 digests from `test_sim_game_model_versions.py`.
- Old saves: the "after" runs loaded saves written by the old code.
- Isolation: `tests/test_sim_isolation.py` passes (the benchmark is allow-listed as an importer).
- Deterministic RNG streams are untouched; nothing in `game_engine`, `game_ai`, `game_eval` or the
  player model changed.

## Known limits / follow-ups

- Multi-worker: correctness comes from the per-request version check, not from affinity. Without
  sticky routing a second worker's first request for a game is a cold load (3 rounds).
- A cache hit still pays one round trip for the version check. Skipping it on writes and retrying on
  a conflict would save one more round, but a revert by another worker leaves a stale `seq` above
  the log (a gap, not a conflict), so it was not done.
- Memory: 12 states per process; tune with `SIM_GAME_STATE_CACHE`.
- App-level response compression was not added: Caddy already encodes (`zstd gzip`) at the edge.
- The in-process `compute()` pool and the per-game stripe locks are unchanged; a command now holds
  its game's lock across the version check, the insert and the overlapped bookkeeping write
  (3 rounds) instead of five.
- `GET /players` still scores every pool player per request to sort and filter (1.2 ms CPU on the
  570-player synthetic pool, but it scales with pool size); an index or a per-state sorted view is the
  next candidate if the real pool makes it show up.
