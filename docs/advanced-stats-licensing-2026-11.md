# Advanced usage stats: free sources and licence gate (verified 2026-11-02)

Request (coridian_): air yards, routes run, target share, yards per route run,
red-zone usage, rolling last-4/last-8 usage and "role expanding" flags, "if we
can without having to pay for it". This is the licence check that gates which
datasets the ingestion (`modules/nflverse_advanced_stats.py`) may touch.
This is an engineering read of public terms, not legal advice; terms change,
so re-verify before adding a dataset.

## Governing text

nflverse licensing page (https://www.nflverse.com/, "Licensing", text as of
2026-11-02): "The majority of all nflverse data available (ie all data stored in
nflverse/nflverse-data releases EXCEPT the FTN data ...) is broadly licensed as
CC-BY 4.0, and the FTN data is licensed as CC-BY-SA 4.0." CC-BY "loosely means
anyone is permitted to use any of the CC-BY 4.0 datasets for both
non-commercial and commercial purposes provided that you attribute the
nflverse and (if applicable) the provider nflverse sourced it from." CC-BY-SA
"means that anything derived from the data (models, applications, etc) must
also be provided under the same terms (i.e. open-source and for free)."
nflverse gives no warranty. The `nflverse-data` repository `LICENSE.md` is the
CC BY 4.0 legal code. `nflreadr` code is MIT; its site says NFL data "belong to
their respective owners, and are governed by their terms of use".

Residual risk to know about: nflverse's CC BY label covers nflverse's own
rights. All nflverse play data ultimately derives from NFL feeds. Our earlier
audit (`docs/news-evidence-scope-2026-10.md`) found nfl.com's own terms bar
systematic retrieval, but we do not retrieve from nfl.com: we use nflverse's
published, openly licensed derived tables, the same position the app already
takes for the schedule (`nfl_schedule.py`) and the `contracts` release.
If the owner wants zero upstream exposure, the fallback is Sleeper-only
metrics (snap share, targets, opportunities), which `usage_trends.py` already
computes without the advanced file.

## Dataset table

| Dataset (nflverse-data release) | Licence | Commercial use in a paid app | Decision |
|---|---|---|---|
| `stats_player` (weekly player stats from nflfastR: targets, carries, target share, air yards share, WOPR, receiving air yards) | CC BY 4.0 (nflverse page; no dataset-specific licence marked on the release) | Yes, with attribution | **USED** |
| `pbp` (play-by-play, nflfastR) | CC BY 4.0 | Yes, with attribution | **USED** (only red-zone/goal-line looks and team totals are aggregated; no play data stored) |
| `player_stats` | Same | Release is marked DEPRECATED 2025-08-01 in favour of `stats_player` | Skipped (deprecated) |
| `nextgen_stats` (NFL Next Gen Stats) | CC BY 4.0 per nflverse, NFL-sourced | Provenance is an NFL product; nothing we need (no routes, no usage shares) | Skipped (unclear upstream terms, no benefit) |
| `pbp_participation` (NGS participation) | CC BY 4.0 per nflverse, NFL-sourced | Lists players on field only, no routes; 49 MB/season | Skipped (unclear upstream terms; does not contain routes run) |
| `snap_counts` | CC BY 4.0 per nflverse, but scraped from Pro Football Reference | Sports Reference data-use page (sports-reference.com/data_use.html): scraped data may not be used without permission; "our licenses completely preclude any redistribution" for some datasets | Skipped (upstream terms bar commercial reuse). Snap share comes from Sleeper instead, already in the app |
| `pfr_advstats` (PFR advanced stats) | Same PFR provenance | Same | Skipped. It has no routes-run field either |
| `draft_picks`, `combine` | PFR-sourced | Same | Skipped (not needed) |
| `ftn_charting` | **CC BY-SA 4.0** (nflreadr: "attribution must be made to FTN Data via nflverse") | Share-alike: anything derived (models, applications) must be offered under the same open terms. Incompatible with a closed paid app | **Skipped** |
| `espn_data` (QBR) | ESPN-sourced | Unclear | Skipped |
| `players`, `rosters`, `depth_charts`, `injuries` | CC BY 4.0 | Allowed, but not needed: GSIS mapping is done from the Sleeper dump plus a name/team/position match | Not used |
| `contracts` (OverTheCap) | CC BY 4.0, already in `DEPENDENCIES.md` | Already live | Unchanged |

