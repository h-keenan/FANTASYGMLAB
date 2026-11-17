# Dependency risk, data freshness and independence plan (2026-11-17)

Scope: (1) the Pat Bryant weekly-stats finding, (2) an inventory of every scheduled sync and how we
would notice it breaking, (3) every external dependency with its failure behaviour, (4) a plan, with
no migration, for owning more of our data. Engineering read of public terms and of this repo, not legal
advice. Terms change: re-verify any licence line before relying on it. Nothing here needed a new
account, key or paid service; the things that would are in "Needs from the owner" at the end.

## 1. Pat Bryant (Sleeper 12492, WR DEN, 2026): what the gap actually was

Checked against live Sleeper `/stats/nfl/regular/2026/{1..12}` on 2026-11-17:

| Weeks | Sleeper says | Our chart showed |
|---|---|---|
| 1-4, 9 | `gp: 1`, real points | points |
| 5-8 | row present (`gms_active: 1`) but **no `gp`**: team played, he did not appear (healthy scratch, WR3, `depth_chart_order` 3) | "no data" |
| 10 | no row for anyone on DEN: **bye** | nothing |
| 11 | empty payload: games not played yet | nothing |

So Sleeper's data is complete and correct. The defect was ours: `_aggregate_player_week_stats` kept only
rows with stat values, so a confirmed non-appearance was indistinguishable from a failed fetch, and the
chart then bridged those weeks with a dashed line (reading as a projection) and stopped at the last
played week. "Healthy, 0 games missed" is consistent: injury-based counters never saw a miss.

Scale (2026 weeks 1-10): 2,081 players have at least one game. 641 of them have at least one listed
non-appearance week, and 153 players (448 player-weeks) have such weeks between games they did play, i.e.
the same "hole" Bryant had.

Separate latent risk found while tracing it, now fixed: a rebuild in which some week fetches failed
(timeout, 429) was written as the season aggregate and trusted for the full TTL (12 h in season, 30 days
after the regular season, 180 days for prior seasons) with no record of which weeks were missing. Fixes:
completeness manifest per season file, partial builds retried every 10 min, a rebuild that obtained fewer
weeks never replaces a more complete cache, `[]` (unplayed week) is a real empty week not a failure.
Backfill: `python scripts/backfill_weekly_stats.py` on the host that owns `data/`.

Chart rule now (web + mobile twins): only bye / injured / provider-confirmed-inactive weeks are bridged
with a dashed line; "missing" is a break with an x marker and caption "x: no data"; the axis runs to the
current week; the week in progress is open axis, not a gap.

## 2. Scheduled sync / ingest inventory

Alert channel that already exists: `.github/workflows/ops-health-check.yml` (every 20 min) runs
`scripts/ops_health_check.py`; any failing check opens or comments on the issue "Ops health check is
failing" and posts to `OPS_ALERT_WEBHOOK_URL` if that secret is set. Several workflows also open their own
issue on failure. GitHub schedules often run hours late, so thresholds are wider than cadence. "Last
success" is not stored in the repo: the ops report prints it live (it reads Actions run history), so it
is recorded here as "ops report".

