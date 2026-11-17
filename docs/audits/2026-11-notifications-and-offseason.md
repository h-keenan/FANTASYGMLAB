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

## Part B: off-season and season rollover

### The model

Three clocks exist and each question uses exactly one:

- `modules/season_clock.py`: NFL season, phase (regular, post, offseason,
  preseason), week, upcoming draft year. Date-injectable (`season_clock(today)`),
  and now also `calendar_year()` for the places that need a plain year.
- The Sleeper league payload: `status` (`in_season`, `post_season`, `complete`,
  `pre_draft`, `drafting`). Sleeper leaves `settings.leg` at the last week it
  reached (17 or 18) after the season. `leg` alone is therefore never "this week".
  New in `modules/league_calendar.py`: `is_offseason()` and `active_league_week()`.
- The league rollover to a new `league_id` (handled earlier by #1311 and #1312).

Frozen-date matrix (calendar fallback, 2026 season): Feb 10 is `post`, May 15 is
`offseason` with the 2028 class as the next draft, Aug 20 is `preseason`.

### Findings and fixes

| # | Pri | Finding | Status |
|---|---|---|---|
| B1 | P0 | Playoff odds (League Rankings, Games, Dashboard strip) for a finished league ran the simulation on `leg` 18: it printed 100% and 0% "odds" and "0 weeks left" all winter. | Fixed: complete, pre_draft and drafting leagues return `reason: "offseason"`, which both clients already render as "Playoff odds will be available once the regular season begins." |
| B2 | P1 | Matchup page read `leg` and showed last season's Week 18 pairing for a finished league. | Fixed: between seasons it returns `no_current_week`. |
| B3 | P1 | GM Plan treated `leg` 17 of a finished league as "Playoff Push" in February. | Fixed: no week between seasons, so the phase is Offseason-Adjacent. |
| B4 | P1 | Standings header said "Through Week 18" after the season and "Through Week 17" in the fantasy playoffs. | Fixed: "Final standings" once complete, and playoff weeks clamp to the last regular-season week. |
| B5 | P1 | Waiver advice ignored the off-season. The "has played this season" gate stayed on (leg above 0), so rookies and new signings never appeared as adds until Week 1. | Fixed: the gate is off between seasons (`waivers_logic.default_played_ids`, waiver opponent and defense-tier context also off). |
| B6 | P1 | Team profile showed an "opponent this week" from last season's final week. | Fixed. |
| B7 | P2 | `datetime.now().year` in pick valuation, draft detection and format context made "today" untestable. | Fixed: one `season_clock.calendar_year()`. Existing pick tests now freeze through it. |
| B8 | P1 | Sim hub card for a dynasty Sim in its off-season reads "Week 17 of 17" (or "Week 18 of 17"): the DB status check only allows drafting, in_season, playoffs and complete, so `offseason` is stored as `in_season`. | Open, box-gated. Needs `sim_games_status_check` to allow `offseason` (docs/supabase_sim_game.sql, hand-applied) plus `db_status` to pass it through. The client label already handles `offseason`. |
| B9 | P2 | "This league hasn't started a week yet" is the matchup copy for a finished league. Honest but not specific. | Open. A new reason code needs web and app copy together (parity), so it was left for the UI pass. |
| B10 | P2 | Projections pages key off `default_player_stats_season`, which is last season until kickoff. Labels do not say "last season" or "next season". | Open. Needs a label audit across web and app. |
| B11 | P2 | The 30 minute push sweep still builds a full briefing per user all summer (see A10). | Open. |

### Tests

`tests/test_offseason_frozen_dates.py` freezes the clock on Feb 10, May 15 and
Aug 20 2027 (plus Nov 17 2026 as the in-season control) and runs the season
clock, playoff odds, the real `/v1/leagues/{id}/matchup` endpoint, standings
labels, Dashboard This Week, GM Plan phase, the waiver played gate and pick
capital.

### Rollover checklist (what to verify each February)

1. Old `league_id` shows Final standings and offseason odds, no weekly pages.
2. After Sleeper rolls over, the user's league list shows the new `league_id`
   in `pre_draft`; Dashboard offers "Prep your draft".
3. No push fires for the old league (all in-season detectors are gated on
   status, and injury pushes dedupe by player and status).
