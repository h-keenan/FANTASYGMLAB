# Runtime Architecture and Performance Audit

**Repository:** `h-keenan/FANTASYGMLAB`
**Audited base:** `trust/complete-production-integration` at `0be81df`
**Audit date:** 2026-07-30
**Scope:** read-only architecture, Streamlit rerun, duplicate-computation, cache, news, injury, and snapshot analysis

## Executive summary

The application is functionally modular at the domain level, but runtime orchestration remains concentrated in `app.py`. The file is 16,344 lines (741,433 bytes), defines 286 functions, has 64 top-level imports, and contains a 3,979-line `main()`. It is now both the Streamlit entrypoint and a composition root, view-model layer, domain-adapter layer, cache registry, and implementation home for several large business workflows.

The largest performance opportunity is not a single formula. It is eliminating repeated construction and transport of the same league state:

1. Build one league snapshot per selected league/settings/player-data version.
2. Derive one team snapshot per selected roster and strategy.
3. Reuse its summary row, lineup, Team Needs assessment, injury context, roster map, and display frames throughout a rerun.
4. Keep raw trade generation independently cached and Trust enforcement outside that cache.

The current five-minute Streamlit caches prevent many repeated builders from executing on a warm hit, but each call still hashes large DataFrame arguments and returns mutation-isolated objects. Nested cached functions also reconstruct derived frames on independent cache misses. Separately, Sleeper endpoint functions use process-local `lru_cache` without a TTL, which eliminates repeated network calls inside a process but risks stale live state until process restart or explicit cache clearing.

The highest-risk runtime behavior is the common pre-route path. Before any authenticated page branch renders, the app loads and normalizes public player data, resolves the valuation lens and league settings, refreshes account/entitlement state, builds startup context, builds team-direction context, and materializes shared league context for the application shell. Page-specific work then begins. This makes inexpensive UI interactions pay for analysis that may not be relevant to the active page.

No production code was changed for this audit.

## Evidence and measurement limits

This report combines:

- static call-site and branch tracing;
- cache-decorator and external-call inspection;
- function and file-size measurement;
- two local, non-production microbenchmarks using the repository data.

Local public-player loading measured:

| Operation | Result |
|---|---:|
| `load_players("data/players.db")`, first call in a fresh process | 860.3 ms |
| same call, warm Streamlit data-cache hit | 2.0 ms |
| returned frame | 988 rows, 69 columns, 0.90 MB deep memory |
| `apply_valuation_lens(...)`, three repeated calls | 59.7 / 57.9 / 57.1 ms |
| resulting local lens frame | 1,928 rows, 76 columns, 2.70 MB deep memory |
| fresh-process `import app` | 1,826.9 ms |

These are workstation microbenchmarks without a Streamlit server runtime and are not production latency claims. The row-count difference between the public cached load and the later `ensure_players()` path reflects their distinct source/rebuild paths.

Exact production wall-clock apportionment is not currently recoverable from the code alone:

- there is no total timer around each page branch;
- most heavy-builder timers are inside `@st.cache_data` functions, so they fire on misses but do not expose warm-hit hashing, lookup, deserialization, or copy cost;
- Sleeper calls are timed, but no rerun-level external-call counter summarizes them;
- news feed calls are not timed by `modules.performance`;
- DataFrame hashing and memory-copy costs are not separately recorded.

The first optimization phase should therefore add observation at existing boundaries, not change behavior.

## 1. `app.py` assessment

### Size and concentration

The largest functions demonstrate the concentration:

| Function | Approximate lines | Responsibility |
|---|---:|---|
| `main()` | 3,979 | startup, session restoration, routing, shared context, and most page implementations |
| `roster_limit_status()` | 835 | roster-limit classification and advice |
| `cached_weekly_league_report()` | 634 | weekly report computation |
| `render_player_quick_view_content()` | 508 | player profile view model and rendering |
| `render_home_dashboard()` | 467 | dashboard data assembly and rendering |
| `evaluate_trade_analyzer_fit()` | 416 | post-trade simulation and fit analysis |
| `cached_league_intelligence_frame()` | 325 | league-wide roster, lineup, injury, and behavior enrichment |
| `render_player_detail_content()` | 322 | full player profile view model and rendering |
| `render_startup_draft_center()` | 277 | startup draft orchestration and rendering |
| `build_my_team_advice()` | 255 | recommendation/advice construction |

`app.py` is about 43% as large as all top-level Python files in `modules/` combined (16,344 versus 38,148 lines), excluding nested platform modules.

### Responsibilities currently held

Correct entrypoint responsibilities:

- Streamlit page configuration and top-level execution;
- route selection and session-state transitions;
- authentication/entitlement orchestration;
- page-shell and navigation composition;
- calling cached/domain services;
- passing already-built immutable context to renderers;
- user-triggered feedback and profile persistence;
- final Trust enforcement at production recommendation boundaries.