| Dataset | Producer | Cadence | Staleness detection (before) | Failure mode | Added |
|---|---|---|---|---|---|
| Weekly stats (Sleeper) | `modules/sleeper.get_season_player_stats`, on demand | 12 h TTL in season; no cron | none | partial week set persisted as fresh; returns old cache if all weeks fail | completeness manifest, `weekly_stats` freshness row (fails on missing expected weeks) |
| Player directory / injury status | `players-db-refresh.yml` (6 h), `injury-status-sync.yml` (30 min), app cache 5 min | 6 h / 30 min | ops: workflow age (14 h / 4 h) | stale injury status up to the threshold; app serves last-known | `players_directory`, `players_db_and_injury_status` rows (file age) |
| Dynasty values (FantasyCalc) | `modules/fantasycalc` on demand, committed by the 6 h refresh | 6 h TTL | ops: `public_values_fresh` (36 h) | expired cache + provider down returned **empty** frame | stale-on-error fallback with `as_of`; `values_fantasycalc` row |
| Depth charts | snapshot appended by the 6 h refresh | 6 h | none | stale snapshot | `depth_charts` row |
| Injury history | `injury-history-ingest.yml` (nflverse) | Tue, Sat 15:30 UTC | own failure issue | issue on failure | `injury_history` row |
| Schedule | `modules/nfl_schedule`, nflverse CSV, on demand | 6 h TTL | none | serves stale CSV on error (tested) | `schedule_nflverse` row |
| Advanced usage stats | `advanced-stats-refresh.yml` (nflverse) | hourly windows Fri-Tue after games, 2x daily | own failure issue | issue on failure, commits nothing bad | `advanced_stats_nflverse` row |
| News | `news-ingest.yml` | every 15 min | ops: `News Ingest` age 9 h, news freshness | stale headlines | unchanged |
| Rating snapshots | `player-rating-snapshot.yml` | daily 07:00 UTC | ops: 36 h | gaps in history charts | unchanged |
| Push triggers | `push-trigger-sweep.yml` | 30 min | ops: 9 h | missed notifications | unchanged |
| Trade outcome results | `trade-outcome-result-sweep.yml` | daily 13:00 UTC | ops: 36 h | outcomes lag | unchanged |
| League roster snapshots | `league-roster-snapshot.yml` | Wed 12:17, Sun 15:17 UTC | own failure issue | issue on failure | unchanged |
| Projection scoreboard | `projection-scoreboard.yml` | Tue 12:00 UTC | none | stale accuracy page | out of scope |

New check: `GET /v1/public/data-freshness` (no auth, never fetches, reads local files and the weekly-stats
manifest, `modules/data_freshness.py`). `ops_health_check.py` turns each failing dataset into a failing
check, so a sync that stops, or weekly stats that come back with missing weeks, raise the existing issue
and webhook. Off-season, file-age failures relax to warnings (14 days).

Known remaining gaps: depth-chart and schedule checks are file-age only (no "every team present"
check); "weekly stats exist for every played week for every active rostered player" is enforced per week
(every expected week obtained, no week with implausibly few player rows), not per rostered player.

## 3. External dependency inventory

Reliance: H = product unusable or materially wrong without it, M = a feature degrades, L = cosmetic.

