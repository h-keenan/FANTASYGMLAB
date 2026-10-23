# Notification audit, 2026-10

Scope: every path that can notify a user. Method: code read plus existing tests
(no real sends, no secrets, no real `data/players.db`).

## Architecture (one line each)

- Channel: Expo push only (mobile iOS + Android). No web push, no email, no SMS.
  `modules/notification_center.py` explicitly states it adds no push/email/SMS.
- Token registry: `push_tokens` table (`docs/supabase_push_tokens.sql`), PK = token,
  RLS own-row. Mobile `syncPushToken()` (`mobile/src/lib/pushNotifications.ts`)
  runs on session start/refresh, calls `POST /v1/push/register`; sign-out and
  account deletion call `unregisterCurrentPushToken()` -> `POST /v1/push/unregister`.
- Sender: `modules/push_triggers.py::run_push_trigger_sweep` + `run_trade_outcome_followup_sweep`,
  run by `scripts/run_push_trigger_sweep.py` from `.github/workflows/push-trigger-sweep.yml`
  (cron every 30 min, service-role key). Not in `render.yaml` anymore.
- Dedup: `push_notification_log` PK (user_id, recommendation_id), checked per league in one batch query, fail-closed.
- Preferences: `user_settings.settings.push_categories` via `GET/POST /v1/push/preferences`;
  UI on mobile More screen and web Account page. Default open (all on).
- In-app: Alerts feed (mobile AlertsScreen, web AlertsContent), notification dropdown, `notification_read_state` table for read/dismiss.

## Notification types

| Type | Trigger | Channel | Toggle | Gating | Status |
|---|---|---|---|---|---|
| Your Next Move (top_priority) | Dashboard engine item category top_priority, new recommendation_id | Expo push | `top_priority` | None (no Free/Pro check) | Working |
| Watch | Dashboard engine item category watch | Expo push | `watch` | None | Working |
| Recap Ready | Completed week detected (`league_recaps.completed_recap_week`), id `recap:{league}:{week}` | Expo push | `recap` | None | Working |
| Injury Update | Rostered player Out/Doubtful/IR etc (not Questionable), id `injury:{pid}:{status}` | Expo push | `injury` | None | Working (one-time backfill on first run) |
| Set Your Team Situation | League has no GM stance set, one-time per league | Expo push | NONE | None | Working, but no opt-out in app |
| Did this trade happen? | trade_outcomes pending, 20h after share | Expo push | NONE | None | Working push; tap is a no-op (see bugs) |
| Test push | `POST /v1/push/test` from More screen | Expo push | n/a | Auth only | Working |
| In-app Alerts / dropdown | News, injury, trade alerts computed on request | In-app | n/a (no mute) | Per alerts module | Working (tests green) |
| Email (digest, waiver, lineup, news) | n/a | none | n/a | n/a | Missing (does not exist) |
| Web push / browser notifications | n/a | none | n/a | n/a | Missing |
| Lineup lock / waiver-claim deadline / weekly digest push | n/a | none | n/a | n/a | Missing |
| Trade-offer-received push | n/a | none | n/a | n/a | Missing |

## Checklist findings