Responsibilities that have grown beyond orchestration:

- league settings detection, overrides, normalization, and display formatting;
- valuation-lens calculation;
- trade analyzer simulation and fit business logic;
- Team Needs adapters and presentation selection;
- player fit, quick-view, and detail view-model creation;
- roster-limit classification;
- My Team advice and primary-recommendation selection;
- league intelligence and weekly-report computation;
- trade asset searching and package UI state;
- injury aggregation adapters;
- large blocks of page-specific DataFrame filtering, sorting, renaming, and card construction.

### “God object” symptoms

- `main()` owns shared startup work and six large route implementations rather than delegating page controllers.
- Domain modules are often imported and then rebound to local aliases, while other app functions implement adjacent policy directly.
- Page rendering and DataFrame construction are interleaved, making it difficult to reuse an already-built result without also adopting Streamlit state.
- Cached functions in `app.py` call other cached functions, Sleeper adapters, and presentation builders. Cache invalidation boundaries therefore overlap rather than align to a single snapshot.
- Large business functions accept DataFrames and loose dictionaries, which encourages repeated filtering and defensive copies.
- Similar “load roster IDs → filter player frame → build lineup → find summary row” sequences exist in Dashboard, My Team, Waivers, player fit, League Overview team detail, and trade flows.

### Import structure

The 64 top-level imports span accounts, authentication, Sleeper, rankings, news, draft tools, Team Needs, trade generation, Trust, premium, feedback, navigation, and nearly every UI module. There is no observed circular import in the audited tree, but the breadth makes `app.py` the central coupling point. The explicit development-only module reload block is correctly gated; enabling `DYNASTYGM_DEV_RELOAD_MODULES` would intentionally invalidate stable module state and should remain disabled in production.

## 2. Streamlit rerun trace

### Common work before every authenticated route

The normal rerun enters `main()` and performs, in order:

1. `performance.begin_rerun()` and top-level Streamlit setup.
2. `ensure_players()` followed by `normalize_player_ids()`.
3. Supabase session restoration and account profile load.
4. entitlement refresh.
5. saved-league and active-league restoration.
6. league settings detection and override resolution.
7. `apply_valuation_lens()` over the public player frame.
8. `cached_startup_draft_context()` for a selected league.
9. `cached_team_direction_summary()` plus `get_team_vs_league()` to resolve strategy.
10. `get_roster_profile()` for the shell.
11. `get_shared_league_context()`, which calls `cached_league_context()` for the shell team identity/rank.
12. navigation/header rendering.
13. active page branch.
14. the global player quick-view modal and debug/footer work.

“Once” means once per Python process or cache entry, not once per user:

- Python imports and `lru_cache` contents survive normal reruns in the same process.
- Streamlit `cache_data` entries survive reruns until TTL/input/source invalidation or eviction.
- session-state values survive within a user session.
- the script body and route orchestration execute again on every widget interaction.

### Dashboard

Call chain:

`main()` → common path → `get_shared_league_context()` → `render_home_dashboard()` → roster IDs/filter → `get_team_vs_league()` → role-weighted roster copy → `suggest_optimal_lineup()` → `build_team_needs_assessment()` → `assess_team_needs()` → `build_my_team_advice()` → strategy lens → `cached_dashboard_trade_headline()` → `cached_trade_ideas()` → `build_trade_ideas()` on miss → `enforce_cached_trade_ideas()` → `enforce_trade_board()` → enrichment/headline selection → injury/waiver/roster-limit summaries → render.

Every rerun:

- roster filtering and role-weighted score column construction;
- lineup generation;
- Team Needs assessment;
- My Team advice;
- Trust enforcement of the returned raw headline candidates;
- headline enrichment and selection;
- injury context and several card-specific DataFrame filters;
- entitlement-based display branching.

Cached:

- public player source;
- startup draft context (five minutes);
- league core/context/intelligence (five minutes);
- raw dashboard trade candidates (five minutes, with three-candidate fallback);
- draft-pick assets and raw trade board dependencies.

Duplicate opportunity:

- the common shell already materializes league context;
- Dashboard correctly accepts and normally reuses it, but retains a fallback call to `cached_league_context()`;
- the selected team lineup and Team Needs assessment are rebuilt from the roster even though league intelligence has already generated lineups for every roster on its cache miss;
- advice, injury, waiver preview, and roster-limit logic traverse overlapping roster columns independently.

### My Team

Call chain:

`main()` → common path → roster IDs/filter → `get_shared_league_context()` → `get_team_vs_league()` → strategy/role adjustment → `suggest_optimal_lineup()` → `build_team_needs_assessment()` → two legacy list adapters from the same assessment → `build_my_team_advice()` → `cached_trade_ideas()` on miss → Trust enforcement → injury context → roster-limit context → waiver preview → trade/waiver/draft-watch candidate assembly → `my_team_ui.render_my_team_workspace()`.

Every rerun:

