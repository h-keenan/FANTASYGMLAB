# Rookie and dynasty ADP: source evaluation (2026-11-17)

Probed live on 2026-11-17 with a generic client User-Agent. Nothing was scraped; every source below is a documented public API or a published data repo.

## Summary / recommendation

| # | Source | Rookie ADP | Dynasty/startup ADP | 1QB vs SF | Licence / terms | Verdict |
|---|--------|-----------|--------------------|-----------|-----------------|---------|
| 1 | Fantasy Football Calculator (FFC) `/api/v1/adp/{format}` | yes (`rookie`, "Dynasty Rookie") | yes (`dynasty`) | 1QB only. `superflex` returns HTTP 400 "Invalid format". `2qb` exists but is redraft only. | Site states ADP is free "in your website or application". No ToS/API terms page found (`/terms`, `/api` are 404); no key, no stated rate limit, no stated attribution rule. | USE. Cite "Fantasy Football Calculator" with link on screen (conservative attribution), poll once per day, cache. |
| 2 | FantasyCalc `/values/current` | no (`maybeAdp` is null for all 421 players probed) | no | values accept `numQbs` 1 or 2 | Terms of Usage require attribution wherever values are shown (already honoured via ValuesCredit) | VALUES ONLY. Keep as is; no ADP to ingest. |
| 3 | DynastyProcess `dynastyprocess/data` CSVs | no ADP file. Files are ECR (`db_fpecr*`, `fp_dynastyvsredraft.csv`), trade values (`values*.csv`, 1QB and 2QB columns) and `db_playerids.csv` | no | values have 1QB and 2QB columns | GPL-3.0 on the repo; ECR is FantasyPros-derived. Copyleft on data and third-party provenance make it a poor redistribution source. | DO NOT INGEST as ADP. `db_playerids.csv` is useful reference only (not needed; we match by name). |
| 4 | Aggregate of users' connected Sleeper rookie/startup drafts | would give SF and 1QB | yes | yes | Sleeper API terms are non-commercial; privacy policy does not cover draft aggregation | HOLD. Needs Zach's approval. Built behind `ADP_USER_DRAFT_AGGREGATE` config flag, default OFF, no collector shipped. |

## Findings that change the ask

- Rookie ADP is only populated in the rookie-draft window. FFC's current `rookie` window (2026-09-05 to 2026-10-05) has zero players and the 2024 window was also empty; 2025 had 260 drafts. Today the live `rookie` response is empty, so the feed stores nothing and the UI shows "no ADP yet" rather than inventing numbers.
- Superflex ADP is not available from any free approved source. We store `format` + `qb_format` columns and only write `1qb`. Superflex is a gap until source 4 is approved.
- Dynasty ADP (`dynasty`) is the startup ADP; it is live in season (Sept-Oct 2026 window currently empty off-season but 2025 populated).
- FFC `player_id` is FFC's own id and is not in any id map we have. Players are matched to Sleeper ids by normalized name + position (+ team when ambiguous) against the existing player pool. Ambiguous or unmatched names are listed in the run report and stored with `sleeper_id = NULL`; never guessed.
- FFC ToS could not be located on the site. Assumption: free use with credit. Recommend Zach confirm via FFC contact if we ever show ADP in a paid-only surface.

## Attribution shown on screen

"ADP: Fantasy Football Calculator (fantasyfootballcalculator.com)". FFC states it is not affiliated with the NFL; we claim no endorsement.

## Owner decision: superflex (2026-11-17)

- (a) In superflex leagues the real FFC ADP is shown labelled "1QB ADP".
- (b) "Est. SF" is a modeled estimate: FFC 1QB ADP slots re-ordered by `adp / (FantasyCalc superflex value / 1QB value)` (modules/rookie_adp.py `estimate_sf_adp`). QBs move up; the ADP scale is unchanged; with no ratios it equals 1QB ADP. Computed at read time, never stored (`adp_snapshots` is real ADP only, constrained to `1qb`), always labelled "Est. SF" with a "?" note on every surface.