| Dependency | Used for | If down | If slow | If garbage | Reliance | Rate limit | ToS / commercial risk | Cached? |
|---|---|---|---|---|---|---|---|---|
| Sleeper API `api.sleeper.app` | users' leagues, rosters, matchups, transactions, player directory, weekly stats | league screens degrade to last-known; stats/directory from disk | 5 s timeout, 2 retries, last-known served | **was: a 200 with a non-JSON body raised into the request; now returns last-known / None** | H | documented guideline of staying under 1,000 calls/min or risking IP block; we self-limit via `sleeper_budget` (default 1000/min, soft 70%) | public read-only API, no written commercial licence; they can change or block it at will | yes: `sleeper_cache` (Redis + local), `sleeper_budget.last_known`, disk files |
| FantasyCalc `api.fantasycalc.com` | market component of dynasty values | **was: empty values once the 6 h cache expired**; now stale values + `as_of` | 4 s timeout then stale | now rejected, never overwrites cache | H (valuations, trade grades) | none published | their terms require attribution (we credit them); commercial redistribution of derived values needs their OK | disk CSV, 6 h TTL |
| nflverse (GitHub releases, `nfldata` CSV) | schedule, injuries history, advanced usage, contracts | stale file served | job retried | validation before commit | M | GitHub release CDN, effectively none | CC BY 4.0 (attribution done); upstream NFL data rights are a residual risk, see `docs/advanced-stats-licensing-2026-11.md` | committed / on disk |
| Supabase (auth, Postgres, storage, billing Edge Functions) | login, saved leagues, GM state, push tokens, billing | **no login or billing; no fallback** | login spinner | n/a | H | plan limits | standard SaaS | session tokens client-side only |
| Redis (self-hosted container) | cross-worker single-flight cache, Sleeper budget counter | falls back to per-process cache (5 s cooldown) | same | n/a | M | n/a | none | n/a |
| Self-hosted box (docker compose, Caddy) | everything server-side | **total outage**; single host | n/a | n/a | H | n/a | none | autopull deploy, previews gated |
| Stripe / RevenueCat | web / in-app billing | cannot purchase; existing entitlements remain | n/a | webhook signature checks | H for revenue | provider limits | standard; Apple/Google store rules apply | n/a |
| Apple / Google sign-in | mobile auth options | that option unavailable, email login remains | n/a | n/a | M | n/a | store policy: Apple requires Sign in with Apple if other social logins exist | n/a |
| Sentry (`@sentry/react-native`, `@sentry/browser`, backend `SENTRY_DSN`) | error reporting | no error visibility | n/a | n/a | L (but blind without it) | plan quota | note: `DEPENDENCIES.md` still says "no Sentry"; update it | n/a |
| Sleeper CDN `sleepercdn.com` | avatars / headshots | initials fallback (`avatarFallback`) | images pop in | broken image handler | L | n/a | hotlinking another company's CDN and player photos we do not hold rights to; the real exposure | browser |
| News RSS (Rotowire, ESPN, CBS, Yahoo, PFT, PFR) | headline feed | news stale | 20 min cache | parse guarded | M | polite polling | headlines/links only; feed terms generally personal/non-commercial: re-verify; we do not fetch article bodies | 20 min disk |
| Expo / EAS / App Store Connect | builds, push delivery (`exp.host`) | no new builds / pushes | n/a | n/a | M | EAS plan queue | standard | n/a |
| LLM providers | none in the backend (`DEPENDENCIES.md`, grep of `modules/`, `services/`) | n/a | n/a | n/a | none | n/a | n/a | n/a |
| ESPN / Yahoo / MFL / Fleaflicker adapters | importing users' non-Sleeper leagues | that platform's import fails | n/a | n/a | L | per platform | ESPN and Yahoo APIs are unofficial or OAuth-gated | n/a |

### Top 5 risks, ranked

1. **Sleeper is both the users' league source and our stats/directory source.** No contract, can throttle
   or change shape. Mitigated by cache and last-known; the garbage-200 hole is now closed.
2. **FantasyCalc is the market leg of every valuation** with attribution-only terms and no stated
   commercial licence. Stale-on-error added; no second market source exists.
3. **One self-hosted box.** Compose, Redis, Caddy, deploy timer all on one host: total outage on host loss.
4. **Supabase is a hard dependency for login and billing with no degraded mode.**
5. **Player photos and news feeds** rely on terms we have not secured in writing (Sleeper CDN images,
   RSS headlines). Low probability, but a takedown is binary.

### Degradation contract (enforced by `tests/test_provider_fault_injection.py`, runs in CI)

For Sleeper, FantasyCalc and the nflverse schedule, each of: down (connection error), slow (timeout),
HTTP 5xx/429, garbage body (HTML, wrong JSON shape, empty list):
no exception escapes into a request; last-known-good data is served when it exists; garbage never
overwrites good data on disk; FantasyCalc exposes `df.attrs["as_of"]` and the weekly-stats response
carries what the UI needs to say "data as of". Not yet covered by CI: Supabase and news RSS (Supabase has
no fallback to inject against, see risk 4).

### Manual drill (quarterly, 30 minutes, on a staging copy or off-peak)

1. Sleeper down: on the box add `127.0.0.1 api.sleeper.app` to `/etc/hosts` inside `mobile-api`
   (`docker compose exec`), open Dashboard, Roster, Player Detail. Expect last-known data, no blank page,
   no 500s in `docker compose logs mobile-api`. Remove the entry.