- roster filter/copy and role adjustments;
- optimal lineup;
- canonical assessment (correctly reused by cards);
- advice generation;
- Trust enforcement and trade enrichment;
- injury and roster-limit analysis;
- numerous sorts/copies for starters, bench, tier tables, core candidates, cut candidates, and draft watch.

Cached:

- shared league context and raw trade generation;
- public data and Sleeper endpoint results.

Duplicate opportunity:

- the same roster is sorted repeatedly for top players, starters, bench, untouchables, core, and candidate sections;
- injury context exists in league intelligence and is recalculated for selected-team advice;
- lineup/assessment are shared within this route, which is a successful local reuse pattern to preserve.

### Trade Hub

Call chain:

`main()` → common path → `get_shared_league_context()` → summary/maps/profiles → selected roster/filter → strategy profile → `cached_trade_ideas()` → `build_trade_ideas()` on miss → `enforce_cached_trade_ideas()` → `enforce_trade_board()` → manager-tendency enrichment → grouping/headline/filter rendering → optional Trade Return Explorer → optional player-specific `cached_player_trade_hub_ideas()` → Trust enforcement → enrichment/render.

Every rerun:

- team filter and strategy adjustment;
- Trust context use and enforcement for each displayed raw board;
- enrichment/grouping/filtering;
- target-pool and owner/profile mapping;
- search and presentation transformations.

Cached:

- shared league context;
- general raw trade board;
- player-specific raw acquisition board;
- trade search pool;
- draft-pick assets.

Largest miss cost:

- raw trade generation, which evaluates combinations and league/team fit.

Duplicate opportunity:

- general and player-specific surfaces can each enforce and enrich during one rerun if both are visible;
- multiple roster/profile maps are already available in league context, but local target frames and lookup maps are reconstructed;
- cached trade functions accept large DataFrames, so warm calls still hash them.

Trust must remain after raw cached generation and before enrichment/display. Optimization must pass an already-built immutable enforcement context; it must not cache final user-specific enforced boards.

### Waivers

Call chain:

`main()` → common path → Sleeper adapter rosters → owned-ID set → free-agent filtering → position-group ranking → selected roster IDs/filter → `suggest_optimal_lineup()` → `cached_team_direction_summary()` → `get_team_vs_league()` → Team Needs assessment → true-needs adapter → injury context/replacement annotation → premium branch → `waivers_ui.render_waiver_workspace_sections()` and FAAB calculation.

Every rerun:

- league ownership set construction;
- free-agent filtering, group-by ranking, percentile/rank columns, and several copies/sorts;
- selected-team lineup and Team Needs assessment;
- injury replacement annotations, including row-wise `apply`;
- presentation and FAAB calls.

Cached:

- Sleeper rosters via process `lru_cache`;
- team-direction summary through five-minute Streamlit caching;
- public player data.

Duplicate opportunity:

- owned-player IDs are already derivable from the shared league roster map;
- the selected team’s summary, lineup, need assessment, and injury context overlap with shared league and My Team state;
- repeated row-wise injury checks should eventually consume precomputed player injury flags.

### Player Detail

Call chain:

`main()` → common path → player lookup → `render_player_detail_content()` → `build_player_roster_needs_context()` → roster IDs/filter → `cached_team_direction_summary()` → `get_team_vs_league()` → `suggest_optimal_lineup()` → Team Needs assessment → category-aware player fit → trade outlook → news session lookup or `fetch_news()` → player filtering/curation → render.

Every rerun:

- selected-player lookup;
- roster filter and team-fit context;
- lineup and Team Needs assessment;
- profile statistic grouping and HTML construction;
- trade outlook;
- player-specific news filtering/curation.

Conditional external work:

- if session news is empty, `fetch_news()` parses all configured RSS feeds synchronously.

Duplicate opportunity:

- the common shell has already loaded league context but `build_player_roster_needs_context()` calls `cached_team_direction_summary()` independently;
- full detail and quick view each build the same kind of roster-fit context. Each does so once per rendered profile, not once per player loop, which is good, but opening both states in one rerun can duplicate it;
- filtered/curated news is computed separately for quick view, full detail, and the News page.

### League Overview

Call chain:

`main()` → common path → `get_shared_league_context()` → league summary/display/intelligence/draft/maturity frames → route-specific sorts and cards. For selected team detail: roster map/filter → `get_team_vs_league()` → `suggest_optimal_lineup()` → `assess_team_needs()` → team advice/render. Draft subsection may independently call `suggest_optimal_lineup()` for the user roster.

Every rerun:

- multiple copies/sorts of league display and intelligence frames;
- selector label construction via row-wise `apply`;
- selected-team roster/filter, lineup, assessment, and advice;
- selected draft-section frame assembly.

Cached:

- league core/context/intelligence, team direction, transactions, manager behavior, matchup history, draft picks.

Duplicate opportunity:

