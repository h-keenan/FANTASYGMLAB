# Player pool, college scouting, and ESPN/Yahoo audits (2026-11-12)

Read-only audit of `origin/main` at `3f2fef7e`. Nothing in `modules/`, `services/` or `data/` was changed.
No `rankings.load_players` / `build_players_table` call was made against the real `data/players.db`;
every data number below comes from read-only `sqlite3` / `json` reads of the committed
`data/players.db` and `data/sleeper_players.json` (both refreshed 2026-11-12) plus
`data/college_prospects_2027.json`.

Labels: **[V]** verified against code or data in this repo, **[I]** inferred (not provable from the repo:
production env, Supabase state, third-party behavior).

---

## Part 1. Player pool audit

### 1.1 How the pool is built (verified map)

| Stage | Where | What it does |
| --- | --- | --- |
| Source dump | `modules/sleeper.py:1447` `get_players` -> `data/sleeper_players.json` (12,229 records, 4,234 with a QB/RB/WR/TE/K `position`) | Sleeper is the only identity authority. |
| Record normalize | `modules/rankings.py:4389` `normalize_player_record` | Keeps `position` (PK->K), drops `college`, `birth_date`, all external ids. Hard-coded K value bands at `rankings.py:4422-4440`. |
| Position gate | `rankings.py:4490` `rec["position"] not in FANTASY_POSITIONS`; set defined at `rankings.py:51` and again at `player_eligibility.py:22` | Uses the primary `position` only. |
| Eligibility gate | `modules/player_eligibility.py:208` `player_eligibility`, called through `filter_current_fantasy_players` (`:938`) | Status text + `active` + "current signals" (news, depth, stats, market, rookie). |
| Valuation | `rankings.py:3629-3720` FantasyCalc join by `normalized name|position`; `:3662` teamless cap | See 1.3. |
| Persist | `rankings.py:4472` `build_players_table` writes `data/players.db`; `modules/structured_player_refresh.py:209` `_current_player_rows_missing_from_persisted_frame` re-adds rows the contract now accepts (valued only from `search_rank`) | `players-db-refresh.yml` commits the db to `main` every 6h. |
| Per-surface filters | waivers `modules/waivers_logic.py:61-130` -> `player_state_authority.waiver_actionable_player_pool` (`:220`) -> `rankings.is_probably_stale_free_agent` (`:5741`); search `modules/player_search.py`; trade analyzer `services/mobile_api_service.py:6223-6233`; roster view `:13530` `_reinstated_inactive_roster_rows`; sim `modules/sim/inputs.py:394-407` | Each surface re-implements "who counts". |

### 1.2 Verified measurements on the committed data (2026-11-12)

- Pool: **1,829 rows** in `players.db` out of 4,234 Sleeper skill-position records.
- **991 pool rows (54%) have no NFL team.** **967** of them also have no market value (`fantasycalc_value` 0) and no
  current-season stats. They are in the pool only because of the rookie rule or stale news.
- **985 rows (54%) carry reason `current_rookie`**, i.e. `active == true and years_exp <= 1`
  (`player_eligibility.py:240`). That is any player in his first two seasons regardless of team, so every cut 2025 and
  2026 UDFA Sleeper still marks `Active` stays "current". 686 rows have `years_exp <= 1` and no team.
- Ghost examples that are in the pool with a value: Henry Ruggs (age shown 22, real age from `birth_date` 27.8,
  value 1,500), Antonio Brown (shown 33, real 38.3, 1,500), Jimmy Garoppolo, Ezekiel Elliott, Le'Veon Bell, Gus Edwards
  (all 1,500). The 1,500 comes from `TEAMLESS_VETERAN_VALUE_CAP` (`rankings.py:3662`), a cap that was added to hide the
  symptom rather than remove the rows.
- **Sleeper `age` is frozen for non-active records.** 612 of 791 teamless pool rows with a `birth_date` have an `age`
  off by 1+ years (up to 9). For teamed rows it is accurate (11 of 823 off). Age curves (`rankings.py:1015`) and the
  stale-FA rules (`rankings.py:5759`, `age >= 40`) therefore run on wrong ages for exactly the rows they are meant to
  police. `birth_date` is present for 3,696 of 4,042 skill records and is dropped by `normalize_player_record`.
