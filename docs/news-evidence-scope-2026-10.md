# News evidence scope (2026-10-22)

> **Status update 2026-10-26:** `modules/news_evidence.py` (the fetch-and-hash
> `EvidenceFetcher`/`EvidenceStore`) was **deleted** in the Streamlit removal
> (#1452) and is not in the tree. Sections 2 and 4 below describe it as it was
> designed on 2026-10-22; treat those parts as history, not as shipped code.
> Still in the tree: `modules/gsis_crosswalk.py` and the Sleeper-dump GSIS
> lookup. The API never fetches or hashes an article document: provenance
> `content_sha256`, `checked_at` and `excerpt` are always `null`. Restoring a
> fetch step (from commit `f609b35c`) would need a source a human has recorded
> as permitted; none exists. See `docs/external-api-contract.md`.

Scope and findings for (A) a GSIS crosswalk and (B) a licensed fetch-and-hash
evidence step for the automatic news pipeline. Everything implemented is OFF
by default behind `DYNASTYGM_NEWS_EVIDENCE_FETCH` (unset/`0`). Production
behaviour is unchanged on merge. This document records what was verified on
2026-10-22; terms change, so re-verify before enabling anything.

## 1. Verification: GSIS identity data

| Source | Carries GSIS? | Licence / terms found | Status |
|---|---|---|---|
| `data/players.db` (`players` table) | No `gsis_id` column (has `sleeper_id`, `canonical_player_id`). | n/a | Unusable alone |
| Sleeper `players/nfl` dump (`data/sleeper_players.json`, already used by the app) | Yes, `gsis_id` on 3,893 of 12,229 records in the local cache. Only 158 of 833 active QB/RB/WR/TE with a team have a valid unique id, so coverage for current skill players is poor (mostly older veterans). 14 records share a GSIS (dropped as ambiguous); one value had stray whitespace (trimmed, then validated). | Public API the app already calls; no separate data licence stated | **Used (A)** |
| nflverse `players` release (`nflverse/nflverse-data`, tag `players`) | Yes (described as the go-to ID mapping) | Release page states no licence. nflverse site: code is MIT, "NFL data ... belong to their respective owners, and are governed by their terms of use." Repo `LICENSE.md` is CC BY 4.0 (the repo already cites CC BY 4.0 for the contracts release in `DEPENDENCIES.md`) but applicability to the players file is not stated | **Licence unclear: not fetched, needs human review** |
| DynastyProcess `db_playerids.csv` (already fetched for ESPN ids in `modules/espn_player_crosswalk.py`) | Believed to (not confirmed from README) | Repo-wide GPL-3.0; README states no data usage terms. GPL copyleft on a data file is an open question | **Not fetched for GSIS; needs human review** |

Decision: the crosswalk is built only from the Sleeper dump. Closing the
coverage gap (rookies and 2nd-year players) needs the nflverse players file;
once someone confirms its licence it can be added as a hash-pinned download
step (single CSV, ~MBs, not committed) feeding the same
`GsisCrosswalk` constructor. Nothing large is committed.

## 2. Official sources and permissions

| Source | robots.txt | Terms | Verdict |
|---|---|---|---|
| nfl.com (injury reports, transactions, news) | `User-agent: *` disallows only `/_ctv/ /_fantasy-app/ /_libraries/ /_mobile-app/ /_mobileview/ /_phs/ /_sponsors/ /account/ /nfl-films-beta/ /search/`; silent on injuries/transactions | Terms s1.3: "systematic retrieval of data or other content" and building a database from it prohibited absent written consent; use "solely for your own individual non-commercial and informational purposes"; s11(f) bars robots/spiders/agents for commercial collection; s1.1 bars copying/reproducing/displaying; s6 bars excerpting Modular Content without written permission | **NOT PERMITTED** (fetch, hash store, excerpt, quote all out) |
| nflpa.com | Only `Noindex` lines for login/admin paths | `/terms-of-use` returned 404; terms not located | **NEEDS HUMAN REVIEW**, not fetched |
| Team sites (e.g. `houstontexans.com`) | Not reviewed (30+ different operators on a shared platform) | Not reviewed | **NEEDS HUMAN REVIEW**, not fetched |
| Allowlisted publishers (espn.com, cbssports.com, sports.yahoo.com, nbcsports.com, rotowire.com, profootballrumors.com) | Not reviewed for article pages | Not reviewed for body fetching; RSS headline use only | **NEEDS HUMAN REVIEW**, not fetched |
| operations.nfl.com | n/a | No public API/data licence for injury reports or transactions found; a "Licensing" form exists for media | Contact NFL |

The registry that existed (`modules/news_evidence.py::SOURCE_POLICIES`, since
deleted) contained **no permitted source**; no fetcher ships today. Any future
fetcher must start from a human-recorded terms review per source.
A source may only be set `permitted` together with `allow_excerpt` and
`max_excerpt_chars` decisions; the default is no excerpt.

## 3. Costs of paid dependencies (not implemented)

No price was found for any official NFL injury/transactions data licence;
the NFL publishes no public price list (licensing is by application, so treat
as "contact sales, enterprise pricing"). Commercial sports-data vendors
(e.g. Sportradar, SportsDataIO) sell injury/transaction feeds under licence;
current prices were not retrieved in this pass and must be quoted by the
vendor. Nothing paid is wired up.

## 4. What is implemented

* `modules/gsis_crosswalk.py`: Sleeper-dump GSIS loader. `^00-\d{7}$` after
  trim; GSIS shared by several Sleeper ids is ambiguous for all; name+team+
  position triple must be unique. Reason codes: `gsis_not_mapped_for_player`,
  `gsis_malformed`, `gsis_shared_by_multiple_sleeper_ids`,
  `ambiguous_name_team_position`, `player_not_in_sleeper_dump`,
  `insufficient_identity_key`. `resolve_player_identity` takes an optional
  `gsis_crosswalk`; `/v1/external/players/{id}/news` passes one only when the
  flag is on (otherwise `None`, identical output to before).
* (DELETED, historical design) `modules/news_evidence.py`: `EvidenceFetcher` (flag, https only, exact
  registry match, `permitted` only, robots.txt with fail-closed, per-host rate
  limit, 10 s timeout, identifying user-agent, 2 MB cap, text content types,
  no redirects), `content_sha256` of the exact bytes, `checked_at`,
  `original_url` (publisher URL for syndicated copies), policy-gated capped
  excerpt. `check_item` binds each claim to the fetched text (player name and
  designation/event keyword/team in the same sentence). A hash alone never
  marks anything `supported`. `confirmed` requires every claim supported by
  an official-primary document, or by at least two documents with distinct
  origins (syndication of one origin counts once). `EvidenceStore` creates a
  new `revision_id` when the hash changes or a retraction notice appears;
  the prior revision is reported `superseded` / `retracted`, and retracted
  documents never support claims. Freshness uses the contract limits (general
  24 h/1 h, urgent availability 6 h/15 min) on the real `checked_at`.
* Tests: `tests/test_news_evidence.py` now covers only the GSIS crosswalk and
  the contract helpers (the fetcher tests went with the module). All players
  in them are synthetic; no live data and no `data/*.json` is committed.

## 5. Remaining gaps

* No permitted official source exists today, so no document is ever fetched
  in production and the API stays headline-only/review-only.
* Sleeper-only GSIS coverage is ~19% of current skill players; the nflverse
  players file would fix it once its licence is confirmed.
* Article-level evidence is not implemented. Revision history for FEED text
  (title/summary changes) is now persisted by the scheduled ingest
  (`modules/news_ingest.py`, `docs/supabase_news_items.sql`), but that is not a
  checked document; the deleted design's `evaluate_claim` is
  conservative keyword matching, not NLP, and `event_type` values it cannot
  verify (e.g. `STARTER_CHANGE`) are never marked supported.
* The public API contract does not yet expose the overlay (`supported`,
  `retracted` claim statuses, real `previous_revision_id`).