- on a league-intelligence cache miss, `cached_league_intelligence_frame()` loops every roster and calls `suggest_optimal_lineup()`;
- selected team detail then rebuilds that roster’s lineup and Team Needs assessment;
- draft posture may build the user lineup again in the same route;
- the same display/intelligence frames are repeatedly copied and sorted for separate boards.

## 3. Duplicate computation inventory

| Computation | Production call sites | Frequency/identity | Safe reuse and opportunity |
|---|---|---|---|
| `build_league_summary()` | `cached_league_summary()`; internally obtains rosters | One actual build per five-minute cache key, but invoked through multiple nested cached contexts | High. Key by league ID, public-player fingerprint, score fields, normalized lineup settings, and roster version. Avoid passing the full frame as the only version signal. |
| `get_team_vs_league()` | player fit, Dashboard, strategy bootstrap, Waivers, My Team, League Overview selected team, Trade Hub, Trade Analyzer, league advice, trade generation | Usually scans/filters an identical summary for the same roster; cheap individually but repeated | High ease/medium payoff. Store a roster-ID keyed metrics mapping in a League Snapshot. |
| `suggest_optimal_lineup()` | trade analyzer, player fit, Dashboard, Team Needs adapter fallback, league intelligence per roster, Waivers, My Team, League Overview team detail, draft posture, trade ideas | Identical for a roster only when player scores/role adjustments/settings match. Dashboard/My Team role-adjusted frames are not necessarily identical to the base league frame | High. Reuse only with an explicit roster-frame/settings/version key; distinguish base valuation lineup from role-adjusted or simulated post-trade lineups. |
| `assess_team_needs()` | canonical adapter and League Overview direct path | Reached indirectly by Dashboard, My Team, Waivers, player fit; same selected-team inputs within a page are now shared | Medium. Put the frozen assessment on a Team Snapshot. Do not reuse across differing role/lineup/settings inputs. |
| `true_roster_needs()` | inside canonical assessment, Draft Assistant, trade ideas | Trade and draft consumers intentionally remain separate/deferred | Medium after product migration decisions. Do not alter trade behavior during a performance change. |
| `classify_roster_rooms()` | canonical `true_roster_needs()`, draft prospects | Same roster/settings can repeat through legacy paths | Low-to-medium today; naturally disappears when consumers use a shared assessment. |
| player value lookup | repeated row filters, `.iterrows()`, DataFrame `isin`, and dictionary creation across pages/trade code | Same player ID/value columns repeatedly accessed | High. A read-only Player Snapshot/index avoids repeated normalization and scans. |
| trade value calculation | raw generation in `modules/trade_ideas.py`; analyzer simulation in `app.py`; presentation totals | Generation is cached; analyzer is interactive and package-specific | Generation: keep conditional short cache. Analyzer: per-rerun memo for identical package only. Do not share final Trust/user decisions. |
| Sleeper normalization/ownership | `normalize_player_ids()` in startup, simulation, search, intelligence; many `get_rosters()`/roster-ID calls | Inputs often identical. Endpoint `lru_cache` prevents repeat network calls in-process, but maps/sets are rebuilt | High. Normalize public identity once and include roster/player maps in League Snapshot. |
| player metadata construction | `rankings.build_players_table()` / `load_players()`, valuation lens, trade search projection, card-specific fallbacks | Public source is cached, but valuation lens is rebuilt every rerun | High/easy: cache or snapshot the league-independent/public portion; key valuation lens by source fingerprint and settings. |
| news parsing | `fetch_news()` for quick view, full detail, News page; `filter_news_for_players()` and `curate_player_news()` at three surfaces | Session state avoids some refetches, but parsing/filtering is repeated by surface | Medium. Background ingest once; index article-to-player matches; render from stored normalized records. |
| injury parsing | value enrichment in `rankings`, `summarize_team_injuries()`, league intelligence, Dashboard/My Team/Waivers, row-wise `is_injury_status()` | Same status strings repeatedly interpreted and same roster summarized | High. Put normalized injury level/freshness on Player Snapshot and team aggregation on Team Snapshot. |

### Repeated external access versus repeated local work

`get_rosters()`, `get_users()`, `get_league()`, drafts, picks, transactions, and matchups are decorated with `functools.lru_cache`. Repeated calls with the same arguments in one process generally do **not** cause repeated Sleeper requests. They still cause:

- repeated function calls and downstream list iteration;
- repeated ownership dictionaries, valid-roster sets, and roster-player maps;
- indefinite staleness because the cache has no TTL.

The process-local cache also means behavior differs after a deployment/restart versus a warm process. This is a correctness/invalidation concern, not a reason to remove caching blindly.

## 4. Cache candidate audit

No caches are added by this audit.

### Safe long cache

