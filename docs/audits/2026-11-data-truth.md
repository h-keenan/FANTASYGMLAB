# Data truth audit, November 2026

Date: 2026-11-19. Production build sampled: `1cde92ebd78d` (api.fantasygmlab.com/health, 2 commits behind main).
Scope: does what users see match the public source APIs, how old is it, and does the screen say so.
Public endpoints only, no secrets, no calls into `rankings.load_players` / `build_players_table`; the committed
`data/players.db` was opened read-only with sqlite and production was read through its unauthenticated
`/v1/public/*` routes. Sources used: FantasyCalc `values/current` (1QB and 2QB), DynastyProcess `values-players.csv`,
Sleeper `players/nfl`, nflverse `games.csv`, Fantasy Football Calculator ADP API, and the repo's own workflow run
history (`gh run list`). Valuation math is out of scope (owned elsewhere): valuation discrepancies are listed for
those owners, nothing here changes them.

Not verifiable without secrets, said plainly: college prospect rows (the CFBD key gates the source and the
`/v1/scouting/prospects` route needs a Pro login) and stored ADP snapshots (Supabase). For those the audit checks the
ingest code, the committed status file and the public freshness report instead.

## Ranked findings

| # | Sev | Finding | Fix status |
|---|---|---|---|
| 1 | P0 | The FantasyCalc input to the committed `players.db` is the July 10 seed CSV, not live FantasyCalc. 364 of 364 name-matched `fantasycalc_value` rows equal the July CSV exactly; against live FantasyCalc (1QB dynasty, PPR, 12 teams) only 52 of 348 id-matched players are within 10% (median ratio 1.23). | Fixed: `DYNASTYGM_FRESH_PROVIDER_CACHE_V1` (#2186, flipped to default ON after the live harness, section 10) |
| 2 | P0 | The public freshness report (`/v1/public/data-freshness`, which the ops watchdog reads) measures file mtimes. In a git deploy every file's mtime is the checkout time, so five datasets (FantasyCalc values, depth charts, injury history, advanced stats, players directory) all report `as_of 1795073009`, "0.1h old", regardless of the data inside. Finding 1 was invisible to it. | Fix PR, same flag |
| 3 | P1 | GitHub-hosted schedules run hours late, so "every 30 min" jobs are really every 6 to 9 hours (table below). Injury status, news and the players rebuild trail their advertised cadence by 12x to 36x. | Documented, needs an external trigger (owner) |
| 4 | P1 | 18 data-bearing surfaces never say how old their numbers are (list below). Only Matchup live scores, the ADP credit, public rankings pages, the Sim banner and the prospect sheet do. | Fix PR: one shared `FreshnessLabel`, web and app |
| 5 | P2 | Valuation discrepancies (report only): our public board vs FantasyCalc live rank, top 150: Spearman 0.83, vs DynastyProcess 0.80. Outliers below. | Reported, not changed |
| 6 | P2 | `modules/fantasycalc.py` transformation bugs: `team` is read from `player.team`, but FantasyCalc sends `maybeTeam`, so the cache `team` column is blank for every row; `value or trade_value or overallRank` would store a rank number as a value if `value` were ever 0 or missing; a 4s timeout silently falls back to a cache of any age with no staleness signal. | Fix PR with tests |
| 7 | P2 | ADP: the FFC window is closed and empty (`start 2026-09-05`, `end 2026-10-05`, `players: []`, 2027 returns "Invalid year"). The ops report shows `warn: no ADP snapshot stored`. Nothing is invented, but there is no "as of" when an older snapshot is shown, other than the credit line. | Reported; credit line already carries `as of` |
| 8 | P3 | College prospects: ingest succeeded today (18:57Z, 832 class rows upserted, 12.5h old at audit time) after three failed manual dispatches (17:40, 18:03, 18:30). The status file records `game_log:HTTPError` and `slow: true`. The prospect list has no "as of"; the sheet prints a raw `as_of` string. | Freshness label covers the list |
| 9 | P3 | Projections: replay scoreboard (docs/projection-scoreboard.md, weeks 2 to 10) shows our MAE 5.88 vs Sleeper 5.61 on relevant players, bias -0.39, 68% interval coverage 65.8%. Projection rows carry no "as of". | Label covers projection surfaces |

Confirmed correct (no action): injury status, team, position, age, schedule and byes (details below).

## 1. Player values (FantasyCalc and DynastyProcess)

Samples: 348 id-matched players (committed DB, field `fantasycalc_value`), 326 players (production
`/v1/public/dynasty-values`, format 1QB, PPR, 12 teams, Dynasty lens), plus a 45-player spread sample of the DB `value`
column (top 15, every 6th of the next 120, 10 random from ranks 200 to 600).

- Committed DB vs live FantasyCalc: Tutu Atwell 94 vs 266, Malik Benson 365 vs 64, Tank Bigsby 1399 vs 805, Will Kacmarek
  114 vs 29, Adam Randall 886 vs 576, Ja'Marr Chase 9842 vs 9076. The DB values are the July CSV: `Ja'Marr Chase,WR,,9842`.
- Root cause: `modules/fantasycalc._load_cache` decides freshness from the CSV's mtime (6h TTL). The players refresh job
  starts from a fresh git checkout, so the July CSV looks 0 seconds old, `get_dynasty_values()` returns it without ever
  calling FantasyCalc, and the job commits a `players.db` built from it. The CSV's own schema proves it: it has
  no `sleeper_id` / `mfl_id` columns that the live fetch writes. `git log` shows the CSV unchanged since 2026-07-10 in
  spite of the 6-hourly refresh job committing `players.db` throughout. A running box refetches once its copy is more than 6h old, so production
  recovers on its own after each deploy; the committed DB and the first hours after every deploy do not.
- Production sample is much healthier: teams match FantasyCalc 326 of 326; board order vs FantasyCalc top 150,
  Spearman 0.833, vs DynastyProcess 0.803.
- Valuation discrepancies for the valuation owners (our public rank vs FantasyCalc overall rank): Puka Nacua 61 vs 7
  (DynastyProcess value 8907), Jeremiyah Love 85 vs 15, Matthew Golden 73 vs 17, Lamar Jackson 141 vs 63, Ashton
  Jeanty 11 vs 22 (we are higher), Trey McBride 7 vs 11, Dallas Goedert 79 vs 160, Davante Adams 233 vs 93, Ollie
  Gordon II 210 vs 87, Theo Johnson 197 vs 371, Jaydon Blue 209 vs 367. Raw DB `value` column outliers (not what the
  public endpoint shows): Brandon Aubrey (K) 7252, Brian Robinson Jr. 7607 vs FantasyCalc 637, Chris Godwin Jr. 7350
  vs 806, Derrick Henry 9827 vs 2650. Some gaps are intended (retool lens, injury and age adjustments); nobody should
  assume so without the owners confirming.

## 2. Injury status (Sleeper and nflverse)

- Committed DB vs live Sleeper `players/nfl`: `injury_status` 1826 of 1826 rows equal; `status`, `team` and `position`
  427 of 427 sampled equal.
- Production public values vs Sleeper: 326 of 326 equal, 74 of them carrying an injury designation.
- Ages: DB age equals the birth-date age for all 1826 players. Sleeper's own `age` field is stale for 7 of 427
  sampled (Tyler Boyd 30 vs real 32); we are right and Sleeper is wrong.
- Staleness is the issue, not accuracy: `injury-status-sync.yml` is cron `*/30`; its last four runs were 01:24Z,
  19:18Z, 10:34Z and 02:16Z (6 to 9 hours apart). The ops threshold for `players_db_and_injury_status` is 4h in season,
  but that check reads the file mtime (finding 2), so it cannot fire. The nflverse injury history job (`injury-history-ingest`,
  Tue and Sat 15:30Z) fed `data/injury_history`; it ran Tue 23:04Z and Sat 19:59Z, 7.5h and 4.5h late.

## 3. ADP

FFC `adp/rookie` and `adp/dynasty` for 2026: `status Success`, `total_drafts 61` and `62`, `start_date 2026-09-05`,
`end_date 2026-10-05`, `players: []`. Year 2027: `Invalid year`. `parse_payload` keeps only rows with a positive ADP and
a QB/RB/WR/TE position, matching the FFC schema, so the code is consistent with the source. Production reports
`adp_rookie_dynasty: warn, no ADP snapshot stored`. Every ADP surface that exists uses `AdpCredit` (`as of <date>`) and
hides when there is no source, which is the honest behaviour. No sample of 30 to 50 is possible: there is nothing
to sample. Superflex ADP is estimated from FantasyCalc ratios (`estimate_sf_adp`) and is labelled as such in code.

## 4. College prospects

- Ingest runs only Mondays (cron) plus manual dispatch; today's run (18:57Z) was a `workflow_dispatch` after three
  failures, `classes: fetched 832, upserted 832`, `retire: 514 seen, 0 retired`, `stats: 14 calls, game_log:HTTPError`,
  CFBD calls 597 of 1000 this month.
- Seed file `data/college_prospects_2027.json` (192 rows): positions QB 33, RB 55, WR 65, TE 39, no duplicate
  (name, school), every row carries a roster URL and a `verified_on` date; class labels are 21 different spellings
  (`Sr.`, `R-Sr.`, `5TH YR`, `Redshirt Junior`...), all of which `draft_year_for` handles through the CFBD recruiting year,
  not the label. `draft_year_for` (season + max(1, 4 - class year)) is consistent with the 2027 class here.
- Not compared against CFBD (needs the secret). Recommendation: when the owner runs the ingest locally, diff 40 rows
  against the school roster pages; the seed file already stores that URL per row.

## 5. Schedules and byes

nflverse `games.csv`, 2026 regular season: 272 games, weeks 1 to 18. Independent bye derivation (the one week with no
game for a team) against `modules.nfl_schedule.team_bye_week`: 32 of 32 teams equal. Kickoff conversion
(`gameday` + Eastern `gametime` to UTC) is right across the DST boundary (2026-11-25 20:00 ET to 2026-11-26T01:00Z).
`LA` is aliased to `LAR` correctly. Disk TTL is 6h (`nfl_games.csv`, fetched at runtime, so mtime is honest here).

## 6. Projections

`docs/projection-scoreboard.md` (weekly Tuesday job, last run 2026-11-17T20:11Z, 8h after its 12:00Z slot): relevant
players n=1548, our MAE 5.88, Sleeper 5.61, season average 6.28, start/sit 62.6% vs Sleeper 65.0%. It does not replay
injuries (documented). Production `weekly_stats`: all weeks 1 to 11 present, self-heal ok. Projection numbers on Matchup,
My Team and Waivers have no timestamp.

## 7. Scheduled data jobs: advertised vs observed

| Job | Advertised cadence | Last four starts (UTC) | Observed |
|---|---|---|---|
| injury-status-sync | every 30 min | 11-19 01:24, 11-18 19:18, 10:34, 02:16 | 6 to 9h |
| news-ingest | every 15 min | 11-19 01:11, 11-18 19:06, 10:43, 02:30 | 6 to 9h |
| players-db-refresh | every 6h | 11-19 07:10, 11-18 23:58, 15:15, 00:40 | 7 to 8h |
| advanced-stats-refresh | hourly windows after games | 11-19 03:43, 01:52, 11-18 18:55, 17:14 | ok around games |
| player-rating-snapshot | daily 07:00 | 11-18 16:10, 11-17 16:41, 11-16 16:45 | about 9h late |
| rookie-adp-snapshot | daily 08:00 | 11-18 16:48 | 8.8h late, stores nothing off-window |
| injury-history-ingest | Tue and Sat 15:30 | 11-17 23:04, 11-14 19:59 | 4.5 to 7.5h late |
| projection-scoreboard | Tue 12:00 | 11-17 20:11 | 8h late |
| college-prospect-ingest | Mon 09:00 | only manual dispatches today | 3 failures then success |

## 8. Surfaces missing an "as of" (web `web-next/src/components/*Content.tsx`, mobile twins)

Dashboard, My Team, Players list, Player profile, Player compare, Trade Analyzer, Trade Finder, Trade Hub, Trade Offer,
Multi-team trade, Waivers, League rankings, Draft Center, College Scouting list, GM Plan, Portfolio, News (items
carry no source timestamp line), and the Player Quick View values and injury blocks (only its ADP line has one).
Already labelled: Matchup live scores (`Updated 3m ago`), `AdpCredit`, public rankings/player pages (`formatUpdated`),
Sim scope line, Sim real history, prospect sheet (raw string).

## 9. Fix plan and what shipped

- Shared freshness (one component, web `components/ui/FreshnessLabel.tsx`, app `components/FreshnessLabel.tsx`, one
  helper pair `lib/dataFreshness.ts`): "Values as of 2h ago", "Injuries updated 9:40am", gentle muted "may be behind" wording
  when over threshold (never red). Wired into the highest-traffic surfaces first; the remainder is the follow-up list above.
- `modules/fantasycalc.py`: sidecar `fantasycalc_values.meta.json` (fetched_at), team and value fixes, tests.
  The TTL change is `DYNASTYGM_FRESH_PROVIDER_CACHE_V1`, shipped OFF in #2186 and flipped to default ON (kill switch `=0`)
  after the live harness below. Harness: `scripts/audits/fantasycalc_freshness_harness.py`.
- `modules/data_freshness.py`: uses the sidecar timestamp for FantasyCalc when the flag is on.

## 10. Follow-up: live FantasyCalc drift (run 2026-11-19, public API only)

Committed July seed CSV (463 rows) vs a live fetch (`values/current`, dynasty, 1QB, PPR, 12 teams) through the fixed
`get_dynasty_values()` on a throwaway directory.

Payload checks, all pass: 423 rows; positions WR 156, RB 108, QB 71, TE 64, PICK 24; value range 10 to 11181, no nulls,
no non-positive values; no duplicate (name, position); `team` is now filled (29 blank, all picks and free agents);
`sleeper_id` present on every row; as_of stamped at fetch time. 331 of the 463 seed names match a live row (the other 132
are July-only names: drafted rookies whose name form changed, e.g. "Kenneth Walker" is now "Kenneth Walker III", and old pick rows).

Drift on the 331 matched players: absolute change median 351, p90 1094, mean 496; relative median 35%, p90 95%.

Top 20 movers (seed to live): Ashton Jeanty RB 7932 to 4392, Omarion Hampton RB 6302 to 2966, Matthew Golden WR 1922 to
5015, De'Von Achane RB 6333 to 4058, Jeremiyah Love RB 7469 to 5263, Christian Watson WR 2263 to 4375, TreVeyon Henderson RB
4191 to 2084, Parker Washington WR 2014 to 4109, Bhayshul Tuten RB 2466 to 4284, A.J. Brown WR 3685 to 1909, Chuba Hubbard RB
2059 to 3682, Quinshon Judkins RB 4286 to 2703, Emeka Egbuka WR 4495 to 2941, Isaiah Likely TE 1800 to 3307, Jonah Coleman RB
1965 to 3450, Saquon Barkley RB 4186 to 2728, Puka Nacua WR 8489 to 7050, Bucky Irving RB 3441 to 4842, Ladd McConkey WR 3758 to
2376, Caleb Douglas WR 605 to 1950.

Top 50 board: 32 of 50 names carry over (a few of the 18 "changes" are name-form changes). Biggest rank moves seed to live:
Matthew Golden 118 to 17, Isaiah Likely 135 to 47, Parker Washington 109 to 30, Jonah Coleman 114 to 42, Christian Watson 90 to 24,
Chuba Hubbard 103 to 39, Bhayshul Tuten 85 to 25, Brock Purdy 87 to 40, D'Andre Swift 89 to 44, Bucky Irving 52 to 18. Left
the top 50: Omarion Hampton, Emeka Egbuka, Quinshon Judkins, Tyler Warren, TreVeyon Henderson, Saquon Barkley, Jayden Daniels,
Lamar Jackson, Ladd McConkey, A.J. Brown, Rashee Rice, Marvin Harrison Jr, Cam Skattebo and three 2026 pick rows. Entered:
Matthew Golden, Bucky Irving, Luther Burden III, Christian Watson, Bhayshul Tuten, Parker Washington, Tee Higgins, Zay Flowers,
Javonte Williams, Chuba Hubbard, Brock Purdy, D'Andre Swift, Isaiah Likely, Trevor Lawrence, Jonah Coleman.

Correction to finding 5: the July seed does NOT explain Puka Nacua at 61. FantasyCalc had him at rank 5 in July and has him at 7
live; our `players.db` carries him at `fantasycalc_value` 8489 with `injury_status` IR, and Jeremiyah Love is also on IR. Those two
low ranks are the model's injury discount, not stale input. Matthew Golden (FantasyCalc 1922 in July, 5015 live; our public
rank 73 vs FantasyCalc 17) is the real stale-input case.

No parse anomalies: no empty payload, no missing position, no wild range. Two observations: `PICK` rows are part of the payload
and of the seed (consumed by the pick valuation, unchanged); and the live list is shorter than the seed (423 vs 463) because the
seed carried long-tail names FantasyCalc no longer lists.

### Who writes `players.db` and does the box serve it

- Writer: `.github/workflows/players-db-refresh.yml` (cron `0 */6 * * *`, in practice every 7 to 8h) runs
  `scripts/refresh_and_commit_players_db.py`, which rebuilds `data/players.db` and commits it, with the sibling caches
  `sleeper_players.json`, `fantasycalc_values.csv` and `depth_chart_snapshots.json`, to `main` as "chore(data): scheduled
  players.db refresh". `.github/workflows/injury-status-sync.yml` commits the injury-only patch as "chore(data): scheduled
  injury-status sync".
- Box: `fantasygmlab-autopull.timer` (server side, `docs/SELF_HOSTED_MIGRATION.md` 5.7) polls `origin/main` about every 2 minutes,
  fast-forwards, rebuilds and recreates the stack. The image does `COPY . .` (the build context excludes the repo history), so each
  deploy ships that committed `data/players.db`. At runtime `startup_cold_path.load_persisted_players` serves the persisted file and
  only queues a background rebuild when the Sleeper cache is stale; the hot path recomputes injury and role stages "without provider
  calls". So yes: the box serves the committed file, and the committed file carried July FantasyCalc values (finding 1).
- Does the box refetch FantasyCalc at runtime? Possibly inside a queued in-container rebuild: Docker `COPY` keeps the source
  file's mtime, and on the box an unchanged CSV keeps its original (old) mtime, so the legacy check would expire and refetch.
  That result lives in the container and is discarded at the next autopull recreate (at least every data commit). This cannot be
  confirmed without box access. The production evidence (Golden at 73 where live FantasyCalc says 17; production board
  correlates 0.860 with live and 0.825 with July) says the stale file dominates what users see. Either way, with the flag on
  the refresh job itself now commits live values.

## 11. Follow-up: scheduling the 15 and 30 minute jobs (for coridian_ box cron and Zach)

Problem (section 7): GitHub schedules run 6 to 9 hours late. Two jobs matter most: `news-ingest` (every 15 min) and
`injury-status-sync` (every 30 min).

**Box layout (corrected 2026-11-19).** Releases run from `/var/lib/fantasygmlab/releases/`. `/opt/fantasygmlab` is an
OLD checkout with a stale compose file. Do not use it. A `deploy` user may not exist. The lines below target the running
API container directly, so they need no compose file or checkout path, and run from root's crontab (or the box's actual
cron user if coridian_ uses another one).

Where each can run:
- `news-ingest` runs `python scripts/ingest_news.py --require-durable`. It needs only `SUPABASE_URL` and
  `SUPABASE_SERVICE_ROLE_KEY`, which the running API container already has in its environment, and it writes to Supabase, not
  the repo. So it can run inside the running API container with `docker exec`.
- `injury-status-sync` runs `python scripts/sync_injury_status.py`, which patches `data/players.db` and **commits and pushes to
  `main`** (needs `GITHUB_PUSH_TOKEN`). It must not run in the container or in any deploy/release directory. Trigger the GitHub
  workflow instead (Option B).

Recommendation: box cron for `news-ingest` (Option A), and a cron `curl` that triggers the existing `injury-status-sync`
workflow with `workflow_dispatch` (Option B). A dispatched run starts within about a minute, where a `schedule` trigger is
throttled. Both are free.

One-time setup on the box (as root):

```
install -d -m 755 /var/log/fgl
# Check the container filter matches exactly one running API container:
docker ps --filter name=mobile-api --format '{{.ID}} {{.Names}}'
```

If the API container has a different name, use that name in the `--filter` below. Add a logrotate stanza for
`/var/log/fgl/*.log` (weekly, rotate 4, compress).

Option A, news ingest every 15 min (root crontab via `crontab -e`, or `/etc/cron.d/fantasygmlab-jobs` with a `root` user
column). `flock -n` stops overlapping runs. The container reads its own secrets, nothing is echoed, and only output is logged:

```
*/15 * * * * flock -n /var/lock/fgl-news.lock sh -c 'C=$(docker ps -qf name=mobile-api | head -n1); [ -n "$C" ] && docker exec "$C" python scripts/ingest_news.py --require-durable || echo "no mobile-api container"' >> /var/log/fgl/news-ingest.log 2>&1
```

(In `/etc/cron.d/` format, insert `root` after the five time fields.)

Option B, injury sync every 30 min via workflow dispatch. Create a fine-grained PAT with only `actions: write` on this repo
(Zach confirms the scope). Store it as `GITHUB_DISPATCH_TOKEN=...` in `/etc/fgl-cron.env` (`chmod 600`, owner root).
`set -a; . file; set +a` loads it without printing it, so do not add `set -x`:

```
*/30 * * * * sh -c 'set -a; . /etc/fgl-cron.env; set +a; curl -fsS -o /dev/null -w "\%{http_code} injury\n" -X POST -H "Authorization: Bearer $GITHUB_DISPATCH_TOKEN" -H "Accept: application/vnd.github+json" https://api.github.com/repos/h-keenan/FANTASYGMLAB/actions/workflows/injury-status-sync.yml/dispatches -d "{\"ref\":\"main\"}"' >> /var/log/fgl/dispatch.log 2>&1
```

Success is HTTP 204, and the log holds only the status code and the job name. In a crontab a bare `%` means newline, so it must be written `\%` (as above), and the lines deliberately avoid `date +%...`. Before relying on Option A, test once
by hand: `docker exec $(docker ps -qf name=mobile-api | head -n1) python scripts/ingest_news.py --require-durable`. Both
workflows already have `workflow_dispatch:` and a `concurrency` group, so an overlapping dispatch queues instead of racing.
Keep the GitHub `schedule:` triggers as the fallback if the box is down. Duplicate runs are harmless (concurrency group,
idempotent upserts, no-diff commits are skipped).

Why not the alternatives: a third-party scheduler adds an external account holding a GitHub token, and Supabase `pg_cron` could
call the dispatch endpoint but needs the token stored in the database. Box cron is free, already trusted with the same secrets
and the easiest to inspect. Owners: coridian_ (box) installs the lines; Zach confirms the token scope.

## Needs from the owner

1. Install the box cron lines in section 11 (Option A for news, Option B for injury sync) and create the dispatch token.
2. Decision on whether the prospect ingest should also be cron-driven daily in the fall (CFBD budget 597 of 1000).