- Sleeper's `status` vocabulary in the dump is `Active` 8,305, `Inactive` 3,647, `Injured Reserve` 227, null 45,
  `Physically Unable to Perform` 3, `Practice Squad` 1, `Non Football Injury` 1. **There is no `Retired`, `Historical`
  or `Deceased`.** `INELIGIBLE_STATUS_TERMS` (`player_eligibility.py:23`) and `NFL_NON_ACTIONABLE_STATUSES`
  (`player_state_authority.py:46`) list them but they never match real Sleeper data. "Inactive" is the retired /
  cut / unsigned bucket, which is why retired-vs-rostered needed band-aids (#1107, #1385).
- FantasyCalc covers only 397 pool rows (22%). The other 78% are valued from Sleeper `search_rank`, a popularity signal.
- FantasyCalc is joined **by name** (`rankings.py:3647-3698`), not id. Verified misses in the committed CSV:
  - **Travis Hunter** (FantasyCalc WR 1,890, Sleeper `position` DB, `fantasy_positions` DB|WR, rank 103): in the pool with
    `value 0.0`, `valuation_authority_status = reconciled_unmodeled`. The build gate at `rankings.py:4490` drops him on
    primary position; the reconcile step re-adds him with no model, and the join key `...|DB` never matches `...|WR`.
  - **Kenny Gainwell** (TB RB, FantasyCalc lists "Kenneth Gainwell", 1,651): `fantasycalc_value = 0`, valued only from
    `search_rank` (7,414).
  - Two exact name+position duplicates in the pool (Chase Cota, Cody Chrest), one of each pair a ghost.
- 20 FB, 1 P rows exist as `reconciled_unmodeled` value 0 (they enter through `fantasy_positions` containing RB).
- ID coverage on Sleeper skill records (4,042): `gsis_id` 1,259 (31%), `espn_id` 2,210, `yahoo_id` 2,258. Every external-id join therefore needs a second source (DynastyProcess).

### 1.3 Hard-coded / heuristic inventory (file:line)

| # | Item | Location | Note |
| --- | --- | --- | --- |
| 1 | Rookie = `years_exp <= 1` and `active` is a permanent "current" signal | `player_eligibility.py:240`; also `draft_assistant.py:987,990` (`<= 1`, `<= 2 and age <= 24`), `rankings.py:2912` (`years_exp <= 1`) | Not tied to a draft class or a season; see F1. |
| 2 | `stats_season >= now.year - 1` | `player_eligibility.py:252` | Calendar-year arithmetic, not NFL season. |
| 3 | Season flips on Sep 1 by `time.localtime()` month | `sleeper.py:236-257` | Server-timezone dependent; flips ~9 days before week 1, so the "current" stats file is empty at the flip. `external_interesting_trades.py:448` uses a different cutoff (May). `league_calendar.py` uses Sleeper `/state/nfl`. Three season definitions. |
| 4 | Age / experience cutoffs: 35 / 10 yrs, news 730d and 180d | `player_eligibility.py:66-69` | Run on frozen Sleeper `age`. |
| 5 | Stale-FA rules: `age >= 40`, news older than 365d with `search_rank >= 150/120/100`, `years_exp >= 12 and age >= 35` | `rankings.py:5759-5790` | Magic numbers; same ghosts the eligibility gate is supposed to remove. |
| 6 | `TEAMLESS_VETERAN_VALUE_CAP = 1500` | `rankings.py:3662` | Symptom cap for ghosts that should not be valued. |
| 7 | K value floors keyed on `search_rank` bands | `rankings.py:4422-4440` | Position hack. |
| 8 | `FANTASY_POSITIONS` defined twice (rankings, eligibility) and a third local copy of QB/RB/WR/TE in `college_scouting.py` | `rankings.py:51`, `player_eligibility.py:22` | Drift risk; K and DEF/IDP handled by different paths. |
| 9 | Only literal `Inactive` is "reinstated" for a roster | `mobile_api_service.py:13590` | Roster view only. Trade analyzer returns `assets_unresolved` for any non-pool id (`:6233`, `:6301-6309`), search and compare cannot find them. Four surfaces, four answers. |
| 10 | Waivers exclude `practice squad`, `inactive`, and every teamless player | `player_state_authority.py:46-60,126-160` | A just-released vet (Tyreek Hill is teamless and valued 5,391 in the pool today) can never be recommended, even though he is the best add on a wire. |
| 11 | League roster-position gate drops K/DEF from pool | `player_eligibility.py:988-993` | Good, but DEF/IDP rostered players are not in the pool at all; DEF handled by `_team_defense_frame_rows` (`mobile_api_service.py:13751`), IDP by a parallel `idp_*` stack. |
| 12 | Six name normalizers | `rankings.py:980`, `player_identity.py:39`, `gsis_crosswalk.py:41`, `news_signal.py:349`, `draft_assistant.py:138`, `news_intelligence.py:1084` | Different suffix and punctuation rules; nickname (Kenny/Kenneth) handled by none. |
| 13 | Five copies of NFL team alias maps, not identical | `sim/inputs.py:44` (no JAC/WSH), `nflverse_advanced_stats.py:67`, `platforms/espn.py:25`, `nfl_schedule.py:52`, `mfl_leagues.py:91` | A relocation or code change must be edited in five places. |
| 13b | Hard-coded Sleeper ids for headshot calibration | `portrait_normalization.py:43-47` | Harmless (calibration only). |
| 14 | `DEFAULT_CLASS_STRENGTH_BY_YEAR = {2026: 1.15}` | `trade_ideas.py:104` | A single editorial year; 2027 and later silently neutral 1.0. |
| 15 | ESPN leagues hard-coded `status: "in_season"` | `espn_leagues.py:488` | Pick-spent logic (`trade_ideas.py:116`) treats this year's picks as already used all year. |
| 16 | Sim pool requires `active > 0` | `sim/inputs.py:405` | Sleeper sets `active false` on many IR players, so IR players vanish from the sim door even though `is_current_fantasy_eligible` allows them. Also defaults age to 26 when missing. |

No hard-coded player names were found in `modules/` or `services/`. Hard-coded seasons are rare and listed above.

### 1.4 Future-season failure scenarios, ranked by risk

**F1. Phantom rookie flood at every rollover (HIGH, already live).** Because `years_exp <= 1 and active` is sufficient
(`player_eligibility.py:240`), each draft cycle adds every Sleeper-created UDFA/camp body as a "current rookie" and
keeps last year's cut class one more year. Today that is 985 rows and 678 with no team. After the 2027 draft, expect
roughly 1,000 to 1,300 teamless rows. Effects: inflated pools and percentiles (`overall_ratings_for_pool`), waiver and
search noise, valued ghosts. Fix: tie "rookie" to a draft class row (see 1.5).

**F2. Frozen ages drive valuation and stale-FA decisions (HIGH, already live).** 612 of 791 teamless rows have wrong ages.
Fix: compute age from `birth_date` at the season clock date.

**F3. Retired/unsigned conflation through Sleeper `Inactive` (HIGH).** The model has no retired state. A real retiree
who stays `Active` with a stale team (Roethlisberger: `Active`, PIT, age 39, news 2022) survives only if the news-age
heuristics happen to catch him; a real IR player marked `Inactive` is valued only because of the #1385 exception. Next
bug will be the next odd Sleeper status combination. Fix: explicit lifecycle state.

**F4. Surface divergence on "who exists" (HIGH).** A roster-owned player outside the pool resolves on My Team (only
if `Inactive`), but the Trade Analyzer refuses the whole trade (`assets_unresolved`), search/compare cannot find him,
and waivers cannot rank him. Any new status quirk again needs N separate patches. Fix: one resolver, rosters always
resolve.

**F5. Name-keyed market join (MEDIUM-HIGH, live).** Hunter and Gainwell above. Next season's new nicknames, suffix
changes, two-way/position changes (WR/DB, RB/WR, QB/TE) and duplicate names (two Michael Thomases, two Josh
Allens at different positions are separated, same-position pairs are not) will silently mis-price or zero-price
players. Fix: join on Sleeper id; FantasyCalc's API payload carries a Sleeper id (**[I]** known API shape, the repo
discards it at `fantasycalc.py` row build, no `sleeperId` reference anywhere in the repo).