| Candidate | Key | Lifetime | Invalidation | Risk |
|---|---|---|---|---|
| Sleeper public player metadata | source URL/version or local file fingerprint | 1–24 hours | source file mtime/size or explicit refresh | stale team/status metadata during active NFL news |
| public valuation inputs and normalized identity frame | database/file fingerprint + valuation model version | until fingerprint/version changes | DB write, model deploy | returning mutable frames; isolate copies |
| historical market values | provider/date/player ID | immutable by snapshot date | corrected provider snapshot | source corrections |
| completed-season stats | season + provider revision | 30 days or immutable | provider correction | late stat corrections |
| rookie model outputs | class/model/data versions | hours to days | new input/model version | combine and draft updates |
| headshot bytes/data URLs | player ID + image source version | 24 hours or longer | image source/version change | memory pressure from base64 duplication |
| league-independent player tiers/opportunity metadata | public-player fingerprint + model version | hours | metadata/model change | injury/role fields may not be truly static |

### Short cache

| Candidate | Key | Lifetime | Invalidation | Risk |
|---|---|---|---|---|
| Sleeper league/users/rosters | league ID + endpoint version | 30–120 seconds in season; up to 5 minutes offseason | transaction, lineup, league-setting change | stale ownership/live lineup |
| league summary | league ID + roster version + player snapshot version + score fields + lineup settings | 1–5 minutes | any key change | DataFrame hashing/copy overhead |
| optimal lineup | roster identity/version + player snapshot + normalized settings + score mode | rerun memo or 1–5 minutes | roster/status/value/settings change | mixing role-adjusted and base lineups |
| Team Needs assessment | lineup/roster snapshot + league-relative metrics version | one rerun or same short snapshot | underlying snapshot change | user-specific leakage if globally under-keyed |
| injury team summary | roster version + player injury snapshot | 1–5 minutes in active periods | injury/status update | stale urgent injury state |
| league intelligence/display frames | League Snapshot version | 1–5 minutes | roster/player/settings/transaction change | large serialized objects |
| transaction/matchup summaries | league ID + week + transaction cursor | 1–5 minutes | new transaction/stat correction | missing very recent activity |

### Conditional cache

| Candidate | Condition/key | Lifetime | Invalidation and risk |
|---|---|---|---|
| raw trade board | league/roster IDs, player snapshot, summary version, strategy, roles, untouchables, picks/settings, generator version | current five minutes is reasonable | roster/value/profile change. Keep raw only; Trust enforcement remains outside. |
| dashboard raw candidates | same as raw board plus `max_ideas=3` | five minutes | preserve three-candidate Trust fallback |
| player-specific raw trade board | general trade key + target player ID | five minutes | potentially many keys/memory growth |
| trade analyzer result | exact package IDs/values, roster snapshot, strategy/settings | rerun-local memo only | user edits package continuously; never share under an incomplete key |
| weekly league report | league/week/schedule/transaction/player snapshot | five minutes or completed-week long cache | current-week live changes |
| news article normalization | article link/content hash | until article changes | article edits/deletions; separate from freshness/ranking |
| article-player match index | article hash + matcher version + player alias version | until inputs change | name collisions and matcher changes |

### No application-response cache

| Data/action | Reason |
|---|---|
| authentication responses and session mutation | security and token lifecycle |
| effective entitlement and Stripe/Supabase billing state | access correctness; existing provider/session behavior must be preserved |
| logout/login/account writes | state-changing |
| feedback/profile/untouchable writes | user-specific mutations |
| live draft polling result beyond its explicit short poll policy | rapid change |
| final Trust-enforced recommendations | user/league/protected constraints and current ownership; do not share across users |
| current widget/navigation/session state | session-specific |
| synchronous news fetch result as an opaque page cache | fetch should move to a freshness-aware ingest store, not hide failures in UI cache |
| rapidly changing injury state as an unversioned final result | must carry source timestamp/freshness |

## 5. News pipeline

### Current flow

1. Articles originate from Rotowire, ESPN, and CBS RSS in `modules/news.py::fetch_news()`.
2. Roster-specific searches originate from Google News RSS in `fetch_roster_news()`, up to 28 player queries with four entries each.
3. Global and roster results are serialized to `data/news_cache.json` and `data/roster_news_cache.json`; roster entries have a 20-minute TTL.
4. `modules.my_news` strips markup, detects phrase groups, matches full/last player names, computes relevance/recency priority, deduplicates, and curates.
5. Sleeper metadata changes become synthetic news cards through `build_sleeper_roster_updates()`.
6. The News page combines roster RSS, global matched RSS, and Sleeper updates.
7. Player quick view and full detail use the session’s global news pool or call `fetch_news()`, then independently filter and curate for one player.

### Valuation and recommendation use

- `modules/news_factor.py::apply_news_factor()` is a stub that assigns `news_factor = 0.0`.
- The audited production loading path does not call `apply_news_factor()`.
- News headlines therefore do not directly change valuation.
- Trade generation does not consume parsed article sentiment or a news-derived value adjustment.
- Dashboard uses roster/injury metadata and recommendation contexts, not article-derived valuation.
- Waivers use normalized player status/injury fields, not RSS sentiment.