- Token registration: works; idempotent upsert, reassigns across accounts on same device. Simulators skipped. Android channel `default` created.
- Stale/invalid tokens: BEFORE this PR never cleaned (Expo tickets ignored, no receipts). Fixed for tickets (below). Receipt polling (delayed errors) still absent.
- Rate limits: NONE. No per-user weekly cap, no per-sweep cap, no batching. A user in N leagues with several Next Move items plus injuries can get many pushes in one sweep. coridian_'s <=2 pushes/week rule for new features is not enforceable today.
- Quiet hours / timezone: none. Sweep runs every 30 min around the clock, pushes at any hour.
- Dedup: solid for recommendation-keyed items. Weakness: top_priority/watch ids change when roster state changes, so a "flapping" recommendation can re-push.
- Free vs Pro: no gating in the sweep; every registered account (incl. Free) gets all categories. Product decision whether that is intended.
- Privacy mode: web/mobile privacy mode is client-side display masking only. Push payloads are built server-side with real league names and partner team names (trade follow-up), so a lock-screen screenshot is not masked. Server cannot know client privacy state.
- Deep links: top_priority/watch/injury with player -> PlayerDetail; others -> LeagueDetail via `league_id`. Cold start handled. Trade follow-up payload has `type`/`outcome_id` only, no `league_id`, so `routeNotificationTap` returns early (tap just opens the app).
- Opt-out compliance: per-category toggles exist for 4 of 6 types; OS-level permission is the only opt-out for the other 2. No email so no CAN-SPAM unsubscribe needed. Turning all four toggles off still leaves Team Situation and trade follow-up pushes.
- Scheduling: GitHub Actions cron `*/30`; GH cron can be delayed or skipped under load, and workflow has `concurrency` guard. No alerting on sweep failure beyond Actions status. Script exits 1 only if unconfigured.
- Sleeper-only: sweep resolves leagues via the linked Sleeper username, so imported leagues (Fleaflicker/MFL/ESPN) never get pushes.
- Preferences read failure (`fetch_push_preferences` returns {} on error) fails OPEN: a transient Supabase error ignores a user's opt-outs for that sweep. Product/safety call, flagged not changed.
- `/v1/push/preferences` POST accepts only the 4 categories; settings blob read-modify-write is not atomic (low risk).

## Bugs and fixes

1. FIXED `modules/push_triggers.py` (run_push_trigger_sweep, dedup record): `record_notification` was called even when the Expo send failed, so a transient Expo outage permanently swallowed that notification (the dedup row blocked every retry). Now logs only after a successful send.
2. FIXED `modules/push_tokens.py::send_expo_push_notifications`: Expo tickets were collected but never inspected, so tokens from uninstalled apps (`DeviceNotRegistered`) were retried every 30 min forever. Now returns `invalid_tokens`, and the sweep deletes them (`delete_invalid_push_tokens`, service role, exact-match delete) and stops using them for the rest of the run.
3. NOT FIXED `mobile/src/lib/pushNotifications.ts` routeNotificationTap: trade follow-up taps do nothing (no league_id). Needs a route decision (TradeHistory screen?) and a mobile build, so left.
4. NOT FIXED `modules/push_triggers.py::run_trade_outcome_followup_sweep`: marks `followup_pushed_at` even if delivery failed. Intentional per its docstring (in-app prompt covers it), noted only.

## Gaps needing product decisions

1. Weekly push cap per user (suggest 2-3/week global, priority: injury > top_priority > watch > recap), plus batching multiple leagues into one push.
2. Quiet hours (suggest 22:00-08:00 user local; needs a timezone field, none stored).
3. Add toggles for Team Situation and trade follow-up (or fold under existing categories) so all-off really means off.
4. Free vs Pro: which categories are Pro-only, if any.
5. Fail-open vs fail-closed when preferences cannot be read.
6. Privacy-sensitive payloads: omit partner/league names from push body? (server cannot see client privacy mode.)
7. Imported leagues (non-Sleeper) pushes; web push / email digest if wanted (none exist).
8. Expo receipt polling for delayed delivery errors.

## Tests

Run in a fresh venv, no network, no real DB:
`pytest tests/test_push_tokens.py tests/test_push_triggers.py tests/test_canonical_notification_center.py tests/test_roster_critical_alert_delivery.py tests/test_notification_dropdown_restoration.py tests/test_alerts_production_reliability.py` -> 70 passed (68 existing + 2 new:
`test_send_expo_push_notifications_reports_device_not_registered_tokens`,
`test_delete_invalid_push_tokens_deletes_each_exact_token`).
Coverage gaps: no test for quiet hours/rate limit (features absent), none for mobile `routeNotificationTap`.
