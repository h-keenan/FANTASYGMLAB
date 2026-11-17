# Audit: notifications and off-season rollover (2026-11)

Audits 5 and 6 of the approved list. Part A covers every push and in-app alert.
Part B covers what each page shows between seasons. Priorities: P0 wrong or
broken, P1 misleading, P2 polish or hardening.

## Part A: alerts and notifications

### Inventory

One delivery path: `.github/workflows/push-trigger-sweep.yml` (every 30 minutes)
-> `scripts/run_push_trigger_sweep.py` -> `modules/push_triggers.py` ->
`modules/notification_decider.py` -> Expo. The in-app Alerts feed reads the same
injury classification. There is no web push, email or SMS channel yet.

| Category | Source | Critical | Dedupe id | Scope |
|---|---|---|---|---|
| injury | roster player Out/Doubtful/IR | yes | `injury:{player}:{status}` | your roster only (decider `not_on_roster`) |
| lineup_lock | starter out / empty slot, kickoff within 2h | yes | `lineup_lock:{league}:{week}:...` | in-season, expires at kickoff |
| trade_deadline | 2 / 1 / 0 weeks out | yes | `trade_deadline:{league}:{week}:{n}` | in-season only |
| top_priority, watch | Next Move briefing | no | briefing recommendation id | your league and roster |
| waiver_reminder | evening before waiver day, real need | no | `waiver_reminder:{league}:{date}` | in-season only |
| recap, weekly_roundup | completed week | no | `recap:` / `weekly_roundup:{league}:{week}` | per league per week |
| gm_stance_reminder | one-time nudge | no | `gm_stance_reminder:{league}` | once per league |
| trade_followup | 20h after a shared trade | no | `trade_followup:{outcome}` | the sharing user |

Sim week-ready is not a push today (Sim has no push category). Listed as a gap.

### What was already right

- Quiet hours (22:00 to 08:00 local, user editable, device timezone, DST safe
  via `zoneinfo`), per-league mute, digest mode, weekly cap with a reserved
  critical slot, fail-closed on unreadable opt-outs, dedupe against
  `push_notification_log` that is only written after Expo accepts a ticket.
- Per-category toggles are honored before the detectors' output reaches the
  decider (`push_item_allowed`); mute skips detector work.
- No league or team names in visible push text.

### Findings and fixes

| # | Pri | Finding | Status |
|---|---|---|---|
| A1 | P1 | No per-day cap. The weekly cap of 4 could all land on one day (one push per 30 minute sweep). | Fixed: rolling 24h cap, default 2 (`PUSH_DAILY_CAP`), last slot reserved for critical categories. Unreadable count holds the push (fail closed). |
| A2 | P1 | Unknown device timezone fell back to US Eastern, so a Pacific user could get a push at 5am local. | Fixed: with no known timezone the morning end of quiet hours is pushed out 3 hours (quiet until 11am Eastern by default). |
| A3 | P1 | The same injured player on two of your leagues produced two items with one id: "X is now Out (+1 more update)". | Fixed: candidates are unique by recommendation id before dedupe and batching. |
| A4 | P1 | Off-season "Next Move" waiver-add pushes in February to August when nothing processes. | Fixed: waiver-destination briefing items are not pushed unless the league is in season. Still visible on the page. |
| A5 | P1 | Recap push opened the Dashboard in the app but News > My League on web. | Fixed: app routes `recap` to News > My League (Recap tab). Test added in `pushRouting.test.ts`. |
| A6 | P2 | Em-dashes in two push strings (Team Situation nudge, trade follow-up). | Fixed, plus a test that guards push copy. |
| A7 | P1 | The sweep exited 0 when it failed closed (opt-outs unreadable), so the freshness check saw a "successful" run that sent nothing. | Fixed: the script exits 1 when `ok` is false. The ops health check already watches the age of the last successful Push Trigger Sweep run (9h), so a stuck sweep now pages through it. |
| A8 | P2 | Injury dedupe is forever per (player, status). A player who is Out, recovers, and is Out again is never pushed twice. | Open. Needs per-player state (last seen healthy). Proposed: log a `injury_clear:{player}` marker row when the sweep sees the player healthy, and treat it as resetting dedupe. |
| A9 | P2 | Fantasy playoffs: league status `post_season` counts as in season, so an eliminated team can still get lineup-lock and waiver reminders. | Open. Needs the roster's playoff elimination flag (playoff odds). |
| A10 | P2 | Off-season sweep still builds valued players and a full briefing for every user every 30 minutes. | Open. Cheap win: skip the briefing detector when no league is in season or drafting and only run injury and recap. |
| A11 | P2 | `docs/notifications.md` listed old web paths. | Fixed in this PR. |
| A12 | P2 | Sim "week ready" has no push. | Open, product decision (new category plus opt-out toggle). |

### Tests added

`tests/test_push_pipeline.py`: dedupe against the log, two leagues one push, a
second sweep after a logged push sends nothing, daily cap with the critical
slot, unreadable daily count, quiet hours across six zones and 48 UTC hours
(DST and non-DST), unknown timezone padding, push copy has no dashes,
off-season waiver gating, script exit code.

### Freshness and ops

`scripts/ops_health_check.py` already compares the newest successful "Push
Trigger Sweep" run to a 9 hour limit. After A7 a failed-closed sweep is a red
run, so it ages out and the check fails. Not covered: a sweep that runs green
but legitimately sends nothing (cannot be told apart from a quiet league).