This separation is important: “news pipeline” currently means display intelligence, while injury and role metadata from Sleeper influence values/opportunity through the rankings pipeline.

### Duplications and stale-data risks

- Phrase taxonomies and priority weights exist in both `modules.news` and `modules.my_news`.
- recency scoring is implemented in both modules;
- article text fields are concatenated and scanned repeatedly per player/surface;
- quick view and full detail independently filter/curate the same global list;
- `fetch_news()` itself has no TTL check before live RSS parsing; it only falls back to disk cache when live fetch returns no items;
- `LAST_FETCH_STATUS` is process-global and reflects the most recent fetch, not a specific user or request;
- disk JSON writes are process-shared and have no locking/atomic replacement;
- no article schema/version or matcher version drives invalidation;
- roster cache keys only contain sorted player names, so alias/matcher changes do not invalidate old matches;
- feed calls are synchronous in a Streamlit rerun.

### Background-processing opportunity

A small scheduled ingest could fetch each source once, normalize/deduplicate articles, record source and fetch timestamps, and precompute player matches. Streamlit would then read a freshness-aware table. This would eliminate N-player Google RSS work from user requests and make failure/freshness observable. It is medium architectural work and should follow instrumentation; it should not be coupled to valuation changes.

## 6. Injury pipeline

### Current flow

1. Sleeper public player metadata supplies `status`, `injury_status`, and `news_updated`.
2. `modules.rankings.injury_level()` converts strings to healthy/minor/moderate/major.
3. `injury_multiplier()`, `injury_risk_score()`, `risk_multiplier()`, and `current_availability_multiplier()` influence the existing player valuation/opportunity construction.
4. opportunity enrichment checks injuries ahead on a depth chart and appends injury-overlay context.
5. `summarize_team_injuries()` combines severity, value, starter status, healthy positional cover, role relevance, and freshness into team impact fields.
6. `cached_league_intelligence_frame()` rebuilds a roster frame and lineup for every team, then calls `summarize_team_injuries()`.
7. Dashboard and My Team call `roster_injury_context()`/`injury_ui` for display and advice.
8. Waivers scans healthy free agents against injury-need positions and annotates replacement relevance.
9. Trade Analyzer and trade generation consume injury pressure/availability through their existing fit paths.

### Duplications and stale-data risks

- status parsing is repeatedly applied row-wise across rankings, player lists, Waivers, league intelligence, cards, and trade analysis;
- roster injury summaries are available in league intelligence but are recalculated on selected-team pages;
- lineup generation is repeated before several injury summaries;
- `news_updated` freshness can be missing, making injury data explicitly uncertain;
- the Sleeper public-player file TTL is one hour, while `load_players()` is also fingerprint cached; invalidation depends on the file being refreshed;
- process `lru_cache` on league endpoints has no TTL, although public injury metadata has a separate file TTL;
- injury data and RSS news are not reconciled into one provenance record.

The safest optimization is precomputation, not formula change: normalize injury level/freshness once per player snapshot and aggregate once per team snapshot, while retaining the existing functions and outputs.

## 7. Internal snapshot feasibility

### Player Snapshot

Suggested content:

- canonical player ID and aliases;
- valuation, market, dynasty, rebuild, age and position;
- role/opportunity/tier;
- normalized injury level, injury freshness, and raw provenance;
- team/depth metadata;
- news match IDs/sentiment only when a real pipeline exists.

Feasibility: high. The local lens frame was 2.70 MB deep memory for 1,928 × 76. A compact typed snapshot should remain in the low single-digit MB range per public model/settings variant. Avoid Python dictionaries per cell and duplicated base64 images.

Invalidation: public data fingerprint, valuation model version, league-format/scoring lens where applicable, injury metadata timestamp, and news matcher version.

Expected payoff: high. It removes repeated identity normalization, status parsing, numeric coercion, fallback tier computation, and many full-frame scans.

### League Snapshot

Suggested content:

- league/users/rosters/settings and explicit source timestamps;
- roster-player and player-owner maps;
- league summary and roster-ID keyed metric rows;
- draft assets/capital;
- roster profiles/manager behavior;
- league display/intelligence frames;
- player snapshot version used to build it.

Feasibility: high. A 10–16-team league snapshot is likely a few MB if it references player IDs rather than embedding duplicate player records.

Invalidation: Sleeper roster/settings/transaction version, player snapshot version, selected scoring/lineup settings, draft state, and manager/profile version.

Expected payoff: very high across every authenticated page.

### Need Snapshot / Team Snapshot

Suggested content:

- roster ID and source versions;
- base and optional role-adjusted lineup;
- `TeamNeedsAssessment`;
- injury summary;
- roster-limit status;
- strategy metrics;
- reusable roster subsets/indexes.