2. Sleeper garbage: point `SLEEPER_BASE` at a local server returning `<html>` with HTTP 200. Same expectations.
3. FantasyCalc down: block `api.fantasycalc.com`, delete nothing; delete `data/fantasycalc_values.csv`
   mtime-wise by `touch -d '3 days ago'`, open Trade Analyzer. Expect values, not an empty list.
4. Redis down: `docker compose stop redis`. Expect slower but working pages; restart.
5. Supabase down (read-only drill, do not touch prod data): block the Supabase host from the web container,
   confirm the signed-in shell still renders from stored session and failures show a retry message.
6. Watchdog: run `python scripts/ops_health_check.py`; stop a scheduled workflow's schedule (or `touch -d`
   a data file old) and confirm `/v1/public/data-freshness` lists it under `failing` and the issue opens.
7. Record results in the incident runbook (`docs/incident-runbook.md`).

## 4. Independence feasibility (plan only, no migration)

Owner goal: FantasyDesk as an independent platform winning on deeper analytics. Split first:

- **Inherently Sleeper:** the user's real Sleeper leagues (rosters, matchups, transactions, league
  settings, drafts) and the Sleeper user/player IDs they are keyed on. We can cache and snapshot these
  (we already do), but cannot replace them. Mitigation is platform adapters (ESPN, Yahoo, MFL,
  Fleaflicker exist) so no single platform is the product, and our own ID crosswalk.
- **Ownable:** everything about NFL players and games independent of a fantasy platform: stats, usage,
  schedules, injuries, depth, values, projections, news synthesis.

| Data type | Free / open alternatives | Quality | Freshness | Licence (commercial?) | Rate limits | Maintenance | Realistic? |
|---|---|---|---|---|---|---|---|
| Weekly box-score stats | nflverse `stats_player` (nflreadr/nflfastR) | high, standard in the field | typically within a day of games, sometimes hours | CC BY 4.0, yes with attribution; upstream NFL rights residual | GitHub CDN | low: we already ingest nflverse | **Yes** |
| Snap counts, usage shares | nflverse `snap_counts`, `pbp`-derived target/air-yards shares | high | after games | CC BY 4.0 (FTN charting is CC BY-SA: exclude) | GitHub CDN | low-medium | **Yes** |
| Fantasy points under league scoring | our own scoring over nflverse stats | exact if stats exact | as stats | n/a | none | low | **Yes** |
| Schedule, spreads, totals, roof | nflverse `games` (already used) | high | early season publish, in-season updates | CC BY | GitHub CDN | none | **Yes** |
| Injuries (status, practice reports) | nflverse injuries (official NFL reports), ESPN public JSON (unofficial) | official but Wed-Fri cadence; no instant news | hours, not minutes | nflverse CC BY; ESPN unofficial, no licence | ESPN unpublished, can vanish | medium | **Partly**: weekly truth yes, breaking status no |
| Depth charts | nflverse `depth_charts`, team pages (scraping), our own role model from snaps | medium; team pages are inconsistent | weekly | nflverse CC BY; scraping team sites is a ToS risk | n/a | high for scraping | **Partly**: own snap-based role model is the durable route |
| Player directory and IDs | nflverse `players` / `ff_playerids`, our `canonical_player_id` crosswalk | good, gaps on new rookies and IDP | days | nflverse release states no licence: **verify** | GitHub CDN | medium (rookie and ID gaps) | **Partly**: we still need Sleeper IDs to join to user leagues |
| Dynasty / trade values | our own model, plus FantasyCalc as one market signal; later our own trade-market data from FantasyDesk users | own model depends on projections quality | continuous | own: yes. KeepTradeCut / scraped sites: no | n/a | high but it is the product | **Partly**: own value yes; a free open market signal does not exist |
| Projections | own model on nflverse inputs (already `modules/player_projections`) | to be measured, see backtest inputs | weekly | own | none | high | **Yes** (accuracy delta is the open question) |
| News | RSS headlines as links, our own synthesis from structured events (injury changes, depth changes, snaps) | headlines good, original reporting no | minutes | headline use ok, article bodies no | polite | medium | **Partly**: structured-event news yes, beat reporting no |
| Headshots, team logos | self-hosted licensed images; ESPN CDN (unofficial); initials fallback | image rights are the issue, not tech | n/a | we hold no licence for NFL player photos | n/a | n/a | **No** (keep fallback; accept or buy a license) |
| Live scores / live plays | ESPN public scoreboard (unofficial), nflverse after the fact | ok | seconds to minutes | unofficial | unpublished | medium | **Partly** |
| Users' league data | none | n/a | n/a | n/a | n/a | n/a | **No** |

