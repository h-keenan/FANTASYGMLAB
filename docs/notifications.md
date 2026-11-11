# Notifications pipeline

Status: Phase 1-2 of the notifications design (decider/deliverer split, events,
receipts, user controls, sharding). Design source: the 2026-11-09 readiness
audit, Part 2. Supersedes `docs/notification-audit-2026-10.md` (stale).

## What exists

Channel: Expo push (iOS + Android) plus the in-app Alerts feed. Delivery runs
from `.github/workflows/push-trigger-sweep.yml` every 30 minutes ->
`scripts/run_push_trigger_sweep.py` -> `modules/push_triggers.py`.

```
detectors (push_triggers)  ->  candidate items per user/league
   category toggles (push_categories)         [user_settings]
   dedupe vs push_notification_log            [1 read per user]
-> decider (modules/notification_decider.py)  [pure, no I/O]
   stale -> roster relevance -> per-league mute/critical
   -> digest -> quiet hours -> weekly cap (reserved critical slot)
-> deliverer (one batched Expo push per user, lead item + "+N more")
   -> push_notification_log (dedupe + cap)   [always]
   -> notification_events (audit/receipts)   [opt-in, see below]
-> receipt poller (run_receipt_poll, same job): delivered/failed, prunes dead tokens
```

Existing categories (unchanged behavior with default prefs, proven by the
untouched `tests/test_push_triggers.py`): `injury`, `lineup_lock`,
`trade_deadline`, `top_priority`, `watch`, `waiver_reminder`, `recap`,
`weekly_roundup`, `team_situation`, `trade_followup` (separate sweep, now also
through the decider).

## User controls (new)

Stored in `user_settings.settings.notification_prefs` (same table and read as
the legacy `push_categories` toggles, so **no SQL is needed** and the sweep pays
no extra query). Edited via `GET/POST /v1/notifications/preferences`.

| Field | Meaning | Default |
|---|---|---|
| `quiet_hours_enabled`, `quiet_start`, `quiet_end` | local-hour window, wraps midnight | on, 22 -> 8 |
| `timezone` | IANA zone; overrides the device timezone | device, else America/New_York |
| `critical_breaks_quiet` | injury / lineup_lock / trade_deadline may send in quiet hours | off |
| `weekly_cap` | pushes per rolling 7 days (1-14); one slot always reserved for critical | server default (4) |
| `league_overrides` | `{league_id: all \| critical \| mute}`; mute skips detector work entirely | all |
| `category_modes` | `{category: instant \| digest}`; critical categories are always instant | instant |
| `digest_hour` | local hour the digest window opens (2h long) | 8 |

Held (quiet hours, digest) is not dropped: nothing is logged as sent, so the next
in-window sweep re-derives and sends what is still live. Dropped with an
auditable reason: `stale`, `not_on_roster`, `league_muted`,
`league_critical_only`, `capped` (counted in sweep stats under `suppressed`).

Relevance rules: injury alerts only for players on YOUR roster in that league;
lineup-lock items carry `expires_at` (kickoff) and are never sent after it.

## Deep links

Sleeper/ESPN expose no write API, so a notification "action" opens the exact
decision. Every push carries `data.url` (canonical web path) plus category and
ids; the app routes with `mobile/src/lib/pushRouting.ts`.

| Category | Web path |
|---|---|
| lineup_lock | `/matchup/{league}` |
| trade_deadline | `/trade-hub/{league}` |
| waiver_reminder | `/waivers/{league}` |
| weekly_roundup | `/league-recaps/{league}?tab=roundup&week=N` |
| recap | `/league-recaps/{league}` |
| injury (player) | `/players/{league}/{player}` |
| trade_followup | `/alerts` |
| other | `/dashboard/{league}` |

`data.notification_id` (the batch id) is what the app reports back to
`POST /v1/notifications/opened` for the open metric.

## notification_events (optional, hand-applied)

1. Run `docs/supabase_notifications.sql` in the Supabase SQL Editor.
2. Set the GitHub repo **variable** `NOTIFICATION_EVENTS=1`.

Until both are done nothing changes: the sweep neither writes nor reads the
table, `/opened` is a silent no-op. If the flag is on but the table is missing,
the first 404 switches events off for that process and the sweep carries on.
The flag is read at runtime, so turning it off again is instant.

Rows: one per item in a push (`sent` -> `delivered` | `failed` | `opened`),
with title, body, deep link, Expo ticket ids, error code. Receipts are polled
15 min - 23 h after sending; `DeviceNotRegistered` receipts prune the token.
A push where Expo accepts the request but rejects every device ticket is
treated as a failure (retried next sweep, never dedup-logged as delivered).

## Capacity

- League payload + rosters: fetched once per league per run (shared Sleeper
  cache underneath), however many users share the league. A muted league does
  zero detector work. One dedupe read per user (was per league).
- Time budget: `PUSH_SWEEP_TIME_BUDGET_SECONDS` (default 1500). Users are walked
  in a per-30-minute-slot pseudo-random order, so when the budget cuts a run
  short the unvisited users differ every run; stats report `skipped_budget`.
- Sharding: `PUSH_SWEEP_SHARDS=N` + `PUSH_SWEEP_SHARD_INDEX=i` (stable hash of
  user id). To scale out, duplicate the workflow job as a matrix over `i`.
  Invalid values fall back to one worker. (The `concurrency` group in the
  workflow must then be per-shard.)
- Known remaining N+1: the weekly-roundup dedupe check (one Supabase read per
  league, only Tue-Thu in-season) and per-user `get_user_leagues`.

## Not done yet (next slices)

Actionable buttons (iOS categories / Android actions, needs a mobile build),
named alternatives in lineup/waiver copy, web push, email channel, news-on-your
-players tier, snooze, Free/Pro policy, event-driven detectors (player->users
index) replacing the per-user detector walk, move off GitHub cron.

## Tests

`tests/test_notification_decider.py` (decider + prefs), `tests/test_notification_events.py`
(events, receipts), `tests/test_push_pipeline.py` (sweep wiring, scale),
`tests/test_notification_preferences_api.py`, plus the unchanged regression
suite `tests/test_push_triggers.py`. No test sends a real push (Expo is mocked).
