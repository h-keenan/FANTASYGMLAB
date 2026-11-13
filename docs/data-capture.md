# Data capture: injury history and league roster snapshots

Two scheduled captures that build point-in-time history we cannot reconstruct
later. Both exist for the Fantasy Sim (see
`docs/audits/2026-11-sim-projection-audit.md` section 4.4) and for recaps.
Neither changes any user-facing behavior.

## 1. Injury history (repo files, no database)

Before this, `data/players.db` held only the current `injury_status`,
overwritten every 30 minutes by `scripts/sync_injury_status.py`.

| What | Where | Written by | Cadence |
| --- | --- | --- | --- |
| Change events (player, status, injury designation, body part, practice status, week, timestamp, source) | `data/injury_history/events_<season>.csv` | `injury-status-sync.yml` (same run and commit as the players.db patch) | every 30 min, only when a tracked player's state **changed** |
| Snapshots of every tracked player that is not fully healthy | `data/injury_history/snapshots_<season>.csv` + `snapshot_index.csv` | same run | Tuesday 14:00 UTC and Friday 21:00 UTC, September to January |
| Official weekly NFL injury reports (practice status + game designation, all positions) | `data/injury_history/nflverse_reports_<season>.csv.gz` | `injury-history-ingest.yml` | Tuesday and Saturday 15:30 UTC; first run backfills 2021 to now |

How to read it:

- Tracked = QB/RB/WR/TE/K with a team (Sleeper's player dump). IDP is left out on
  purpose; widen `TRACKED_POSITIONS` in `modules/injury_history.py` if wanted.
- An event is written when `(status, injury_status, body_part, practice)` differs
  from the last recorded tuple. A **recovery is an event** (Active, empty
  injury fields), so an injury duration is the gap to the next event. A healthy
  player with no prior record writes nothing: silence means healthy.
- A player absent from a snapshot listed in `snapshot_index.csv` was healthy
  (not "not captured"). The index is the proof the snapshot ran.
- The nflverse file has the league's official report for each team/week:
  `practice_status` (for example "Did Not Participate In Practice"),
  `practice_primary_injury` (which includes reasons such as "Not injury related -
  resting player", which is how injuries are separated from rest/benching), and
  `report_status` (Out/Doubtful/Questionable). Rows carry `gsis_id` and a
  best-effort `sleeper_id` (exact GSIS match through Sleeper's dump, else a unique
  name+team+position match against the current dump; blank when unknown, about 75-95%
  for skill positions depending on the season). Join on `gsis_id` when you need
  certainty.
- Season in the filenames is the NFL league year from `modules/season_clock.py`.

Safeguards: a Sleeper dump under 2,000 players is ignored; a single run that would
write over 1,500 events (3,000 for the very first run) is discarded as a likely
poisoned dump; history capture is wrapped so it can never fail or alter the
players.db patch; nflverse files refuse to shrink by more than 20% and a finished
season under 2,000 rows fails the job (committed files stay untouched).

Size (measured 2026-11-12): one snapshot is about 19 KB (about 200 non-healthy
players), so two per week for roughly 21 weeks is about 0.8 MB/season; events are
about 0.5 MB/season after a 15 KB baseline; plain appends delta-compress in git.
nflverse files are 100-140 KB gzipped per season (about 670 KB for the 2021-2026
backfill); the in-progress season is rewritten when it changes (about 40 times a
year), so budget about 5 MB/year of git history for it. Total growth is roughly
7 MB/year, so files in the repo were chosen over a database table.

Licence/attribution: nflverse data is CC BY 4.0 ("Injury reports: nflverse
(nflverse.com)"). Sleeper data is the same public feed the app already reads.

Disable: set the repo variable `INJURY_HISTORY_DISABLE=1` (passed to the sync step;
the players.db patch is unaffected). To stop the nflverse ingest, disable the "Injury
History Ingest" workflow in the Actions tab. No secrets or variables are required for
either to run.

Local checks (never touches `data/players.db`):

```
python scripts/ingest_nflverse_injuries.py --dry-run     # fetch + validate, write nothing
python scripts/ingest_nflverse_injuries.py --no-push     # write files, no git
```

## 2. Weekly league roster snapshots (Supabase)

Table `public.league_roster_snapshots` (`docs/supabase_league_roster_snapshots.sql`).
Purpose: "what did every roster look like at week N" for the Sim's
start-of-season mode and recaps. Sleeper only exposes current rosters, so this
cannot be rebuilt afterwards.

- **What**: for every distinct saved Sleeper league (ESPN/Fleaflicker/MFL ids
  are skipped), one row per `(league_id, season, week, slot)` holding, per roster:
  Sleeper roster id, owner id, and player **ids only** split into starters, bench,
  IR (`reserve`) and taxi, plus the league's traded-pick ledger and draft rounds
  (picks owned = each roster's own picks, minus those traded away, plus those
  traded in; helper `picks_owned`). No names, values or scores.
- **When** (UTC): `post_waivers` Wednesday 12:17 (after Sleeper's default
  waiver run, so the week's adds/drops have settled) and `pre_kickoff` Sunday
  15:17 (lineups set before the 1pm ET kickoff; regular season/playoffs only).
  Off-season and pre-season snapshots use week 0 and only the Wednesday slot, so
  a dynasty league's off-season rosters are recorded too.
- **Dedupe**: each row has a `content_hash`; a league identical to its previous
  snapshot **in the same season** is stored with `unchanged = true` and no
  document (about 150 bytes). Readers carry the earlier document forward.
  Dedupe never crosses a season, so pruning old seasons cannot orphan rows.
- **Reading** (backend, service role only): `modules.league_roster_snapshots`
  - `get_roster_snapshot(league_id, season, week, slot=None)` returns the
    snapshot in effect at or before that point (`exact` says whether that
    week itself was captured; never fabricates a roster).
  - `get_season_start_snapshot(league_id, season)` for the Sim's start-of-season
    mode (first week 1 `pre_kickoff`, else first week 1, else the week 0 one).
  - pure `resolve_roster_snapshot(rows, season, week, slot)` /
    `resolve_season_start(rows, season)` / `picks_owned(...)` for callers that
    already hold the rows.
- **Scale and politeness to Sleeper**: 3 calls per league (league, rosters,
  traded picks; `--no-picks` drops one), all through `modules.sleeper`, which
  already uses the shared `sleeper_cache`, retry/backoff and call budget. On top:
  a call throttle (default 300 calls/min per shard), stable-hash sharding across
  parallel jobs, a per-run time budget (default 40 min) with a visit order that
  rotates weekly so a cut-off run starves nobody, resumability (leagues already
  recorded for this slot are skipped on a re-run), and a circuit breaker that
  stops after 15 consecutive failed fetches (and fails the job). A league id Sleeper
  has rolled over to a newer season is skipped in season (the saved-league rollover
  resolver moves the account to the new id).
- **Size estimate** per 1,000 saved leagues: about 44 slots a year; unchanged rows
  about 150 B; a changed row about 2-4 KB (12 rosters of ids, jsonb). If a third of
  slot-rows change, that is about 40-50 MB/year per 1,000 leagues, so retention
  matters: keep 3 seasons (default), then older seasons are deleted.
- **Retention**: the weekly job (shard 0) calls
  `prune_league_roster_snapshots(keep_seasons => 3, orphan_grace_days => 120)`,
  which drops seasons older than the window and snapshots of leagues no account
  has saved for 120+ days. That is also how deleting an account (which cascades
  its `saved_leagues` rows) eventually clears a league nobody else saved.

Privacy: nothing beyond what we already store or Sleeper publishes: league id,
Sleeper roster/owner ids (public on Sleeper) and player ids. No `user_id`,
username, email, token or Sleeper username is written. The table has RLS on with no
policies and all client privileges revoked; only the service role (the sweep, the
backend) can touch it. Readers must apply the normal league-membership check before
returning a snapshot to a client.

Run / test by hand (read-only first):

```
python scripts/run_league_roster_snapshot.py --dry-run --limit 20
python scripts/run_league_roster_snapshot.py --slot post_waivers --prune
```

### Owner actions

1. Apply `docs/supabase_league_roster_snapshots.sql` in the Supabase SQL Editor
   (idempotent). Until then the weekly job fails (and opens an issue).
2. Secrets `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` already exist; nothing new.
3. Optional repo variables: `ROSTER_SNAPSHOT_SHARDS` (default 1),
   `ROSTER_SNAPSHOT_TIME_BUDGET_SECONDS`, `ROSTER_SNAPSHOT_MAX_CALLS_PER_MINUTE`,
   `ROSTER_SNAPSHOT_RETENTION_SEASONS`.
4. **Disable**: set repo variable `ROSTER_SNAPSHOT_DISABLE=1` (job exits 0 without
   work) or disable the "League Roster Snapshot" workflow. Existing rows stay until
   pruned; to erase everything run `truncate public.league_roster_snapshots;`.

Per-league diagnostics: every failed league is listed in the summary `errors` as
`<truncated id>: <reason>` and every skip in `skipped_leagues`, and both are printed to
the log. Reasons: `league_not_found` (deleted/never existed: skipped, not a failure, no
alert), `season_mismatch_previous_season_league` (id Sleeper rolled over; skipped),
`sleeper_http_<code>`, `sleeper_unreachable`, `sleeper_fetch_failed_transient`,
`rosters_empty`, `league_season_unreadable`, `exception:<Type>` (these count as failures).

Failure alerts: both new workflows open (and later close) a tracking issue like the
Advanced Stats Refresh does. They are deliberately not in
`scripts/ops_health_check.py`'s freshness list: that check reads only the newest
100 successful runs of all workflows, which the 30-minute jobs fill within a day,
so a weekly workflow would always look "missing".