### Phased roadmap

- **Phase 0 (done in this PR set):** completeness manifest, freshness endpoint plus ops alerts,
  stale-on-error for FantasyCalc, garbage-body hardening for Sleeper, fault-injection tests.
- **Phase 1 (weeks 1-4, no accounts needed):** second source for weekly stats and snaps from nflverse
  so Sleeper stats become the fallback instead of the only source; reconcile the two nightly and alert on
  disagreement. Move all provider calls behind one `provider_health` record (last success, last error)
  so the ops check reads real success times instead of file mtimes.
- **Phase 2 (weeks 4-10):** own the player identity crosswalk (Sleeper id, gsis, ESPN, nflverse) as a
  versioned table; own depth/role model from snaps; structured-event news from our own diffs.
- **Phase 3 (weeks 10-20):** value model that treats FantasyCalc as an optional signal with measured
  weight; start capturing FantasyDesk trade-market data to become our own market signal.
- **Phase 4 (hosting resilience):** a warm standby for the box and Supabase backups tested by restore.
  Needs owner decisions on cost (see needs).

Verdicts: weekly stats yes, snaps/usage yes, schedule yes, projections yes, scoring yes, injuries partly,
depth partly, player IDs partly, values partly, news partly, live partly, headshots no, users' leagues no.
Overall: **partly realistic**. Analytics inputs can be fully ours; the user-league graph and the
imagery cannot.

### Inputs for the projections backtest agent

Measure accuracy deltas of free-source inputs against the current Sleeper-fed pipeline, per position,
weeks 1-10 of 2026 and 2024-2025: nflverse `stats_player` weekly stats; `snap_counts` (snap share, trend);
`pbp`-derived target share, air-yards share, red-zone looks, carries inside the 10; `games` spread,
total and implied team total, roof, rest days; weekly NFL injury practice reports (DNP/limited/full) versus
Sleeper `injury_status` timing; `depth_charts` versus snap-derived role; defence-vs-position computed
from nflverse stats; `draft_picks` capital and age for rookies; `contracts` flag. Exclude FTN data
(CC BY-SA). Also test the effect of the confirmed-inactive weeks (`inactive_weeks`) as an availability
feature, since that signal was previously discarded.

## Needs from the owner (none done, none required for the merged work)

1. Set the `OPS_ALERT_WEBHOOK_URL` repo secret (Discord/Slack webhook) if it is not set, so freshness
   failures page you instead of only opening an issue. Free.
2. An external uptime monitor with push/SMS paging (free tiers exist); a new account.
3. A written answer from FantasyCalc on commercial use of derived values and a rate limit; and, if you
   want certainty, a contact at Sleeper confirming API use at our volume.
4. A decision and budget on a standby host and tested Supabase backups (likely paid tier).
5. A decision on player imagery: keep hotlinking with fallback, or license/replace.
6. Confirm the Sentry DSN story so `DEPENDENCIES.md` can be corrected (it says no Sentry; the code has it).
7. Run `python scripts/backfill_weekly_stats.py 2025 2026` on the production host after deploy (this
   repo cannot reach production `data/`).