## What this means for the request

| Ask | Delivered? | Source |
|---|---|---|
| Target share | Yes | nflverse `stats_player` |
| Air yards (receiving air yards, air yards share) | Yes | nflverse `stats_player` |
| Red-zone and goal-line usage (targets, carries, share of team red-zone looks) | Yes | nflverse `pbp`, aggregated |
| Touch / opportunity share | Yes | nflverse `pbp` team totals; Sleeper touches |
| Snap share | Yes | Sleeper (already in app) |
| Rolling last-4 / last-8, role flags | Yes | `modules/usage_trends.py` |
| **Routes run, yards per route run** | **No** | No free source that permits commercial use publishes routes run. PFF/other charting is paid; FTN is share-alike; NGS/participation do not contain it. The profile lists it under `not_available` rather than approximating it |

## Required attribution

Wherever advanced usage numbers are shown (web + mobile), a visible credit:
"Usage stats: nflverse (nflverse.com), CC BY 4.0", linking to
https://www.nflverse.com/. CC BY also asks that a licence link and a note of
changes be available: the legal "Third-party names and data" page carries the
licence link and says the figures are aggregated and combined with Sleeper
data. nflverse is not an endorser; wording must not imply endorsement.

## Operating limits respected

* Two public GitHub release downloads per run (0.5 MB + ~9-20 MB), two runs a
  day, no auth, no API quota. Downloads are size-capped (25 MB / 120 MB), have
  a timeout and bounded retries.
* The app never calls nflverse at request time: it reads the derived file
  `data/nflverse_advanced_stats_<season>.json` (~0.7 MB) committed by the
  scheduled workflow, the same pattern as `players.db`.
* Upstream outage or a bad file: the job exits non-zero, nothing is committed,
  the previous file keeps serving and shows its "through week N" stamp, and the
  workflow opens a tracking issue.

## Pro gate (owner decision, coridian_, 2026-11-03)

Advanced usage is a Pro feature, enforced on the server (the client never
decides; `modules/usage_trends.py` `free_view` / `PRO_GATE`):

| Surface | Free | Pro |
|---|---|---|
| Player Quick View / profile Usage block (`model.usage_profile`) | Season snap share, target share, touches and opportunities per game (already free in rankings/profile) with percentiles; `gated: true` marker, static "what Pro unlocks" list, nflverse credit kept | Everything: air-yards share, opportunity share, red-zone looks, last-4 / last-8 windows and deltas, points-vs-usage read, role flags |
| `GET /v1/players/{id}/percentile-explorer` for `air_yards_share`, `opportunity`, `red_zone_looks` | `reason: "pro_required"`, no data | Distribution as before |
| Waivers priority adds: usage chip and "Usage:" line | Fields omitted, `usage_locked: true`; page-level `usage_gate` drives one teaser line | `usage_flag` as before |
| Waivers drop suggestions: role-change reasons, usage chip | Text blanked (the protect/shrinking *decision* is unchanged for everyone, only the displayed text is Pro) | Shown |
| Trade Analyzer `role_notes` and suggested-lineup (start/sit) `why` role line | Omitted | Display-only role-change lines; scores, verdicts and lineups are unchanged |

Free payloads never contain `last4`, `last8`, `prior`, `delta_last4_vs_prior`,
`direction`, `season_total`, `last4_total` or any flag text; pinned by
`tests/test_usage_pro_gate.py`. The nflverse attribution stays visible on every
usage block (target share is nflverse-derived even in the Free view).