Feasibility: high; usually tens of KB plus lineup rows.

Invalidation: League Snapshot, Player Snapshot, role/profile/strategy, and lineup settings.

Expected payoff: high on Dashboard, My Team, Waivers, player fit, and League Overview.

### Trade Snapshot

Suggested content:

- raw generated candidate IDs/packages and generator inputs/version;
- no final Trust decision;
- optional compact enrichment inputs.

Feasibility: medium. Candidate objects are modest, but the key space grows by league, roster, target player, strategy, roles, untouchables, and settings.

Invalidation: every raw-generation input plus player/league/draft snapshot versions.

Expected payoff: already partly achieved by five-minute raw caches. Main improvement is smaller/version keys rather than full DataFrame hashing.

### Snapshot risks

- mixing public and user-specific data under an incomplete cache key;
- stale league ownership or live draft state;
- retaining many league/player-specific frames and increasing process memory;
- accidental mutation of a shared DataFrame;
- mismatched versions between Player, League, Need, and Trade snapshots;
- hiding source freshness from the UI.

Use frozen metadata objects and mutation-isolated frames. Snapshot IDs should be explicit, not inferred from object identity.

## 8. Module boundary recommendations

Movement is recommended only where it reduces work, coupling, or test difficulty.

### High priority

1. **League context builder:** move the implementation behind `cached_league_core_context()`/`cached_league_context()` into a module that returns a versioned League Snapshot. Keep Streamlit decoration/composition at the edge.
2. **Team context builder:** extract the repeated roster filter, metric lookup, lineup, Team Needs, and injury aggregation sequence into a pure builder accepting an existing League Snapshot.
3. **Player view-model builder:** place roster fit, trade outlook inputs, status, and news IDs in a pure module so quick view/detail share data without Streamlit coupling.
4. **Trade Analyzer fit engine:** `evaluate_trade_analyzer_fit()` and `_simulate_post_trade_roster()` are business logic and should be independently testable/importable. Moving them also keeps simulated lineups distinct from reusable base lineups.
5. **Roster-limit engine:** the 835-line `roster_limit_status()` is a substantial policy engine, not entrypoint orchestration.

### Medium priority

1. Dashboard and My Team view-model builders, while leaving Streamlit rendering in UI modules.
2. Weekly report builder (already cached but 634 lines in `app.py`).
3. trade search/index construction.
4. league settings detection/resolution into one settings service.
5. news ingestion/matching service with versioned records.
6. injury snapshot adapter around existing rankings functions.

### Low priority

- thin formatting functions used only by Streamlit;
- route/query/session synchronization;
- small rendering wrappers;
- page-shell composition;
- component definitions that are genuinely UI-specific.

Moving these would reduce line count without materially improving runtime or test boundaries.

## 9. Performance priority ranking

### Easy wins

| Priority | Opportunity | Effort | Expected payoff |
|---|---|---:|---|
| High | Add total common-path/page timers, warm-cache event timing, external-call counters, and DataFrame size telemetry | 1–2 days | Enables reliable decisions; low runtime gain by itself |
| High | Stop rebuilding maps already present in `league_context` (ownership, roster-player, roster metrics) | 1–3 days | Medium CPU/allocation reduction |
| High | Reuse one selected-team lineup/injury/needs context across route cards | 2–4 days | Medium-to-high on Dashboard/My Team/Waivers/player pages |
| Medium | Precompute normalized injury flag/level columns once per player frame | 1–2 days | Medium; removes repeated row-wise `apply` |
| Medium | Replace repeated sorts with named pre-sorted roster views inside a rerun | 1–2 days | Low-to-medium |
| Medium | Avoid full DataFrame cache keys where an explicit source/version key is available | 2–4 days | Medium warm-rerun latency and lower hash churn |

### Medium work

| Priority | Opportunity | Effort | Expected payoff |
|---|---|---:|---|
| High | Introduce Player and League Snapshots behind existing outputs | 1–2 weeks | High across all authenticated routes |
| High | Introduce Team Snapshot and reuse lineup/assessment/injury context | 4–7 days | High on four primary roster pages |
| High | Add TTL/version-aware Sleeper endpoint cache policy | 3–5 days | Correcter freshness plus controlled network load |
| Medium | Move news fetching to scheduled ingest and precompute matches | 1–2 weeks | High on News cold path; medium app-wide |
| Medium | Extract pure page view-model builders | 1–2 weeks incrementally | Medium runtime, high testability/coupling payoff |

### Major architectural work

| Priority | Opportunity | Effort | Expected payoff |
|---|---|---:|---|
| High | Versioned snapshot dependency graph with explicit invalidation | 3–6 weeks | Very high scalability and feature readiness |
| Medium | Background jobs for news/injury/league refresh | 3–6 weeks including operations | High freshness and tail-latency improvement |
| Medium | Persisted league snapshots shared across processes | 3–5 weeks | High for multi-worker deployment; adds consistency complexity |