**F6. September flip with an empty current-season file (MEDIUM).** `default_player_stats_season` jumps to the new year on
Sep 1 (`sleeper.py:240`); the new season's weekly stats do not exist until the first games (about Sep 10), so every
player has `stats_season` null in the window. Today only 51 pool rows rely on stats alone (the rest are carried by
news/depth/market), so impact is limited, but the cutover is timezone- and calendar-dependent and the 2027 stats
file is rebuilt with 18 empty weekly fetches. Use the NFL state clock (Sleeper `/state/nfl`, already used by
`league_calendar.py`).

**F7. Class-strength and calendar constants (MEDIUM).** `{2026: 1.15}` only; the 2027 class and every later class are
neutral. `external_interesting_trades.py:448` rolls the "rookie draft year" on May 1.

**F8. Multi-position players and non-skill primary positions (MEDIUM).** Primary `position` gates the build; the
eligibility function and the reconcile step use `fantasy_positions`. The two disagree, producing `reconciled_unmodeled`
zero-value rows (Travis Hunter, 20 FBs, a P). Fix: one position-eligibility function.

**F9. ID coverage (MEDIUM).** `gsis_id` on 31% of skill records. `espn_player_crosswalk.py` pulls
`dynastyprocess/data/master/files/db_playerids.csv` from GitHub at runtime; `gsis_crosswalk.py` explicitly avoids it
for licence reasons (docs/news-evidence-scope-2026-10.md). Two ID authorities with different licence postures.

