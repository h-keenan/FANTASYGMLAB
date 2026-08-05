# Release Candidate performance audit

## Scope

Engineering optimization only. No football logic, rankings, valuations,
recommendation ordering, Trust rules, auth, entitlements, Stripe, or Supabase
schema changes. UI was not redesigned.

Measurement environment: logged-out AppTest / fixture harness on CI-equivalent
hardware. Authenticated Sleeper/Supabase network paths were instrumented but not
exercised with real credentials in this pass — those remain documented gaps.

## Method

1. Static inventory via `scripts/audit_founder_beta_performance.py`
2. CI budget gate via `scripts/check_founder_beta_performance_budget.py`
3. AppTest cold/warm with `DYNASTYGM_RUNTIME_TRACE=1`
4. Fixture surface walls for Dashboard, My Team, Trade Hub, Waivers, League
5. Tracemalloc probe for startup
6. Chromium `scripts/validate_mobile_ui.py` after optimizations

## Architecture inventory

| Metric | Before | After |
| --- | ---: | ---: |
| Cache boundaries | 33 | 34 (`_injury_level_cached` LRU) |
| Explicit `st.rerun()` sites | 42 | 42 |
| Deferred section gates | 4 | 4 |
| Reduced-context league calls | 3 | **4** (News added) |
| Instrumented timing labels | 61 | 61 |

## Before / after — production AppTest budgets

Canonical gate (`scripts/check_founder_beta_performance_budget.py`):

| Measure | Before | After | Delta | Limit |
| --- | ---: | ---: | ---: | ---: |
| Cold server `total_page_ms` | 378.3 | 375.3 | -3.0 | 2,500 |
| Warm server `total_page_ms` | 64.2 | 62.6 | -1.6 | 750 |
| Cold protobuf bytes | 505,784 | 505,784 | 0 | 510,000 |
| Warm protobuf bytes | 463,330 | 463,330 | 0 | 510,000 |

Fixture walls (budget script single pass):

| Surface | Before ms | After ms |
| --- | ---: | ---: |
| Dashboard | 116.0 | 116.6 |
| My Team | 97.7 | 98.5 |
| Trade Hub | 97.1 | 97.7 |
| Waivers | 102.9 | 103.3 |
| League | 96.9 | 97.6 |

Fixture deltas are noise-bounded (±2 ms). Causal wins below are request/build
elimination contracts that logged-out fixtures cannot fully exercise.

## Causal operation evidence

| Operation | Before | After | Notes |
| --- | ---: | ---: | --- |
| `injury_level` total_ms (cold) | 15.8 | 0.4 | LRU cache; classifications unchanged |
| `injury_parsing` counter (cold) | 4,940 | 988 | Fewer unique status evaluations after normalize+cache |
| DataFrame copies (cold) | 18 | 10 | Observed with runtime trace; plumbing-sensitive |
| Trade Hub second `get_roster_player_ids` | 1 | **0** | Reuses context `my_player_ids` |
| Waivers second roster-id adapter call | 1 | **0** when map present | Reuses `_build_roster_player_map` |
| My Team / Dashboard / News roster fetches | Always adapter | Prefer shared map | Adapter only as fallback |
| News deep league analysis | Full context risk | Reduced context | intelligence/trust/maturity skipped |

## Memory

| Probe | Before peak | After peak |
| --- | ---: | ---: |
| Cold AppTest | 63.3 MB | 62.4 MB |
| Warm AppTest | 113.7 MB | 64.0 MB |

Warm peak variance is environment-sensitive; no retained-object leak was found
in Trade fixture growth (dominated by tracemalloc/Streamlit internals).

## Top 10 slowest / largest remaining costs

1. Cold `player_data_loading` / public player construction (~300–380 ms)
2. Uncompressed ForwardMsg protobuf (~506 KB), largest HTML ~421 KB
3. Authenticated Trade Hub board generation on cache miss (historical 1.5–3 s)
4. Valuation lens application every rerun (historical ~50–60 ms)
5. CSS / markdown style ForwardMsgs (~6 KB × many)
6. Authenticated Supabase preference + saved-league lookups (not measured here)
7. League intelligence rebuild on cache miss (all-roster lineups)
8. Player Quick View synchronous `fetch_news()` when pool empty
9. Waivers free-agent `DataFrame.apply` stale/injury annotation
10. Explicit navigation still capped at 42 `st.rerun()` sites (budget)

## Optimizations performed

1. **LRU-cache `injury_level`** (`modules/rankings.py`, `maxsize=4096`) — pure status parsing.
2. **Trade Hub** reuses `my_player_ids` from context roster map.
3. **Dashboard** prefers `league_context["roster_player_map"]` before adapter fetch.
4. **My Team** loads shared context first; roster IDs from map.
5. **Waivers** builds roster map once from fetched rosters; injury path reuses it.
6. **News** uses reduced shared league context (4th reduced-context site).
7. Budget gate now requires **≥ 4** reduced-context calls.

## Cache audit / invalidation

| Cache | TTL / policy | Invalidation |
| --- | --- | --- |
| League `@st.cache_data` stack | 5 minutes | League/args change |
| Headshots | 24 hours | URL change |
| Sleeper player directory | 15 minutes | TTL |
| Sleeper API `lru_cache` | Process lifetime | Process restart |
| Public players fingerprint | `max_entries=4` | Source fingerprint |
| `_injury_level_cached` | 4096 entries | Process lifetime |
| Session saved-league cache | Session | Account mutations |
| Deferred section gates | Session | Reset / new section id |

No stale caches removed. Sleeper process LRU remains intentional for request coalescing.

## Session-state notes

No broad session_state schema changes. Roster-map reuse reduces adapter calls
that previously could repopulate process caches and trigger redundant work on
the same rerun. Deferred gates and preference lazy-load from prior sprints remain.

## Network notes (logged-out)

| Boundary | Cold | Warm |
| --- | ---: | ---: |
| Sleeper | 0 | 0 |
| Supabase | 0 | 0 |
| RSS news | 0 | 0 |

Authenticated idle-wait evidence still requires redacted production observation.

## Browser / Chromium

`scripts/validate_mobile_ui.py` at 320 / 390 / 430 / 768 / 1024 / 1440 must stay
green (no overflow/clipping; shell ≤140px mobile). No loading-overlay or DOM
redesign was introduced.

## Updated performance budget

| Gate | Limit |
| --- | ---: |
| Cold server | 2,500 ms |
| Warm server | 750 ms |
| Fixture render | 3,000 ms / surface |
| Protobuf | 510,000 bytes |
| Explicit reruns | ≤ 42 |
| Deferred gates | ≥ 4 |
| Reduced-context calls | **≥ 4** (was ≥ 3) |

No limit was loosened.

## Explicit non-changes

Football formulas, rankings, valuations, recommendation generation/ordering,
Trust enforcement, Stripe, Supabase schema, authentication, and entitlement
rules are unchanged.