## 10. Architecture risks

1. **Warm cache opacity:** current timers can make a page appear to do no analysis while it still hashes/copies large frames.
2. **Common-path amplification:** every widget rerun pays for shell context and strategy resolution before the active route.
3. **Overlapping cache graphs:** nested five-minute caches can rebuild different layers at different times.
4. **Sleeper staleness:** endpoint `lru_cache` entries have no TTL.
5. **User isolation:** Team Needs, roles, untouchables, entitlement, and final Trust decisions must never enter under-keyed shared caches.
6. **DataFrame mutation:** many builders defensively copy, but a future snapshot could expose shared mutation if not frozen/isolated.
7. **Memory growth:** player-target trade caches and multiple large DataFrame variants can accumulate.
8. **Synchronous feeds:** News page cold requests can issue many sequential Google RSS parses.
9. **Disk cache concurrency:** news JSON writes are not atomic or locked.
10. **Freshness ambiguity:** injury/news timestamps and source versions are not consistently surfaced through downstream contexts.
11. **Business logic in rendering:** policy changes can accidentally trigger UI-dependent imports or duplicated recomputation.
12. **Trade boundary sensitivity:** caching final enforced recommendations would violate Trust and user-specific ownership/protection guarantees.

## 11. Recommended optimization roadmap

### Stage 0 — observation only

1. Add a total timer for common startup and each route.
2. Record warm/cold status and elapsed time around calls to cached builders, not only inside their bodies.
3. Count Sleeper, Supabase, RSS, and other external calls per rerun.
4. Record DataFrame rows/columns/deep bytes at major boundaries.
5. Capture p50/p95 cold and warm reruns for all six audited pages in production-like conditions.

Effort: 1–2 days. Payoff: high confidence, negligible behavioral risk.

### Stage 1 — reuse within one rerun

1. Extend the existing `get_shared_league_context()` pattern with an explicit selected-team context.
2. Pass existing roster maps/metrics into Waivers, player fit, and selected-team League Overview.
3. Reuse lineup, Team Needs assessment, and injury summary across cards.
4. Precompute injury status columns and named roster views.

Effort: 3–7 days. Payoff: medium-to-high. Risk: low if output-characterization tests remain unchanged.

### Stage 2 — explicit version keys

1. Define public-player, league, profile, draft, and generator versions/fingerprints.
2. Replace full-frame cache-key transport where possible.
3. add bounded, TTL-aware Sleeper endpoint caching.
4. preserve raw trade caches and post-cache Trust enforcement.

Effort: 1–2 weeks. Payoff: high. Risk: medium because invalidation errors cause stale or cross-context results.

### Stage 3 — internal snapshots

1. Introduce Player Snapshot.
2. Build League Snapshot from it and Sleeper state.
3. Build Team/Need Snapshot from league, roster, profile, and strategy state.
4. Adapt existing functions to consume snapshots without formula changes.

Effort: 3–6 weeks incrementally. Payoff: very high. Risk: medium-high; requires versioning and mutation tests.

### Stage 4 — background ingestion

1. Move RSS/Google News fetch and article matching off request paths.
2. Refresh injury/player metadata on a schedule with provenance.
3. optionally persist League Snapshots for multi-process reuse.

Effort: 3–6 weeks. Payoff: high tail-latency/freshness improvement. Risk: operational complexity.

## 12. Future architecture compatibility

| Future feature | Current readiness | Required prerequisite |
|---|---|---|
| three-team trades | Low | Extract trade analyzer/generator contexts and adopt compact versioned League/Trade Snapshots before expanding combinatorics |
| notification feed | Low-to-medium | background news/injury ingest, durable event IDs, user/team subscription mapping |
| background news updates | Medium | move current fetch/match logic behind scheduled ingestion and atomic storage |
| precomputed player snapshots | High feasibility | explicit source/model versions and immutable/mutation-isolated representation |
| league snapshots | High feasibility | TTL/version-aware Sleeper layer and one canonical context builder |
| AI explanations | Medium | stable structured snapshots with provenance; never recompute league analysis per prompt |
| modal expansion | Medium | pure player/team view models so modal reruns do not rebuild page context |
| additional recommendation engines | Low-to-medium | shared snapshots and explicit recommendation input contracts to avoid another independent definition of roster state |

Before adding these features, the application should establish:

1. rerun-level measurement;
2. Player/League/Team context contracts;
3. explicit freshness/version metadata;
4. external-call isolation;
5. pure view-model boundaries;
6. strict public versus user-specific cache separation.

## Final recommendation

Do not begin with a broad `app.py` split or add more indiscriminate Streamlit caches. First measure complete reruns, then consolidate existing data into one versioned league context and one selected-team context per rerun. That sequence attacks the actual duplication while preserving valuations, rankings, Team Needs, trade logic, Trust enforcement, entitlement, navigation, and UI behavior.