**F10. Waiver pool excludes just-released players and practice squad (LOW-MEDIUM).** See table row 10.

**F11. players.db is a build artifact committed to `main` every 6h (LOW, operational).** Golden tests drift against it
(CLAUDE.md). `data/sleeper_player_stats_2026.json` and `data/nfl_games.csv` are not committed, so a clean clone cannot
reproduce production's 2026 stats or the sim's bye weeks **[V: files absent; I: produced on the box]**.

### 1.5 Proposed single source of truth

One module, `modules/player_universe.py`, owns identity and lifecycle. Everything else consumes it.

1. **Season clock** (`season_clock()`): season, week, phase (`offseason | preseason | regular | post`), from Sleeper
   `/state/nfl` with the nflverse schedule as fallback. Replace `default_player_stats_season`, the May cutoff and
   `now.year - 1`.
2. **Identity table** (`player_ids`): one row per Sleeper id with `birth_date`, `gsis_id`, `espn_id`, `yahoo_id`,
   `fantasycalc_id`, `mfl_id`, `fleaflicker_id`, `college`, `draft_year/round/pick` where known; built from the Sleeper
   dump plus DynastyProcess and the FantasyCalc payload; one name normalizer (nickname table included) used only as
   a last-resort fallback and always logged.
3. **Lifecycle state per row** with evidence, computed once at build: `rostered`, `reserve`, `practice_squad`,
   `free_agent_signable`, `free_agent_stale`, `rookie_class_<year>` (requires a draft-class source, e.g. Sleeper
   `metadata.rookie_year` equal to the season clock's rookie year, or the draft board), `retired_or_gone`. Age is derived
   from `birth_date` at the clock date.
4. **Nothing is deleted from the pool.** Rows are valued or flagged `unmodeled`. Surfaces use named predicates over the
   same table (`is_rankable`, `is_waiver_actionable`, `is_searchable`, `is_tradeable_asset`) instead of build-time
   filters. Rosters and trade assets always resolve any id to a row (placeholder with lifecycle, never
   `assets_unresolved`).
5. **Markets join on ids**, with unmatched provider rows reported (FantasyCalc, nflverse, ESPN) in one coverage report;
   promote `scripts/player_coverage_audit.py` into a CI check that fails on new unexplained gaps.
6. **Delete** the exceptions once 3 and 4 land: `TEAMLESS_VETERAN_VALUE_CAP`, `_reinstated_inactive_roster_rows`'s
   Inactive special case, the `INELIGIBLE_STATUS_TERMS` retired words, the five alias maps, the five extra name
   normalizers, the stale-FA age/news constants.

Rough effort: season clock + age from birth_date (0.5 day, immediately removes F2/F6/F7 hard-codes); id-based
FantasyCalc join (0.5 day); lifecycle + rookie-class rule (2-3 days incl. tests/golden refresh); pool-never-deletes and
resolver unification across waivers, search, trade analyzer, roster, sim (3-4 days); CI coverage gate (0.5 day).

---

## Part 2. College scouting audit

### 2.1 End-to-end trace (verified)

| Step | What exists | Evidence |
| --- | --- | --- |
| Data source | **Names, positions, schools only.** Candidate list scraped from WalterFootball 2027 position pages and Stick To The Model's big board (`scripts/build_college_prospects_seed.py`), then each name is checked against the school's official roster page for class label. Ranks, grades and stats are deliberately not copied. | `data/college_prospects_2027.json` keys per prospect: `id, name, position, school, draft_year, roster_class, roster_position, roster_url, class_source_url, roster_season, roster_parse, verified_on, boards`. |
| Size / shape | 192 prospects (QB 33, RB 55, TE 39, WR 65), 71 schools, **all `draft_year` 2027**, all `roster_season` 2026, all `verified_on` 2026-10-21. 122 appear on one board, 70 on two. | json read. |
| Load into app | Manual: render SQL and paste in Supabase SQL Editor (`docs/supabase_college_prospects_seed_2027.sql`, 217 lines, header: "AFTER docs/supabase_college_scouting.sql"). Read path `services/mobile_api_service.py:10868` `/v1/scouting/prospects` -> `college_scouting.fetch_all_prospects` (Supabase table `college_prospects`). No migration runner, so whether prod has the seed applied is **[I] unverifiable from the repo**. |
| Freshness | Manifest last touched by #1340 (2026-10-21). No workflow refreshes it (`.github/workflows/` has none for college). It is 22 days old today, mid-season, and it only holds a 2027 class: **no 2028 class** (underclassmen are excluded by the `draft_year` rule at the script's step 3). |
| Real college stats | **None anywhere.** No stat field in the manifest, the seed SQL, the API row (`college_scouting.py:278-330` `build_prospect_views` returns id/name/position/school/draft_year/aggregate/my_report/on_watchlist), or the web/mobile cards (`CollegeScoutingContent.tsx`, `CollegeProspectsScreen.tsx` show school, class label and community grades). |
| Phantom stat plumbing | `modules/player_profile_ui.py:50-57` and `modules/player_quick_view.py:1079-1086` define a "College Stats" group reading `college_games`, `college_receptions`, `college_receiving_yards`, etc. **Nothing populates those columns** (`players.db` has no `college*` column; `normalize_player_record` drops Sleeper's `college`; only tests set them). The UI therefore always reports `college_available = false`. |
| Matching to a draft class / NFL player | **No link** between a prospect row and a Sleeper/NFL player. Sleeper carries `college` for ~94% of rookies and `metadata.rookie_year`, but nothing joins on it. After the draft, prospects stay forever (the seed never deletes, by design: reports cascade) and a drafted player's NFL row is a different identity. A naive name join is unsafe: "Jacob Harris (Wisconsin)" collides with Sleeper's UCF "Jacob Harris", "Jackson Harris (LSU)" with Georgia's. A (name, school, position) join is required. |
| Rookie rankings / draft tools | Draft Center "Scouting" tab shows the prospect list with a league lens (`scoutingLens.ts`: position need + user's pick round vs. community projected round). Rookie valuation does not use college data: `docs/rookie-prenfl-valuation-evidence-audit.md` found no draft round/pick/ADP source and dropped `college`. The only valuation hook is `trade_ideas.py:104` `DEFAULT_CLASS_STRENGTH_BY_YEAR = {2026: 1.15}`, a hand-typed editorial constant, plus a crowd multiplier that is off by default (`DYNASTYGM_COLLEGE_SCOUTING_CLASS_STRENGTH_SIGNAL`, `college_scouting.py:57`, default False) and needs real scout volume. |
| Gating | Pro only (`_is_pro_caller`, `mobile_api_service.py:10885`; the `/v1/scouting/prospects` handler starts at `:10868`). |
| Stale docs/code | `college_scouting.py` docstring and `docs/supabase_college_scouting.sql` still say there is no data feed; the code comment in `trade_ideas.py` and the evidence doc reference `modules/draft_prospects.py`, which does not exist on `main`. `docs/plan-hosted-leagues-and-college.md:265` records the competitor college-fantasy idea only. |

### 2.2 Direct answers

- **Are real current-season college stats present?** No. Zero stat fields exist in the data files, DB schema or API.
  What is present and verified against official rosters is identity (name, school, position, class label), as of
  2026-10-21 for the 2026 season. [V]
- **Are the identity fields correct?** Internally consistent: 192 unique ids, class labels all map to 2027
  eligibility by the documented rule, rejections are logged (8 rejected: e.g. Brendan Sorsby "not on official
  roster"). Whether the roster scrape is correct for each school is **[I]**: the scraper parses 71 different athletics
  sites (`roster_parse` nuxt etc.) and the 8 rejections include names that plausibly are on rosters (Sorsby listed at
  Texas Tech), so parser false negatives are possible and should be spot-checked.
- **Class buckets look right but are rough.** `roster_class` includes 21 distinct labels ("5th", "Gr.", "R-So.",
  "Redshirt Sophomore"), so eligibility depends on a label-to-years table in the script; a 3rd-year "R-So." or
  "Jr." counts as 2027.

### 2.3 Gaps and exact fixes

| # | Gap | Fix | Effort |
| --- | --- | --- | --- |
| C1 | No real college stats | Add a CollegeFootballData.com ingest (free API key required from the owner, sent as `Authorization: Bearer`; the script docstring already names it). New table `college_prospect_stats(prospect_id, season, games, pass/rush/rec yards, tds, attempts, receptions, targets, ppa optional, fetched_at)`; nightly workflow like `news-ingest.yml`; render in `CollegeScoutingContent.tsx` and `mobile/src/screens/ProspectScoutingDetailScreen.tsx`; fill `college_*` keys so the existing `player_profile_ui.py:50` group lights up for drafted rookies. | 3-4 days + key |
| C2 | Prospect to NFL player link | Add `players.college` and `players.rookie_year` back into `normalize_player_record`; add `sleeper_player_id` on `college_prospects`, matched by (normalized name, school, position) with ambiguity -> unlinked; run after each draft. | 1-1.5 days |
| C3 | Freshness / classes | Replace manual SQL paste with a scheduled refresh writing via a service role (or a documented one-click admin path); seed 2028 class (`--draft-years 2027,2028`); show `verified_on` in UI ("as of"). | 1-2 days |
| C4 | Class-strength constants | Remove `{2026: 1.15}` or make it data-driven from the linked prospects once C1/C2 exist; keep the crowd signal off until volume exists. | 0.5 day |
| C5 | Stale text | Fix the `college_scouting.py` / SQL header comments and the missing `draft_prospects.py` references. | 0.25 day |
| C6 | Verify prod seed | Owner/SQL check: `select count(*) from college_prospects;` expect 192. | minutes |
| C7 | Parser spot-check | Re-verify the 8 rejected rows and 10 random accepted rows by hand against rosters. | 0.5 day |

---

## Part 3. ESPN and Yahoo integration audit

### 3.1 What exists

- **`slow-wt`**: `/private/tmp/claude-501/slow-wt` exists but is an empty directory skeleton: **0 files, not a git
  worktree**, absent from `git worktree list`. No ESPN WIP lives there. [V]
- ESPN branches `espn-league-import`, `espn-private-league-hint`, `fix/espn-player-matching` and
  `yahoo-oauth-integration-spike` are unmerged pre-squash copies whose content shipped as #1339, #1442, #1358 and #861
  **[I: commit subjects match]**. `feat/espn-private-leagues` (#1677) and `feat/espn-private-ui` (#1679) are fully merged.
- `docs/platform-import-status.md` (checked 2026-10-22) is **stale**: it says ESPN private is "not built" while
  `00fc9179` (#1677) and `c4a04a7d` (#1679) shipped private-league cookies afterwards.

### 3.2 Status table (verified in code; production state marked [I])

| Capability | ESPN | Yahoo |
| --- | --- | --- |
| Connect / auth | Public leagues: league id + season, no auth (`espn_leagues.py`, `POST /v1/espn/leagues/preview` `mobile_api_service.py:1938`). Private: user pastes `espn_s2` + `SWID`; stored Fernet-encrypted in Supabase `espn_credentials` (`espn_credentials.py`, `docs/supabase_espn_credentials.sql`, routes `:1995-2052`), bound per request (`:928-970`). Web `EspnImportForm.tsx`, mobile `PlatformPicker.tsx`. | OAuth2 auth-code client exists (`modules/platforms/yahoo_oauth.py`: authorize URL, code exchange, refresh) but **no route, no callback, no token store, no UI**. Reads `YAHOO_CLIENT_ID/SECRET/REDIRECT_URI`. Never run against Yahoo (runbook says so). |
| League import / settings | Yes: scoring (`_scoring_settings`), roster slots, IR slots, league type guess (keepers -> dynasty heuristic `espn_leagues.py:337`). | Adapter methods written for league/settings against documented shapes (`modules/platforms/yahoo.py:228-336`), unexercised live. |
| Rosters / players | Yes, mapped to Sleeper ids via DynastyProcess crosswalk then name+pos+team (`espn_player_crosswalk.py`, `platforms/espn.py`); unmatched listed, import can be blocked on low match (`mapping_blocks_import`). | Adapter only; no Yahoo id crosswalk wired (Sleeper has `yahoo_id` on 2,258 skill records; DynastyProcess also carries it). |
| Scoring / projections | League scoring translated; values lensed per league. | Not done. |
| Lineups / matchup | Current-week lineups + pairings from the single `espn_api` load (`external_matchups.py`); Dashboard + Matchup routes open (`espn_leagues.py:62-83`). Live per-player points not used. | Not done. |
| Transactions / waivers | **No.** Adapter has `get_transactions` (`platforms/espn.py:412`) but the API refuses waivers/alerts/recaps for ESPN. Free agents indistinguishable from unmapped players. | Adapter `get_transactions` stub only. |
| Trades | Trade Analyzer runs players-only (no pick ownership: `/draft-picks` returns empty with `espn_not_supported`); Trade Hub/Finder refused. | Not done. |
| Draft / picks | Not available (adapter has draft reads, unused). | Stub only. |
| Sync / refresh | 5-min in-process snapshot cache (`ESPN_SNAPSHOT_TTL_SECONDS`), private snapshots per user; key includes season (`espn:{id}:{season}`), so **no automatic season rollover** [I: derived from key design, not run]. League `status` hard-coded `in_season` (`:488`). | None. |
| Tests | `tests/test_espn_leagues.py`, `test_espn_platform_adapter.py`, `test_espn_player_crosswalk.py`; validated once against a live league (#1306, league 42654852, 2026). | `tests/test_yahoo_oauth.py`, `test_yahoo_platform_adapter.py`: mocked fixtures only. |
| Dependency | Unofficial `espn-api` package (`requirements.txt:11`); ESPN has no OAuth, cookie scraping of a private API [I: terms risk]. | Official OAuth2 API. |

### 3.3 Claims vs reality

| Surface | Claim | Verdict |
| --- | --- | --- |
| Landing (`web-next/src/app/page.tsx:54,181`) | "Sleeper username, an ESPN league ID, or a public Fleaflicker or MFL league"; imported leagues get "Dashboard, Matchup, My Team, Trade Analyzer, Players and League Rankings". | Matches the route allow-list. Does not claim Yahoo. OK. |
| `web-next/src/app/connect-league/page.tsx:53` | "Add a Sleeper, ESPN, Fleaflicker or MFL league". | OK. |
| Import-step feature list `espn_leagues.py:88-107` `ESPN_FEATURE_SUPPORT` | Lists **Dashboard and Matchup as "not_available"** | **Under-claims**: the same module serves `/dashboard` and `/matchup` (`:75-77`) and the landing page advertises them. Fix the list (and the stale comment `LandingAuthIsland.tsx:242` "no ESPN Dashboard yet"). |
| `docs/platform-import-status.md` | ESPN private "not built" | Stale. Update. |
| Privacy policy (`modules/legal_pages.py:175-176`, mirrored in `mobile/src/data/legalContent.json`) | Names Sleeper API and ESPN Fantasy API as processors | **Gap**: no mention that encrypted ESPN login cookies are stored, nor of Fleaflicker/MFL; `grep` for `espn_s2|SWID|cookie|Fleaflicker|MyFantasyLeague` in `legal_pages.py` returns nothing. Should be fixed before relying on private-league import. |
| Yahoo | No in-product claim found in web, mobile, landing or legal. | Correct as is. Competitor docs (`docs/competitive-audit-2026-10*.md`) record Yahoo as a gap. |

### 3.4 Gap list and effort (engineering days, one engineer, includes web + mobile per the parity rule)

| # | Work | Days |
| --- | --- | --- |
| E1 | Correct ESPN copy/status: `ESPN_FEATURE_SUPPORT`, `LandingAuthIsland` comment, `platform-import-status.md`, privacy policy (ESPN cookie storage, Fleaflicker, MFL) web + mobile legal | 0.5-1 |
| E2 | Confirm prod prerequisites for private ESPN: `ESPN_CREDENTIAL_KEY` set on the box and `docs/supabase_espn_credentials.sql` applied by hand (neither is verifiable from the repo; `docker-compose.yml` does not name the key, it relies on `env_file`) | 0.25 |
| E3 | ESPN season rollover (re-resolve key to current season like #1312 does for Sleeper) and real `status` | 1-1.5 |
| E4 | ESPN transactions/free-agent awareness so Waivers can run (needs a reliable free-agent list from `espn_api`, not `recent_activity`) | 3-5 |
| E5 | ESPN draft picks / keeper picks (limited by ESPN data) | 2-3 |
| Y1 | Yahoo OAuth routes: `GET /v1/yahoo/connect` (state + PKCE-style CSRF binding), `GET /v1/yahoo/callback` (HTTPS), token exchange, encrypted token store (Fernet pattern of `espn_credentials.py`, new table + manual SQL, key env), refresh + revoke + delete-account purge | 3-4 |
| Y2 | Live-validate `YahooPlatformAdapter` against a real league (JSON-quirk collections, `game_key` per season, rate limits); fix shapes; add fixtures from real responses | 3-5 |
| Y3 | Yahoo id crosswalk (Yahoo player_key -> Sleeper id via Sleeper `yahoo_id` + DynastyProcess), name fallback, unmatched report | 1-2 |
| Y4 | League import snapshot in the Sleeper-shaped form (`yahoo:{league}:{season}`), scoring + roster-slot translation (Yahoo stat_id map), route allow-list, web + mobile picker | 4-6 |
| Y5 | Yahoo lineups/matchups, then transactions/waivers/trades (separate, each optional) | 3 + 4-6 |
| Y6 | App-store, privacy-policy and ToS review for third-party OAuth tokens; mobile OAuth return path (web redirect then deep link) | 1-2 |

Totals: Yahoo roster-level parity with current ESPN (My Team, Trade Analyzer, Players, Rankings, Dashboard/Matchup):
**about 3-4 weeks** with live debugging; Yahoo with transactions/waivers/trades: about 6 weeks. ESPN cleanup (E1-E3):
about 2-3 days.

### 3.5 What the owner must supply

**Yahoo (all blocking):**
1. A Yahoo Developer app registered by the owner's Yahoo account at developer.yahoo.com/apps with the Fantasy Sports
   Read permission; give back **Client ID and Client Secret** (store as server env, never in the repo).
2. Approved **HTTPS redirect URI(s)**, one for web (e.g. `https://app.fantasygmlab.com/...` / the `fantasydesk.app` host,
   decide which brand domain) and one return path for mobile. Yahoo does not accept plain-http production redirects
   **[I]**.
3. A real **test league with a human account** to validate against (the agent environment has none, per the runbook).
4. A decision and an encryption key for stored refresh tokens (`YAHOO_TOKEN_KEY` or reuse a vault), and permission to
   run a new Supabase migration by hand.
5. Acceptance of Yahoo's Fantasy Sports API terms (volume limits, display/attribution) and a privacy-policy update.
6. **[I] Risk to confirm early:** Yahoo has historically throttled or paused new Fantasy API app approvals; verify the
   registration form still offers the Fantasy Sports scope before committing build time.

**ESPN (private leagues):** `ESPN_CREDENTIAL_KEY` (Fernet key) on the production box; the credentials table migration
applied; a decision to accept the terms risk of holding user session cookies (they expire and users must re-paste;
no OAuth exists); a refreshed privacy policy.

**Fleaflicker / MFL (adjacent, for completeness):** MFL registered client User-Agent for higher limits and a secret
store if private (APIKEY) MFL leagues are wanted.

---

## Prioritized recommendations

1. Remove the rookie `years_exp <= 1` blanket rule and compute age from `birth_date` (F1, F2): small change, removes
   most ghost rows and the 1,500-value cap hack.
2. Join FantasyCalc on id and unify position eligibility (F5, F8): fixes Travis Hunter and Kenny Gainwell class bugs.
3. Season clock from `/state/nfl` (F6, F7, row 3 in 1.3).
4. Introduce the lifecycle/resolver module (1.5) so rosters, trades, search and waivers agree (F3, F4).
5. College: ingest real stats (C1) and link prospects to NFL ids (C2) before the 2027 draft; verify the prod seed (C6).
6. ESPN: correct copy and privacy text now (E1, E2); decide on Yahoo only after the prerequisites in 3.5 exist.
